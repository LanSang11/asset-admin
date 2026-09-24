from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class MenuType(StrEnum):
    CATALOG = "catalog"  # 目录
    MENU = "menu"  # 菜单


class BaseMenu(BaseModel):
    id: int
    name: str
    path: str
    remark: Optional[dict]
    menu_type: Optional[MenuType]
    icon: Optional[str]
    order: int
    parent_id: int
    is_hidden: bool
    component: str
    keepalive: bool
    redirect: Optional[str]
    children: Optional[list["BaseMenu"]]


class MenuCreate(BaseModel):
    menu_type: MenuType = Field(default=MenuType.CATALOG.value)
    name: str = Field(example="用户管理", min_length=1, max_length=20)
    icon: Optional[str] = Field("ph:user-list-bold", max_length=100)
    path: str = Field(example="/system/user", min_length=1, max_length=100)
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0, default=0)
    is_hidden: Optional[bool] = False
    component: str = Field(default="Layout", example="/system/user", max_length=100)
    keepalive: Optional[bool] = True
    redirect: Optional[str] = Field("", max_length=100)


class MenuUpdate(BaseModel):
    id: int
    menu_type: Optional[MenuType] = Field(example=MenuType.CATALOG.value)
    name: Optional[str] = Field(example="用户管理", min_length=1, max_length=20)
    icon: Optional[str] = Field("ph:user-list-bold", max_length=100)
    path: Optional[str] = Field(example="/system/user", min_length=1, max_length=100)
    order: Optional[int] = Field(example=1)
    parent_id: Optional[int] = Field(example=0)
    is_hidden: Optional[bool] = False
    component: str = Field(example="/system/user", max_length=100)
    keepalive: Optional[bool] = False
    redirect: Optional[str] = Field("", max_length=100)
