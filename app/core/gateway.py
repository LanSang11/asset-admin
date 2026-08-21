"""网关层：限流 + 黑名单（四层架构第一层）。

设计原则（v3 重构，2026-08-10）：
1. 已登录用户的正常操作永不误伤：
   - 带有效 token 的请求按账号维度宽松限流（5 分钟 1000 次），不按 IP 连坐；
   - 正常页面刷新/轮询远低于该阈值，账号维度超限只临时限流、不进黑名单；
   - 登录成功（含 TOTP 恢复）解开该 IP 的自动封禁，不解开手动封 / uid:。
2. 防爆破/目录扫描只针对"异常特征"：
   - 未登录请求：1 分钟 30 次 / IP（正常业务均需登录，未登录高频即异常）；
   - 404 高频（目录扫描特征）：1 分钟 30 次 404 / IP → 判定扫描，黑名单 15 分钟；
   - 登录接口由 login_guard 管理（5 次失败锁 5 分钟），本层豁免避免双重计数。
3. 黑名单仅由异常特征触发，15 分钟自动解冻；超管可经
   GET  /api/v1/base/blacklist        查看黑名单
   DELETE /api/v1/base/blacklist?key= 手动解封
   管理（详见 app/api/v1/base/blacklist.py）。
4. 持久化：JSON 文件（重启不丢），与 SQLite 单文件可移植。

实现：内存滑动窗口计数（快速）+ JSON 黑名单持久化，零外部依赖。
"""
import json
import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.security_agg import record_attack
from app.settings.config import settings
from app.utils.request_info import is_unusable_client_ip

# 配置（均可调）
AUTH_WINDOW_SECONDS = 300      # 已登录用户窗口：5 分钟
AUTH_MAX_REQUESTS = 1000       # 已登录用户 5 分钟上限（正常刷新+轮询远低于此）
ANON_WINDOW_SECONDS = 60       # 未登录窗口：1 分钟
ANON_MAX_REQUESTS = 30         # 未登录 1 分钟上限 / IP（防匿名爆破）
SCAN_WINDOW_SECONDS = 60       # 404 扫描统计窗口：1 分钟
SCAN_MAX_404 = 30              # 1 分钟 30 次 404 → 判定目录扫描
BLACKLIST_SECONDS = 15 * 60    # 黑名单时长：15 分钟（原 1 小时，误伤后下调）

# 免限流路径（登录由 login_guard 更严管理，避免双重计数）
EXEMPT_PATHS = ("/docs", "/openapi.json", "/favicon.svg", "/resource/")

# 模块级实例引用：供黑名单管理 API（app/api/v1/base/blacklist.py）使用
_gateway_instance = None


def get_gateway() -> "GatewayRateLimitMiddleware":
    return _gateway_instance


def unban_ip_after_login(ip: str) -> bool:
    """密码+滑块（及 TOTP）通过后调用。网关未初始化时静默跳过。"""
    gw = get_gateway()
    if gw is None:
        return False
    try:
        return gw.clear_auto_ip_ban(ip)
    except Exception:
        return False


class GatewayRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        global _gateway_instance
        _gateway_instance = self
        self._auth_requests: dict[str, deque] = defaultdict(deque)  # uid -> [timestamps]
        self._anon_requests: dict[str, deque] = defaultdict(deque)  # ip -> [timestamps]
        self._scan_404: dict[str, deque] = defaultdict(deque)       # ip -> [404 timestamps]
        self._lock = Lock()
        self._blacklist_db = os.path.join(settings.BASE_DIR, "gateway_blacklist.json")
        self._blacklist: dict[str, float] = self._load_blacklist()  # key -> 解冻时间戳

    # ---------- 黑名单持久化 ----------
    def _normalize_entry(self, raw) -> dict:
        """兼容旧格式 float 解冻时间戳 → 新格式 dict。"""
        if isinstance(raw, dict):
            return {
                "expire": float(raw.get("expire") or 0),
                "reason": str(raw.get("reason") or "")[:200],
                "source": str(raw.get("source") or "auto")[:20],
            }
        try:
            return {"expire": float(raw), "reason": "", "source": "auto"}
        except (TypeError, ValueError):
            return {"expire": 0.0, "reason": "", "source": "auto"}

    def _load_blacklist(self) -> dict:
        try:
            with open(self._blacklist_db, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {k: self._normalize_entry(v) for k, v in data.items()}
        except Exception:
            return {}

    def _save_blacklist(self):
        """修复：原子写（tmp+rename），避免并发写损坏 JSON 导致黑名单整体失效"""
        try:
            tmp = f"{self._blacklist_db}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._blacklist, f, ensure_ascii=False)
            os.replace(tmp, self._blacklist_db)
        except Exception:
            pass

    def _entry_expire(self, entry) -> float:
        return float(self._normalize_entry(entry).get("expire") or 0)

    def is_blacklisted(self, key: str) -> bool:
        """修复：过期清理移入锁内（原锁外 pop+save 与并发写存在竞态）"""
        now = time.time()
        with self._lock:
            entry = self._blacklist.get(key)
            if not entry:
                return False
            expire = self._entry_expire(entry)
            if expire and now < expire:
                return True
            if expire:  # 已过期，清理
                self._blacklist.pop(key, None)
                self._save_blacklist()
            return False

    def add_to_blacklist(
        self,
        key: str,
        seconds: int | None = None,
        reason: str = "",
        source: str = "auto",
    ):
        """seconds=None 用默认 15 分钟；seconds<=0 视为长期封禁（约 10 年）。"""
        if key.startswith("ip:") and is_unusable_client_ip(key[3:]):
            return
        if seconds is None:
            sec = BLACKLIST_SECONDS
        elif seconds <= 0:
            sec = 10 * 365 * 24 * 3600
        else:
            sec = int(seconds)
        self._blacklist[key] = {
            "expire": time.time() + sec,
            "reason": (reason or "")[:200],
            "source": (source or "auto")[:20],
        }
        self._save_blacklist()

    def remove_blacklist(self, key: str) -> bool:
        # 修复：读写入锁（原锁外读写，最坏丢一次保存）
        with self._lock:
            if key in self._blacklist:
                self._blacklist.pop(key, None)
                self._save_blacklist()
                return True
            return False

    def _is_request_blocked(self, client_ip: str, uid: str | None) -> bool:
        """已登录不按 IP 连坐；匿名才吃 IP 黑名单。"""
        if uid:
            return self.is_blacklisted(f"uid:{uid}")
        if is_unusable_client_ip(client_ip):
            return False
        return self.is_blacklisted(f"ip:{client_ip}")

    def clear_auto_ip_ban(self, ip: str) -> bool:
        """登录成功：解开该 IP 的自动封禁，并清掉文档网段误封。不碰 manual / uid:。"""
        cleaned = (ip or "").strip()[:64]
        removed = False
        with self._lock:
            for k, raw in list(self._blacklist.items()):
                if not k.startswith("ip:"):
                    continue
                entry = self._normalize_entry(raw)
                source = (entry.get("source") or "auto")[:20]
                addr = k[3:]
                if is_unusable_client_ip(addr):
                    self._blacklist.pop(k, None)
                    removed = True
                    continue
                if source == "manual":
                    continue
                if cleaned and k == f"ip:{cleaned}":
                    self._blacklist.pop(k, None)
                    removed = True
            if removed:
                self._save_blacklist()
        return removed

    def list_blacklist(self) -> dict:
        """返回 {key: {expire, reason, source, remain_seconds}}。"""
        now = time.time()
        out = {}
        for k, raw in self._blacklist.items():
            entry = self._normalize_entry(raw)
            exp = entry["expire"]
            if exp > now:
                out[k] = {
                    "expire": exp,
                    "reason": entry.get("reason") or "",
                    "source": entry.get("source") or "auto",
                    "remain_seconds": int(exp - now),
                }
        return out

    # ---------- 滑动窗口计数 ----------
    def _check(self, bucket: dict, key: str, window: int, limit: int, blacklist_on_overflow: bool) -> bool:
        """窗口内计数；超限返回 False。blacklist_on_overflow=True 时超限触发黑名单（异常特征）。"""
        now = time.time()
        with self._lock:
            dq = bucket[key]
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= limit:
                if blacklist_on_overflow:
                    self.add_to_blacklist(key)
                return False
            dq.append(now)
            return True

    def _record_404(self, client_ip: str):
        """404 高频 = 目录扫描特征 → 黑名单 IP。"""
        now = time.time()
        with self._lock:
            dq = self._scan_404[client_ip]
            while dq and now - dq[0] > SCAN_WINDOW_SECONDS:
                dq.popleft()
            dq.append(now)
            if len(dq) >= SCAN_MAX_404:
                self.add_to_blacklist(f"ip:{client_ip}")
                self._scan_404.pop(client_ip, None)

    # ---------- 主流程 ----------
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 登录与验证码由 login_guard / 业务接口管理，网关层豁免避免双重计数
        if (
            path.startswith(EXEMPT_PATHS)
            or path.startswith("/api/v1/base/access_token")
            or path.startswith("/api/v1/base/captcha/")
        ):
            return await call_next(request)

        # 与登录一致：反代场景取 X-Forwarded-For
        from app.utils.request_info import client_ip as _client_ip_fn

        client_ip = _client_ip_fn(request)
        token = request.headers.get("token")
        uid = None
        if token:
            try:
                import jwt
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                uid = str(payload.get("user_id"))
            except Exception:
                uid = None  # 无效/过期 token 一律按未登录处理

        # 黑名单：已登录只查 uid（不按 IP 连坐，与文件头第 1 条一致）；
        # 未登录 / 无效 token 才查 IP。手动封账号仍走 uid:。
        if self._is_request_blocked(client_ip, uid):
            try:
                record_attack("blacklist_hit", ip=client_ip)
            except Exception:
                pass
            return JSONResponse(
                status_code=429,
                content={"code": 429, "msg": "访问已被限制，请稍后再试或联系管理员", "data": None},
            )

        # 限流检查
        if uid:
            # 已登录：账号维度宽松限流，超限只临时拒绝、不进黑名单（正常用户可自行放缓）
            if not self._check(self._auth_requests, f"uid:{uid}", AUTH_WINDOW_SECONDS, AUTH_MAX_REQUESTS, blacklist_on_overflow=False):
                try:
                    record_attack("rate_limit", ip=client_ip, source_key=f"uid:{uid}")
                except Exception:
                    pass
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "msg": "请求过于频繁，请稍后再试", "data": None},
                )
        else:
            # 未登录：IP 维度严格限流，超限即黑名单（匿名高频 = 爆破特征）
            if not self._check(self._anon_requests, f"ip:{client_ip}", ANON_WINDOW_SECONDS, ANON_MAX_REQUESTS, blacklist_on_overflow=True):
                try:
                    record_attack("rate_limit", ip=client_ip)
                except Exception:
                    pass
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "msg": "请求过于频繁，请稍后再试", "data": None},
                )

        response = await call_next(request)

        # 404 高频统计（目录扫描特征）
        if response.status_code == 404 and not path.startswith("/api/"):
            pass  # 静态资源 404 不统计（nginx 已托管静态资源，正常不会到后端）
        elif response.status_code == 404:
            self._record_404(client_ip)
            try:
                record_attack("scan", ip=client_ip)
            except Exception:
                pass

        return response
