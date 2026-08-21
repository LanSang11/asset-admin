"""安全事件 / 登录日志（仅超管硬锁）。"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.dependency import DependSuperUser, require_operation, require_step_up
from app.core.gateway import get_gateway
from app.models.admin import Role, SecurityAggBucket, SecurityEvent, User, VerificationPolicy, VerificationSettings
from app.schemas.base import Success, SuccessExtra
from app.services.security_agg import build_security_posture, spec_to_agg_q
from app.services.security_event_service import enrich_event_dict
from app.services.security_query import from_legacy_params
from app.services.security_event_service import log_security_event
from app.services.tls_cert import tls_renew, tls_status
from app.services.verification_policy import (
    OPERATION_DEFINITIONS,
    VALID_MODES,
    policies_payload,
    set_acceptance_mode,
)
from app.settings.config import settings
from app.utils.geoip import format_location
from app.utils.security_risk import tag_catalog
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


class VerificationOperationIn(BaseModel):
    operation_key: str = Field(..., min_length=1, max_length=64)
    mode: str = Field(..., min_length=2, max_length=16)


class VerificationLoginIn(BaseModel):
    force_superuser: bool = True
    role_ids: list[int] = Field(default_factory=list)


class PasswordRotateIn(BaseModel):
    max_days: int = Field(0, ge=0, le=3650)
    deadline: Optional[datetime] = None


class VerificationPoliciesIn(BaseModel):
    operations: list[VerificationOperationIn]
    login: VerificationLoginIn
    password_rotate: PasswordRotateIn = Field(default_factory=PasswordRotateIn)


class AcceptanceModeIn(BaseModel):
    enabled: bool


def _event_filters(
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
) -> Q:
    return from_legacy_params(
        event_type=event_type,
        username=username,
        ip=ip,
        device_hash=device_hash,
        country=country,
        region=region,
        exclude_region=exclude_region,
        risk_tag=risk_tag,
        success=success,
        start_time=start_time,
        end_time=end_time,
        login_only=login_only,
        unknown_region=unknown_region,
    ).to_q()


@router.get("/posture", summary="安全态势（仅超管）")
async def security_posture(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = DependSuperUser,
):
    _ = current_user
    return Success(data=await build_security_posture(hours=hours))


@router.get("/attacks", summary="攻击聚合桶（仅超管）")
async def list_attack_agg(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    event_type: str = Query(""),
    ip: str = Query(""),
    country: str = Query(""),
    region: str = Query(""),
    exclude_region: str = Query(""),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    unknown_region: Optional[bool] = Query(None),
    current_user: User = DependSuperUser,
):
    _ = current_user
    from app.services.security_agg import flush_attack_buckets

    await flush_attack_buckets()
    spec = from_legacy_params(
        event_type=event_type,
        ip=ip,
        country=country,
        region=region,
        exclude_region=exclude_region,
        start_time=start_time,
        end_time=end_time,
        unknown_region=unknown_region,
    )
    q = spec_to_agg_q(spec)
    total = await SecurityAggBucket.filter(q).count()
    rows = (
        await SecurityAggBucket.filter(q)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .order_by("-bucket_minute", "-hit_count")
    )
    data = []
    for r in rows:
        item = await r.to_dict()
        item["location"] = (
            "未知" if unknown_region is True else format_location(r.country or "", r.region or "")
        )
        data.append(item)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/dashboard", summary="近24小时运营数字")
async def security_dashboard(current_user: User = DependSuperUser):
    _ = current_user
    since = datetime.now() - timedelta(hours=24)
    success = await SecurityEvent.filter(event_type="login_success", created_at__gte=since).count()
    failure = await SecurityEvent.filter(event_type="login_failure", created_at__gte=since).count()
    ips = await SecurityEvent.filter(
        event_type__in=["login_success", "login_failure"],
        created_at__gte=since,
    ).values_list("ip", flat=True)
    unique_ip = len({i for i in ips if i})
    gateway = get_gateway()
    ban_count = len(gateway.list_blacklist()) if gateway is not None else 0
    return Success(
        data={
            "hours": 24,
            "login_success": success,
            "login_failure": failure,
            "unique_ip": unique_ip,
            "ban_count": ban_count,
            "auto_ban": False,
            "common_countries": settings.SECURITY_COMMON_COUNTRIES,
        }
    )


@router.get("/tag-help", summary="风险标签说明（仅超管）")
async def security_tag_help(current_user: User = DependSuperUser):
    _ = current_user
    return Success(data=tag_catalog())


@router.get("/user-devices", summary="某账号近次设备摘要")
async def list_user_devices(
    username: str = Query(..., min_length=1, max_length=64),
    current_user: User = DependSuperUser,
):
    _ = current_user
    rows = (
        await SecurityEvent.filter(username=username, device_hash__not="")
        .order_by("-created_at")
        .limit(200)
    )
    grouped: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        dh = r.device_hash
        if dh not in grouped:
            order.append(dh)
            grouped[dh] = {
                "device_hash": dh,
                "last_seen": r.created_at.strftime(settings.DATETIME_FORMAT) if r.created_at else "",
                "first_seen": r.created_at.strftime(settings.DATETIME_FORMAT) if r.created_at else "",
                "ip": r.ip,
                "country": r.country,
                "region": r.region,
                "isp": r.isp,
                "risk_tags": r.risk_tags,
                "login_count": 0,
            }
        item = grouped[dh]
        item["login_count"] += 1
        if r.created_at:
            item["first_seen"] = r.created_at.strftime(settings.DATETIME_FORMAT)
    data = [grouped[k] for k in order[:20]]
    for item in data:
        enrich_event_dict(item)
    return Success(data=data)


@router.get("/events", summary="安全事件列表（含登录）")
async def list_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    event_type: str = Query(""),
    username: str = Query(""),
    ip: str = Query(""),
    device_hash: str = Query(""),
    country: str = Query(""),
    region: str = Query(""),
    exclude_region: str = Query(""),
    risk_tag: str = Query(""),
    success: Optional[bool] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    unknown_region: Optional[bool] = Query(None),
    current_user: User = DependSuperUser,
):
    _ = current_user
    q = _event_filters(
        event_type=event_type,
        username=username,
        ip=ip,
        device_hash=device_hash,
        country=country,
        region=region,
        exclude_region=exclude_region,
        risk_tag=risk_tag,
        success=success,
        start_time=start_time,
        end_time=end_time,
        unknown_region=unknown_region,
    )
    total = await SecurityEvent.filter(q).count()
    rows = await SecurityEvent.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    data = []
    for r in rows:
        item = await r.to_dict()
        if unknown_region is True:
            item["location"] = "未知"
            item["risk_tag_list"] = []
        else:
            enrich_event_dict(item)
        data.append(item)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/login-events", summary="登录相关事件")
async def list_login_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    username: str = Query(""),
    ip: str = Query(""),
    device_hash: str = Query(""),
    country: str = Query(""),
    region: str = Query(""),
    exclude_region: str = Query(""),
    risk_tag: str = Query(""),
    success: Optional[bool] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    unknown_region: Optional[bool] = Query(None),
    current_user: User = DependSuperUser,
):
    _ = current_user
    q = _event_filters(
        username=username,
        ip=ip,
        device_hash=device_hash,
        country=country,
        region=region,
        exclude_region=exclude_region,
        risk_tag=risk_tag,
        success=success,
        start_time=start_time,
        end_time=end_time,
        login_only=True,
        unknown_region=unknown_region,
    )
    total = await SecurityEvent.filter(q).count()
    rows = await SecurityEvent.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    data = []
    for r in rows:
        item = await r.to_dict()
        if unknown_region is True:
            item["location"] = "未知"
            item["risk_tag_list"] = []
        else:
            enrich_event_dict(item)
        data.append(item)
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/retention", summary="日志保留策略（只读）")
async def get_retention(current_user: User = DependSuperUser):
    _ = current_user
    return Success(
        data={
            "audit_retention_days": settings.AUDIT_RETENTION_DAYS,
            "audit_max_rows": settings.AUDIT_MAX_ROWS,
            "security_event_retention_days": settings.SECURITY_EVENT_RETENTION_DAYS,
            "security_event_max_rows": settings.SECURITY_EVENT_MAX_ROWS,
            "security_agg_retention_days": getattr(settings, "SECURITY_AGG_RETENTION_DAYS", 180),
            "security_agg_max_rows": getattr(settings, "SECURITY_AGG_MAX_ROWS", 200000),
            "log_cleanup_interval_seconds": settings.LOG_CLEANUP_INTERVAL_SECONDS,
            "step_up_expire_seconds": settings.STEP_UP_EXPIRE_SECONDS,
            "auto_ban": False,
        }
    )


@router.get("/verification-policies", summary="查看二次验证策略")
async def get_verification_policies(current_user: User = DependSuperUser):
    _ = current_user
    return Success(data=await policies_payload())


@router.put("/verification-policies", summary="更新二次验证策略")
async def update_verification_policies(
    body: VerificationPoliciesIn,
    request: Request,
    current_user: User = require_operation("verification_policy_update"),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可修改二次验证策略")
    definitions = {key: (label, default) for key, label, default in OPERATION_DEFINITIONS}
    incoming = {item.operation_key: item.mode for item in body.operations}
    if set(incoming) != set(definitions):
        raise HTTPException(status_code=400, detail="二次验证策略项目不完整")
    if any(mode not in VALID_MODES for mode in incoming.values()):
        raise HTTPException(status_code=400, detail="二次验证模式无效")
    role_ids = sorted(set(body.login.role_ids))
    existing_role_ids = set(await Role.filter(id__in=role_ids).values_list("id", flat=True)) if role_ids else set()
    if existing_role_ids != set(role_ids):
        raise HTTPException(status_code=400, detail="包含不存在的角色")
    async with in_transaction() as connection:
        for key, mode in incoming.items():
            label, _ = definitions[key]
            await VerificationPolicy.update_or_create(
                operation_key=key,
                defaults={"label": label, "mode": mode},
                using_db=connection,
            )
        settings_obj, _ = await VerificationSettings.get_or_create(id=1, using_db=connection)
        settings_obj.force_superuser = body.login.force_superuser
        settings_obj.role_ids = role_ids
        settings_obj.password_max_days = int(body.password_rotate.max_days or 0)
        deadline = body.password_rotate.deadline
        if deadline and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        settings_obj.password_deadline = deadline
        await settings_obj.save(using_db=connection)
    await log_security_event(
        event_type="verification_policy_update",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="更新二次验证策略",
        success=True,
    )
    return Success(data=await policies_payload(), msg="二次验证策略已更新")


@router.put("/acceptance-mode", summary="开启或关闭限时验收模式")
async def update_acceptance_mode(
    body: AcceptanceModeIn,
    request: Request,
    current_user: User = DependSuperUser,
):
    if body.enabled:
        if not (getattr(current_user, "totp_enabled", False) and getattr(current_user, "totp_secret", None)):
            raise HTTPException(status_code=403, detail="请先绑定动态验证器后再开启验收模式")
        current_user = await require_step_up("acceptance_mode_update", request, current_user)
    status = await set_acceptance_mode(body.enabled)
    await log_security_event(
        event_type="acceptance_mode",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="开启限时验收模式" if body.enabled else "关闭限时验收模式",
        success=True,
    )
    return Success(
        data=status,
        msg="已开启 2 小时验收模式，到期自动恢复登录动态码" if body.enabled else "验收模式已关闭，登录恢复动态码",
    )


@router.get("/tls", summary="查看 HTTPS 证书状态")
async def get_tls_status(current_user: User = DependSuperUser):
    _ = current_user
    return Success(data=tls_status())


@router.post("/tls/renew", summary="续签 HTTPS 证书")
async def renew_tls_cert(
    request: Request,
    current_user: User = require_operation("tls_cert_renew"),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可续签证书")
    data = tls_renew()
    renew = data.get("renew") or {}
    await log_security_event(
        event_type="tls_renew",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=renew.get("message") or ("证书续签成功" if renew.get("ok") else "证书续签未完成"),
        success=bool(renew.get("ok")),
    )
    if renew.get("ok") and renew.get("skipped"):
        return Success(data=data, msg=renew.get("message") or "尚未到自动续签窗口，证书仍有效")
    if renew.get("ok"):
        return Success(data=data, msg=renew.get("message") or "证书已续签")
    raise HTTPException(status_code=400, detail=renew.get("message") or "证书续签失败")
