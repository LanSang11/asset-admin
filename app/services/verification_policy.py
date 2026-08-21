from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from app.models.admin import Role, User, VerificationPolicy, VerificationSettings

VerificationMode = Literal["off", "password", "totp"]

ROOT_OPERATION_KEYS = frozenset(
    {
        "verification_policy_update",
        "user_totp_reset",
        "acceptance_mode_update",
        "tls_cert_renew",
    }
)
ACCEPTANCE_MODE_HOURS = 2

OPERATION_DEFINITIONS = (
    ("user_create", "创建系统用户", "totp"),
    ("user_update_security", "修改用户角色、超管或启停状态", "totp"),
    ("user_delete", "删除用户", "totp"),
    ("user_reset_password", "重置用户密码", "totp"),
    ("role_delete", "删除角色", "totp"),
    ("role_authorize", "修改角色权限", "totp"),
    ("api_delete", "删除 API", "totp"),
    ("api_refresh", "刷新 API 权限清单", "totp"),
    ("dept_delete", "删除部门", "totp"),
    ("menu_delete", "删除菜单", "totp"),
    ("employee_delete", "删除员工", "password"),
    ("asset_delete", "删除资产", "password"),
    ("asset_import_commit", "批量导入资产并写库", "password"),
    ("blacklist_ban", "封禁 IP 或账号", "totp"),
    ("blacklist_unban", "解除封禁", "totp"),
    ("export_employees", "导出员工数据", "totp"),
    ("export_assets", "导出资产数据", "totp"),
    ("export_asset_uses", "导出领用记录", "totp"),
)

VALID_MODES = frozenset({"off", "password", "totp"})


async def ensure_verification_defaults() -> None:
    for key, label, mode in OPERATION_DEFINITIONS:
        await VerificationPolicy.get_or_create(
            operation_key=key,
            defaults={"label": label, "mode": mode},
        )
    await VerificationSettings.get_or_create(
        id=1,
        defaults={"force_superuser": True, "role_ids": []},
    )


async def operation_mode(operation_key: str) -> str:
    if operation_key in ROOT_OPERATION_KEYS:
        return "totp"
    definition = next((item for item in OPERATION_DEFINITIONS if item[0] == operation_key), None)
    if definition is None:
        raise ValueError("未知的高危操作")
    policy = await VerificationPolicy.filter(operation_key=operation_key).first()
    return policy.mode if policy and policy.mode in VALID_MODES else definition[2]


async def login_totp_required(user: User) -> bool:
    settings = await VerificationSettings.filter(id=1).first()
    force_superuser = True if settings is None else bool(settings.force_superuser)
    if force_superuser and user.is_superuser:
        return True
    role_ids = [] if settings is None else [int(item) for item in (settings.role_ids or [])]
    if not role_ids:
        return False
    roles: list[Role] = await user.roles
    return any(role.id in role_ids for role in roles)


async def policies_payload() -> dict:
    settings = await VerificationSettings.filter(id=1).first()
    policies = {item.operation_key: item for item in await VerificationPolicy.all()}
    operations = []
    for key, label, default_mode in OPERATION_DEFINITIONS:
        policy = policies.get(key)
        operations.append(
            {
                "operation_key": key,
                "label": label,
                "mode": policy.mode if policy and policy.mode in VALID_MODES else default_mode,
            }
        )
    roles = await Role.all().order_by("id")
    return {
        "operations": operations,
        "login": {
            "force_superuser": True if settings is None else bool(settings.force_superuser),
            "role_ids": [] if settings is None else [int(item) for item in (settings.role_ids or [])],
        },
        "roles": [{"id": role.id, "name": role.name} for role in roles],
        "root_operations": [
            {"operation_key": "verification_policy_update", "label": "修改二次验证策略", "mode": "totp"},
            {"operation_key": "user_totp_reset", "label": "重置他人 TOTP", "mode": "totp"},
            {"operation_key": "acceptance_mode_update", "label": "开启限时验收模式", "mode": "totp"},
            {"operation_key": "tls_cert_renew", "label": "续签 HTTPS 证书", "mode": "totp"},
        ],
        "acceptance_mode": acceptance_window(getattr(settings, "acceptance_until", None)),
        "password_rotate": password_rotate_payload(settings),
    }


def _aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def acceptance_window(until: Optional[datetime], now: Optional[datetime] = None) -> dict:
    current = _aware_utc(now) or datetime.now(timezone.utc)
    expires = _aware_utc(until)
    active = bool(expires and expires > current)
    remaining = int((expires - current).total_seconds()) if active else 0
    return {
        "active": active,
        "expires_at": expires.isoformat() if active else None,
        "remaining_seconds": max(remaining, 0),
        "duration_hours": ACCEPTANCE_MODE_HOURS,
    }


async def acceptance_mode_status() -> dict:
    settings = await VerificationSettings.filter(id=1).first()
    return acceptance_window(getattr(settings, "acceptance_until", None) if settings else None)


async def acceptance_mode_active() -> bool:
    return bool((await acceptance_mode_status()).get("active"))


def password_rotate_due(
    *,
    max_days: int,
    deadline: Optional[datetime],
    password_changed_at: Optional[datetime],
    created_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """默认关：max_days=0 且无截止日期时不过期。"""
    current = _aware_utc(now) or datetime.now(timezone.utc)
    limit = _aware_utc(deadline)
    if limit and current >= limit:
        return True
    days = int(max_days or 0)
    if days <= 0:
        return False
    changed = _aware_utc(password_changed_at) or _aware_utc(created_at)
    if changed is None:
        return True
    return current >= changed + timedelta(days=days)


def password_rotate_payload(settings: Optional[VerificationSettings]) -> dict:
    if settings is None:
        return {"max_days": 0, "deadline": None, "enabled": False}
    max_days = int(getattr(settings, "password_max_days", 0) or 0)
    deadline = _aware_utc(getattr(settings, "password_deadline", None))
    return {
        "max_days": max_days,
        "deadline": deadline.isoformat() if deadline else None,
        "enabled": bool(max_days > 0 or deadline),
    }


async def password_must_rotate(user: User) -> bool:
    settings = await VerificationSettings.filter(id=1).first()
    if settings is None:
        return False
    return password_rotate_due(
        max_days=int(getattr(settings, "password_max_days", 0) or 0),
        deadline=getattr(settings, "password_deadline", None),
        password_changed_at=getattr(user, "password_changed_at", None),
        created_at=getattr(user, "created_at", None),
    )


async def set_acceptance_mode(enabled: bool) -> dict:
    settings, _ = await VerificationSettings.get_or_create(
        id=1,
        defaults={"force_superuser": True, "role_ids": []},
    )
    settings.acceptance_until = (
        datetime.now(timezone.utc) + timedelta(hours=ACCEPTANCE_MODE_HOURS) if enabled else None
    )
    await settings.save()
    return acceptance_window(settings.acceptance_until)
