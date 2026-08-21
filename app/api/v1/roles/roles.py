import logging

from fastapi import APIRouter, Query, Request
from fastapi.exceptions import HTTPException
from tortoise.expressions import Q

from app.controllers import role_controller
from app.core.dependency import require_operation
from app.models.admin import User
from app.schemas.base import Success, SuccessExtra
from app.schemas.roles import *
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list", summary="查看角色列表")
async def list_role(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    role_name: str = Query("", description="角色名称，用于查询"),
):
    q = Q()
    if role_name:
        q = Q(name__contains=role_name)
    total, role_objs = await role_controller.list(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in role_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看角色")
async def get_role(
    role_id: int = Query(..., description="角色ID"),
):
    role_obj = await role_controller.get(id=role_id)
    return Success(data=await role_obj.to_dict())


@router.post("/create", summary="创建角色")
async def create_role(role_in: RoleCreate):
    if await role_controller.is_exist(name=role_in.name):
        raise HTTPException(
            status_code=400,
            detail="系统中已存在同名角色",
        )
    await role_controller.create(obj_in=role_in)
    return Success(msg="创建成功")


@router.post("/update", summary="更新角色")
async def update_role(role_in: RoleUpdate):
    role_obj = await role_controller.get(id=role_in.id)
    # 保护内置角色："管理员"不允许改名（防角色名判断被绕过导致提权链）
    if role_obj.name == "管理员" and role_in.name != "管理员":
        raise HTTPException(status_code=403, detail="内置角色「管理员」不允许改名")
    await role_controller.update(id=role_in.id, obj_in=role_in)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除角色")
async def delete_role(
    request: Request,
    role_id: int = Query(..., description="角色ID"),
    current_user: User = require_operation("role_delete"),
):
    role_obj = await role_controller.get(id=role_id)
    # 保护内置角色："管理员"不允许删除（防止用户管理失去管理员角色保护）
    if role_obj.name == "管理员":
        raise HTTPException(status_code=403, detail="内置角色「管理员」不允许删除")
    # 删除前检查是否有用户仍绑定该角色，避免用户变成"无角色"后所有接口 403
    bound = await role_obj.user_roles.all()
    if bound:
        raise HTTPException(status_code=400, detail=f"仍有 {len(bound)} 个用户绑定该角色，请先解绑")
    await role_controller.remove(id=role_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除角色 id={role_id} name={role_obj.name}",
        success=True,
    )
    return Success(msg="删除成功")


@router.get("/authorized", summary="查看角色权限")
async def get_role_authorized(id: int = Query(..., description="角色ID")):
    role_obj = await role_controller.get(id=id)
    # 安全：m2m 会序列化关联用户；必须排除 password，避免 argon2 哈希经角色授权接口泄露
    data = await role_obj.to_dict(m2m=True, exclude_fields=["password"])
    # 关联侧字段名可能挂在 user_roles；双保险再剥一次
    for key in ("user_roles", "users"):
        rows = data.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    row.pop("password", None)
                    row.pop("api_config", None)
    return Success(data=data)


@router.post("/authorized", summary="更新角色权限")
async def update_role_authorized(
    role_in: RoleUpdateMenusApis,
    request: Request,
    current_user: User = require_operation("role_authorize"),
):
    # 修复：接口内超管校验（与 exports/blacklist 一致）——原实现仅依赖 API 权限表，
    # 持有 /role/authorized 权限的非超管可修改任意角色（含「管理员」）授权，构成提权链
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可修改角色权限")
    role_obj = await role_controller.get(id=role_in.id)
    await role_controller.update_roles(role=role_obj, menu_ids=role_in.menu_ids, api_infos=role_in.api_infos)
    await log_security_event(
        event_type="role_authorize",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"更新角色权限 role_id={role_in.id}",
        success=True,
    )
    return Success(msg="更新成功")
