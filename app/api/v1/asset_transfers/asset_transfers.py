from fastapi import APIRouter, Body, Query

from app.controllers.asset_transfer import asset_transfer_controller
from app.core.dependency import DependAuth
from app.models.admin import Dept
from app.models.business import Asset, Employee
from app.schemas.asset_transfers import AssetTransferCreate
from app.schemas.base import Success

router = APIRouter()


async def _enrich(items):
    asset_ids = {i.asset_id for i in items}
    emp_ids = {i.from_employee_id for i in items} | {i.to_employee_id for i in items} | {i.applicant_id for i in items}
    assets = {a.id: a for a in await Asset.filter(id__in=list(asset_ids))} if asset_ids else {}
    emps = {e.id: e for e in await Employee.filter(id__in=list(emp_ids))} if emp_ids else {}
    data = []
    for item in items:
        d = await item.to_dict()
        a = assets.get(item.asset_id)
        frm = emps.get(item.from_employee_id)
        to = emps.get(item.to_employee_id)
        ap = emps.get(item.applicant_id)
        d["asset_name"] = a.name if a else ""
        d["asset_no"] = a.asset_no if a else ""
        d["from_employee_name"] = frm.name if frm else ""
        d["to_employee_name"] = to.name if to else ""
        d["applicant_name"] = ap.name if ap else ""
        data.append(d)
    return data


@router.post("/apply", summary="发起调拨", dependencies=[DependAuth])
async def apply_transfer(req_in: AssetTransferCreate):
    obj = await asset_transfer_controller.apply(req_in)
    return Success(data=await obj.to_dict(), msg="调拨已提交")


@router.post("/approve", summary="审批调拨", dependencies=[DependAuth])
async def approve_transfer(
    transfer_id: int = Body(..., embed=True),
    approve: bool = Body(..., embed=True),
    comment: str = Body("", embed=True),
):
    obj = await asset_transfer_controller.approve(transfer_id, approve, comment)
    return Success(data=await obj.to_dict(), msg="审批完成")


@router.get("/list", summary="调拨单列表", dependencies=[DependAuth])
async def list_transfers(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: int = Query(0, description="0全部 1待主管 2待管理员 3通过 4驳回"),
    scope: str = Query("all", description="all / mine / pending"),
):
    total, items = await asset_transfer_controller.list_transfers(page, page_size, status, scope)
    return Success(data={"list": await _enrich(items), "total": total})


@router.get("/candidates", summary="调入人选（在职员工摘要）", dependencies=[DependAuth])
async def transfer_candidates():
    rows = await asset_transfer_controller.candidates()
    dept_ids = {r["dept_id"] for r in rows if r.get("dept_id")}
    depts = {d.id: d.name for d in await Dept.filter(id__in=list(dept_ids))} if dept_ids else {}
    for row in rows:
        row["dept_name"] = depts.get(row.get("dept_id")) or ""
    return Success(data=rows)
