from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 资产状态枚举（与 app/controllers/asset.py 的 ASSET_CATEGORIES 保持一致）
ASSET_STATUS = Literal[1, 2, 3, 4]  # 1在用 2闲置 3维修 4报废


class BaseAsset(BaseModel):
    asset_no: str = Field(..., min_length=1, max_length=50, description="资产编号", example="AST001")
    name: str = Field(..., min_length=1, max_length=100, description="资产名称", example="联想笔记本")
    category: str = Field("其他", max_length=50, description="分类：电脑/办公设备/办公用品/其他")
    model: str = Field("", max_length=100, description="型号")
    serial_no: str = Field("", max_length=100, description="序列号")
    purchase_date: Optional[date] = Field(None, description="采购日期")
    warranty_until: Optional[date] = Field(None, description="质保到期日")
    price: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="采购价格（元）")

    @field_validator("purchase_date", "warranty_until", mode="before")
    @classmethod
    def empty_date_to_none(cls, value):
        if value == "":
            return None
        return value
    # 修复：status 枚举校验（原任意 int，5/99 入库后看板/导出显示裸数字）
    status: ASSET_STATUS = Field(2, description="状态：1在用 2闲置 3维修 4报废")
    location: str = Field("", max_length=100, description="存放位置")
    # 修复：owner_emp_id 存在性由 controller 校验（防造"在用但无领用人/领用人不存在"矛盾数据）
    owner_emp_id: Optional[int] = Field(None, description="当前领用人（employees.id）")
    remark: str = Field("", max_length=255, description="备注")


class AssetCreate(BaseAsset):
    pass


class AssetUpdate(BaseAsset):
    id: int

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})
