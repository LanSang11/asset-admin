from fastapi import APIRouter

from .base import router
from .blacklist import router as blacklist_router

base_router = APIRouter()
base_router.include_router(router, tags=["基础模块"])
base_router.include_router(blacklist_router, tags=["基础模块"])

__all__ = ["base_router"]
