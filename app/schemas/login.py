from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    # 示例禁止使用 admin/123456 等弱口令（信息暴露门禁）
    username: str = Field(..., description="用户名称", example="user01")
    password: str = Field(..., description="密码", example="********")
    # L2 风险滑块：失败达阈值后必填；服务端一次性校验
    captcha_id: Optional[str] = Field(None, description="滑块验证码 ID")
    captcha_x: Optional[float] = Field(None, description="滑块横向偏移像素")
    captcha_ticket: Optional[str] = Field(None, max_length=128, description="滑块预验证一次性票据")
    # 零成本 TOTP：启用后登录必填
    totp_code: Optional[str] = Field(None, description="TOTP 二次验证码")
    # 可选前端设备 hint（分辨率等），仅用于轻量 device_hash
    device_hint: Optional[str] = Field(None, max_length=128, description="可选设备提示")
    timezone: Optional[str] = Field(None, max_length=64, description="可选浏览器时区")
    platform: Optional[str] = Field(None, max_length=64, description="可选平台")
    languages: Optional[str] = Field(None, max_length=128, description="可选语言列表")


class JWTOut(BaseModel):
    access_token: str
    username: str


class JWTPayload(BaseModel):
    user_id: int
    username: str
    is_superuser: bool
    exp: datetime
    auth_version: int = 0
    totp_verified: bool = False
    security_setup_only: bool = False
    totp_recovery_only: bool = False
