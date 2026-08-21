from fastapi import APIRouter, Query, Request
from tortoise.expressions import Q

from app.controllers.api import api_controller
from app.core.dependency import require_operation
from app.models.admin import User
from app.schemas import Success, SuccessExtra
from app.schemas.apis import *
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


@router.get("/list", summary="查看API列表")
async def list_api(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    path: str = Query(None, description="API路径"),
    summary: str = Query(None, description="API简介"),
    tags: str = Query(None, description="API模块"),
):
    q = Q()
    if path:
        q &= Q(path__contains=path)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)
    total, api_objs = await api_controller.list(page=page, page_size=page_size, search=q, order=["tags", "id"])
    data = [await obj.to_dict() for obj in api_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看Api")
async def get_api(
    id: int = Query(..., description="Api"),
):
    api_obj = await api_controller.get(id=id)
    data = await api_obj.to_dict()
    return Success(data=data)


@router.post("/create", summary="创建Api")
async def create_api(
    api_in: ApiCreate,
):
    await api_controller.create(obj_in=api_in)
    return Success(msg="创建成功")


@router.post("/update", summary="更新Api")
async def update_api(
    api_in: ApiUpdate,
):
    await api_controller.update(id=api_in.id, obj_in=api_in)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除Api")
async def delete_api(
    request: Request,
    api_id: int = Query(..., description="ApiID"),
    current_user: User = require_operation("api_delete"),
):
    await api_controller.remove(id=api_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除API id={api_id}",
        success=True,
    )
    return Success(msg="删除成功")


@router.post("/refresh", summary="刷新API列表")
async def refresh_api(
    current_user: User = require_operation("api_refresh"),
):
    _ = current_user
    await api_controller.refresh_api()
    return Success(msg="OK")
