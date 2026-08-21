from fastapi import APIRouter

from .employees import router as employees_router

employees_router_all = APIRouter()
employees_router_all.include_router(employees_router, tags=["员工模块"])
