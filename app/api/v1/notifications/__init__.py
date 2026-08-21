from fastapi import APIRouter

from .notifications import router as notifications_router

notifications_router_all = APIRouter()
notifications_router_all.include_router(notifications_router, tags=["通知模块"])
