from pydantic import BaseModel, Field

from app.models.enums import MethodType


class BaseApi(BaseModel):
    path: str = Field(..., min_length=1, max_length=100, description="API路径", example="/api/v1/user/list")
    summary: str = Field("", max_length=500, description="API简介", example="查看用户列表")
    method: MethodType = Field(..., description="API方法", example="GET")
    tags: str = Field(..., min_length=1, max_length=100, description="API标签", example="User")


class ApiCreate(BaseApi): ...


class ApiUpdate(BaseApi):
    id: int
