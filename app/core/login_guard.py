# -*- coding: utf-8 -*-
from __future__ import annotations

"""登录暴力破解防护：按用户名+IP 计数，超限锁定；失败达阈值要求滑块。

用法: from app.core.login_guard import login_guard
      login_guard.check(username, ip)           # 超限抛 HTTPException 429
      login_guard.requires_captcha(username, ip)
      login_guard.record_failure(username, ip)
      login_guard.reset(username, ip)

策略：
- 用户名+IP 连续失败 ≥ max_attempts → 锁定 lock_seconds
- 同一 IP 总失败 ≥ ip_max_attempts → 锁定（防换用户名绕过）
- 失败 ≥ captcha_threshold → 必须通过滑块（L2 风险触发）
"""
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException


class LoginGuard:
    def __init__(
        self,
        max_attempts: int = 5,
        lock_seconds: int = 300,
        ip_max_attempts: int = 20,
        captcha_threshold: int = 3,
    ):
        self.max_attempts = max_attempts
        self.ip_max_attempts = ip_max_attempts
        self.lock_seconds = lock_seconds
        self.captcha_threshold = captcha_threshold
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._ip_failures: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _key(self, username: str, ip: str) -> str:
        return f"{(username or '').strip().lower()}|{ip}"

    def _prune(self, records: list[float]) -> list[float]:
        now = time.time()
        return [t for t in records if now - t < self.lock_seconds]

    def fail_count(self, username: str, ip: str) -> int:
        with self._lock:
            key = self._key(username, ip)
            self._failures[key] = self._prune(self._failures.get(key, []))
            return len(self._failures[key])

    def ip_fail_count(self, ip: str) -> int:
        with self._lock:
            self._ip_failures[ip] = self._prune(self._ip_failures.get(ip, []))
            return len(self._ip_failures[ip])

    def requires_captcha(self, username: str, ip: str) -> bool:
        """失败达到阈值后要求滑块；IP 连挂也触发（防撞库换账号）。"""
        with self._lock:
            key = self._key(username, ip)
            self._failures[key] = self._prune(self._failures.get(key, []))
            self._ip_failures[ip] = self._prune(self._ip_failures.get(ip, []))
            if len(self._failures[key]) >= self.captcha_threshold:
                return True
            # IP 维度：阈值 ×2，避免共享 NAT 过早打扰正常用户
            if len(self._ip_failures[ip]) >= max(self.captcha_threshold * 2, 6):
                return True
            return False

    def status(self, username: str, ip: str) -> dict:
        with self._lock:
            key = self._key(username, ip)
            self._failures[key] = self._prune(self._failures.get(key, []))
            self._ip_failures[ip] = self._prune(self._ip_failures.get(ip, []))
            u_fails = len(self._failures[key])
            i_fails = len(self._ip_failures[ip])
            locked = u_fails >= self.max_attempts or i_fails >= self.ip_max_attempts
            need_captcha = u_fails >= self.captcha_threshold or i_fails >= max(
                self.captcha_threshold * 2, 6
            )
            return {
                "fail_count": u_fails,
                "ip_fail_count": i_fails,
                "require_captcha": need_captcha,
                "locked": locked,
                "lock_minutes": self.lock_seconds // 60,
                "captcha_threshold": self.captcha_threshold,
                "max_attempts": self.max_attempts,
            }

    def check(self, username: str, ip: str) -> None:
        with self._lock:
            key = self._key(username, ip)
            self._failures[key] = self._prune(self._failures.get(key, []))
            self._ip_failures[ip] = self._prune(self._ip_failures.get(ip, []))
            if len(self._failures[key]) >= self.max_attempts or len(self._ip_failures[ip]) >= self.ip_max_attempts:
                raise HTTPException(
                    status_code=429,
                    detail=f"登录失败次数过多，请 {self.lock_seconds // 60} 分钟后再试",
                )

    def record_failure(self, username: str, ip: str) -> None:
        with self._lock:
            now = time.time()
            key = self._key(username, ip)
            self._failures[key].append(now)
            self._failures[key] = self._prune(self._failures[key])
            self._ip_failures[ip].append(now)
            self._ip_failures[ip] = self._prune(self._ip_failures[ip])

    def reset(self, username: str, ip: str) -> None:
        with self._lock:
            self._failures.pop(self._key(username, ip), None)
            # 登录成功后同时清零该 IP 的失败计数，避免共享出口 IP 连坐
            self._ip_failures.pop(ip, None)


# captcha_threshold=3：第 3 次失败后再次登录必须滑块；第 5 次失败锁定 5 分钟
login_guard = LoginGuard(max_attempts=5, lock_seconds=300, captcha_threshold=3)
# 已登录会话的高危二次验证同样限次，防止无限猜密码或 6 位动态码。
step_up_guard = LoginGuard(max_attempts=5, lock_seconds=300, captcha_threshold=5)
