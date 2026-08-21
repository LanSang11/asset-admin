from fastapi import APIRouter, Query

from app.controllers.notification import notification_controller
from app.core.dependency import DependAuth
from app.schemas.base import Success

router = APIRouter()


@router.get("/list", summary="我的通知列表", dependencies=[DependAuth])
async def list_notification(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量（上限 100）"),
    unread_only: bool = Query(False, description="只看未读"),
):
    # 修复：分页参数与前端契约统一；type 推断便于铃铛过滤（ISO-A1/A6）
    total, items = await notification_controller.list_notifications(page, page_size, unread_only)
    data = [await notification_controller.to_client_dict(item) for item in items]
    return Success(data={"list": data, "total": total})


@router.get("/unread_count", summary="未读通知数", dependencies=[DependAuth])
async def unread_count():
    count = await notification_controller.unread_count()
    return Success(data={"count": count})


@router.post("/read", summary="标记已读", dependencies=[DependAuth])
async def mark_read(
    notification_id: int = Query(..., description="通知ID"),
):
    await notification_controller.mark_read(notification_id)
    return Success(msg="已读")


@router.post("/read_all", summary="全部已读", dependencies=[DependAuth])
async def mark_all_read():
    count = await notification_controller.mark_all_read()
    return Success(msg=f"已标记 {count} 条为已读")
