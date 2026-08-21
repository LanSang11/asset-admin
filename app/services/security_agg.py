"""High-frequency attack buckets (per minute). Login/high-risk stay as raw rows.

This module is importable without FastAPI/Tortoise so unit tests can load it
via importlib. App wiring uses the lazy async helpers at the bottom.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Iterable, Optional

DEFAULT_RAW_RETENTION_DAYS = 30
DEFAULT_AGG_RETENTION_DAYS = 180

AGG_EVENT_TYPES = frozenset({"scan", "rate_limit", "blacklist_hit", "permission_denied"})
RAW_KEEP_EVENT_TYPES = frozenset(
    {
        "login_success",
        "login_failure",
        "ban",
        "unban",
        "high_risk_delete",
        "step_up",
        "step_up_denied",
        "reset_password",
        "totp_bind",
        "totp_disable",
        "acceptance_mode",
    }
)
ATTACK_CATEGORIES = (
    ("login_failure", "认证失败", "raw"),
    ("scan", "扫描", "agg"),
    ("rate_limit", "限流", "agg"),
    ("blacklist_hit", "黑名单命中", "agg"),
    ("permission_denied", "权限拒绝", "agg"),
)

AGG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS security_agg_bucket (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket_minute TIMESTAMP NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    source_key VARCHAR(80) NOT NULL,
    ip VARCHAR(64) NOT NULL DEFAULT '',
    country VARCHAR(64) NOT NULL DEFAULT '',
    region VARCHAR(64) NOT NULL DEFAULT '',
    hit_count INTEGER NOT NULL DEFAULT 0,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_agg_bucket_uniq
    ON security_agg_bucket(bucket_minute, event_type, source_key);
CREATE INDEX IF NOT EXISTS idx_sec_agg_type_minute
    ON security_agg_bucket(event_type, bucket_minute);
CREATE INDEX IF NOT EXISTS idx_sec_agg_ip_minute
    ON security_agg_bucket(ip, bucket_minute);
"""

UPSERT_SQL = """
INSERT INTO security_agg_bucket (
    bucket_minute, event_type, source_key, ip, country, region,
    hit_count, first_seen, last_seen, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(bucket_minute, event_type, source_key) DO UPDATE SET
    hit_count = hit_count + excluded.hit_count,
    last_seen = excluded.last_seen,
    updated_at = excluded.updated_at,
    country = CASE WHEN security_agg_bucket.country = '' THEN excluded.country ELSE security_agg_bucket.country END,
    region = CASE WHEN security_agg_bucket.region = '' THEN excluded.region ELSE security_agg_bucket.region END
"""

COUNT_SQL = """
SELECT COALESCE(SUM(hit_count), 0) FROM security_agg_bucket
WHERE event_type = ? AND bucket_minute >= ? AND bucket_minute < ?
"""


def classify_security_write(event_type: str) -> str:
    if (event_type or "") in AGG_EVENT_TYPES:
        return "agg"
    return "raw"


def minute_floor(value: datetime) -> datetime:
    dt = value
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.replace(second=0, microsecond=0)


def _sql_dt(value: datetime) -> str:
    dt = value
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build_drill_filter(
    *,
    event_type: str,
    start: datetime,
    end: datetime,
    ip: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_type": event_type,
        "start_time": start.isoformat(timespec="seconds"),
        "end_time": end.isoformat(timespec="seconds"),
    }
    if ip:
        payload["ip"] = ip
    if event_type == "login_failure":
        payload["tab"] = "login"
        payload["success"] = False
    elif event_type in AGG_EVENT_TYPES:
        payload["tab"] = "attacks"
    else:
        payload["tab"] = "events"
    return payload


class MinuteAggregator:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[tuple, dict[str, Any]] = {}

    def record(
        self,
        event_type: str,
        *,
        ip: str = "",
        source_key: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> None:
        ts = now or datetime.now()
        if ts.tzinfo is not None:
            ts = ts.astimezone().replace(tzinfo=None)
        minute = minute_floor(ts)
        ip_text = (ip or "")[:64]
        key = (source_key or (f"ip:{ip_text}" if ip_text else "ip:unknown"))[:80]
        bucket_key = (minute, event_type, key)
        with self._lock:
            item = self._buckets.get(bucket_key)
            if item is None:
                self._buckets[bucket_key] = {
                    "bucket_minute": minute,
                    "event_type": event_type,
                    "source_key": key,
                    "ip": ip_text,
                    "country": "",
                    "region": "",
                    "hit_count": 1,
                    "first_seen": ts,
                    "last_seen": ts,
                }
                return
            item["hit_count"] += 1
            if ts < item["first_seen"]:
                item["first_seen"] = ts
            if ts > item["last_seen"]:
                item["last_seen"] = ts

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._buckets.values())
            self._buckets.clear()
        return items

    def pending_count(self) -> int:
        with self._lock:
            return sum(item["hit_count"] for item in self._buckets.values())


_aggregator = MinuteAggregator()


def get_aggregator() -> MinuteAggregator:
    return _aggregator


def record_attack(
    event_type: str,
    *,
    ip: str = "",
    source_key: Optional[str] = None,
    now: Optional[datetime] = None,
) -> None:
    if classify_security_write(event_type) != "agg":
        return
    _aggregator.record(event_type, ip=ip, source_key=source_key, now=now)


def ensure_agg_schema(conn) -> None:
    conn.executescript(AGG_SCHEMA_SQL)
    conn.commit()


def persist_buckets(conn, items: Iterable[dict[str, Any]]) -> int:
    rows = list(items)
    if not rows:
        return 0
    now = datetime.now()
    payload = []
    for item in rows:
        payload.append(
            (
                _sql_dt(item["bucket_minute"]),
                item["event_type"],
                item["source_key"],
                item.get("ip") or "",
                item.get("country") or "",
                item.get("region") or "",
                int(item.get("hit_count") or 0),
                _sql_dt(item["first_seen"]),
                _sql_dt(item["last_seen"]),
                _sql_dt(now),
                _sql_dt(now),
            )
        )
    conn.executemany(UPSERT_SQL, payload)
    conn.commit()
    return len(payload)


def count_hits(conn, event_type: str, start: datetime, end: datetime) -> int:
    row = conn.execute(COUNT_SQL, (event_type, _sql_dt(start), _sql_dt(end))).fetchone()
    return int(row[0] or 0)


def explain_count_plan(conn, event_type: str, start: datetime, end: datetime) -> list[str]:
    rows = conn.execute(
        "EXPLAIN QUERY PLAN " + COUNT_SQL,
        (event_type, _sql_dt(start), _sql_dt(end)),
    ).fetchall()
    return [str(row) for row in rows]


def spec_to_agg_q(spec) -> Any:
    """Map an existing FilterSpec onto security_agg_bucket. Does not change FilterSpec."""
    from tortoise.expressions import Q

    from app.services.security_query import FilterSpecError, _as_bool, _norm, parse_query_time

    if getattr(spec, "login_only", False):
        return Q(id=-1)
    q = Q(event_type__in=list(AGG_EVENT_TYPES))
    for item in spec.conditions:
        field = item.field
        op = item.op
        if field in {"username", "device_hash", "risk_tag"}:
            if op in {"is_empty"}:
                continue
            if op in {"not_empty", "eq", "contains", "in"} and _norm(item.value):
                return Q(id=-1)
            continue
        if field == "success":
            wanted = _as_bool(item.value)
            if (op == "eq" and wanted) or (op == "neq" and not wanted):
                return Q(id=-1)
            continue
        col = "bucket_minute" if field == "created_at" else field
        if field == "created_at":
            bound = parse_query_time(item.value)
            if op == "gte":
                q &= Q(bucket_minute__gte=bound)
            elif op == "lt":
                q &= Q(bucket_minute__lt=bound)
            else:
                raise FilterSpecError("时间只支持 gte/lt")
            continue
        if col not in {"event_type", "ip", "country", "region"}:
            continue
        if op == "eq":
            q &= Q(**{col: _norm(item.value)})
        elif op == "neq":
            q &= ~Q(**{col: _norm(item.value)})
            if field in {"country", "region"}:
                q &= ~Q(**{col: ""})
        elif op == "contains":
            q &= Q(**{f"{col}__contains": _norm(item.value)})
        elif op == "not_contains":
            q &= ~Q(**{f"{col}__contains": _norm(item.value)})
        elif op == "in":
            values = [_norm(v) for v in (item.value or [])]
            q &= Q(**{f"{col}__in": values})
        elif op == "not_in":
            values = [_norm(v) for v in (item.value or [])]
            q &= ~Q(**{f"{col}__in": values})
        elif op == "is_empty":
            q &= Q(**{col: ""})
        elif op == "not_empty":
            q &= ~Q(**{col: ""})
    return q


async def flush_attack_buckets() -> int:
    items = get_aggregator().drain()
    if not items:
        return 0
    try:
        from app.utils.geoip import lookup_ip
    except Exception:
        lookup_ip = None
    if lookup_ip:
        for item in items:
            if item.get("ip") and not item.get("country"):
                try:
                    geo = lookup_ip(item["ip"])
                    item["country"] = (geo.get("country") or "")[:64]
                    item["region"] = (geo.get("region") or "")[:64]
                except Exception:
                    pass
    from tortoise import Tortoise, connections

    try:
        conn = connections.get("sqlite")
    except Exception:
        conn = Tortoise.get_connection("sqlite")
    now = datetime.now()
    for item in items:
        await conn.execute_query(
            UPSERT_SQL,
            [
                _sql_dt(item["bucket_minute"]),
                item["event_type"],
                item["source_key"],
                item.get("ip") or "",
                item.get("country") or "",
                item.get("region") or "",
                int(item.get("hit_count") or 0),
                _sql_dt(item["first_seen"]),
                _sql_dt(item["last_seen"]),
                _sql_dt(now),
                _sql_dt(now),
            ],
        )
    return len(items)


async def _agg_sum(event_type: str, start: datetime, end: datetime) -> int:
    from tortoise import Tortoise, connections

    try:
        conn = connections.get("sqlite")
    except Exception:
        conn = Tortoise.get_connection("sqlite")
    rows = await conn.execute_query_dict(COUNT_SQL, [event_type, _sql_dt(start), _sql_dt(end)])
    if not rows:
        return 0
    first = rows[0]
    return int(next(iter(first.values())) or 0)


async def _hourly_from_agg(start: datetime, end: datetime) -> dict[tuple[str, str], int]:
    from tortoise import Tortoise, connections

    try:
        conn = connections.get("sqlite")
    except Exception:
        conn = Tortoise.get_connection("sqlite")
    sql = """
        SELECT strftime('%Y-%m-%d %H:00:00', bucket_minute) AS hour, event_type, SUM(hit_count) AS hits
        FROM security_agg_bucket
        WHERE bucket_minute >= ? AND bucket_minute < ?
        GROUP BY hour, event_type
    """
    rows = await conn.execute_query_dict(sql, [_sql_dt(start), _sql_dt(end)])
    out: dict[tuple[str, str], int] = {}
    for row in rows:
        out[(str(row.get("hour") or ""), str(row.get("event_type") or ""))] = int(row.get("hits") or 0)
    return out


async def build_security_posture(hours: int = 24) -> dict[str, Any]:
    from app.models.admin import SecurityEvent

    await flush_attack_buckets()
    hours = max(1, min(int(hours or 24), 168))
    end = datetime.now().replace(microsecond=0)
    start = end - timedelta(hours=hours)
    categories = []
    for key, label, kind in ATTACK_CATEGORIES:
        if kind == "raw":
            count = await SecurityEvent.filter(
                event_type=key, created_at__gte=start, created_at__lt=end
            ).count()
        else:
            count = await _agg_sum(key, start, end)
        categories.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "kind": kind,
                "filter": build_drill_filter(event_type=key, start=start, end=end),
            }
        )

    hourly_map = await _hourly_from_agg(start, end)
    login_rows = await SecurityEvent.filter(
        event_type="login_failure", created_at__gte=start, created_at__lt=end
    ).values_list("created_at", flat=True)
    for created in login_rows:
        if not created:
            continue
        hour = created.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00:00")
        hourly_map[(hour, "login_failure")] = hourly_map.get((hour, "login_failure"), 0) + 1

    hours_ordered = []
    cursor = start.replace(minute=0, second=0, microsecond=0)
    step = timedelta(hours=1)
    while cursor < end:
        hours_ordered.append(cursor.strftime("%Y-%m-%d %H:00:00"))
        cursor += step

    hourly = []
    for hour in hours_ordered:
        item = {"hour": hour, "total": 0}
        for key, _label, _kind in ATTACK_CATEGORIES:
            value = int(hourly_map.get((hour, key), 0))
            item[key] = value
            item["total"] += value
        hour_start = datetime.strptime(hour, "%Y-%m-%d %H:%M:%S")
        item["filter"] = {
            "tab": "attacks",
            "start_time": hour_start.isoformat(timespec="seconds"),
            "end_time": (hour_start + timedelta(hours=1)).isoformat(timespec="seconds"),
        }
        hourly.append(item)

    from tortoise import Tortoise, connections

    try:
        conn = connections.get("sqlite")
    except Exception:
        conn = Tortoise.get_connection("sqlite")
    top_sql = """
        SELECT ip, SUM(hit_count) AS hits
        FROM security_agg_bucket
        WHERE bucket_minute >= ? AND bucket_minute < ? AND ip != ''
        GROUP BY ip
        ORDER BY hits DESC
        LIMIT 8
    """
    top_rows = await conn.execute_query_dict(top_sql, [_sql_dt(start), _sql_dt(end)])
    top_sources = []
    for row in top_rows:
        ip = str(row.get("ip") or "")
        top_sources.append(
            {
                "ip": ip,
                "count": int(row.get("hits") or 0),
                "filter": {
                    "tab": "attacks",
                    "ip": ip,
                    "start_time": start.isoformat(timespec="seconds"),
                    "end_time": end.isoformat(timespec="seconds"),
                },
            }
        )

    return {
        "hours": hours,
        "start_time": start.isoformat(timespec="seconds"),
        "end_time": end.isoformat(timespec="seconds"),
        "categories": categories,
        "hourly": hourly,
        "top_sources": top_sources,
        "retention": {
            "raw_days": DEFAULT_RAW_RETENTION_DAYS,
            "agg_days": DEFAULT_AGG_RETENTION_DAYS,
        },
    }
