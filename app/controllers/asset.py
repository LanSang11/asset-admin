from typing import Any, Dict, List, Optional, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, Employee
from app.schemas.assets import AssetCreate, AssetUpdate
from app.services.warranty import attach_warranty_fields, emit_warranty_alerts, warranty_q
from app.utils.identity import resolve_biz_role

# 资产分类常量（后台可扩展）
ASSET_CATEGORIES = ["电脑", "办公设备", "办公用品", "其他"]

# 资产状态常量
ASSET_STATUS_IN_USE = 1   # 在用
ASSET_STATUS_IDLE = 2     # 闲置
ASSET_STATUS_REPAIR = 3   # 维修
ASSET_STATUS_SCRAPPED = 4 # 报废

# 员工可见闲置资产摘要字段外的敏感字段（ISO-B1）
_EMP_SENSITIVE_FIELDS = ("price", "serial_no", "purchase_date", "warranty_until", "remark", "owner_emp_id")


class AssetController(CRUDBase[Asset, AssetCreate, AssetUpdate]):
    def __init__(self):
        super().__init__(model=Asset)

    async def get_by_asset_no(self, asset_no: str) -> Optional[Asset]:
        return await self.model.filter(asset_no=asset_no).first()

    async def _validate_owner(self, owner_emp_id: Optional[int]) -> None:
        """校验领用人存在（防造出领用人不存在的矛盾数据）"""
        if owner_emp_id is not None:
            if not await Employee.filter(id=owner_emp_id).first():
                raise HTTPException(status_code=400, detail="领用人不存在，请先创建员工档案")

    async def _validate_status_owner(self, status: int, owner_emp_id: Optional[int]) -> None:
        """状态与领用人一致性：在用必须有领用人；非在用不应挂着领用人。"""
        if status == ASSET_STATUS_IN_USE and owner_emp_id is None:
            raise HTTPException(status_code=400, detail="资产状态为「在用」时必须指定当前领用人")
        # 维修：允许保留领用人（送修中仍算该员工设备）
        if status == ASSET_STATUS_REPAIR:
            return
        if status in (ASSET_STATUS_IDLE, ASSET_STATUS_SCRAPPED) and owner_emp_id is not None:
            raise HTTPException(status_code=400, detail="闲置/报废资产不能指定领用人（请先走归还或报修修好回闲置）")

    async def list_assets(
        self, page: int, page_size: int, keyword: str = "", category: str = "",
        status: int = 0, dept_id: int = 0, warranty_state: str = ""
    ) -> Tuple[int, List[Asset]]:
        """ISO-B1 行级：admin 全量；manager 本部门名下+闲置；employee 本人名下+闲置。"""
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        emp = await Employee.filter(user_id=user_id).first()
        role = await resolve_biz_role(user, emp)

        q = Q()
        if keyword:
            q &= Q(name__icontains=keyword) | Q(asset_no__icontains=keyword) | Q(serial_no__icontains=keyword)
        if category:
            q &= Q(category=category)
        if status:
            q &= Q(status=status)
        if dept_id and role == "admin":
            emp_ids = await Employee.filter(dept_id=dept_id).values_list("id", flat=True)
            q &= Q(owner_emp_id__in=emp_ids) if emp_ids else Q(id=0)
        if (warranty_state or "").strip().lower() in ("expired", "expiring", "due", "ok", "none"):
            q &= warranty_q(warranty_state)

        if role == "admin":
            pass
        elif role == "manager" and emp and emp.dept_id:
            dept_emp_ids = await Employee.filter(dept_id=emp.dept_id).values_list("id", flat=True)
            # 本部门名下资产 + 公司闲置（领用需要）
            q &= Q(owner_emp_id__in=list(dept_emp_ids)) | Q(status=ASSET_STATUS_IDLE)
        elif emp:
            q &= Q(owner_emp_id=emp.id) | Q(status=ASSET_STATUS_IDLE)
        else:
            # 无员工档案：仅闲置摘要（仍可领用场景极少；保守只给闲置）
            q &= Q(status=ASSET_STATUS_IDLE)

        return await self.list(page, page_size, q, ["-created_at"])

    async def serialize_for_viewer(self, asset: Asset, role: str, viewer_emp: Optional[Employee]) -> Dict[str, Any]:
        """按角色脱敏。员工看他人闲置资产时去掉价格/序列号等。"""
        d = await asset.to_dict()
        is_own = bool(viewer_emp and asset.owner_emp_id == viewer_emp.id)
        hide_warranty = role == "employee" and not is_own
        if role == "admin":
            return attach_warranty_fields(d)
        if role == "employee" and not is_own:
            for f in _EMP_SENSITIVE_FIELDS:
                if f in d:
                    d[f] = None if f in ("price", "owner_emp_id", "warranty_until") else ""
        elif role == "manager" and not is_own and asset.status == ASSET_STATUS_IDLE:
            # 闲置且非本部门在用：价格可保留给主管；序列号仍可看，仅普通员工脱敏
            pass
        return attach_warranty_fields(d, hide=hide_warranty)

    async def can_view_asset(self, asset: Asset, role: str, viewer_emp: Optional[Employee]) -> bool:
        if role == "admin":
            return True
        if asset.status == ASSET_STATUS_IDLE:
            return True
        if not viewer_emp:
            return False
        if asset.owner_emp_id == viewer_emp.id:
            return True
        if role == "manager" and viewer_emp.dept_id:
            owner = await Employee.filter(id=asset.owner_emp_id).first() if asset.owner_emp_id else None
            return bool(owner and owner.dept_id == viewer_emp.dept_id)
        return False

    async def create_asset(self, obj_in: AssetCreate) -> Asset:
        exist = await self.get_by_asset_no(obj_in.asset_no)
        if exist:
            raise HTTPException(status_code=400, detail=f"资产编号 {obj_in.asset_no} 已存在")
        # 修复：分类枚举 + 领用人存在性 + 状态/领用人一致性校验
        if obj_in.category not in ASSET_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"资产分类不合法，可选：{'/'.join(ASSET_CATEGORIES)}")
        await self._validate_owner(obj_in.owner_emp_id)
        await self._validate_status_owner(obj_in.status, obj_in.owner_emp_id)
        data = obj_in.model_dump()
        # 修复：price 留空（null）时落库为 0（模型字段非空，原实现直接 500）
        if data.get("price") is None:
            data["price"] = 0
        obj = await self.create(data)
        await emit_warranty_alerts([obj])
        return obj

    async def update_asset(self, obj_in: AssetUpdate) -> Asset:
        if obj_in.asset_no:
            exist = await self.get_by_asset_no(obj_in.asset_no)
            if exist and exist.id != obj_in.id:
                raise HTTPException(status_code=400, detail=f"资产编号 {obj_in.asset_no} 已存在")
        # 修复：分类枚举 + 领用人存在性 + 状态/领用人一致性校验
        if obj_in.category not in ASSET_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"资产分类不合法，可选：{'/'.join(ASSET_CATEGORIES)}")
        await self._validate_owner(obj_in.owner_emp_id)
        await self._validate_status_owner(obj_in.status, obj_in.owner_emp_id)
        current = await self.get(id=obj_in.id)
        data = obj_in.update_dict()
        if "warranty_until" in data and current.warranty_until != data.get("warranty_until"):
            data["warranty_notified_state"] = ""
        obj = await self.update(obj_in.id, data)
        await emit_warranty_alerts([obj])
        return obj

    async def delete_asset(self, asset_id: int) -> None:
        """删除前校验（修复：原直接删除导致在用/有历史资产的悬空引用）"""
        from app.models.business import AssetUse, AssetUseHistory, Employee
        asset = await self.get(id=asset_id)
        # 在用资产不可删
        if asset.status == ASSET_STATUS_IN_USE and asset.owner_emp_id:
            raise HTTPException(status_code=400, detail="该资产当前在用，请先走归还流程")
        # 有在途申请不可删
        if await AssetUse.filter(asset_id=asset_id, status__in=[1, 2]).first():
            raise HTTPException(status_code=400, detail="该资产有待审批的申请，请先处理")
        # 有历史记录不可删（保留追溯）
        if await AssetUseHistory.filter(asset_id=asset_id).first():
            raise HTTPException(status_code=400, detail="该资产存在领用历史，不可删除（可改为报废状态）")
        await self.remove(id=asset_id)


asset_controller = AssetController()
