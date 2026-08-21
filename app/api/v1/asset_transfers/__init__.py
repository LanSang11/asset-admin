from fastapi import APIRouter

from .asset_transfers import router as transfers_router

asset_transfers_router_all = APIRouter()
asset_transfers_router_all.include_router(transfers_router, tags=["资产调拨模块"])
