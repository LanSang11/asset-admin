# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import List, Tuple

from fastapi.exceptions import HTTPException

from app.controllers.employee import employee_controller
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Employee, EmployeeAttachment
from app.settings.config import settings
from app.utils.identity import resolve_biz_role

MAX_BYTES = 5 * 1024 * 1024
ALLOWED_EXT = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAGIC = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8",),
    ".jpeg": (b"\xff\xd8",),
    ".docx": (b"PK",),
    ".xlsx": (b"PK",),
}


def upload_root() -> Path:
    root = Path(settings.BASE_DIR) / "uploads" / "employee"
    root.mkdir(parents=True, exist_ok=True)
    return root


class EmployeeAttachmentController:
    async def _actor(self) -> tuple[User, Employee | None, str]:
        user = await User.get(id=CTX_USER_ID.get())
        emp = await Employee.filter(user_id=user.id).first()
        role = await resolve_biz_role(user, emp)
        return user, emp, role

    async def _target(self, employee_id: int) -> tuple[User, Employee | None, str, Employee]:
        user, me, role = await self._actor()
        target = await Employee.get_or_none(id=employee_id)
        if not target:
            raise HTTPException(status_code=400, detail="员工不存在")
        if not await employee_controller.can_view_employee(target, role, me):
            raise HTTPException(status_code=403, detail="只能管理权限范围内的员工附件")
        return user, me, role, target

    def _validate_file(self, filename: str, data: bytes) -> tuple[str, str]:
        if not data:
            raise HTTPException(status_code=400, detail="文件为空")
        if len(data) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="附件不能超过 5MB")
        ext = Path(filename or "").suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        heads = MAGIC.get(ext)
        if heads and not any(data.startswith(h) for h in heads):
            raise HTTPException(status_code=400, detail="文件内容与扩展名不符")
        if ext == ".txt":
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(status_code=400, detail="文本附件须为 UTF-8") from exc
        stored = f"{uuid.uuid4().hex}{ext}"
        return stored, ALLOWED_EXT[ext]

    async def resolve_employee_id(self, employee_id: int | None) -> int:
        if employee_id:
            return employee_id
        _user, me, _role = await self._actor()
        if not me:
            raise HTTPException(status_code=400, detail="当前账号未绑定员工档案")
        return me.id

    async def upload(self, employee_id: int | None, filename: str, data: bytes) -> EmployeeAttachment:
        employee_id = await self.resolve_employee_id(employee_id)
        user, _me, _role, target = await self._target(employee_id)
        stored, mime = self._validate_file(filename, data)
        folder = upload_root() / str(target.id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / stored
        path.write_bytes(data)
        obj = await EmployeeAttachment.create(
            employee_id=target.id,
            original_name=(filename or stored)[:200],
            stored_name=stored,
            mime=mime,
            size=len(data),
            uploader_id=user.id,
        )
        return obj

    async def list_for(self, employee_id: int | None) -> List[EmployeeAttachment]:
        employee_id = await self.resolve_employee_id(employee_id)
        await self._target(employee_id)
        return await EmployeeAttachment.filter(employee_id=employee_id).order_by("-id")

    async def get_file(self, attach_id: int) -> Tuple[EmployeeAttachment, Path]:
        obj = await EmployeeAttachment.get_or_none(id=attach_id)
        if not obj:
            raise HTTPException(status_code=400, detail="附件不存在")
        await self._target(obj.employee_id)
        path = upload_root() / str(obj.employee_id) / obj.stored_name
        if not path.is_file():
            raise HTTPException(status_code=400, detail="附件文件缺失")
        return obj, path

    async def delete(self, attach_id: int) -> None:
        _user, me, role = await self._actor()
        obj = await EmployeeAttachment.get_or_none(id=attach_id)
        if not obj:
            raise HTTPException(status_code=400, detail="附件不存在")
        target = await Employee.get_or_none(id=obj.employee_id)
        if not target or not await employee_controller.can_view_employee(target, role, me):
            raise HTTPException(status_code=403, detail="无权删除该附件")
        if role != "admin" and not (me and me.id == obj.employee_id):
            raise HTTPException(status_code=403, detail="只能删除自己的附件")
        path = upload_root() / str(obj.employee_id) / obj.stored_name
        try:
            if path.is_file():
                os.remove(path)
        except OSError:
            pass
        await obj.delete()


employee_attachment_controller = EmployeeAttachmentController()
