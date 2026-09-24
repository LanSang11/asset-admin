"""关键字段改前改后记录的共享服务。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from tortoise.transactions import in_transaction

from app.models.admin import User
from app.models.business import DataFieldChange

ASSET_FIELD_LABELS = {
    "asset_no": "资产编号", "name": "资产名称", "category": "分类", "model": "型号",
    "serial_no": "序列号", "purchase_date": "采购日期", "warranty_until": "质保到期",
    "price": "采购价格", "status": "状态", "location": "存放位置",
    "owner_emp_id": "当前领用人", "remark": "备注",
}
EMPLOYEE_FIELD_LABELS = {
    "emp_no": "工号", "name": "姓名", "gender": "性别", "dept_id": "部门",
    "position": "职位", "hire_date": "入职日期", "phone": "手机", "email": "邮箱",
    "user_id": "绑定账号", "is_manager": "部门主管", "status": "在职状态",
}
ASSET_STATUS_LABELS = {1: "在用", 2: "闲置", 3: "维修", 4: "报废"}
GENDER_LABELS = {0: "未知", 1: "男", 2: "女"}
RETENTION_DAYS = 180
MAX_CHANGE_ROWS = 20_000


def mask_phone(value: object) -> str:
    text = str(value or "")
    return f"{text[:3]}****{text[-4:]}" if len(text) >= 8 else "*" * len(text)


def mask_email(value: object) -> str:
    text = str(value or "")
    local, sep, domain = text.partition("@")
    return f"{local[:1]}***@{domain}" if sep else "*" * len(text)


def format_shanghai_time(value) -> str:
    """Format a UTC/naive timestamp for the UI's established Shanghai convention."""
    if value is None:
        return ""
    shanghai = _shanghai_timezone()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(shanghai).strftime("%Y-%m-%d %H:%M:%S")


def _shanghai_timezone():
    try:
        return ZoneInfo("Asia/Shanghai")
    except Exception:
        return timezone(timedelta(hours=8))


def _labels_for(entity_type: str) -> dict[str, str]:
    if entity_type == "asset":
        return ASSET_FIELD_LABELS
    if entity_type == "employee":
        return EMPLOYEE_FIELD_LABELS
    raise ValueError("unsupported field-change entity type")


def _canonical_value(value: object) -> str:
    """Comparable form: None and empty strings are intentionally equivalent."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _display_value(entity_type: str, field_name: str, value: object) -> str:
    canonical = _canonical_value(value)
    if not canonical:
        return "未填写"
    if entity_type == "asset" and field_name == "status":
        return ASSET_STATUS_LABELS.get(value, canonical)
    if entity_type == "employee":
        if field_name == "gender":
            return GENDER_LABELS.get(value, canonical)
        if field_name == "status":
            return "在职" if bool(value) else "离职"
        if field_name == "is_manager":
            return "是" if bool(value) else "否"
        if field_name == "phone":
            return mask_phone(value) or "未填写"
        if field_name == "email":
            return mask_email(value) or "未填写"
    return canonical


def _field_changes(
    entity_type: str,
    before_values: dict[str, object],
    persisted_after,
    submitted_fields: dict,
) -> list[tuple[str, str, str]]:
    labels = _labels_for(entity_type)
    changes = []
    for field_name in labels:
        if field_name not in submitted_fields:
            continue
        before = before_values[field_name]
        after = getattr(persisted_after, field_name)
        if _values_equal(entity_type, field_name, before, after):
            continue
        changes.append(
            (
                field_name,
                _persisted_display_value(entity_type, field_name, before),
                _persisted_display_value(entity_type, field_name, after),
            )
        )
    return changes


def _persisted_display_value(entity_type: str, field_name: str, value: object) -> str:
    """Timeline columns are VARCHAR(500); SQLite itself does not enforce that limit."""
    return _display_value(entity_type, field_name, value)[:500]


def _values_equal(entity_type: str, field_name: str, before: object, after: object) -> bool:
    """Compare values by field semantics before emitting a timeline row."""
    return _comparison_value(entity_type, field_name, before) == _comparison_value(entity_type, field_name, after)


def _comparison_value(entity_type: str, field_name: str, value: object):
    if value is None or value == "":
        return ("empty", "")
    if entity_type == "employee" and field_name in {"status", "is_manager"}:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"0", "false"}:
                return ("bool", False)
            if lowered in {"1", "true"}:
                return ("bool", True)
        return ("bool", bool(value))
    if (entity_type == "asset" and field_name == "status") or (
        entity_type == "employee" and field_name == "gender"
    ):
        try:
            return ("enum", int(value))
        except (TypeError, ValueError):
            return ("enum", _canonical_value(value))
    if field_name in {"purchase_date", "warranty_until", "hire_date"}:
        if isinstance(value, datetime):
            return ("date", value.date().isoformat())
        if isinstance(value, date):
            return ("date", value.isoformat())
        return ("date", str(value))
    if field_name == "price":
        try:
            return ("decimal", Decimal(str(value)).normalize())
        except (InvalidOperation, ValueError):
            return ("decimal", _canonical_value(value))
    # phone/email intentionally compare raw normalized values; only the display is masked.
    return ("text", _canonical_value(value))


async def update_with_field_changes(model, entity_type: str, entity_id: int, data: dict, operator_id: int):
    """Update a business object and its allowlisted timeline rows atomically."""
    _labels_for(entity_type)
    fields_to_update = {
        key: value
        for key, value in data.items()
        if key in model._meta.db_fields and key not in {"id", "created_at", "updated_at"}
    }
    for key, value in fields_to_update.items():
        if value is None and not model._meta.fields_map[key].null:
            # 旧接口会把未填写的文本字段传成 None；持久层的非空字段统一为空串。
            fields_to_update[key] = ""
    async with in_transaction("sqlite") as conn:
        obj = await model.select_for_update().using_db(conn).get(id=entity_id)
        before_values = {field_name: getattr(obj, field_name) for field_name in _labels_for(entity_type)}
        obj.update_from_dict(fields_to_update)
        await obj.save(using_db=conn)
        persisted_after = await model.filter(id=entity_id).using_db(conn).get()
        changes = _field_changes(entity_type, before_values, persisted_after, fields_to_update)

        if operator_id == 0:
            operator_name = "系统"
        else:
            operator = await User.filter(id=operator_id).using_db(conn).first()
            operator_name = operator.username if operator else ""
        if changes:
            rows = [
                DataFieldChange(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    operator_id=operator_id,
                    operator_name=operator_name,
                )
                for field_name, old_value, new_value in changes
            ]
            await DataFieldChange.bulk_create(rows, using_db=conn)
        await prune_field_changes(using_db=conn)
        return persisted_after


async def list_field_changes(
    entity_type: str,
    entity_id: int,
    page: int,
    page_size: int,
    excluded_fields: set[str] | None = None,
) -> dict:
    labels = _labels_for(entity_type)
    page = max(int(page), 1)
    page_size = max(int(page_size), 1)
    query = DataFieldChange.filter(entity_type=entity_type, entity_id=entity_id)
    if excluded_fields:
        query = query.exclude(field_name__in=excluded_fields)
    total = await query.count()
    rows = await query.order_by("-created_at", "-id").offset((page - 1) * page_size).limit(page_size)
    return {
        "list": [
            {
                "id": row.id,
                "field_name": row.field_name,
                "field_label": labels.get(row.field_name, row.field_name),
                "old_value": row.old_value,
                "new_value": row.new_value,
                "operator_id": row.operator_id,
                "operator_name": row.operator_name,
                "changed_at": format_shanghai_time(row.created_at),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def prune_field_changes(
    retention_days: int = RETENTION_DAYS,
    max_rows: int = MAX_CHANGE_ROWS,
    using_db=None,
) -> dict[str, int]:
    """Keep only the retention window and newest bounded number of timeline rows."""
    query = DataFieldChange.all()
    if using_db is not None:
        query = query.using_db(using_db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    by_days = await query.filter(created_at__lt=cutoff).delete()
    total = await query.count()
    by_rows = 0
    if total > max_rows:
        excess = total - max_rows
        ids = await query.order_by("created_at", "id").limit(excess).values_list("id", flat=True)
        if ids:
            by_rows = await query.filter(id__in=ids).delete()
    return {"by_days": by_days, "by_rows": by_rows}
