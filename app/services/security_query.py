"""Typed security FilterSpec. Superuser query UI, dashboard drill-down and
future read-only AI tools must reuse this module so the three surfaces
never diverge.

AND only. Unknown region/country is empty string and is NOT treated as
"not Shanghai". Time window is start inclusive, end exclusive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from tortoise.expressions import Q

LOGIN_EVENT_TYPES = ("login_success", "login_failure")
ALLOWED_FIELDS = frozenset(
    {
        "event_type",
        "success",
        "username",
        "ip",
        "device_hash",
        "country",
        "region",
        "risk_tag",
        "created_at",
    }
)
LOCATION_FIELDS = frozenset({"country", "region"})
ALLOWED_OPS = frozenset(
    {"eq", "neq", "in", "not_in", "contains", "not_contains", "is_empty", "not_empty", "gte", "lt"}
)
_COLUMN = {
    "event_type": "event_type",
    "success": "success",
    "username": "username",
    "ip": "ip",
    "device_hash": "device_hash",
    "country": "country",
    "region": "region",
    "risk_tag": "risk_tags",
    "created_at": "created_at",
}


class FilterSpecError(ValueError):
    pass


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "ok", "success"}:
        return True
    if text in {"0", "false", "no", "fail", "failed"}:
        return False
    raise FilterSpecError("success 条件无效")


def parse_query_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            raise FilterSpecError("时间不能为空")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise FilterSpecError("时间格式无效") from exc
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: Any = None


@dataclass
class FilterSpec:
    conditions: list[Condition] = field(default_factory=list)
    login_only: bool = False

    def matches(self, row: dict[str, Any]) -> bool:
        if self.login_only and _norm(row.get("event_type")) not in LOGIN_EVENT_TYPES:
            return False
        return all(_match_condition(row, item) for item in self.conditions)

    def to_q(self) -> Q:
        q = Q()
        if self.login_only:
            q &= Q(event_type__in=list(LOGIN_EVENT_TYPES))
        for item in self.conditions:
            q &= _condition_to_q(item)
        return q


def _row_value(row: dict[str, Any], name: str) -> Any:
    if name == "success":
        return bool(row.get("success"))
    if name == "created_at":
        return row.get("created_at")
    if name == "risk_tag":
        return _norm(row.get("risk_tags") or row.get("risk_tag") or "")
    return _norm(row.get(name))


def _match_condition(row: dict[str, Any], item: Condition) -> bool:
    actual = _row_value(row, item.field)
    op = item.op
    if op == "is_empty":
        return actual in ("", None)
    if op == "not_empty":
        return actual not in ("", None)
    if item.field == "success":
        wanted = _as_bool(item.value)
        if op == "eq":
            return bool(actual) is wanted
        if op == "neq":
            return bool(actual) is not wanted
        raise FilterSpecError("success 只支持 eq/neq")
    if item.field == "created_at":
        if not isinstance(actual, datetime):
            return False
        bound = parse_query_time(item.value)
        actual_naive = actual.replace(tzinfo=None) if actual.tzinfo else actual
        if op == "gte":
            return actual_naive >= bound
        if op == "lt":
            return actual_naive < bound
        raise FilterSpecError("时间只支持 gte/lt")
    if op == "eq":
        return actual == _norm(item.value)
    if op == "neq":
        expected = _norm(item.value)
        if item.field in LOCATION_FIELDS:
            return bool(actual) and actual != expected
        return actual != expected
    if op == "contains":
        return _norm(item.value).lower() in str(actual).lower()
    if op == "not_contains":
        needle = _norm(item.value).lower()
        if item.field in LOCATION_FIELDS and not actual:
            return False
        return needle not in str(actual).lower()
    if op == "in":
        return actual in {_norm(v) for v in _as_list(item.value)}
    if op == "not_in":
        values = {_norm(v) for v in _as_list(item.value)}
        if item.field in LOCATION_FIELDS:
            return bool(actual) and actual not in values
        return actual not in values
    raise FilterSpecError("不支持的运算符")


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    text = _norm(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _condition_to_q(item: Condition) -> Q:
    col = _COLUMN[item.field]
    if item.op == "is_empty":
        return Q(**{col: ""}) | Q(**{f"{col}__isnull": True})
    if item.op == "not_empty":
        return ~Q(**{col: ""}) & ~Q(**{f"{col}__isnull": True})
    if item.field == "success":
        wanted = _as_bool(item.value)
        if item.op == "eq":
            return Q(success=wanted)
        if item.op == "neq":
            return Q(success=not wanted)
        raise FilterSpecError("success 只支持 eq/neq")
    if item.field == "created_at":
        bound = parse_query_time(item.value)
        if item.op == "gte":
            return Q(created_at__gte=bound)
        if item.op == "lt":
            return Q(created_at__lt=bound)
        raise FilterSpecError("时间只支持 gte/lt")
    if item.op == "eq":
        return Q(**{col: item.value})
    if item.op == "neq":
        q = ~Q(**{col: item.value})
        if item.field in LOCATION_FIELDS:
            q &= ~Q(**{col: ""})
        return q
    if item.op == "contains":
        return Q(**{f"{col}__icontains": item.value})
    if item.op == "not_contains":
        q = ~Q(**{f"{col}__icontains": item.value})
        if item.field in LOCATION_FIELDS:
            q &= ~Q(**{col: ""})
        return q
    if item.op == "in":
        return Q(**{f"{col}__in": _as_list(item.value)})
    if item.op == "not_in":
        q = ~Q(**{f"{col}__in": _as_list(item.value)})
        if item.field in LOCATION_FIELDS:
            q &= ~Q(**{col: ""})
        return q
    raise FilterSpecError("不支持的运算符")


def add_condition(spec: FilterSpec, field_name: str, op: str, value: Any = None) -> None:
    if field_name not in ALLOWED_FIELDS:
        raise FilterSpecError("不支持的筛选项")
    if op not in ALLOWED_OPS:
        raise FilterSpecError("不支持的运算符")
    spec.conditions.append(Condition(field=field_name, op=op, value=value))


def from_legacy_params(
    *,
    event_type: str = "",
    username: str = "",
    ip: str = "",
    device_hash: str = "",
    country: str = "",
    region: str = "",
    exclude_region: str = "",
    risk_tag: str = "",
    success: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    login_only: bool = False,
    unknown_region: Optional[bool] = None,
) -> FilterSpec:
    spec = FilterSpec(login_only=login_only)
    if event_type:
        add_condition(spec, "event_type", "eq", event_type)
    if username:
        add_condition(spec, "username", "contains", username)
    if ip:
        add_condition(spec, "ip", "contains", ip)
    if device_hash:
        add_condition(spec, "device_hash", "eq", device_hash)
    if country:
        add_condition(spec, "country", "contains", country)
    if region:
        add_condition(spec, "region", "eq", region)
    if exclude_region:
        add_condition(spec, "region", "neq", exclude_region)
    if unknown_region is True:
        add_condition(spec, "region", "is_empty")
    elif unknown_region is False:
        add_condition(spec, "region", "not_empty")
    if risk_tag:
        add_condition(spec, "risk_tag", "contains", risk_tag)
    if success is not None:
        add_condition(spec, "success", "eq", success)
    if start_time:
        add_condition(spec, "created_at", "gte", start_time)
    if end_time:
        add_condition(spec, "created_at", "lt", end_time)
    return spec


def filter_rows(rows: Iterable[dict[str, Any]], spec: FilterSpec) -> list[dict[str, Any]]:
    return [row for row in rows if spec.matches(row)]
