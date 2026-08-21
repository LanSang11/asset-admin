# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, Employee, InventoryLine, InventorySession
from app.schemas.inventory import InventoryClose, InventoryCount, InventoryStart
from app.utils.identity import resolve_biz_role

ST_OPEN = 1
ST_CLOSED = 2
SKIP_STATUS = {4}  # 报废不进盘点
OK_RESULTS = {"found", "missing", "mismatch"}


class InventoryController:
    async def _ctx(self):
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await Employee.filter(user_id=user_id).first()
        role = await resolve_biz_role(user, emp)
        return user, emp, role

    def _line_q(self, role: str, emp: Optional[Employee]) -> Q:
        if role == "admin":
            return Q()
        if role == "manager" and emp and emp.dept_id:
            return Q(book_dept_id=emp.dept_id)
        if emp:
            return Q(book_owner_emp_id=emp.id)
        return Q(id=-1)

    def _session_q(self, role: str, emp: Optional[Employee], user_id: int) -> Q:
        if role == "admin":
            return Q()
        if role == "manager" and emp and emp.dept_id:
            return Q(scope="dept", dept_id=emp.dept_id) | Q(created_by=user_id)
        return Q(created_by=user_id)

    async def start(self, req: InventoryStart) -> InventorySession:
        user, emp, role = await self._ctx()
        scope = (req.scope or "all").strip().lower()
        if scope not in ("all", "dept"):
            raise HTTPException(status_code=400, detail="范围只能是全部或按部门")
        dept_id = req.dept_id
        if role == "employee":
            raise HTTPException(status_code=403, detail="员工不能发起盘点，请联系主管或管理员")
        if role == "manager":
            if not emp or not emp.dept_id:
                raise HTTPException(status_code=400, detail="主管未绑定部门，不能发起盘点")
            scope = "dept"
            dept_id = emp.dept_id
        if scope == "dept" and not dept_id:
            raise HTTPException(status_code=400, detail="按部门盘点需要选择部门")
        if scope == "all":
            dept_id = None

        open_q = Q(status=ST_OPEN)
        if scope == "dept":
            open_q &= Q(scope="dept", dept_id=dept_id)
        else:
            open_q &= Q(scope="all")
        if await InventorySession.filter(open_q).first():
            raise HTTPException(status_code=400, detail="已有进行中的同类盘点，请先结束再开新的")

        qs = Asset.filter(~Q(status__in=list(SKIP_STATUS)))
        if scope == "dept":
            emp_ids = list(await Employee.filter(dept_id=dept_id).values_list("id", flat=True))
            # 部门盘只收该部门员工名下；无主闲置留给全司盘，避免跨部门误盘
            qs = qs.filter(Q(owner_emp_id__in=emp_ids) if emp_ids else Q(id=-1))
        rows = await qs.all()
        if not rows:
            raise HTTPException(status_code=400, detail="这个范围内没有可盘点的资产（报废不纳入）")

        owners = {e.id: e for e in await Employee.filter(id__in=list({a.owner_emp_id for a in rows if a.owner_emp_id}))}

        async with in_transaction():
            session = await InventorySession.create(
                title=req.title.strip(),
                scope=scope,
                dept_id=dept_id,
                status=ST_OPEN,
                created_by=user.id,
                note=(req.note or "").strip(),
            )
            payload = []
            for a in rows:
                owner = owners.get(a.owner_emp_id) if a.owner_emp_id else None
                payload.append(
                    InventoryLine(
                        session_id=session.id,
                        asset_id=a.id,
                        asset_no=a.asset_no,
                        asset_name=a.name,
                        book_status=a.status,
                        book_owner_emp_id=a.owner_emp_id,
                        book_owner_name=owner.name if owner else "",
                        book_dept_id=owner.dept_id if owner else None,
                    )
                )
            await InventoryLine.bulk_create(payload)
        return session

    async def list_sessions(self, page: int, page_size: int, status: int = 0) -> Tuple[int, List[InventorySession]]:
        user, emp, role = await self._ctx()
        q = self._session_q(role, emp, user.id)
        if role == "employee" and emp:
            sids = await InventoryLine.filter(book_owner_emp_id=emp.id).distinct().values_list("session_id", flat=True)
            q = Q(id__in=list(sids) or [-1])
        if status in (ST_OPEN, ST_CLOSED):
            q &= Q(status=status)
        qs = InventorySession.filter(q)
        total = await qs.count()
        items = await qs.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        return total, items

    async def get(self, session_id: int) -> dict:
        user, emp, role = await self._ctx()
        session = await InventorySession.get_or_none(id=session_id)
        if not session:
            raise HTTPException(status_code=400, detail="盘点任务不存在")
        await self._assert_can_see_session(session, role, emp, user.id)
        line_q = Q(session_id=session.id) & self._line_q(role, emp)
        total = await InventoryLine.filter(line_q).count()
        pending = await InventoryLine.filter(line_q, result="").count()
        found = await InventoryLine.filter(line_q, result="found").count()
        missing = await InventoryLine.filter(line_q, result="missing").count()
        mismatch = await InventoryLine.filter(line_q, result="mismatch").count()
        data = await session.to_dict()
        data["summary"] = {
            "total": total,
            "pending": pending,
            "found": found,
            "missing": missing,
            "mismatch": mismatch,
        }
        return data

    async def _assert_can_see_session(self, session: InventorySession, role: str, emp, user_id: int) -> None:
        if role == "admin":
            return
        if role == "manager" and emp and emp.dept_id:
            if session.scope == "dept" and session.dept_id == emp.dept_id:
                return
            if session.created_by == user_id:
                return
        if emp:
            hit = await InventoryLine.filter(session_id=session.id, book_owner_emp_id=emp.id).first()
            if hit:
                return
        raise HTTPException(status_code=403, detail="无权查看该盘点")

    async def list_lines(
        self, session_id: int, page: int, page_size: int, result: str = ""
    ) -> Tuple[int, List[InventoryLine]]:
        user, emp, role = await self._ctx()
        session = await InventorySession.get_or_none(id=session_id)
        if not session:
            raise HTTPException(status_code=400, detail="盘点任务不存在")
        await self._assert_can_see_session(session, role, emp, user.id)
        q = Q(session_id=session.id) & self._line_q(role, emp)
        if result in OK_RESULTS or result == "pending":
            q &= Q(result="") if result == "pending" else Q(result=result)
        qs = InventoryLine.filter(q)
        total = await qs.count()
        items = await qs.order_by("asset_no").offset((page - 1) * page_size).limit(page_size)
        return total, items

    async def count(self, req: InventoryCount) -> InventoryLine:
        user, emp, role = await self._ctx()
        line = await InventoryLine.get_or_none(id=req.line_id)
        if not line:
            raise HTTPException(status_code=400, detail="盘点行不存在")
        session = await InventorySession.get_or_none(id=line.session_id)
        if not session or session.status != ST_OPEN:
            raise HTTPException(status_code=400, detail="盘点已结束，不能再改结果")
        await self._assert_can_see_session(session, role, emp, user.id)
        if role != "admin":
            vis = self._line_q(role, emp)
            ok = await InventoryLine.filter(Q(id=line.id) & vis).first()
            if not ok:
                raise HTTPException(status_code=403, detail="只能盘点你权限内的资产")
        result = (req.result or "").strip().lower()
        if result not in OK_RESULTS:
            raise HTTPException(status_code=400, detail="结果只能是相符、盘亏或不符")
        line.result = result
        line.counted_status = req.counted_status
        line.note = (req.note or "").strip()
        line.counted_by = user.id
        line.counted_at = datetime.now()
        await line.save()
        return line

    async def close(self, req: InventoryClose) -> dict:
        user, emp, role = await self._ctx()
        if role == "employee":
            raise HTTPException(status_code=403, detail="员工不能结束盘点")
        session = await InventorySession.get_or_none(id=req.session_id)
        if not session:
            raise HTTPException(status_code=400, detail="盘点任务不存在")
        if session.status != ST_OPEN:
            raise HTTPException(status_code=400, detail="盘点已经结束")
        await self._assert_can_see_session(session, role, emp, user.id)
        if role == "manager" and session.created_by != user.id:
            if not (emp and session.scope == "dept" and session.dept_id == emp.dept_id):
                raise HTTPException(status_code=403, detail="只能结束本部门盘点")
        session.status = ST_CLOSED
        session.closed_by = user.id
        session.closed_at = datetime.now()
        if req.note:
            session.note = req.note.strip()
        await session.save()
        return await self.get(session.id)


inventory_controller = InventoryController()
