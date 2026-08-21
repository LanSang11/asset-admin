from fastapi import APIRouter

from .dashboard import router as dashboard_router

dashboard_router_all = APIRouter()
dashboard_router_all.include_router(dashboard_router, tags=["统计看板模块"])
