from fastapi import APIRouter, Body, Query

from app.controllers.asset_repair import asset_repair_controller
from app.core.dependency import DependAuth
from app.models.business import Asset, Employee
from app.schemas.asset_repairs import AssetRepairComplete, AssetRepairCreate, AssetRepairRegister
from app.schemas.base import Success

router = APIRouter()


async def _enrich(items):
    asset_ids = {i.asset_id for i in items}
    emp_ids = {i.employee_id for i in items}
    assets = {a.id: a for a in await Asset.filter(id__in=list(asset_ids))} if asset_ids else {}
    emps = {e.id: e for e in await Employee.filter(id__in=list(emp_ids))} if emp_ids else {}
    data = []
    for item in items:
        d = await item.to_dict()
        a = assets.get(item.asset_id)
        e = emps.get(item.employee_id)
        d["asset_name"] = a.name if a else ""
        d["asset_no"] = a.asset_no if a else ""
        d["employee_name"] = e.name if e else ""
        data.append(d)
    return data


@router.post("/apply", summary="发起报修", dependencies=[DependAuth])
async def apply_repair(req_in: AssetRepairCreate):
    obj = await asset_repair_controller.apply(req_in)
    return Success(data=await obj.to_dict(), msg="报修已提交")


@router.post("/approve", summary="审批报修", dependencies=[DependAuth])
async def approve_repair(
    repair_id: int = Body(..., embed=True),
    approve: bool = Body(..., embed=True),
    comment: str = Body("", embed=True),
):
    obj = await asset_repair_controller.approve(repair_id, approve, comment)
    return Success(data=await obj.to_dict(), msg="审批完成")


@router.post("/complete", summary="登记修好", dependencies=[DependAuth])
async def complete_repair(req_in: AssetRepairComplete):
    obj = await asset_repair_controller.complete(req_in)
    return Success(data=await obj.to_dict(), msg="已登记修好")


@router.post("/register", summary="管理员登记送修", dependencies=[DependAuth])
async def register_repair(req_in: AssetRepairRegister):
    obj = await asset_repair_controller.register(req_in)
    return Success(data=await obj.to_dict(), msg="已登记送修")


@router.get("/list", summary="报修单列表", dependencies=[DependAuth])
async def list_repairs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: int = Query(0, description="0全部 1待主管 2待管理员 3维修中 4已修复 5驳回"),
    scope: str = Query("all", description="all / mine / pending / repairing"),
):
    total, items = await asset_repair_controller.list_repairs(page, page_size, status, scope)
    return Success(data={"list": await _enrich(items), "total": total})
