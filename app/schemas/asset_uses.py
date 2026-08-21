from typing import Literal, Optional

from pydantic import BaseModel, Field


class AssetUseCreate(BaseModel):
    asset_id: int = Field(..., gt=0, description="资产ID")
    # 修复：use_type 枚举校验（原为任意 int，0/3/99 会误走"归还"分支，
    # 审批通过后被错误清空领用人）
    use_type: Literal[1, 2] = Field(..., description="1领用 2归还")


class AssetUseUpdate(BaseModel):
    id: int
