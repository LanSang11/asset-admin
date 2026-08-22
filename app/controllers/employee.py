from typing import Any, Dict, List, Optional, Tuple

from fastapi.exceptions import HTTPException
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Employee
from app.schemas.employees import EmployeeCreate, EmployeeUpdate
from app.services.employee_query import build_employee_filter, resolve_employee_order
from app.utils.identity import resolve_biz_role


class EmployeeController(CRUDBase[Employee, EmployeeCreate, EmployeeUpdate]):
    def __init__(self):
        super().__init__(model=Employee)

    async def get_by_emp_no(self, emp_no: str) -> Optional[Employee]:
        return await self.model.filter(emp_no=emp_no).first()

    async def get_by_user_id(self, user_id: int) -> Optional[Employee]:
        return await self.model.filter(user_id=user_id).first()

    async def _validate_user(self, user_id: Optional[int]) -> None:
        """校验绑定账号存在（修复：原可绑定不存在的账号 id，员工永远无法登录关联）"""
        if user_id is not None:
            if not await User.filter(id=user_id).first():
                raise HTTPException(status_code=400, detail="绑定的登录账号不存在")

    async def list_employees(
        self,
        page: int,
        page_size: int,
        keyword: str = "",
        dept_id: int = 0,
        status: int = -1,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[int, List[Employee]]:
        """ISO-B2 行级：admin 全员；manager 本部门；employee 仅本人。"""
        user_id = CTX_USER_ID.get()
        user = await User.get(id=user_id)
        me = await Employee.filter(user_id=user_id).first()
        role = await resolve_biz_role(user, me)

        q = build_employee_filter(keyword, 0, status)

        if role == "admin":
            if dept_id:
                q &= Q(dept_id=dept_id)
        elif role == "manager" and me and me.dept_id:
            # 主管强制本部门；忽略跨部门 dept_id 查询
            q &= Q(dept_id=me.dept_id)
        elif me:
            q &= Q(id=me.id)
        else:
            return 0, []

        return await self.list(page, page_size, q, [resolve_employee_order(sort_by, sort_order)])

    async def serialize_for_viewer(
        self, emp: Employee, role: str, viewer_emp: Optional[Employee]
    ) -> Dict[str, Any]:
        """字段级：员工看非本人时脱敏手机邮箱；主管看本部门可看联系方式。"""
        d = await emp.to_dict()
        if role == "admin":
            return d
        is_self = bool(viewer_emp and emp.id == viewer_emp.id)
        if role == "employee" and not is_self:
            d["phone"] = ""
            d["email"] = ""
            d["user_id"] = None
        return d

    async def can_view_employee(self, emp: Employee, role: str, viewer_emp: Optional[Employee]) -> bool:
        if role == "admin":
            return True
        if not viewer_emp:
            return False
        if emp.id == viewer_emp.id:
            return True
        if role == "manager" and viewer_emp.dept_id and emp.dept_id == viewer_emp.dept_id:
            return True
        return False

    async def create_employee(self, obj_in: EmployeeCreate) -> Employee:
        exist = await self.get_by_emp_no(obj_in.emp_no)
        if exist:
            raise HTTPException(status_code=400, detail=f"工号 {obj_in.emp_no} 已存在")
        if obj_in.user_id:
            bound = await self.get_by_user_id(obj_in.user_id)
            if bound:
                raise HTTPException(status_code=400, detail="该账号已绑定其他员工")
            await self._validate_user(obj_in.user_id)
        return await self.create(obj_in)

    async def update_employee(self, obj_in: EmployeeUpdate) -> Employee:
        if obj_in.emp_no:
            exist = await self.get_by_emp_no(obj_in.emp_no)
            if exist and exist.id != obj_in.id:
                raise HTTPException(status_code=400, detail=f"工号 {obj_in.emp_no} 已存在")
        if obj_in.user_id:
            bound = await self.get_by_user_id(obj_in.user_id)
            if bound and bound.id != obj_in.id:
                raise HTTPException(status_code=400, detail="该账号已绑定其他员工")
            await self._validate_user(obj_in.user_id)
        return await self.update(obj_in.id, obj_in.update_dict())

    async def delete_employee(self, emp_id: int) -> None:
        """删除前校验（修复：原直接删除导致名下资产/申请历史悬空引用）"""
        from app.models.business import Asset, AssetUse, AssetUseHistory
        # 名下有在用资产不可删
        if await Asset.filter(owner_emp_id=emp_id, status=1).first():
            raise HTTPException(status_code=400, detail="该员工名下还有在用资产，请先归还")
        # 有申请/历史记录不可删（保留追溯）
        if await AssetUse.filter(employee_id=emp_id).first():
            raise HTTPException(status_code=400, detail="该员工存在资产申请记录，不可删除（可改为离职状态）")
        if await AssetUseHistory.filter(employee_id=emp_id).first():
            raise HTTPException(status_code=400, detail="该员工存在领用历史，不可删除（可改为离职状态）")
        await self.remove(id=emp_id)


employee_controller = EmployeeController()
