from typing import Any, Dict, List, Tuple

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Employee, Notification
from app.schemas.notifications import NotificationUpdate
from app.services.notification_service import (
    TYPE_APPROVAL_TASK,
    infer_type_from_legacy,
)
from app.utils.identity import resolve_biz_role


class NotificationController(CRUDBase[Notification, None, NotificationUpdate]):
    def __init__(self):
        super().__init__(model=Notification)

    async def _viewer_role(self) -> str:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await Employee.filter(user_id=user_id).first()
        return await resolve_biz_role(user, emp)

    def _is_approval_task(self, obj: Notification) -> bool:
        ntype = (obj.type or "").strip()
        if ntype == TYPE_APPROVAL_TASK:
            return True
        if ntype:
            return False
        return infer_type_from_legacy(obj.title or "", obj.content or "") == TYPE_APPROVAL_TASK

    async def list_notifications(self, page: int, page_size: int, unread_only: bool = False) -> Tuple[int, List[Notification]]:
        """列表按 user_id 隔离；普通员工额外隐藏 approval_task（ISO-A6 服务端闸）。"""
        user_id = CTX_USER_ID.get()
        role = await self._viewer_role()
        q = Q(user_id=user_id)
        if unread_only:
            q &= Q(is_read=False)
        # 先多取再过滤（历史空 type 需文案推断；数据量小可接受）
        # 用较大窗口再分页，避免 type 过滤后空洞
        fetch_size = max(page * page_size * 3, 50)
        total_raw, items_raw = await self.list(1, fetch_size, q, ["-created_at"])
        if role == "employee":
            items_raw = [x for x in items_raw if not self._is_approval_task(x)]
            # total 近似：再扫全部用户通知做准确计数（通知量通常不大）
            all_mine = await self.model.filter(user_id=user_id).all()
            total = len([x for x in all_mine if not self._is_approval_task(x)])
            if unread_only:
                total = len([x for x in all_mine if not self._is_approval_task(x) and not x.is_read])
        else:
            total = total_raw
        start = (page - 1) * page_size
        end = start + page_size
        return total, items_raw[start:end]

    async def to_client_dict(self, obj: Notification) -> Dict[str, Any]:
        """补全 type（历史空 type 按文案推断），供前端铃铛过滤。"""
        d = await obj.to_dict()
        ntype = (d.get("type") or "").strip()
        if not ntype:
            ntype = infer_type_from_legacy(d.get("title") or "", d.get("content") or "")
            d["type"] = ntype
        return d

    async def mark_read(self, notification_id: int) -> Notification:
        user_id = CTX_USER_ID.get()
        obj = await self.get(notification_id)
        if obj.user_id != user_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="无权操作他人通知")
        obj.is_read = True
        await obj.save()
        return obj

    async def mark_all_read(self) -> int:
        user_id = CTX_USER_ID.get()
        objs = await self.model.filter(user_id=user_id, is_read=False).all()
        count = len(objs)
        for obj in objs:
            obj.is_read = True
            await obj.save(update_fields=["is_read"])
        return count

    async def unread_count(self) -> int:
        user_id = CTX_USER_ID.get()
        role = await self._viewer_role()
        objs = await self.model.filter(user_id=user_id, is_read=False).all()
        if role == "employee":
            objs = [x for x in objs if not self._is_approval_task(x)]
        return len(objs)


notification_controller = NotificationController()
