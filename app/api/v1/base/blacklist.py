"""黑名单管理接口（超管专属）：查看 / 手动封禁 / 解封网关黑名单。

  GET    /api/v1/base/blacklist              查看当前黑名单
  POST   /api/v1/base/blacklist              手动封禁（需 step-up）
  DELETE /api/v1/base/blacklist?key=         解封（需 step-up）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.dependency import DependAuth, require_operation
from app.core.gateway import get_gateway
from app.models.admin import User
from app.schemas.base import Fail, Success
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


class BlacklistBanIn(BaseModel):
    """手动封禁。target 为 IP 或完整 key（ip:x.x.x.x / uid:1）。"""

    target: str = Field(..., min_length=1, max_length=80, description="IP 或 key")
    minutes: int = Field(15, description="封禁分钟；0 表示长期封禁")
    reason: str = Field("", max_length=200, description="原因备注")


def _normalize_key(target: str) -> str:
    t = (target or "").strip()
    if not t:
        return ""
    if t.startswith("ip:") or t.startswith("uid:"):
        return t[:80]
    # 纯数字当 uid
    if t.isdigit():
        return f"uid:{t}"
    return f"ip:{t}"


@router.get("/blacklist", summary="查看网关黑名单", dependencies=[DependAuth])
async def list_blacklist(current_user: User = DependAuth):
    if not current_user.is_superuser:
        return Fail(code=403, msg="仅超级管理员可查看黑名单")
    gateway = get_gateway()
    if gateway is None:
        return Success(data={})
    return Success(data=gateway.list_blacklist())


@router.post("/blacklist", summary="手动封禁IP或账号")
async def ban_blacklist(
    body: BlacklistBanIn,
    request: Request,
    current_user: User = require_operation("blacklist_ban"),
):
    if not current_user.is_superuser:
        return Fail(code=403, msg="仅超级管理员可封禁")
    key = _normalize_key(body.target)
    if not key:
        return Fail(msg="目标不能为空")
    if key == f"uid:{current_user.id}":
        return Fail(code=400, msg="不能封禁当前登录的超级管理员账号")
    current_ip_key = f"ip:{client_ip(request)}"
    if key == current_ip_key:
        return Fail(code=400, msg="不能封禁当前登录出口 IP")
    gateway = get_gateway()
    if gateway is None:
        return Fail(msg="网关未初始化")
    seconds = 0 if body.minutes <= 0 else int(body.minutes) * 60
    gateway.add_to_blacklist(key, seconds=seconds, reason=body.reason or "管理员手动封禁", source="manual")
    await log_security_event(
        event_type="ban",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"封禁 {key} minutes={body.minutes} reason={body.reason or ''}",
        success=True,
    )
    return Success(msg=f"已封禁 {key}")


@router.delete("/blacklist", summary="解封黑名单")
async def remove_blacklist(
    request: Request,
    key: str = Query(..., description="黑名单 key，如 ip:127.0.0.1 或 uid:1"),
    current_user: User = require_operation("blacklist_unban"),
):
    if not current_user.is_superuser:
        return Fail(code=403, msg="仅超级管理员可解封")
    gateway = get_gateway()
    if gateway is None:
        return Fail(msg="网关未初始化")
    nk = _normalize_key(key) or key
    ok = gateway.remove_blacklist(nk)
    await log_security_event(
        event_type="unban",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"解封 {nk}",
        success=ok,
    )
    if ok:
        return Success(msg=f"已解封 {nk}")
    return Fail(msg=f"黑名单中不存在 {nk}")
