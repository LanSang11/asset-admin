# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, AssetRepair, AssetTransfer, AssetUse, AssetUseHistory, Employee
from app.schemas.asset_transfers import AssetTransferCreate
from app.services.notification_service import (
    list_superuser_ids,
    notify_applicant,
    notify_approver,
    notify_approvers,
    notify_user,
    TYPE_APPLICANT_PROGRESS,
)
from app.utils.identity import resolve_biz_role

ST_WAIT_MGR = 1
ST_WAIT_ADMIN = 2
ST_APPROVED = 3
ST_REJECTED = 4

ASSET_IN_USE = 1
USE_TYPE_TRANSFER = 3


class AssetTransferController:
    async def _employee(self, user_id: int) -> Employee:
        emp = await Employee.filter(user_id=user_id).first()
        if not emp:
            raise HTTPException(status_code=400, detail="当前账号未绑定员工档案，请联系管理员")
        if not emp.status:
            raise HTTPException(status_code=400, detail="离职员工不能发起调拨")
        return emp

    async def _manager_of(self, emp: Employee):
        if not emp.dept_id:
            return None
        return await Employee.filter(
            dept_id=emp.dept_id, is_manager=True, status=True, user_id__not_isnull=True
        ).first()

    async def _assert_no_conflict(self, asset_id: int) -> None:
        if await AssetTransfer.filter(asset_id=asset_id, status__in=[ST_WAIT_MGR, ST_WAIT_ADMIN]).first():
            raise HTTPException(status_code=400, detail="该资产已有待审批的调拨单")
        if await AssetUse.filter(asset_id=asset_id, status__in=[1, 2]).first():
            raise HTTPException(status_code=400, detail="该资产有待审批的领用或归还，不能调拨")
        if await AssetRepair.filter(asset_id=asset_id, status__in=[1, 2, 3]).first():
            raise HTTPException(status_code=400, detail="该资产正在报修或维修中，不能调拨")

    async def apply(self, req: AssetTransferCreate) -> AssetTransfer:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await self._employee(user_id)
        asset = await Asset.get_or_none(id=req.asset_id)
        if not asset:
            raise HTTPException(status_code=400, detail="资产不存在")
        if asset.status != ASSET_IN_USE or not asset.owner_emp_id:
            raise HTTPException(status_code=400, detail="只能调拨「在用」且已有领用人的资产")
        to_emp = await Employee.get_or_none(id=req.to_employee_id)
        if not to_emp or not to_emp.status:
            raise HTTPException(status_code=400, detail="调入员工不存在或已离职")
        if to_emp.id == asset.owner_emp_id:
            raise HTTPException(status_code=400, detail="不能调拨给当前领用人")
        role = await resolve_biz_role(user, emp)
        if role != "admin" and asset.owner_emp_id != emp.id:
            raise HTTPException(status_code=403, detail="只能申请调拨自己名下的资产")
        await self._assert_no_conflict(asset.id)

        from_emp = await Employee.get_or_none(id=asset.owner_emp_id)
        if not from_emp:
            raise HTTPException(status_code=400, detail="当前领用人档案不存在")

        async with in_transaction():
            obj = await AssetTransfer.create(
                asset_id=asset.id,
                from_employee_id=from_emp.id,
                to_employee_id=to_emp.id,
                applicant_id=emp.id,
                reason=req.reason.strip(),
                status=ST_WAIT_MGR,
            )
            manager = await self._manager_of(from_emp)
            if manager and manager.user_id:
                await notify_approver(
                    manager.user_id,
                    applicant_name=emp.name,
                    action="调拨",
                    asset_name=asset.name,
                    stage="manager",
                    route_kind="transfer",
                )
            else:
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=emp.name,
                    action="调拨",
                    asset_name=asset.name,
                    stage="admin",
                    route_kind="transfer",
                )
        return obj

    async def approve(self, transfer_id: int, approve: bool, comment: str) -> AssetTransfer:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        obj = await AssetTransfer.get_or_none(id=transfer_id)
        if not obj:
            raise HTTPException(status_code=400, detail="调拨单不存在")
        asset = await Asset.get(id=obj.asset_id)
        from_emp = await Employee.get(id=obj.from_employee_id)
        to_emp = await Employee.get(id=obj.to_employee_id)
        applicant = await Employee.get(id=obj.applicant_id)
        if obj.status in (ST_APPROVED, ST_REJECTED):
            raise HTTPException(status_code=400, detail="该调拨单已处理，不能重复审批")

        if obj.status == ST_WAIT_MGR:
            if not user.is_superuser:
                manager = await self._manager_of(from_emp)
                if not manager or manager.user_id != user.id:
                    raise HTTPException(status_code=403, detail="只有调出人本部门主管才能审批该调拨")
            if user.is_superuser and approve:
                async with in_transaction():
                    now = datetime.now()
                    obj.manager_approver_id = user.id
                    obj.manager_comment = comment or "超管代审（一级）"
                    obj.manager_time = now
                    obj.admin_approver_id = user.id
                    obj.admin_comment = comment or "超管终审通过"
                    obj.admin_time = now
                    await self._complete(obj, asset, from_emp, to_emp, applicant, user.id)
                return obj
            async with in_transaction():
                obj.manager_approver_id = user.id
                obj.manager_comment = comment or ""
                obj.manager_time = datetime.now()
                if not approve:
                    obj.status = ST_REJECTED
                    await obj.save()
                    await notify_applicant(
                        applicant.user_id,
                        action="调拨",
                        asset_name=asset.name,
                        msg="部门主管已驳回",
                        route_kind="transfer",
                    )
                    return obj
                obj.status = ST_WAIT_ADMIN
                await obj.save()
                await notify_applicant(
                    applicant.user_id,
                    action="调拨",
                    asset_name=asset.name,
                    msg="部门主管已通过，等待管理员审批",
                    route_kind="transfer",
                )
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=applicant.name,
                    action="调拨",
                    asset_name=asset.name,
                    stage="admin",
                    route_kind="transfer",
                )
                return obj

        if obj.status == ST_WAIT_ADMIN:
            if not user.is_superuser:
                raise HTTPException(status_code=403, detail="只有管理员才能进行调拨终审")
            async with in_transaction():
                obj.admin_approver_id = user.id
                obj.admin_comment = comment or ""
                obj.admin_time = datetime.now()
                if not approve:
                    obj.status = ST_REJECTED
                    await obj.save()
                    await notify_applicant(
                        applicant.user_id,
                        action="调拨",
                        asset_name=asset.name,
                        msg="管理员已驳回",
                        route_kind="transfer",
                    )
                    return obj
                await self._complete(obj, asset, from_emp, to_emp, applicant, user.id)
                return obj
        raise HTTPException(status_code=400, detail="未知调拨状态")

    async def _complete(
        self,
        obj: AssetTransfer,
        asset: Asset,
        from_emp: Employee,
        to_emp: Employee,
        applicant: Employee,
        operator_id: int,
    ) -> None:
        fresh = await Asset.get(id=asset.id)
        if fresh.status != ASSET_IN_USE or fresh.owner_emp_id != from_emp.id:
            raise HTTPException(status_code=400, detail="审批期间资产领用人或状态已变化，无法调拨")
        if not to_emp.status:
            raise HTTPException(status_code=400, detail="调入员工已离职，无法调拨")
        obj.status = ST_APPROVED
        asset.owner_emp_id = to_emp.id
        await asset.save()
        await obj.save()
        await AssetUseHistory.create(
            asset_id=asset.id,
            employee_id=to_emp.id,
            use_type=USE_TYPE_TRANSFER,
            operator_id=operator_id,
            remark=f"从{from_emp.name}调拨至{to_emp.name}",
        )
        await notify_applicant(
            applicant.user_id,
            action="调拨",
            asset_name=asset.name,
            msg=f"已调拨给{to_emp.name}，资产仍为在用",
            route_kind="transfer",
        )
        if to_emp.user_id and to_emp.user_id != applicant.user_id:
            await notify_user(
                to_emp.user_id,
                title="资产已调入",
                content=f"资产「{asset.name}」已调入你名下",
                ntype=TYPE_APPLICANT_PROGRESS,
                route_kind="transfer",
            )

    async def list_transfers(
        self, page: int, page_size: int, status: int = 0, scope: str = "all"
    ) -> Tuple[int, List[AssetTransfer]]:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await Employee.filter(user_id=user_id).first()
        q = Q()
        if status:
            q &= Q(status=status)
        if scope == "mine":
            if not emp:
                return 0, []
            q &= Q(applicant_id=emp.id) | Q(from_employee_id=emp.id) | Q(to_employee_id=emp.id)
        elif scope == "pending":
            if user.is_superuser:
                q &= Q(status__in=[ST_WAIT_MGR, ST_WAIT_ADMIN])
            else:
                if not emp or not emp.is_manager or not emp.dept_id:
                    return 0, []
                emp_ids = await Employee.filter(dept_id=emp.dept_id).values_list("id", flat=True)
                q = Q(status=ST_WAIT_MGR, from_employee_id__in=list(emp_ids))
        else:
            if not user.is_superuser:
                if not emp:
                    return 0, []
                q &= Q(applicant_id=emp.id) | Q(from_employee_id=emp.id) | Q(to_employee_id=emp.id)
        total = await AssetTransfer.filter(q).count()
        items = (
            await AssetTransfer.filter(q)
            .order_by("-created_at")
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return total, items

    async def candidates(self) -> list[dict]:
        user_id = CTX_USER_ID.get()
        rows = await Employee.filter(status=True).order_by("emp_no")
        return [
            {
                "id": e.id,
                "emp_no": e.emp_no,
                "name": e.name,
                "dept_id": e.dept_id,
            }
            for e in rows
            if e.user_id != user_id
        ]


asset_transfer_controller = AssetTransferController()
