"""Short in-memory chat history for the read-only assistant. Not persisted."""
from __future__ import annotations

import time
from typing import Any


MAX_MESSAGES = 8
TTL_SECONDS = 30 * 60


class AssistantSessionStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def _key(self, user_id: int, session_id: str) -> str:
        return f"{int(user_id or 0)}:{(session_id or '')[:64]}"

    def _purge(self) -> None:
        now = time.time()
        dead = [key for key, rec in self._data.items() if now - float(rec.get("ts") or 0) > TTL_SECONDS]
        for key in dead:
            self._data.pop(key, None)
        if len(self._data) > 2000:
            self._data.clear()

    def history(self, user_id: int, session_id: str) -> list[dict[str, str]]:
        self._purge()
        rec = self._data.get(self._key(user_id, session_id))
        if not rec:
            return []
        return list(rec.get("messages") or [])

    def remember(self, user_id: int, session_id: str, user_text: str, assistant_text: str) -> None:
        if not session_id:
            return
        self._purge()
        key = self._key(user_id, session_id)
        rec = self._data.get(key) or {"ts": time.time(), "messages": []}
        messages: list[dict[str, str]] = list(rec.get("messages") or [])
        user = (user_text or "").strip()[:2000]
        assistant = (assistant_text or "").strip()[:4000]
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})
        rec["messages"] = messages[-MAX_MESSAGES:]
        rec["ts"] = time.time()
        self._data[key] = rec


assistant_sessions = AssistantSessionStore()
