from typing import Optional

from pydantic import BaseModel, Field


class InventoryStart(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    scope: str = Field("all", description="all / dept")
    dept_id: Optional[int] = None
    note: str = Field("", max_length=255)


class InventoryCount(BaseModel):
    line_id: int
    result: str = Field(..., description="found / missing / mismatch")
    counted_status: Optional[int] = None
    note: str = Field("", max_length=255)


class InventoryClose(BaseModel):
    session_id: int
    note: str = Field("", max_length=255)
