from datetime import datetime
from typing import List, Optional, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, AssetUse, AssetUseHistory, Employee
from app.schemas.asset_uses import AssetUseCreate, AssetUseUpdate
from app.services.notification_service import (
    list_superuser_ids,
    notify_applicant,
    notify_approver,
    notify_approvers,
)

# 状态常量
STATUS_WAIT_MANAGER = 1  # 待主管审批
STATUS_WAIT_ADMIN = 2    # 待管理员审批
STATUS_APPROVED = 3      # 通过
STATUS_REJECTED = 4      # 驳回

USE_TYPE_TAKE = 1        # 领用
USE_TYPE_RETURN = 2      # 归还


class AssetUseController(CRUDBase[AssetUse, AssetUseCreate, AssetUseUpdate]):
    def __init__(self):
        super().__init__(model=AssetUse)

    async def _get_employee(self, user_id: int) -> Employee:
        """当前登录用户对应的员工档案（一人一号）"""
        emp = await Employee.filter(user_id=user_id).first()
        if not emp:
            raise HTTPException(status_code=400, detail="当前账号未绑定员工档案，请联系管理员")
        # 修复：离职员工不允许发起新申请
        if not emp.status:
            raise HTTPException(status_code=400, detail="离职员工不能发起资产申请")
        return emp

    async def _get_manager(self, emp: Employee) -> Optional[Employee]:
        """申请人所在部门的主管（is_manager 标记，且必须绑定登录账号才能审批）"""
        if not emp.dept_id:
            return None
        return await Employee.filter(dept_id=emp.dept_id, is_manager=True, status=True, user_id__not_isnull=True).first()

    async def create_application(self, obj_in: AssetUseCreate) -> AssetUse:
        """员工发起领用/归还申请（事务化：申请 + 通知要么全成功要么全回滚）"""
        user_id = CTX_USER_ID.get()
        emp = await self._get_employee(user_id)
        asset = await Asset.get_or_none(id=obj_in.asset_id)
        if not asset:
            raise HTTPException(status_code=400, detail="资产不存在")

        if obj_in.use_type == USE_TYPE_TAKE:
            if asset.status != 2:
                raise HTTPException(status_code=400, detail="该资产当前不可领用（非闲置状态）")
            if await AssetUse.filter(asset_id=obj_in.asset_id, status__in=[1, 2]).first():
                raise HTTPException(status_code=400, detail="该资产已有待审批的申请")
        else:  # 归还
            if asset.owner_emp_id != emp.id:
                raise HTTPException(status_code=400, detail="只能归还自己名下的资产")
            if await AssetUse.filter(asset_id=obj_in.asset_id, employee_id=emp.id, status__in=[1, 2]).first():
                raise HTTPException(status_code=400, detail="该资产已有待审批的归还申请")

        action = "领用" if obj_in.use_type == USE_TYPE_TAKE else "归还"
        async with in_transaction():
            obj = await self.create({
                "asset_id": obj_in.asset_id,
                "employee_id": emp.id,
                "use_type": obj_in.use_type,
                "status": STATUS_WAIT_MANAGER,
            })

            # ISO-A2 阶段投递：有本部门主管 → 仅通知主管；无主管 → 升级通知超管终审
            manager = await self._get_manager(emp)
            if manager and manager.user_id:
                await notify_approver(
                    manager.user_id,
                    applicant_name=emp.name,
                    action=action,
                    asset_name=asset.name,
                    stage="manager",
                )
            else:
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=emp.name,
                    action=action,
                    asset_name=asset.name,
                    stage="admin",
                )
        return obj

    async def approve(self, application_id: int, approve: bool, comment: str) -> AssetUse:
        """审批：主管（一级）或管理员（二级）。

        修复：① 整个审批流程事务化（状态+资产+历史+通知一致）；
             ② 最终通过前复核资产当前状态/领用人，防止审批期间管理员改资产被覆盖；
             ③ 驳回也记录审批人信息。
        """
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        obj = await self.get(application_id)
        asset = await Asset.get(id=obj.asset_id)
        emp = await Employee.get(id=obj.employee_id)
        action = "领用" if obj.use_type == USE_TYPE_TAKE else "归还"

        if obj.status in (STATUS_REJECTED, STATUS_APPROVED):
            raise HTTPException(status_code=400, detail="该申请已处理，不能重复审批")

        # 一级：部门主管审批
        if obj.status == STATUS_WAIT_MANAGER:
            if not user.is_superuser:
                manager = await self._get_manager(emp)
                if not manager or manager.user_id != user.id:
                    raise HTTPException(status_code=403, detail="只有本部门主管才能审批该申请")

            # 超管在一级点「通过」= 一次终审（两级都记，并联动资产）。
            # 历史问题：超管只能把状态 1→2，界面提示「审批完成」但资产未变更，
            # 用户以为失败；刷新后仍待终审，再点一次才真正通过——业务上像抽风。
            if user.is_superuser and approve:
                async with in_transaction():
                    now = datetime.now()
                    obj.manager_approver_id = user.id
                    obj.manager_comment = comment or "超管代审（一级）"
                    obj.manager_time = now
                    obj.admin_approver_id = user.id
                    obj.admin_comment = comment or "超管终审通过"
                    obj.admin_time = now
                    await self._apply_final_approve(obj, emp, asset, action, user)
                return obj

            async with in_transaction():
                obj.manager_approver_id = user.id
                obj.manager_comment = comment
                obj.manager_time = datetime.now()
                if not approve:
                    obj.status = STATUS_REJECTED
                    await obj.save()
                    await self._notify_applicant(obj, emp, asset, action, "部门主管已驳回")
                    return obj
                obj.status = STATUS_WAIT_ADMIN
                await obj.save()
                await self._notify_applicant(obj, emp, asset, action, "部门主管已通过，等待管理员审批")
                # ISO-A2：主管通过后再通知超管终审（提交时不轰炸超管）
                await notify_approvers(
                    await list_superuser_ids(),
                    applicant_name=emp.name,
                    action=action,
                    asset_name=asset.name,
                    stage="admin",
                )
                return obj

        # 二级：管理员审批
        if obj.status == STATUS_WAIT_ADMIN:
            if not user.is_superuser:
                raise HTTPException(status_code=403, detail="只有管理员才能进行最终审批")
            async with in_transaction():
                obj.admin_approver_id = user.id
                obj.admin_comment = comment
                obj.admin_time = datetime.now()
                if not approve:
                    obj.status = STATUS_REJECTED
                    await obj.save()
                    await self._notify_applicant(obj, emp, asset, action, "管理员已驳回")
                    return obj
                await self._apply_final_approve(obj, emp, asset, action, user)
                return obj

        raise HTTPException(status_code=400, detail="未知审批状态")

    async def _apply_final_approve(self, obj: AssetUse, emp: Employee, asset: Asset, action: str, user: User) -> None:
        """终审通过：复核资产状态 + 改资产/历史/通知。调用方需已在事务内。"""
        if obj.use_type == USE_TYPE_TAKE:
            fresh = await Asset.get(id=asset.id)
            if fresh.status != 2:
                raise HTTPException(
                    status_code=400,
                    detail="审批期间资产状态已变化（不再闲置），本次领用审批无法通过",
                )
        else:
            fresh = await Asset.get(id=asset.id)
            if fresh.owner_emp_id != emp.id:
                raise HTTPException(
                    status_code=400,
                    detail="审批期间资产领用人已变化，本次归还审批无法通过",
                )

        obj.status = STATUS_APPROVED
        if obj.use_type == USE_TYPE_TAKE:
            asset.status = 1  # 在用
            asset.owner_emp_id = emp.id
            remark = f"领用通过（{emp.name}）"
        else:
            asset.status = 2  # 闲置
            asset.owner_emp_id = None
            obj.return_time = datetime.now()
            remark = f"归还通过（{emp.name}）"
        await asset.save()
        await obj.save()
        await AssetUseHistory.create(
            asset_id=asset.id,
            employee_id=emp.id,
            use_type=obj.use_type,
            operator_id=user.id,
            remark=remark,
        )
        await self._notify_applicant(obj, emp, asset, action, "审批通过")

    async def _notify_applicant(self, obj, emp, asset, action, msg):
        """通知申请人审批进度/结果（未绑定账号时静默跳过）。"""
        await notify_applicant(
            emp.user_id,
            action=action,
            asset_name=asset.name,
            msg=msg,
        )

    async def list_applications(
        self, page: int, page_size: int, status: int = 0, use_type: int = 0, scope: str = "all"
    ) -> Tuple[int, List[AssetUse]]:
        """申请列表：scope=all 全部 / mine 我的 / pending 待我审批。

        ISO-B4 口径（与实现一致）：
        - scope=mine：仅本人申请
        - scope=pending：超管看全部待审；本部门 is_manager 主管看本部门一级待审；
          非主管非超管返回空
        - scope=all（及其它）：仅超管看全部；其余用户强制 mine
        永远不相信用户输入扩大可见范围。
        """
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        q = Q()
        if status:
            q &= Q(status=status)
        if use_type:
            q &= Q(use_type=use_type)

        if scope == "mine":
            emp = await Employee.filter(user_id=user_id).first()
            if not emp:
                return 0, []
            q &= Q(employee_id=emp.id)
        elif scope == "pending":
            # 待我审批：管理员看全部待审；主管看本部门待一级
            if user.is_superuser:
                q &= Q(status__in=[STATUS_WAIT_MANAGER, STATUS_WAIT_ADMIN])
            else:
                emp = await Employee.filter(user_id=user_id, is_manager=True).first()
                if not emp:
                    return 0, []
                # 通过 employee 关联部门
                emp_ids = await Employee.filter(dept_id=emp.dept_id).values_list("id", flat=True)
                q = Q(status=STATUS_WAIT_MANAGER, employee_id__in=emp_ids)
        else:
            # scope=all：仅超级管理员可看全部；其他用户强制只看自己的申请
            if not user.is_superuser:
                emp = await Employee.filter(user_id=user_id).first()
                if not emp:
                    return 0, []
                q &= Q(employee_id=emp.id)
        return await self.list(page, page_size, q, ["-created_at"])

    async def get_history(self, asset_id: int) -> List[AssetUseHistory]:
        """资产历史追溯。

        安全：仅超级管理员可查任意资产历史；
        普通用户/主管只能查自己名下（或申请过）的资产历史，防 IDOR。
        """
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        if not user.is_superuser:
            emp = await Employee.filter(user_id=user_id).first()
            if not emp:
                raise HTTPException(status_code=403, detail="无权查看该资产历史")
            # 是否与资产相关：当前领用人 or 申请过（领用/归还记录中涉及）
            related = await AssetUse.filter(
                Q(asset_id=asset_id) & Q(employee_id=emp.id)
            ).first()
            asset = await Asset.get_or_none(id=asset_id)
            if not related and not (asset and asset.owner_emp_id == emp.id):
                raise HTTPException(status_code=403, detail="无权查看该资产历史")
        return await AssetUseHistory.filter(asset_id=asset_id).order_by("-use_time")


asset_use_controller = AssetUseController()
