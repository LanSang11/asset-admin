from fastapi import APIRouter, Body, Query

from app.controllers.asset_use import asset_use_controller
from app.core.dependency import DependAuth
from app.models.business import AssetUseHistory
from app.schemas.base import Success
from app.schemas.asset_uses import *

router = APIRouter()


@router.post("/apply", summary="发起领用/归还申请", dependencies=[DependAuth])
async def apply_asset_use(
    req_in: AssetUseCreate,
):
    obj = await asset_use_controller.create_application(req_in)
    return Success(data=await obj.to_dict(), msg="申请已提交")


@router.post("/approve", summary="审批申请（主管/管理员）", dependencies=[DependAuth])
async def approve_asset_use(
    application_id: int = Body(..., embed=True, description="申请ID"),
    approve: bool = Body(..., embed=True, description="是否通过"),
    comment: str = Body("", embed=True, description="审批意见"),
):
    obj = await asset_use_controller.approve(application_id, approve, comment)
    return Success(data=await obj.to_dict(), msg="审批完成")


@router.get("/list", summary="申请列表", dependencies=[DependAuth])
async def list_asset_use(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量（上限 100）"),
    status: int = Query(0, description="状态：0全部 1待主管 2待管理员 3通过 4驳回"),
    use_type: int = Query(0, description="类型：0全部 1领用 2归还"),
    scope: str = Query("all", description="范围：all全部 mine我的 pending待我审批"),
):
    # 修复：分页参数与前端 CrudTable 契约统一
    total, items = await asset_use_controller.list_applications(page, page_size, status, use_type, scope)
    # 修复：批量预取资产/员工（原每行 2 次查询 N+1）
    from app.models.business import Asset, Employee

    asset_ids = {item.asset_id for item in items}
    emp_ids = {item.employee_id for item in items}
    assets = {a.id: a for a in await Asset.filter(id__in=list(asset_ids))} if asset_ids else {}
    emps = {e.id: e for e in await Employee.filter(id__in=list(emp_ids))} if emp_ids else {}
    data = []
    for item in items:
        d = await item.to_dict()
        asset = assets.get(item.asset_id)
        emp = emps.get(item.employee_id)
        d["asset_name"] = asset.name if asset else ""
        d["asset_no"] = asset.asset_no if asset else ""
        d["employee_name"] = emp.name if emp else ""
        data.append(d)
    return Success(data={"list": data, "total": total})


@router.get("/history", summary="资产使用历史追溯", dependencies=[DependAuth])
async def asset_history(
    asset_id: int = Query(..., description="资产ID"),
):
    items = await asset_use_controller.get_history(asset_id)
    # 修复：批量预取员工（原每行 1 次查询 N+1）
    from app.models.business import Employee

    emp_ids = {item.employee_id for item in items}
    emps = {e.id: e for e in await Employee.filter(id__in=list(emp_ids))} if emp_ids else {}
    data = []
    for item in items:
        d = await item.to_dict()
        emp = emps.get(item.employee_id)
        d["employee_name"] = emp.name if emp else ""
        d["use_type_text"] = "领用" if item.use_type == 1 else "归还"
        data.append(d)
    return Success(data=data)
