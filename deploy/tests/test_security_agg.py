# -*- coding: utf-8 -*-
"""Q2：高频攻击按分钟聚合，一万条只计桶、走索引；登录失败仍保留明细。"""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(name, rel):
    path = os.path.join(ROOT, rel)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


try:
    from tortoise.expressions import Q as _real_q  # noqa: F401
except ImportError:
    tortoise = types.ModuleType("tortoise")
    expressions = types.ModuleType("tortoise.expressions")

    class _Q:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __and__(self, other):
            return self

        def __or__(self, other):
            return self

        def __invert__(self):
            return self

    expressions.Q = _Q
    tortoise.expressions = expressions
    sys.modules["tortoise"] = tortoise
    sys.modules["tortoise.expressions"] = expressions

_query = _load("security_query_helper", os.path.join("app", "services", "security_query.py"))
_agg = _load("security_agg_helper", os.path.join("app", "services", "security_agg.py"))
filter_rows = _query.filter_rows
from_legacy_params = _query.from_legacy_params
DEFAULT_AGG_RETENTION_DAYS = _agg.DEFAULT_AGG_RETENTION_DAYS
DEFAULT_RAW_RETENTION_DAYS = _agg.DEFAULT_RAW_RETENTION_DAYS
MinuteAggregator = _agg.MinuteAggregator
build_drill_filter = _agg.build_drill_filter
classify_security_write = _agg.classify_security_write
count_hits = _agg.count_hits
ensure_agg_schema = _agg.ensure_agg_schema
explain_count_plan = _agg.explain_count_plan
persist_buckets = _agg.persist_buckets


def _dt(minute_offset=0, second=12):
    return datetime(2026, 8, 15, 10, 3, second) + timedelta(minutes=minute_offset)


class MinuteAggregatorTests(unittest.TestCase):
    def test_10k_same_ip_same_minute_is_one_bucket(self):
        agg = MinuteAggregator()
        now = _dt()
        for _ in range(10_000):
            agg.record("scan", ip="203.0.113.9", now=now)
        drained = agg.drain()
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0]["hit_count"], 10_000)
        self.assertEqual(drained[0]["event_type"], "scan")
        self.assertEqual(drained[0]["source_key"], "ip:203.0.113.9")
        self.assertEqual(drained[0]["bucket_minute"], now.replace(second=0, microsecond=0))

    def test_10k_across_20_ips_and_two_minutes(self):
        agg = MinuteAggregator()
        for minute in (0, 1):
            for host in range(20):
                for _ in range(250):
                    agg.record("rate_limit", ip=f"203.0.113.{host}", now=_dt(minute_offset=minute))
        drained = agg.drain()
        self.assertEqual(len(drained), 40)
        self.assertEqual(sum(item["hit_count"] for item in drained), 10_000)


class SqlitePersistIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        ensure_agg_schema(self.conn)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_10k_persist_count_and_index(self):
        agg = MinuteAggregator()
        now = _dt()
        for i in range(10_000):
            agg.record("scan", ip=f"198.51.100.{i % 25}", now=now)
        persist_buckets(self.conn, agg.drain())
        persist_buckets(self.conn, [])  # 二次刷新不得复制

        row_count = self.conn.execute("SELECT COUNT(*) FROM security_agg_bucket").fetchone()[0]
        self.assertEqual(row_count, 25)
        self.assertEqual(count_hits(self.conn, "scan", _dt().replace(second=0), _dt(1).replace(second=0)), 10_000)

        plan = explain_count_plan(self.conn, "scan", _dt().replace(second=0), _dt(1).replace(second=0))
        plan_text = " ".join(plan).lower()
        self.assertIn("idx_sec_agg_type_minute", plan_text)
        full_scan = "scan table security_agg_bucket" in plan_text and "using index" not in plan_text
        self.assertFalse(full_scan, plan)

    def test_upsert_merges_same_bucket(self):
        now = _dt()
        first = MinuteAggregator()
        first.record("blacklist_hit", ip="192.0.2.8", now=now)
        persist_buckets(self.conn, first.drain())
        second = MinuteAggregator()
        for _ in range(4):
            second.record("blacklist_hit", ip="192.0.2.8", now=now)
        persist_buckets(self.conn, second.drain())
        self.assertEqual(count_hits(self.conn, "blacklist_hit", now.replace(second=0), _dt(1).replace(second=0)), 5)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM security_agg_bucket").fetchone()[0], 1)


class WritePolicyAndFilterReuseTests(unittest.TestCase):
    def test_login_failure_stays_raw_scan_is_agg(self):
        self.assertEqual(classify_security_write("login_failure"), "raw")
        self.assertEqual(classify_security_write("high_risk_delete"), "raw")
        self.assertEqual(classify_security_write("scan"), "agg")
        self.assertEqual(classify_security_write("rate_limit"), "agg")
        self.assertEqual(classify_security_write("blacklist_hit"), "agg")
        self.assertEqual(classify_security_write("permission_denied"), "agg")

    def test_retention_defaults(self):
        self.assertEqual(DEFAULT_RAW_RETENTION_DAYS, 30)
        self.assertEqual(DEFAULT_AGG_RETENTION_DAYS, 180)

    def test_drill_filter_reuses_filterspec_without_mixing_unknown_region(self):
        start = datetime(2026, 8, 15, 0, 0, 0)
        end = datetime(2026, 8, 16, 0, 0, 0)
        payload = build_drill_filter(event_type="scan", start=start, end=end, ip="203.0.113.9")
        spec = from_legacy_params(
            event_type=payload["event_type"],
            ip=payload.get("ip") or "",
            start_time=datetime.fromisoformat(payload["start_time"]),
            end_time=datetime.fromisoformat(payload["end_time"]),
        )
        rows = [
            {
                "event_type": "scan",
                "success": False,
                "username": "",
                "ip": "203.0.113.9",
                "device_hash": "",
                "country": "中国",
                "region": "北京",
                "risk_tags": "",
                "created_at": start + timedelta(hours=1),
            },
            {
                "event_type": "scan",
                "success": False,
                "username": "",
                "ip": "203.0.113.9",
                "device_hash": "",
                "country": "",
                "region": "",
                "risk_tags": "",
                "created_at": start + timedelta(hours=2),
            },
            {
                "event_type": "login_failure",
                "success": False,
                "username": "x",
                "ip": "203.0.113.9",
                "device_hash": "",
                "country": "中国",
                "region": "北京",
                "risk_tags": "",
                "created_at": start + timedelta(hours=1),
            },
        ]
        got = filter_rows(rows, spec)
        self.assertEqual(len(got), 2)
        self.assertTrue(all(row["event_type"] == "scan" for row in got))
        self.assertEqual(payload["tab"], "attacks")

        login_payload = build_drill_filter(event_type="login_failure", start=start, end=end)
        self.assertEqual(login_payload["tab"], "login")
        self.assertIs(login_payload["success"], False)


class SourceContractTests(unittest.TestCase):
    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_posture_endpoint_hard_locks_superuser(self):
        src = self._read("app/api/v1/security/security.py")
        self.assertIn('/posture', src)
        self.assertIn("DependSuperUser", src)
        posture_idx = src.index("def security_posture")
        snippet = src[posture_idx : posture_idx + 240]
        self.assertIn("DependSuperUser", snippet)

    def test_dashboard_stats_does_not_embed_security(self):
        src = self._read("app/services/dashboard_service.py")
        self.assertNotIn("security_posture", src)
        self.assertNotIn("login_failure", src)

    def test_gateway_records_aggregated_attacks(self):
        src = self._read("app/core/gateway.py")
        self.assertIn("record_attack", src)
        self.assertIn("scan", src)
        self.assertIn("rate_limit", src)
        self.assertIn("blacklist_hit", src)


if __name__ == "__main__":
    unittest.main()
