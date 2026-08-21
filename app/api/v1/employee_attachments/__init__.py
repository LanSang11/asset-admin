from fastapi import APIRouter

from .employee_attachments import router as attachments_router

employee_attachments_router_all = APIRouter()
employee_attachments_router_all.include_router(attachments_router, tags=["员工附件"])
