from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from tortoise.expressions import Q

from app.core.dependency import DependSuperUser
from app.models.admin import AuditLog, User
from app.schemas import SuccessExtra

router = APIRouter()


@router.get("/list", summary="查看操作日志（仅超管）")
async def get_audit_log_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=500, description="每页数量（上限 500）"),
    username: str = Query("", description="操作人名称"),
    module: str = Query("", description="功能模块"),
    method: str = Query("", description="请求方法"),
    summary: str = Query("", description="接口描述"),
    path: str = Query("", description="请求路径"),
    status: int = Query(None, description="状态码"),
    ip: str = Query("", description="客户端IP"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user: User = DependSuperUser,
):
    # DependSuperUser 硬锁；保留参数避免未使用告警
    _ = current_user
    q = Q()
    if username:
        q &= Q(username__icontains=username)
    if module:
        q &= Q(module__icontains=module)
    if method:
        q &= Q(method__icontains=method)
    if summary:
        q &= Q(summary__icontains=summary)
    if path:
        q &= Q(path__icontains=path)
    if ip:
        q &= Q(ip__icontains=ip)
    if status:
        q &= Q(status=status)
    if start_time and end_time:
        q &= Q(created_at__range=[start_time, end_time])
    elif start_time:
        q &= Q(created_at__gte=start_time)
    elif end_time:
        q &= Q(created_at__lte=end_time)

    audit_log_objs = await AuditLog.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    total = await AuditLog.filter(q).count()
    data = [await audit_log.to_dict() for audit_log in audit_log_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)
