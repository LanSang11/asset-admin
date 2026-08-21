"""用户大模型 API 配置接口（四层架构第二层）。

规则：
- 每个用户只能配置/查看自己的 Key
- Key 加密存储（AES-256-GCM），任何接口不返回明文
- 只有本人能读写；管理员可查看用户是否已配置（不能看明文）
- 视觉模型配置（图片理解）：独立于对话模型的第二组 Key，同为加密存储
"""
from fastapi import APIRouter

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.models.admin import User
from app.core.ai_presets import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_PROVIDER, apply_preset, preset_catalog
from app.schemas.api_config import ApiConfigIn
from app.schemas.base import Fail, Success
from app.utils.crypto import decrypt_secret, encrypt_secret, mask_key
from app.utils.net_utils import validate_base_url

router = APIRouter()


@router.post("/save", summary="保存我的API配置", dependencies=[DependAuth])
async def save_api_config(req_in: ApiConfigIn):
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)

    # SSRF 防护：base_url 保存时校验（仅 https + 非内网/本机地址）
    try:
        base_url = validate_base_url(req_in.base_url)
    except ValueError as e:
        return Fail(code=400, msg=str(e))

    # 加密存储（api_key 为空串时保留已有 Key，与前端"留空保持不变"一致）
    cfg = user.api_config or {}
    if req_in.api_key:
        encrypted = encrypt_secret(req_in.api_key)
    else:
        encrypted = cfg.get("api_key_enc", "")

    # 视觉模型配置：同样空串保留旧值；base_url 非空时校验
    if req_in.vision_api_key:
        vision_encrypted = encrypt_secret(req_in.vision_api_key)
    else:
        vision_encrypted = cfg.get("vision_api_key_enc", "")
    vision_base_url = req_in.vision_base_url.strip()
    if vision_base_url:
        try:
            vision_base_url = validate_base_url(vision_base_url)
        except ValueError as e:
            return Fail(code=400, msg=f"视觉模型 {e}")

    if not encrypted:
        return Fail(code=400, msg="未配置 API Key，不能外呼模型")
    preset = apply_preset(req_in.provider)
    model = (req_in.model or "").strip() or preset.get("model") or DEFAULT_MODEL
    user.api_config = {
        "provider": req_in.provider or DEFAULT_PROVIDER,
        "api_key_enc": encrypted,
        "model": model,
        "base_url": base_url,
        "vision_provider": req_in.vision_provider,
        "vision_api_key_enc": vision_encrypted,
        "vision_model": req_in.vision_model,
        "vision_base_url": vision_base_url,
    }
    await user.save(update_fields=["api_config"])
    return Success(msg="API 配置已保存（密钥已加密）")


@router.get("/my", summary="查看我的API配置（密钥脱敏）", dependencies=[DependAuth])
async def get_my_api_config():
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    cfg = user.api_config or {}
    api_key_enc = cfg.get("api_key_enc", "")
    plain = decrypt_secret(api_key_enc) if api_key_enc else ""
    vision_enc = cfg.get("vision_api_key_enc", "")
    vision_plain = decrypt_secret(vision_enc) if vision_enc else ""
    preset = apply_preset(cfg.get("provider") or DEFAULT_PROVIDER)
    return Success(data={
        "provider": cfg.get("provider") or DEFAULT_PROVIDER,
        "api_key_masked": mask_key(plain),
        "model": cfg.get("model") or preset.get("model") or DEFAULT_MODEL,
        "base_url": cfg.get("base_url") or preset.get("base_url") or DEFAULT_BASE_URL,
        "has_key": bool(plain),
        "presets": preset_catalog(),
        "vision_provider": cfg.get("vision_provider", ""),
        "vision_api_key_masked": mask_key(vision_plain),
        "vision_model": cfg.get("vision_model", ""),
        "vision_base_url": cfg.get("vision_base_url", ""),
        "has_vision_key": bool(vision_plain),
    })
