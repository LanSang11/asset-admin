"""Build OpenAI-compatible chat payloads. No I/O, no secrets."""
from __future__ import annotations


def uses_deepseek_thinking(provider: str, model: str) -> bool:
    blob = f"{provider or ''} {model or ''}".lower()
    return "deepseek" in blob


def build_chat_payload(
    *,
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    thinking: str = "disabled",
    provider: str = "",
) -> dict:
    """thinking: disabled | low | default(omit, provider default)."""
    payload: dict = {
        "model": model,
        "messages": [
            {
                **item,
                "content": "" if item.get("content") is None else item["content"],
            }
            for item in messages
        ],
        "stream": False,
    }
    mode = (thinking or "disabled").strip().lower()
    if uses_deepseek_thinking(provider, model):
        if mode in {"off", "disabled", "none"}:
            payload["thinking"] = {"type": "disabled"}
            payload["temperature"] = temperature
        elif mode == "low":
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "low"
        else:
            payload["temperature"] = temperature
    else:
        payload["temperature"] = temperature
    return payload
