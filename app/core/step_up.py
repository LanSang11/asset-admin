"""Per-operation high-risk verification tokens."""
from __future__ import annotations

import secrets
import time
from threading import Lock
from typing import Optional

from app.settings.config import settings


class StepUpStore:
    def __init__(self, expire_seconds: Optional[int] = None):
        self.expire_seconds = int(expire_seconds or getattr(settings, "STEP_UP_EXPIRE_SECONDS", 300))
        self._items: dict[str, tuple[int, str, str, float]] = {}
        self._lock = Lock()

    def issue(self, user_id: int, operation_key: str, mode: str) -> tuple[str, int]:
        token = secrets.token_urlsafe(24)
        exp = time.time() + self.expire_seconds
        with self._lock:
            self._purge_locked()
            self._items[token] = (int(user_id), operation_key, mode, exp)
        return token, self.expire_seconds

    def consume(self, user_id: int, operation_key: str, mode: str, token: Optional[str]) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            self._purge_locked()
            item = self._items.pop(token, None)
            if not item:
                return False
            uid, bound_operation, issued_mode, exp = item
            return (
                uid == int(user_id)
                and bound_operation == operation_key
                and issued_mode == mode
                and now < exp
            )

    def _purge_locked(self) -> None:
        now = time.time()
        dead = [key for key, (_, _, _, exp) in self._items.items() if exp <= now]
        for key in dead:
            self._items.pop(key, None)


step_up_store = StepUpStore()
