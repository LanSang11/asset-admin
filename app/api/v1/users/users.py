import asyncio
import logging

from fastapi import APIRouter, Body, HTTPException, Query, Request
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.controllers.dept import dept_controller
from app.controllers.role import role_controller
from app.controllers.user import user_controller
from app.core.auth_version import bump_user_auth_version
from app.core.dependency import DependAuth, require_operation, require_step_up
from app.models.admin import User
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.users import *
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

logger = logging.getLogger(__name__)

router = APIRouter()
_superuser_mutation_lock = asyncio.Lock()


async def assert_no_super_privilege(current_user: User, is_superuser: bool, role_ids: list[int]) -> None:
    """防自我提权：非超管调用者不得创建/授予超管权限，也不得分配管理员角色"""
    if current_user.is_superuser:
        return
    if is_superuser:
        raise HTTPException(status_code=403, detail="无权授予超级管理员权限")
    if role_ids:
        for rid in role_ids:
            role_obj = await role_controller.get(id=rid)
            if role_obj and role_obj.name == "管理员":
                raise HTTPException(status_code=403, detail="无权分配管理员角色")


async def assert_superuser_count_safe(exclude_user_id: int, using_db=None) -> None:
    """系统中至少保留一个可用超管；调用方须在写事务持锁后检查。"""
    query = User.filter(is_superuser=True, is_active=True).exclude(id=exclude_user_id)
    if using_db is not None:
        query = query.using_db(using_db)
    superuser_count = await query.count()
    if superuser_count < 1:
        raise HTTPException(status_code=400, detail="系统必须至少保留一个可用的超级管理员账号")


@router.get("/list", summary="查看用户列表")
async def list_user(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量（上限 100）"),
    username: str = Query("", description="用户名称，用于搜索"),
    email: str = Query("", description="邮箱地址"),
    dept_id: int = Query(None, description="部门ID"),
):
    q = Q()
    if username:
        q &= Q(username__contains=username)
    if email:
        q &= Q(email__contains=email)
    if dept_id is not None:
        q &= Q(dept_id=dept_id)
    total, user_objs = await user_controller.list(page=page, page_size=page_size, search=q)
    data = [
        await obj.to_dict(m2m=True, exclude_fields=["password", "totp_secret", "api_config"])
        for obj in user_objs
    ]
    # 修复：批量查询部门（原每用户一次查询 N+1；dept_id 为脏数据时 get 抛 DoesNotExist 使整个列表 404）
    dept_ids = {item.get("dept_id") for item in data if item.get("dept_id")}
    dept_map = {d.id: d for d in await dept_controller.model.filter(id__in=list(dept_ids))} if dept_ids else {}
    for item, obj in zip(data, user_objs):
        did = item.pop("dept_id", None)
        item["dept"] = await dept_map[did].to_dict() if did and did in dept_map else {}
        cfg = obj.api_config if isinstance(obj.api_config, dict) else {}
        item["has_key"] = bool(cfg.get("api_key_enc"))

    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看用户")
async def get_user(
    user_id: int = Query(..., description="用户ID"),
):
    user_obj = await user_controller.get(id=user_id)
    user_dict = await user_obj.to_dict(exclude_fields=["password", "totp_secret", "api_config"])
    cfg = user_obj.api_config if isinstance(user_obj.api_config, dict) else {}
    user_dict["has_key"] = bool(cfg.get("api_key_enc"))
    return Success(data=user_dict)


@router.post("/create", summary="创建用户")
async def create_user(
    user_in: UserCreate,
    current_user: User = require_operation("user_create"),
):
    # 防自我提权：非超管不得创建超管账号或分配管理员角色
    await assert_no_super_privilege(
        current_user,
        bool(user_in.is_superuser),
        user_in.role_ids or [],
    )
    user = await user_controller.get_by_email(user_in.email)
    if user:
        return Fail(code=400, msg="系统中已存在该邮箱用户")
    new_user = await user_controller.create_user(obj_in=user_in)
    await user_controller.update_roles(new_user, user_in.role_ids)
    return Success(msg="创建成功")


@router.post("/update", summary="更新用户")
async def update_user(
    user_in: UserUpdate,
    request: Request,
    current_user: User = DependAuth,
):
    target = await user_controller.get(id=user_in.id)
    sensitive_fields = {"role_ids", "is_superuser", "is_active"}
    if current_user.is_superuser and user_in.model_fields_set & sensitive_fields:
        current_user = await require_step_up("user_update_security", request, current_user)
    # 防自我提权：非超管不得授予超管权限/管理员角色，不得修改超管账号
    await assert_no_super_privilege(
        current_user,
        bool(user_in.is_superuser),
        user_in.role_ids or [],
    )
    if target.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权修改超级管理员账号")
    demoting = "is_superuser" in user_in.model_fields_set and user_in.is_superuser is False
    disabling = "is_active" in user_in.model_fields_set and user_in.is_active is False
    if target.is_superuser and (demoting or disabling):
        async with _superuser_mutation_lock:
            async with in_transaction() as connection:
                await connection.execute_query(
                    "UPDATE user SET auth_version = auth_version WHERE id = ?",
                    [target.id],
                )
                await assert_superuser_count_safe(
                    exclude_user_id=target.id,
                    using_db=connection,
                )
                target.update_from_dict(user_in.model_dump(exclude_unset=True, exclude={"id", "role_ids"}))
                await target.save(using_db=connection)
            if "role_ids" in user_in.model_fields_set:
                await user_controller.update_roles(target, user_in.role_ids or [])
            return Success(msg="更新成功")
    # 非超管仅允许修改自己的基本资料（修复：禁止自行修改 role_ids，
    # 原实现非超管可在普通角色间切换造成权限蔓延）
    if not current_user.is_superuser:
        if target.id != current_user.id:
            raise HTTPException(status_code=403, detail="无权修改其他用户信息")
        if "role_ids" in user_in.model_fields_set:
            raise HTTPException(status_code=403, detail="无权修改角色，请联系管理员")
        if user_in.is_active is not None and user_in.is_active != target.is_active:
            raise HTTPException(status_code=403, detail="无权修改账户启用状态")
    user = await user_controller.update(id=user_in.id, obj_in=user_in)
    # 仅当请求显式携带 role_ids 时才更新角色（profile 页更新资料不传 role_ids，避免误清空角色）
    if "role_ids" in user_in.model_fields_set:
        await user_controller.update_roles(user, user_in.role_ids)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除用户")
async def delete_user(
    request: Request,
    user_id: int = Query(..., description="用户ID"),
    current_user: User = require_operation("user_delete"),
):
    target = await user_controller.get(id=user_id)
    if target.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="无权删除超级管理员账号")
    if target.is_superuser:
        async with _superuser_mutation_lock:
            async with in_transaction() as connection:
                await connection.execute_query(
                    "UPDATE user SET auth_version = auth_version WHERE id = ?",
                    [target.id],
                )
                await assert_superuser_count_safe(
                    exclude_user_id=target.id,
                    using_db=connection,
                )
                await target.delete(using_db=connection)
    else:
        await user_controller.remove(id=user_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除用户 id={user_id} username={target.username}",
        success=True,
    )
    return Success(msg="删除成功")


@router.post("/reset_password", summary="重置密码")
async def reset_password(
    request: Request,
    user_id: int = Body(..., description="用户ID", embed=True),
    current_user: User = require_operation("user_reset_password"),
):
    # 仅超级管理员可重置他人密码（防止持 API 权限角色滥用重置功能接管账号）
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可重置密码")
    new_password = await user_controller.reset_password(user_id)
    # 修复：日志只记录掩码（原明文写日志，日志泄露即账号被接管）；完整一次性密码经接口返回给管理员转交
    masked = new_password[:2] + "***"
    logger.warning(
        "管理员 %s 重置用户 %s 的密码，一次性新密码（仅本次可见，用户首次登录后必须修改）：%s",
        current_user.username,
        user_id,
        masked,
    )
    await log_security_event(
        event_type="reset_password",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"重置用户密码 target_id={user_id}",
        success=True,
    )
    return Success(data={"temporary_password": new_password}, msg="密码已重置，请将一次性密码告知用户；用户首次登录需修改密码")


@router.post("/reset_totp", summary="重置他人的动态验证器绑定")
async def reset_totp(
    request: Request,
    user_id: int = Body(..., description="用户ID", embed=True),
    current_user: User = require_operation("user_totp_reset"),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可重置动态验证器")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能通过管理员接口重置自己的动态验证器")
    target = await user_controller.get(id=user_id)
    target.totp_secret = None
    target.totp_enabled = False
    target.recovery_question = None
    target.recovery_answer_hash = None
    target.recovery_fail_count = 0
    target.recovery_locked_until = None
    bump_user_auth_version(target)
    await target.save()
    await log_security_event(
        event_type="totp_admin_reset",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"重置他人 TOTP target_id={target.id}",
        success=True,
    )
    return Success(msg="动态验证器已重置，该账号需要重新绑定")
