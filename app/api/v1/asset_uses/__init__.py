from fastapi import APIRouter

from .asset_uses import router as asset_uses_router

asset_uses_router_all = APIRouter()
asset_uses_router_all.include_router(asset_uses_router, tags=["领用归还模块"])
