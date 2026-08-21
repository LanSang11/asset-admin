# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, AssetRepair, Employee
from app.schemas.asset_repairs import AssetRepairComplete, AssetRepairCreate, AssetRepairRegister
from app.services.notification_service import (
    list_superuser_ids,
    notify_applicant,
    notify_approver,
    notify_approvers,
)
from app.utils.identity import resolve_biz_role

ST_WAIT_MGR = 1
ST_WAIT_ADMIN = 2
ST_REPAIRING = 3
ST_DONE = 4
ST_REJECTED = 5

ASSET_IN_USE = 1
ASSET_IDLE = 2
ASSET_REPAIR = 3


class AssetRepairController:
    async def _employee(self, user_id: int) -> Employee:
        emp = await Employee.filter(user_id=user_id).first()
        if not emp:
            raise HTTPException(status_code=400, detail="当前账号未绑定员工档案，请联系管理员")
        if not emp.status:
            raise HTTPException(status_code=400, detail="离职员工不能发起报修")
        return emp

    async def _manager(self, emp: Employee) -> Optional[Employee]:
        if not emp.dept_id:
            return None
        return await Employee.filter(
            dept_id=emp.dept_id, is_manager=True, status=True, user_id__not_isnull=True
        ).first()

    async def apply(self, req: AssetRepairCreate) -> AssetRepair:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await self._employee(user_id)
        asset = await Asset.get_or_none(id=req.asset_id)
        if not asset:
            raise HTTPException(status_code=400, detail="资产不存在")
        if asset.status != ASSET_IN_USE:
            raise HTTPException(status_code=400, detail="只能报修「在用」资产")
        role = await resolve_biz_role(user, emp)
        if role != "admin":
            if role == "manager" and emp.dept_id:
                owner = await Employee.get_or_none(id=asset.owner_emp_id) if asset.owner_emp_id else None
                if not owner or owner.dept_id != emp.dept_id:
                    raise HTTPException(status_code=403, detail="只能报修本部门名下资产")
            elif asset.owner_emp_id != emp.id:
                raise HTTPException(status_code=403, detail="只能报修自己名下的资产")
        if await AssetRepair.filter(asset_id=asset.id, status__in=[ST_WAIT_MGR, ST_WAIT_ADMIN, ST_REPAIRING]).first():
            raise HTTPException(status_code=400, detail="该资产已有进行中的报修单")

        async with in_transaction():
            obj = await AssetRepair.create(
                asset_id=asset.id,
                employee_id=emp.id,
                reason=req.reason.strip(),
                status=ST_WAIT_MGR,
            )
            manager = await self._manager(emp)
            if manager and manager.user_id:
                await notify_approver(
                    manager.user_id,
                    applicant_name=emp.name,
                    action="报修",
                    asset_name=asset.name,
                    stage="manager",
                    route_kind="repair",
                )
            else:
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=emp.name,
                    action="报修",
                    asset_name=asset.name,
                    stage="admin",
                    route_kind="repair",
                )
        return obj

    async def register(self, req: AssetRepairRegister) -> AssetRepair:
        """管理员直接登记送修（跳过申请）。"""
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="只有管理员可以登记送修")
        asset = await Asset.get_or_none(id=req.asset_id)
        if not asset:
            raise HTTPException(status_code=400, detail="资产不存在")
        if asset.status == 4:
            raise HTTPException(status_code=400, detail="报废资产不能送修")
        if await AssetRepair.filter(asset_id=asset.id, status__in=[ST_WAIT_MGR, ST_WAIT_ADMIN, ST_REPAIRING]).first():
            raise HTTPException(status_code=400, detail="该资产已有进行中的报修单")
        emp_id = req.employee_id or asset.owner_emp_id
        if not emp_id:
            raise HTTPException(status_code=400, detail="请指定报修人员工，或先给资产指定领用人")
        emp = await Employee.get_or_none(id=emp_id)
        if not emp:
            raise HTTPException(status_code=400, detail="员工不存在")
        async with in_transaction():
            obj = await AssetRepair.create(
                asset_id=asset.id,
                employee_id=emp.id,
                reason=req.reason.strip(),
                status=ST_REPAIRING,
                admin_approver_id=user.id,
                admin_comment="管理员登记送修",
                admin_time=datetime.now(),
            )
            asset.status = ASSET_REPAIR
            await asset.save()
        return obj

    async def approve(self, repair_id: int, approve: bool, comment: str) -> AssetRepair:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        obj = await AssetRepair.get_or_none(id=repair_id)
        if not obj:
            raise HTTPException(status_code=400, detail="报修单不存在")
        asset = await Asset.get(id=obj.asset_id)
        emp = await Employee.get(id=obj.employee_id)
        if obj.status in (ST_DONE, ST_REJECTED, ST_REPAIRING):
            raise HTTPException(status_code=400, detail="该报修单已处理，不能重复审批")

        if obj.status == ST_WAIT_MGR:
            if not user.is_superuser:
                manager = await self._manager(emp)
                if not manager or manager.user_id != user.id:
                    raise HTTPException(status_code=403, detail="只有本部门主管才能审批该报修")
            if user.is_superuser and approve:
                async with in_transaction():
                    now = datetime.now()
                    obj.manager_approver_id = user.id
                    obj.manager_comment = comment or "超管代审（一级）"
                    obj.manager_time = now
                    obj.admin_approver_id = user.id
                    obj.admin_comment = comment or "超管终审通过"
                    obj.admin_time = now
                    await self._enter_repair(obj, emp, asset)
                return obj
            async with in_transaction():
                obj.manager_approver_id = user.id
                obj.manager_comment = comment or ""
                obj.manager_time = datetime.now()
                if not approve:
                    obj.status = ST_REJECTED
                    await obj.save()
                    await notify_applicant(
                        emp.user_id, action="报修", asset_name=asset.name, msg="部门主管已驳回",
                        route_kind="repair",
                    )
                    return obj
                obj.status = ST_WAIT_ADMIN
                await obj.save()
                await notify_applicant(
                    emp.user_id, action="报修", asset_name=asset.name, msg="部门主管已通过，等待管理员审批",
                    route_kind="repair",
                )
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=emp.name,
                    action="报修",
                    asset_name=asset.name,
                    stage="admin",
                    route_kind="repair",
                )
                return obj

        if obj.status == ST_WAIT_ADMIN:
            if not user.is_superuser:
                raise HTTPException(status_code=403, detail="只有管理员才能进行报修终审")
            async with in_transaction():
                obj.admin_approver_id = user.id
                obj.admin_comment = comment or ""
                obj.admin_time = datetime.now()
                if not approve:
                    obj.status = ST_REJECTED
                    await obj.save()
                    await notify_applicant(
                        emp.user_id, action="报修", asset_name=asset.name, msg="管理员已驳回",
                        route_kind="repair",
                    )
                    return obj
                await self._enter_repair(obj, emp, asset)
                return obj
        raise HTTPException(status_code=400, detail="未知报修状态")

    async def _enter_repair(self, obj: AssetRepair, emp: Employee, asset: Asset) -> None:
        fresh = await Asset.get(id=asset.id)
        if fresh.status not in (ASSET_IN_USE, ASSET_REPAIR):
            raise HTTPException(status_code=400, detail="审批期间资产状态已变化，无法进入维修")
        obj.status = ST_REPAIRING
        asset.status = ASSET_REPAIR
        await asset.save()
        await obj.save()
        await notify_applicant(
            emp.user_id, action="报修", asset_name=asset.name, msg="已进入维修",
            route_kind="repair",
        )

    async def complete(self, req: AssetRepairComplete) -> AssetRepair:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail="只有管理员可以登记修好")
        if req.result not in ("in_use", "idle"):
            raise HTTPException(status_code=400, detail="result 只能是 in_use 或 idle")
        obj = await AssetRepair.get_or_none(id=req.repair_id)
        if not obj:
            raise HTTPException(status_code=400, detail="报修单不存在")
        if obj.status != ST_REPAIRING:
            raise HTTPException(status_code=400, detail="仅「维修中」的单可以登记修好")
        asset = await Asset.get(id=obj.asset_id)
        emp = await Employee.get(id=obj.employee_id)
        async with in_transaction():
            obj.status = ST_DONE
            obj.complete_time = datetime.now()
            obj.complete_result = req.result
            if req.comment:
                obj.admin_comment = (obj.admin_comment or "") + (("；" + req.comment) if obj.admin_comment else req.comment)
            if req.result == "idle":
                asset.status = ASSET_IDLE
                asset.owner_emp_id = None
                msg = "已修好并回闲置库"
            else:
                asset.status = ASSET_IN_USE
                if not asset.owner_emp_id:
                    asset.owner_emp_id = emp.id
                msg = "已修好并交回领用人"
            await asset.save()
            await obj.save()
            await notify_applicant(
                emp.user_id, action="报修", asset_name=asset.name, msg=msg, route_kind="repair",
            )
        return obj

    async def list_repairs(
        self, page: int, page_size: int, status: int = 0, scope: str = "all"
    ) -> Tuple[int, List[AssetRepair]]:
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        q = Q()
        if status:
            q &= Q(status=status)
        if scope == "mine":
            emp = await Employee.filter(user_id=user_id).first()
            if not emp:
                return 0, []
            q &= Q(employee_id=emp.id)
        elif scope == "pending":
            if user.is_superuser:
                q &= Q(status__in=[ST_WAIT_MGR, ST_WAIT_ADMIN])
            else:
                emp = await Employee.filter(user_id=user_id, is_manager=True).first()
                if not emp:
                    return 0, []
                emp_ids = await Employee.filter(dept_id=emp.dept_id).values_list("id", flat=True)
                q = Q(status=ST_WAIT_MGR, employee_id__in=list(emp_ids))
        elif scope == "repairing":
            emp = await Employee.filter(user_id=user_id).first()
            if user.is_superuser:
                q &= Q(status=ST_REPAIRING)
            elif emp:
                q &= Q(status=ST_REPAIRING, employee_id=emp.id)
            else:
                return 0, []
        else:
            if not user.is_superuser:
                emp = await Employee.filter(user_id=user_id).first()
                if not emp:
                    return 0, []
                q &= Q(employee_id=emp.id)
        total = await AssetRepair.filter(q).count()
        items = await AssetRepair.filter(q).order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
        return total, items


asset_repair_controller = AssetRepairController()
