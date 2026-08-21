from pydantic import BaseModel, Field

from app.core.ai_presets import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_PROVIDER


class ApiConfigIn(BaseModel):
    """用户大模型 API 配置（提交时明文，服务端加密存储）"""
    provider: str = Field(DEFAULT_PROVIDER, max_length=50, description="服务商：deepseek/openai/openai_legacy/其他")
    api_key: str = Field("", max_length=200, description="API Key（明文提交，服务端加密）")
    model: str = Field(DEFAULT_MODEL, max_length=100, description="模型名，如 deepseek-v4-flash")
    base_url: str = Field(DEFAULT_BASE_URL, max_length=200, description="Base URL")
    # 多模态（图片理解）：可选的视觉模型配置，独立于对话模型（DeepSeek 无视觉时的"眼睛"）
    vision_provider: str = Field("", max_length=50, description="视觉服务商（可选）")
    vision_api_key: str = Field("", max_length=200, description="视觉模型 API Key（可选，明文提交，服务端加密）")
    vision_model: str = Field("", max_length=100, description="视觉模型名，如 qwen-vl-plus / glm-4v（可选）")
    vision_base_url: str = Field("", max_length=200, description="视觉模型 Base URL（可选，默认通义 DashScope 兼容端点）")


class ApiConfigOut(BaseModel):
    """返回给前端的配置（密钥脱敏）"""
    provider: str = ""
    api_key_masked: str = ""
    model: str = ""
    base_url: str = ""
    has_key: bool = False
    # 视觉模型配置（脱敏）
    vision_provider: str = ""
    vision_api_key_masked: str = ""
    vision_model: str = ""
    vision_base_url: str = ""
    has_vision_key: bool = False
