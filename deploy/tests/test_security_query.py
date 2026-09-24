# -*- coding: utf-8 -*-
"""FilterSpec：成功登录 + 排除上海时，未知地区不得算作上海之外。"""
from __future__ import annotations

from datetime import datetime
import importlib.util
import os
import unittest

_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "app",
    "services",
    "security_query.py",
)
_SPEC = importlib.util.spec_from_file_location("security_query_helper", _PATH)
_mod = importlib.util.module_from_spec(_SPEC)

import sys
import types

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

sys.modules[_SPEC.name] = _mod
_SPEC.loader.exec_module(_mod)
FilterSpecError = _mod.FilterSpecError
filter_rows = _mod.filter_rows
from_legacy_params = _mod.from_legacy_params


def _row(**kwargs):
    base = {
        "event_type": "login_success",
        "success": True,
        "username": "demoemp",
        "ip": "1.2.3.4",
        "device_hash": "abc",
        "country": "中国",
        "region": "上海",
        "risk_tags": "new_device",
        "created_at": datetime(2026, 8, 15, 10, 0, 0),
    }
    base.update(kwargs)
    return base


class SecurityQueryTests(unittest.TestCase):
    def test_success_exclude_shanghai_keeps_unknown_out(self):
        spec = from_legacy_params(success=True, exclude_region="上海", login_only=True)
        rows = [
            _row(region="上海"),
            _row(region="北京"),
            _row(region="", country=""),
            _row(event_type="login_failure", success=False, region="北京"),
        ]
        got = filter_rows(rows, spec)
        self.assertEqual([item["region"] for item in got], ["北京"])

    def test_unknown_region_is_its_own_filter(self):
        spec = from_legacy_params(unknown_region=True, login_only=True)
        rows = [_row(region="上海"), _row(region="", username="ghost")]
        got = filter_rows(rows, spec)
        self.assertEqual([item["username"] for item in got], ["ghost"])

    def test_time_window_start_inclusive_end_exclusive(self):
        spec = from_legacy_params(
            start_time=datetime(2026, 8, 15, 10, 0, 0),
            end_time=datetime(2026, 8, 15, 11, 0, 0),
        )
        rows = [
            _row(created_at=datetime(2026, 8, 15, 9, 59, 59), username="early"),
            _row(created_at=datetime(2026, 8, 15, 10, 0, 0), username="start"),
            _row(created_at=datetime(2026, 8, 15, 10, 59, 59), username="inside"),
            _row(created_at=datetime(2026, 8, 15, 11, 0, 0), username="end"),
        ]
        got = [item["username"] for item in filter_rows(rows, spec)]
        self.assertEqual(got, ["start", "inside"])

    def test_rejects_unknown_field_via_direct_add(self):
        with self.assertRaises(FilterSpecError):
            _mod.add_condition(_mod.FilterSpec(), "password", "eq", "x")

    def test_legacy_username_contains(self):
        spec = from_legacy_params(username="nor")
        rows = [_row(username="demoemp"), _row(username="admin")]
        got = [item["username"] for item in filter_rows(rows, spec)]
        self.assertEqual(got, ["demoemp"])


if __name__ == "__main__":
    unittest.main()
