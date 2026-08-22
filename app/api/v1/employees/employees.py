from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.controllers.employee import employee_controller
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth, DependPermission, require_operation
from app.models.admin import User
from app.models.business import Employee
from app.schemas.base import Success
from app.schemas.employees import *
from app.services.security_event_service import log_security_event
from app.utils.identity import resolve_biz_role
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


@router.get("/list", summary="查看员工列表", dependencies=[DependAuth])
async def list_employee(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量（上限 100）"),
    keyword: str = Query("", description="搜索关键词（姓名/工号/手机）"),
    dept_id: int = Query(0, description="部门ID"),
    status: int = Query(-1, description="状态：-1全部 1在职 0离职"),
    sort_by: Literal["created_at", "emp_no", "name", "hire_date"] = Query("created_at"),
    sort_order: Literal["desc", "asc"] = Query("desc"),
):
    # 修复：分页参数与前端 CrudTable 契约统一
    # ISO-B2：行级缩圈 + 字段脱敏
    total, items = await employee_controller.list_employees(
        page, page_size, keyword, dept_id, status, sort_by, sort_order
    )
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    me = await Employee.filter(user_id=user_id).first()
    role = await resolve_biz_role(user, me)
    data = [await employee_controller.serialize_for_viewer(item, role, me) for item in items]
    return Success(data={"list": data, "total": total})


@router.get("/get", summary="查看员工", dependencies=[DependAuth])
async def get_employee(
    id: int = Query(..., description="员工ID"),
):
    obj = await employee_controller.get(id=id)
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    me = await Employee.filter(user_id=user_id).first()
    role = await resolve_biz_role(user, me)
    if not await employee_controller.can_view_employee(obj, role, me):
        raise HTTPException(status_code=403, detail="无权查看该员工")
    return Success(data=await employee_controller.serialize_for_viewer(obj, role, me))


@router.post("/create", summary="创建员工", dependencies=[DependPermission])
async def create_employee(
    employee_in: EmployeeCreate,
):
    obj = await employee_controller.create_employee(employee_in)
    return Success(data=await obj.to_dict(), msg="创建成功")


@router.post("/update", summary="更新员工", dependencies=[DependPermission])
async def update_employee(
    employee_in: EmployeeUpdate,
):
    obj = await employee_controller.update_employee(employee_in)
    return Success(data=await obj.to_dict(), msg="更新成功")


@router.delete("/delete", summary="删除员工", dependencies=[DependPermission])
async def delete_employee(
    request: Request,
    employee_id: int = Query(..., description="员工ID"),
    current_user: User = require_operation("employee_delete"),
):
    # 修复：删除前校验名下资产/申请历史（防止悬空引用）
    await employee_controller.delete_employee(employee_id)
    await log_security_event(
        event_type="high_risk_delete",
        username=current_user.username,
        user_id=current_user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"删除员工 id={employee_id}",
        success=True,
    )
    return Success(msg="删除成功")
