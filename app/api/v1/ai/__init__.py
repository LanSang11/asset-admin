from fastapi import APIRouter

from .ai import router as ai_router

ai_router_all = APIRouter()
ai_router_all.include_router(ai_router, tags=["AI助手模块"])
