from fastapi import APIRouter, HTTPException, Query, Request

from app.controllers.asset import ASSET_CATEGORIES, asset_controller
from app.services.warranty import attach_warranty_fields
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, DependPermission, require_operation
from app.models.admin import User
from app.models.business import Employee
from app.schemas.base import Success
from app.schemas.assets import *
from app.services.security_event_service import log_security_event
from app.utils.identity import resolve_biz_role
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


@router.get("/list", summary="查看资产列表", dependencies=[DependAuth])
async def list_asset(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量（上限 100）"),
    keyword: str = Query("", description="搜索关键词（名称/编号/序列号）"),
    category: str = Query("", description="分类"),
    status: int = Query(0, description="状态：0全部 1在用 2闲置 3维修 4报废"),
    warranty_state: str = Query("", description="质保：expired/expiring/due/ok/none"),
):
    # 修复：分页参数与前端 CrudTable 契约统一（原后端收 limit，前端发 page_size → 每页条数失效）
    # ISO-B1：行级缩圈 + 字段脱敏
    total, items = await asset_controller.list_assets(
        page, page_size, keyword, category, status, warranty_state=warranty_state or ""
    )
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    emp = await Employee.filter(user_id=user_id).first()
    role = await resolve_biz_role(user, emp)
    data = [await asset_controller.serialize_for_viewer(item, role, emp) for item in items]
    return Success(data={"list": data, "total": total})


@router.get("/get", summary="查看资产", dependencies=[DependAuth])
async def get_asset(
    id: int = Query(..., description="资产ID"),
):
    obj = await asset_controller.get(id=id)
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    emp = await Employee.filter(user_id=user_id).first()
    role = await resolve_biz_role(user, emp)
    if not await asset_controller.can_view_asset(obj, role, emp):
        raise HTTPException(status_code=403, detail="无权查看该资产")
    return Success(data=await asset_controller.serialize_for_viewer(obj, role, emp))


@router.get("/categories", summary="资产分类列表", dependencies=[DependAuth])
async def list_categories():
    return Success(data=ASSET_CATEGORIES)


@router.get("/my", summary="我名下的在用资产（归还申请用）", dependencies=[DependAuth])
async def my_assets():
    # 修复：归还申请需要"我自己名下的在用资产"列表
    # （原前端加载闲置资产，闲置资产无 owner，归还功能永远选不到可归项）
    from app.core.ctx import CTX_USER_ID
    from app.models.business import Asset, Employee

    user_id = CTX_USER_ID.get()
    emp = await Employee.filter(user_id=user_id).first()
    if not emp:
        return Success(data=[])
    # 在用 + 维修中（送修仍挂在名下）
    items = await Asset.filter(owner_emp_id=emp.id, status__in=[1, 3]).order_by("-created_at")
    return Success(data=[attach_warranty_fields(await a.to_dict()) for a in items])


@router.post("/create", summary="创建资产", dependencies=[DependPermission])
async def create_asset(
    asset_in: AssetCreate,
):
    obj = await asset_controller.create_asset(asset_in)
    return Success(data=await obj.to_dict(), msg="创建成功")


@router.post("/update", summary="更新资产", dependencies=[DependPermission])
async def update_asset(
    asset_in: AssetUpdate,
):
    obj = await asset_controller.update_asset(asset_in)
    return Success(data=await obj.to_dict(), msg="更新成功")


@router.delete("/delete", summary="删除资产", dependencies=[DependPermission])
async def delete_asset(
    request: Request,
    asset_id: int = Query(..., description="资产ID"),
    current_user: User = require_operation("asset_delete"),
):
    # 修复：删除前校验在用/在途/历史（防止悬空引用）
    await asset_controller.delete_asset(asset_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除资产 id={asset_id}",
        success=True,
    )
    return Success(msg="删除成功")
