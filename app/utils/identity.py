"""业务身份解析：审批认 Employee.is_manager，入口/菜单认 User 角色（portal）。

ISO-C1：双轨并存时用本模块统一「业务角色」口径，避免各处复制 if。
"""
from __future__ import annotations

from typing import Literal, Optional, Tuple

from app.models.admin import User
from app.models.business import Employee

BizRole = Literal["admin", "manager", "employee"]


async def get_employee_by_user_id(user_id: int) -> Optional[Employee]:
    return await Employee.filter(user_id=user_id).first()


async def is_dept_manager_employee(emp: Optional[Employee]) -> bool:
    """审批链路口径：员工档案 is_manager=True 且在职。"""
    return bool(emp and emp.is_manager and emp.status)


async def resolve_biz_role(user: User, emp: Optional[Employee] = None) -> BizRole:
    """业务可见性角色：admin > manager > employee。

    - admin：超管，或角色名含「管理员」
    - manager：员工档案 is_manager（与审批一致）
    - employee：其余
    """
    if user.is_superuser:
        return "admin"
    role_objs = await user.roles
    role_names = [r.name for r in role_objs if getattr(r, "name", None)]
    if "管理员" in role_names:
        return "admin"
    if emp is None:
        emp = await get_employee_by_user_id(user.id)
    if await is_dept_manager_employee(emp):
        return "manager"
    return "employee"


async def resolve_user_context(user_id: int) -> Tuple[User, Optional[Employee], BizRole]:
    user = await User.get(id=user_id)
    emp = await get_employee_by_user_id(user_id)
    role = await resolve_biz_role(user, emp)
    return user, emp, role


def portal_for_user(user: User, role_names: list[str] | None = None) -> str:
    """与 /base/userinfo 一致的 portal：admin | work。"""
    if user.is_superuser:
        return "admin"
    names = role_names or []
    if "管理员" in names:
        return "admin"
    return "work"
