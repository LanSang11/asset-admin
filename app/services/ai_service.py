"""大模型调用代理（四层架构第二层：业务层）。

规则：
- 每个用户用自己的 API Key（加密存储，服务端解密后调用）
- 多接口格式兼容：DeepSeek / OpenAI 统一 OpenAI 兼容格式
- 并发控制：同一用户同时最多 1 个请求（进程内 asyncio.Lock）
- 频控：同一用户 1 分钟最多 10 次调用（进程内内存计数）
- 多模态（图片理解）：独立配置的视觉模型（如 qwen-vl-plus / glm-4v），
  解决 DeepSeek 纯文本模型无法看图的问题——视觉模型当"眼睛"，DeepSeek 当"大脑"

注意（如实标注实现边界）：
- 当前并发锁与频控均为【单进程内存实现】。生产多副本部署（多 uvicorn worker/多容器）时
  需升级为分布式方案（Redis/SQLite 行锁），见《四层安全架构规则书.md》第二层待办。
"""
import asyncio
import logging
import time

import httpx

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.core.ai_chat_payload import build_chat_payload
from app.core.ai_presets import DEFAULT_BASE_URL, DEFAULT_MODEL
from app.utils.crypto import decrypt_secret
from app.utils.net_utils import validate_base_url

logger = logging.getLogger(__name__)

# 频控
MAX_CALLS_PER_MINUTE = 10


class AILockManager:
    """每用户并发锁（进程内 asyncio.Lock；多副本需升级分布式方案）"""

    def __init__(self):
        self._locks: dict[int, asyncio.Lock] = {}
        self._last_used: dict[int, float] = {}

    def get_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        self._last_used[user_id] = time.time()
        return self._locks[user_id]

    def cleanup(self):
        """清理 10 分钟未使用的锁，防内存泄漏"""
        now = time.time()
        for uid in list(self._last_used):
            if now - self._last_used[uid] > 600:
                self._locks.pop(uid, None)
                self._last_used.pop(uid, None)


ai_lock_manager = AILockManager()

# 频控：同一用户 1 分钟最多 MAX_CALLS_PER_MINUTE 次（threading.Lock 保护，跨协程安全）
_freq: dict[int, list[float]] = {}
_freq_guard = __import__("threading").Lock()


def _check_frequency(user_id: int) -> None:
    """频控检查，超限抛 ValueError（1 分钟窗口）"""
    now = time.time()
    window_start = now - 60
    with _freq_guard:
        records = [t for t in _freq.get(user_id, []) if t > window_start]
        if len(records) >= MAX_CALLS_PER_MINUTE:
            raise ValueError("调用过于频繁，请 1 分钟后再试")
        records.append(now)
        _freq[user_id] = records
        # 内存控制：超过 1000 个活跃用户时整体清理
        if len(_freq) > 1000:
            _freq.clear()


async def _get_user_config(user: User) -> dict:
    """取用户 API 配置并解密"""
    cfg = user.api_config or {}
    api_key = decrypt_secret(cfg.get("api_key_enc", ""))
    if not api_key:
        raise ValueError("未配置 API Key，请先在「AI 助手」页面配置")
    # SSRF 防护（纵深防御）：调用时二次校验 base_url，防数据库被直接篡改后打内网
    try:
        base_url = validate_base_url(cfg.get("base_url") or DEFAULT_BASE_URL)
    except ValueError as e:
        raise ValueError(f"base_url 配置不合法: {e}")
    return {
        "provider": cfg.get("provider", "deepseek"),
        "api_key": api_key,
        "model": cfg.get("model") or DEFAULT_MODEL,
        "base_url": base_url,
    }


async def get_user_model() -> str:
    """取当前用户配置的模型名（供缓存 key 使用；不解密 API Key，轻量）"""
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    cfg = user.api_config or {}
    return cfg.get("model") or DEFAULT_MODEL


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.7,
    *,
    thinking: str = "disabled",
    timeout: float = 120.0,
) -> dict:
    """代理调用大模型（OpenAI 兼容格式）。DeepSeek 默认关闭思考。"""
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    cfg = await _get_user_config(user)

    # 频控检查：同一用户 1 分钟最多 10 次（内存计数）
    _check_frequency(user_id)

    # 获取并发锁（同一用户串行化）
    lock = ai_lock_manager.get_lock(user_id)
    async with lock:
        url = f"{cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        payload = build_chat_payload(
            model=cfg["model"],
            messages=messages,
            temperature=temperature,
            thinking=thinking,
            provider=str(cfg.get("provider") or ""),
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                # 安全：完整错误仅记日志，客户端只回显状态码（防泄露对话内容/内网响应）
                logger.error(
                    "AI upstream error: user=%s status=%s body=%s",
                    user_id,
                    resp.status_code,
                    resp.text[:500],
                )
                raise ValueError(f"模型调用失败: HTTP {resp.status_code}")
            data = resp.json()
            # 响应 content 可为 null（tool_calls 场景），归一化空串
            content = data["choices"][0]["message"].get("content") or ""
            usage = data.get("usage", {})
            return {
                "content": content,
                "model": data.get("model", cfg["model"]),
                "usage": usage,
            }


async def vision_describe(image_base64: str, prompt: str = "请详细描述这张图片的内容") -> dict:
    """多模态（图片理解）：调用用户独立配置的视觉模型描述图片。

    DeepSeek 为纯文本模型（无多模态），图片理解走独立视觉模型（OpenAI 兼容
    vision 格式，如 qwen-vl-plus / glm-4v / gpt-4o-mini），返回文字描述，
    可再交给 DeepSeek 做进一步分析——视觉模型当"眼睛"，DeepSeek 当"大脑"。
    """
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    cfg = user.api_config or {}
    vision_key = decrypt_secret(cfg.get("vision_api_key_enc", ""))
    vision_model = cfg.get("vision_model", "")
    vision_base_url = cfg.get("vision_base_url", "")
    if not vision_key or not vision_model:
        raise ValueError(
            "未配置视觉模型（图片理解能力）。请先在「AI 助手」→ 配置 中填写视觉模型 API Key 与模型名"
            "（如 qwen-vl-plus / glm-4v / gpt-4o-mini），可选用通义 DashScope 兼容端点"
        )
    try:
        base_url = validate_base_url(vision_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1")
    except ValueError as e:
        raise ValueError(f"视觉模型 base_url 配置不合法: {e}")

    # 频控 + 并发锁（与对话同一套限流）
    _check_frequency(user_id)
    lock = ai_lock_manager.get_lock(user_id)
    async with lock:
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {vision_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    ],
                }
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                # 安全：完整错误仅记日志，客户端只回显状态码
                logger.error(
                    "vision upstream error: user=%s status=%s body=%s",
                    user_id,
                    resp.status_code,
                    resp.text[:300],
                )
                raise ValueError(f"视觉模型调用失败: HTTP {resp.status_code}")
            data = resp.json()
            content = data["choices"][0]["message"].get("content") or ""
            return {
                "content": content,
                "model": data.get("model", vision_model),
                "usage": data.get("usage", {}),
            }
