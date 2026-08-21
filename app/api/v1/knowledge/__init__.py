from fastapi import APIRouter

from .knowledge import router as knowledge_router

knowledge_router_all = APIRouter()
knowledge_router_all.include_router(knowledge_router, tags=["知识库"])
