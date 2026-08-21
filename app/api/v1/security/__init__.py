from fastapi import APIRouter

from .security import router

security_router = APIRouter()
security_router.include_router(router, tags=["安全中心"])

__all__ = ["security_router"]
