from fastapi import APIRouter, Query

from app.controllers.inventory import inventory_controller
from app.core.dependency import DependAuth
from app.schemas.base import Success
from app.schemas.inventory import InventoryClose, InventoryCount, InventoryStart

router = APIRouter()


@router.post("/start", summary="发起盘点", dependencies=[DependAuth])
async def start_inventory(req_in: InventoryStart):
    obj = await inventory_controller.start(req_in)
    data = await inventory_controller.get(obj.id)
    return Success(data=data, msg="盘点已开始")


@router.get("/list", summary="盘点任务列表", dependencies=[DependAuth])
async def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: int = Query(0, description="0全部 1进行中 2已结束"),
):
    total, items = await inventory_controller.list_sessions(page, page_size, status)
    data = [await i.to_dict() for i in items]
    return Success(data={"list": data, "total": total})


@router.get("/get", summary="盘点任务详情与汇总", dependencies=[DependAuth])
async def get_inventory(id: int = Query(..., ge=1)):
    data = await inventory_controller.get(id)
    return Success(data=data)


@router.get("/lines", summary="盘点明细", dependencies=[DependAuth])
async def list_inventory_lines(
    session_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    result: str = Query("", description="空/pending/found/missing/mismatch"),
):
    total, items = await inventory_controller.list_lines(session_id, page, page_size, result)
    data = [await i.to_dict() for i in items]
    return Success(data={"list": data, "total": total})


@router.post("/count", summary="登记实盘结果", dependencies=[DependAuth])
async def count_inventory(req_in: InventoryCount):
    obj = await inventory_controller.count(req_in)
    return Success(data=await obj.to_dict(), msg="已记录")


@router.post("/close", summary="结束盘点", dependencies=[DependAuth])
async def close_inventory(req_in: InventoryClose):
    data = await inventory_controller.close(req_in)
    return Success(data=data, msg="盘点已结束。盘盈请走资产登记，盘亏不会自动报废")
