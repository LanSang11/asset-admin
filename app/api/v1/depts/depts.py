from fastapi import APIRouter, Query, Request

from app.controllers.dept import dept_controller
from app.core.dependency import require_operation
from app.models.admin import User
from app.schemas import Success
from app.schemas.depts import *
from app.services.security_event_service import log_security_event
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


@router.get("/list", summary="查看部门列表")
async def list_dept(
    name: str = Query(None, description="部门名称"),
):
    dept_tree = await dept_controller.get_dept_tree(name)
    return Success(data=dept_tree)


@router.get("/get", summary="查看部门")
async def get_dept(
    id: int = Query(..., description="部门ID"),
):
    dept_obj = await dept_controller.get(id=id)
    data = await dept_obj.to_dict()
    return Success(data=data)


@router.post("/create", summary="创建部门")
async def create_dept(
    dept_in: DeptCreate,
):
    await dept_controller.create_dept(obj_in=dept_in)
    return Success(msg="创建成功")


@router.post("/update", summary="更新部门")
async def update_dept(
    dept_in: DeptUpdate,
):
    await dept_controller.update_dept(obj_in=dept_in)
    return Success(msg="更新成功")


@router.delete("/delete", summary="删除部门")
async def delete_dept(
    request: Request,
    dept_id: int = Query(..., description="部门ID"),
    current_user: User = require_operation("dept_delete"),
):
    await dept_controller.delete_dept(dept_id=dept_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除部门 id={dept_id}",
        success=True,
    )
    return Success(msg="删除成功")
