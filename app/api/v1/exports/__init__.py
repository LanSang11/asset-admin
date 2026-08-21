from fastapi import APIRouter

from .exports import router as exports_router

exports_router_all = APIRouter()
exports_router_all.include_router(exports_router, tags=["数据导出模块"])
