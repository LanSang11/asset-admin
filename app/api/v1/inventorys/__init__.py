from fastapi import APIRouter

from .inventorys import router as inventory_router

inventory_router_all = APIRouter()
inventory_router_all.include_router(inventory_router, tags=["资产盘点模块"])
