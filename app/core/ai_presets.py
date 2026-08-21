"""开源开箱用的模型预设。不含任何真实 Key。"""

from __future__ import annotations

# DeepSeek 官方 2026-08：deepseek-chat 将弃用，生产默认改为 deepseek-v4-flash。
# OpenAI 新地址走 /v1；旧兼容保留同一官方主机，给仍按 chat/completions 拼路径的客户端。
AI_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "label": "DeepSeek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    },
    "openai": {
        "label": "OpenAI 新地址",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "openai_legacy": {
        "label": "OpenAI 旧兼容",
        "model": "gpt-3.5-turbo",
        "base_url": "https://api.openai.com/v1",
    },
}

DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = AI_PRESETS[DEFAULT_PROVIDER]["model"]
DEFAULT_BASE_URL = AI_PRESETS[DEFAULT_PROVIDER]["base_url"]


def apply_preset(provider: str) -> dict[str, str]:
    key = (provider or DEFAULT_PROVIDER).strip().lower()
    if key in AI_PRESETS:
        preset = AI_PRESETS[key]
        return {"provider": key, "model": preset["model"], "base_url": preset["base_url"]}
    return {"provider": key or "other", "model": "", "base_url": ""}


def preset_catalog() -> list[dict[str, str]]:
    return [{"value": key, **value} for key, value in AI_PRESETS.items()]
