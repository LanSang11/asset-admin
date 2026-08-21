"""RFC 6238 TOTP（纯标准库，零外部依赖）。

用于超管可选二次验证；密钥以 Base32 存库。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from typing import Optional
from urllib.parse import quote


def generate_secret(nbytes: int = 20) -> str:
    raw = os.urandom(nbytes)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    s = (secret or "").strip().upper().replace(" ", "")
    # 补齐 Base32 padding
    pad = (-len(s)) % 8
    if pad:
        s += "=" * pad
    return base64.b32decode(s, casefold=True)


def totp_at(secret: str, for_time: Optional[float] = None, step: int = 30, digits: int = 6) -> str:
    counter = int((for_time if for_time is not None else time.time()) // step)
    key = _normalize_secret(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10**digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1, step: int = 30, digits: int = 6) -> bool:
    """允许前后 window 个时间步（默认 ±30s）。"""
    if not secret or not code:
        return False
    c = "".join(ch for ch in str(code).strip() if ch.isdigit())
    if len(c) != digits:
        return False
    now = time.time()
    for w in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret, now + w * step, step=step, digits=digits), c):
            return True
    return False


def provisioning_uri(secret: str, account_name: str, issuer: str = "企业资产管理系统") -> str:
    """otpauth:// URI，供 Authenticator 扫码。"""
    label = quote(f"{issuer}:{account_name}")
    params = f"secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    return f"otpauth://totp/{label}?{params}"
