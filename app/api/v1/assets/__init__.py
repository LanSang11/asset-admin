from fastapi import APIRouter

from .assets import router as assets_router

assets_router_all = APIRouter()
assets_router_all.include_router(assets_router, tags=["资产模块"])
