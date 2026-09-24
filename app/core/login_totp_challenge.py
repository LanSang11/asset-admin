"""Password-verified, short-lived login TOTP challenge.

The first login request (password + slide captcha) may issue a 120s ticket
instead of an access token. Completing the ticket with a valid TOTP issues
the JWT. Tickets are single-use on success; IP / username / auth_version
mismatches and expiry invalidate them immediately.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from threading import Lock
from typing import Literal, Optional

TTL_SECONDS = 300
MAX_FAILS = 3
FailureResult = Literal["ok", "exhausted", "missing"]


@dataclass
class LoginChallenge:
    token: str
    user_id: int
    username: str
    ip: str
    auth_version: int
    expire: float
    fail_count: int = 0
    recovery_question: Optional[str] = None


class LoginTotpChallengeStore:
    def __init__(self, ttl_seconds: int = TTL_SECONDS, max_fails: int = MAX_FAILS):
        self.ttl_seconds = int(ttl_seconds)
        self.max_fails = int(max_fails)
        self._items: dict[str, LoginChallenge] = {}
        self._lock = Lock()

    def issue(
        self,
        *,
        user_id: int,
        username: str,
        ip: str,
        auth_version: int,
        recovery_question: Optional[str] = None,
        now: Optional[float] = None,
    ) -> LoginChallenge:
        token = secrets.token_urlsafe(24)
        current = time.time() if now is None else float(now)
        challenge = LoginChallenge(
            token=token,
            user_id=int(user_id),
            username=(username or "").strip(),
            ip=ip or "unknown",
            auth_version=int(auth_version or 0),
            expire=current + self.ttl_seconds,
            recovery_question=recovery_question,
        )
        with self._lock:
            self._purge_locked(current)
            stale = [key for key, item in self._items.items() if item.user_id == challenge.user_id]
            for key in stale:
                self._items.pop(key, None)
            self._items[token] = challenge
        return challenge

    def get(self, token: Optional[str], now: Optional[float] = None) -> Optional[LoginChallenge]:
        if not token:
            return None
        current = time.time() if now is None else float(now)
        with self._lock:
            self._purge_locked(current)
            item = self._items.get(token)
            if not item:
                return None
            if item.expire <= current:
                self._items.pop(token, None)
                return None
            return item

    def consume(self, token: Optional[str], now: Optional[float] = None) -> Optional[LoginChallenge]:
        if not token:
            return None
        current = time.time() if now is None else float(now)
        with self._lock:
            self._purge_locked(current)
            item = self._items.pop(token, None)
            if not item or item.expire <= current:
                return None
            return item

    def invalidate(self, token: Optional[str]) -> None:
        if not token:
            return
        with self._lock:
            self._items.pop(token, None)

    def record_failure(self, token: Optional[str], now: Optional[float] = None) -> FailureResult:
        if not token:
            return "missing"
        current = time.time() if now is None else float(now)
        with self._lock:
            self._purge_locked(current)
            item = self._items.get(token)
            if not item or item.expire <= current:
                self._items.pop(token, None)
                return "missing"
            item.fail_count += 1
            if item.fail_count >= self.max_fails:
                self._items.pop(token, None)
                return "exhausted"
            return "ok"

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _purge_locked(self, now: Optional[float] = None) -> None:
        current = time.time() if now is None else float(now)
        dead = [key for key, item in self._items.items() if item.expire <= current]
        for key in dead:
            self._items.pop(key, None)


def challenge_payload(challenge: LoginChallenge, now: Optional[float] = None) -> dict:
    current = time.time() if now is None else float(now)
    remaining = max(0, int(challenge.expire - current))
    return {
        "next_step": "totp",
        "login_challenge": challenge.token,
        "require_totp": True,
        "recovery_question": challenge.recovery_question,
        "expires_in": remaining,
    }


login_totp_challenge = LoginTotpChallengeStore()
