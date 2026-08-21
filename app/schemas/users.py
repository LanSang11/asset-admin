from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password


def _check_password(value: str) -> str:
    """修复：pydantic-core(rust regex) 不支持 lookahead 正则，
    pattern=PASSWORD_PATTERN 会导致应用启动即崩溃。
    改用 Python re 的 validate_password 做强度校验（规则不变）。"""
    if not validate_password(value):
        raise ValueError("密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号")
    return value


class BaseUser(BaseModel):
    id: int
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    roles: Optional[list] = []


class UserCreate(BaseModel):
    # 示例禁止使用 admin/弱口令等演示 DNA（信息暴露门禁）
    email: EmailStr = Field(example="user01@example.com")
    username: str = Field(example="user01", min_length=2, max_length=32)
    password: str = Field(
        example="********",
        min_length=8,
        max_length=32,
        description="密码：8~32 位，需包含大写、小写、数字、特殊符号",
    )
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    role_ids: Optional[List[int]] = []
    dept_id: Optional[int] = Field(0, description="部门ID")

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        return _check_password(v)

    def create_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"role_ids"})


class UserUpdate(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[List[int]] = None
    dept_id: Optional[int] = None


class UpdatePassword(BaseModel):
    old_password: str = Field(description="旧密码")
    new_password: str = Field(
        description="新密码：8~32 位，需包含大写、小写、数字、特殊符号",
        min_length=8,
        max_length=32,
    )

    @field_validator("new_password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        return _check_password(v)
