"""请求侧信息提取：IP / UA / 轻量设备摘要（零成本审计用，非硬件指纹）。"""
from __future__ import annotations

import hashlib
import ipaddress
from typing import Optional

from fastapi import Request

# RFC5737 / RFC3849 文档网段：公网不会作为真实 TCP 对端，只会出现在伪造头里。
_DOC_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
)


def is_unusable_client_ip(ip: str) -> bool:
    """空值、unknown、文档保留地址：不能当限流/黑名单桶。"""
    text = (ip or "").strip()
    if not text or text.lower() in {"unknown", "null", "none", "-"}:
        return True
    if "%" in text:
        text = text.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return True
    return any(addr in net for net in _DOC_NETWORKS)


def client_ip(request: Request) -> str:
    """反代后的客户端 IP。

    Nginx 模板用 `$remote_addr` 覆盖 XFF。若误配成 `$proxy_add_x_forwarded_for`，
    客户端伪造的首段会在左边——因此从右往左取第一个非文档网段。
    不读 `Forwarded`（客户端可伪造；由 Nginx 清空该头）。
    """
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For") or ""
    hops = [part.strip()[:64] for part in xff.split(",") if part.strip()]
    socket_ip = ""
    if request.client and request.client.host:
        socket_ip = str(request.client.host).strip()[:64]
    for candidate in list(reversed(hops)) + ([socket_ip] if socket_ip else []):
        if candidate and not is_unusable_client_ip(candidate):
            return candidate
    return "unknown"


def user_agent(request: Request) -> str:
    ua = request.headers.get("user-agent") or request.headers.get("User-Agent") or ""
    return ua[:512]


def device_hash(
    request: Request,
    client_hint: Optional[str] = None,
    timezone: Optional[str] = None,
    platform: Optional[str] = None,
    languages: Optional[str] = None,
) -> str:
    """轻量设备摘要：UA + 语言 + 平台 + 时区 + 分辨率。

    可被伪造，仅作「是否换过浏览器/是否多账号同摘要」审计，不当身份证，不替代 TOTP。
    """
    ua = user_agent(request)
    lang = (languages or request.headers.get("accept-language") or "")[:128]
    plat = (platform or "")[:64]
    tz = (timezone or "")[:64]
    hint = (client_hint or "").strip()[:128]
    raw = f"{ua}|{lang}|{plat}|{tz}|{hint}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
