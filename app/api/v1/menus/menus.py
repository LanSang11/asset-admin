import logging

from fastapi import APIRouter, Query, Request

from app.controllers.menu import menu_controller
from app.core.dependency import require_operation
from app.models.admin import User
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.menus import *
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看菜单列表")
async def list_menu(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
):
    # 修复：一次查询全部菜单 + 内存组装树（原递归每层一次子查询 N+1；
    # 菜单树为树形结构，分页无意义，page/page_size 保留仅作接口兼容）
    all_menus = await menu_controller.model.all().order_by("order")

    async def build_tree(parent_id: int):
        result = []
        for m in all_menus:
            if m.parent_id == parent_id:
                d = await m.to_dict()
                d["children"] = await build_tree(m.id)
                result.append(d)
        return result

    res_menu = await build_tree(0)
    return SuccessExtra(data=res_menu, total=len(res_menu), page=page, page_size=page_size)


@router.get("/get", summary="查看菜单")
async def get_menu(
    menu_id: int = Query(..., description="菜单id"),
):
    result = await menu_controller.get(id=menu_id)
    return Success(data=result)


@router.post("/create", summary="创建菜单")
async def create_menu(
    menu_in: MenuCreate,
):
    await menu_controller.create(obj_in=menu_in)
    return Success(msg="创建成功")


@router.post("/update", summary="更新菜单")
async def update_menu(
    menu_in: MenuUpdate,
):
    await menu_controller.update(id=menu_in.id, obj_in=menu_in)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除菜单")
async def delete_menu(
    request: Request,
    id: int = Query(..., description="菜单id"),
    current_user: User = require_operation("menu_delete"),
):
    child_menu_count = await menu_controller.model.filter(parent_id=id).count()
    if child_menu_count > 0:
        return Fail(msg="无法删除含子菜单的菜单")
    await menu_controller.remove(id=id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除菜单 id={id}",
        success=True,
    )
    return Success(msg="删除成功")
