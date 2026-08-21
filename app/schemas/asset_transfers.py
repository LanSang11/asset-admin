from pydantic import BaseModel, Field


class AssetTransferCreate(BaseModel):
    asset_id: int = Field(..., ge=1, description="资产ID")
    to_employee_id: int = Field(..., ge=1, description="调入人员工ID")
    reason: str = Field(..., min_length=2, max_length=255, description="调拨说明")
