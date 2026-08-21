"""AI 助手对话接口（四层架构第二/四层）。

- 用户用自己的加密 Key 调用（第二层）
- 多接口格式兼容：统一 OpenAI 兼容格式（DeepSeek/OpenAI/通义/智谱都支持）
- 语义缓存（第四层）：相同提问规范化哈希，直接返回缓存
- 多模态（图片理解）：/vision 走独立视觉模型（DeepSeek 无视觉时的"眼睛"通道）
"""
import base64
import hashlib
import time

from typing import List

from fastapi import APIRouter, Body

from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.schemas.base import Fail, Success
from app.services.ai_service import chat_completion, get_user_model, vision_describe

router = APIRouter()

# 简单语义缓存：规范化文本+用户ID+温度+模型哈希（v1 轻量实现，后续可换 sqlite-vec 向量）
# 安全：key 含 user_id，防止跨用户缓存泄露他人对话内容
# 修复：缓存值带时间戳，TTL 10 分钟（原永久缓存，"今天几号"类问题永远返回旧答案）
_cache: dict[str, tuple[float, dict]] = {}
CACHE_MAX = 200
CACHE_TTL_SECONDS = 10 * 60
MAX_MESSAGES = 50  # 单次对话消息条数上限（防滥用）
# 修复：role 白名单（原任意 dict 透传；禁止 tool/function 等危险 role 与异常结构）
ALLOWED_ROLES = {"user", "assistant"}
_cleanup_counter = 0  # 定期清理闲置锁的计数器

# 图片理解限制
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB


def _cache_key(messages: list[dict], temperature: float, model: str) -> str:
    """规范化消息文本+当前用户+温度+模型生成缓存 key（去除多余空白，content 兼容 None/非字符串）"""
    user_id = CTX_USER_ID.get() or 0
    parts = []
    for m in messages:
        role = str(m.get("role", "") or "")
        content = m.get("content")
        if content is None:
            content = ""
        parts.append(f"{role}:{' '.join(str(content).split())}")
    text = "|".join(parts)
    return f"{user_id}:{temperature}:{model}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _validate_messages(messages: list[dict]) -> None:
    """消息结构校验：role 白名单 + content 必须为字符串/None（防结构注入）"""
    for m in messages:
        if not isinstance(m, dict):
            raise ValueError("消息格式不合法")
        role = m.get("role")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"消息角色不合法，仅允许：{'/'.join(sorted(ALLOWED_ROLES))}")
        content = m.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("消息内容必须是文本")


@router.post("/chat", summary="AI 对话", dependencies=[DependAuth])
async def chat(
    messages: List[dict] = Body(..., description="对话消息列表"),
    temperature: float = Body(0.7, description="温度"),
):
    if not messages:
        return Fail(code=400, msg="消息不能为空")
    if len(messages) > MAX_MESSAGES:
        return Fail(code=400, msg=f"消息条数不能超过 {MAX_MESSAGES} 条")
    if not isinstance(temperature, (int, float)) or not (0 <= temperature <= 2):
        return Fail(code=400, msg="temperature 必须在 0~2 之间")
    try:
        _validate_messages(messages)
    except ValueError as e:
        return Fail(code=400, msg=str(e))

    # 定期清理闲置锁（防内存泄漏；每 50 次调用触发一次，含缓存命中路径）
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % 50 == 0:
        from app.services.ai_service import ai_lock_manager
        ai_lock_manager.cleanup()

    # 第四层：语义缓存（相同规范化提问+温度+模型直接返回缓存；TTL 10 分钟）
    model = await get_user_model()
    ck = _cache_key(messages, temperature, model)
    hit = _cache.get(ck)
    if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
        return Success(data={**hit[1], "from_cache": True})
    if hit:  # 过期清理
        _cache.pop(ck, None)

    try:
        result = await chat_completion(messages, temperature)
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception:
        return Fail(code=500, msg="AI 调用失败")

    # 写缓存（防止恶意重复调用消耗费用；超容量时全清后重写）
    if len(_cache) >= CACHE_MAX:
        _cache.clear()
    _cache[ck] = (time.time(), result)
    result["from_cache"] = False
    return Success(data=result)


@router.post("/vision", summary="图片理解（多模态：DeepSeek 无视觉时的眼睛通道）", dependencies=[DependAuth])
async def vision(
    image_base64: str = Body(..., description="图片 base64（不含 data: 前缀，jpg/png/webp，≤5MB）"),
    prompt: str = Body("请详细描述这张图片的内容，包括所有可见的文字、数字与关键信息", description="引导提示词"),
):
    """上传图片 → 视觉模型（如 qwen-vl-plus / glm-4v）→ 返回文字描述。

    DeepSeek 是纯文本模型（不能看图），本接口用用户独立配置的视觉模型
    作为"眼睛"：先转文字，可再交给 DeepSeek 分析。
    """
    if not image_base64:
        return Fail(code=400, msg="图片内容不能为空")
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception:
        return Fail(code=400, msg="图片 base64 解码失败，请上传有效图片")
    if not raw:
        return Fail(code=400, msg="图片内容为空")
    if len(raw) > MAX_IMAGE_BYTES:
        return Fail(code=400, msg="图片不能超过 5MB")
    if not prompt or len(prompt) > 500:
        return Fail(code=400, msg="prompt 长度需在 1~500 之间")

    try:
        result = await vision_describe(image_base64, prompt)
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    except Exception:
        return Fail(code=500, msg="图片理解失败")
    return Success(data=result)
