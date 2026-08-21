from fastapi import APIRouter

from .asset_repairs import router as repairs_router

asset_repairs_router_all = APIRouter()
asset_repairs_router_all.include_router(repairs_router, tags=["资产报修模块"])
