from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BaseEmployee(BaseModel):
    emp_no: str = Field(..., min_length=1, max_length=20, description="工号", example="EMP001")
    name: str = Field(..., min_length=1, max_length=50, description="姓名", example="张三")
    # 修复：gender 枚举校验
    gender: Literal[0, 1, 2] = Field(0, description="性别：0未知 1男 2女")
    dept_id: Optional[int] = Field(None, description="部门ID")
    position: str = Field("", max_length=100, description="职位")
    hire_date: Optional[date] = Field(None, description="入职日期")
    phone: str = Field("", max_length=20, description="手机")
    email: str = Field("", max_length=100, description="邮箱")
    # 修复：user_id 存在性由 controller 校验（防绑定到不存在的账号 id）
    user_id: Optional[int] = Field(None, description="绑定登录账号ID")
    is_manager: bool = Field(False, description="是否部门主管")
    status: bool = Field(True, description="1在职 0离职")


class EmployeeCreate(BaseEmployee):
    pass


class EmployeeUpdate(BaseEmployee):
    id: int

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})
