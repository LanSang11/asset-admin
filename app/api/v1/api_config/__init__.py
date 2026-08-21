from fastapi import APIRouter

from .api_config import router as api_config_router

api_config_router_all = APIRouter()
api_config_router_all.include_router(api_config_router, tags=["API配置模块"])
