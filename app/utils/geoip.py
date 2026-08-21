"""离线 IP 地理查询。禁止在登录路径请求公网 IP 接口。"""
from __future__ import annotations

import ipaddress
import os
from typing import Optional

from app.log import logger
from app.utils.ip2region_xdb import XdbSearcher

_searcher: Optional[XdbSearcher] = None
_load_tried = False


def _default_xdb_path() -> str:
    try:
        from app.settings.config import settings

        env_path = (getattr(settings, "GEOIP_XDB_PATH", "") or "").strip()
        if env_path and os.path.isfile(env_path):
            return env_path
        base = getattr(settings, "BASE_DIR", "")
    except Exception:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    candidates = [
        os.path.join(base, "deploy", "data", "ip2region.xdb"),
        os.path.join(base, "data", "ip2region.xdb"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return candidates[0]


def _get_searcher() -> Optional[XdbSearcher]:
    global _searcher, _load_tried
    if _searcher is not None:
        return _searcher
    if _load_tried:
        return None
    _load_tried = True
    path = _default_xdb_path()
    if not os.path.isfile(path):
        logger.warning(f"geoip xdb missing: {path}")
        return None
    try:
        _searcher = XdbSearcher.from_file(path)
        logger.info(f"geoip xdb loaded: {path}")
        return _searcher
    except Exception as e:
        logger.warning(f"geoip xdb load failed: {e!r}")
        return None


def reset_geoip_cache() -> None:
    """测试用：清掉单例。"""
    global _searcher, _load_tried
    _searcher = None
    _load_tried = False


def ip_kind(ip: str) -> str:
    """public / private / invalid / ipv6。"""
    text = (ip or "").strip()
    if not text or text.lower() in {"unknown", "null", "-"}:
        return "invalid"
    if "%" in text:
        text = text.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return "invalid"
    if addr.version == 6:
        if addr.is_loopback or addr.is_private or addr.is_link_local:
            return "private"
        return "ipv6"
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
        return "private"
    return "public"


def parse_region_line(line: str) -> dict[str, str]:
    """ip2region: 国家|区域|省份|城市|ISP"""
    parts = [(p or "").strip() for p in (line or "").split("|")]
    while len(parts) < 5:
        parts.append("")

    def _clean(v: str) -> str:
        if not v or v in {"0", "null", "None", "*"}:
            return ""
        return v[:64]

    country = _clean(parts[0])
    region = _clean(parts[2]) or _clean(parts[1])
    city = _clean(parts[3])
    isp = _clean(parts[4])[:128]
    return {"country": country, "region": region, "city": city, "isp": isp}


def empty_geo(*, country: str = "未知", region: str = "", isp: str = "") -> dict[str, str]:
    return {"country": country, "region": region, "city": "", "isp": isp}


def lookup_ip(ip: str) -> dict[str, str]:
    """返回 country/region/city/isp。失败不抛。"""
    kind = ip_kind(ip)
    if kind == "invalid":
        return empty_geo(country="未知")
    if kind == "private":
        return empty_geo(country="内网", region="局域网")
    if kind == "ipv6":
        return empty_geo(country="未知", region="IPv6")
    searcher = _get_searcher()
    if searcher is None:
        return empty_geo()
    try:
        raw = searcher.search(ip)
    except Exception:
        return empty_geo()
    if not raw:
        return empty_geo()
    parsed = parse_region_line(raw)
    if not parsed["country"]:
        parsed["country"] = "未知"
    return parsed


def format_location(country: str, region: str = "") -> str:
    c = (country or "").strip() or "未知"
    r = (region or "").strip()
    if c in {"内网", "未知"}:
        return c if not r or r in {"局域网", "IPv6"} else f"{c} / {r}"
    if r and r != c:
        return f"{c} / {r}"
    return c
