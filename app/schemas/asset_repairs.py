from typing import Optional

from pydantic import BaseModel, Field


class AssetRepairCreate(BaseModel):
    asset_id: int = Field(..., ge=1, description="资产ID")
    reason: str = Field(..., min_length=2, max_length=255, description="故障说明")


class AssetRepairRegister(BaseModel):
    asset_id: int = Field(..., ge=1)
    reason: str = Field("管理员登记送修", min_length=1, max_length=255)
    employee_id: Optional[int] = Field(None, description="可选：指定报修人员工ID")


class AssetRepairComplete(BaseModel):
    repair_id: int = Field(..., ge=1)
    result: str = Field("in_use", description="in_use 回在用 | idle 回闲置")
    comment: str = Field("", max_length=255)
