"""登录风险标签（只标记，不自动封、不做定罪式鉴定）。"""
from __future__ import annotations

import os
from typing import Iterable, Optional

# 常见国家：配置里写 CN / 中国 均可
_DEFAULT_COMMON = "CN,中国"

_COUNTRY_ALIASES = {
    "CN": "中国",
    "CHN": "中国",
    "中国": "中国",
    "HK": "中国",
    "香港": "中国",
    "MO": "中国",
    "澳门": "中国",
    "TW": "中国",
    "台湾": "中国",
}

# 机房 / 云 / 常见托管词（ISP 或组织名）。误伤云办公是预期，只提示。
DATACENTER_KEYWORDS = (
    "阿里云",
    "阿里巴巴",
    "腾讯云",
    "华为云",
    "天翼云",
    "移动云",
    "百度云",
    "金山云",
    "ucloud",
    "aws",
    "amazon",
    "google",
    "gcp",
    "azure",
    "microsoft",
    "digitalocean",
    "hetzner",
    "linode",
    "akamai",
    "vultr",
    "ovh",
    "cloudflare",
    "oracle cloud",
    "bandwagon",
    "搬瓦工",
    "hostwinds",
    "contabo",
    "datacenter",
    "data center",
    "colocation",
    "hosting",
    "dedicated",
    "server",
    "vps",
    "vpn",
    "proxy",
    "机房",
    "数据中心",
    "托管",
    "云服务",
)

# 国家与时区「明显」矛盾才打标；出差/改时区会误伤，所以只做显眼冲突
_TZ_CONFLICT_PREFIX = {
    "中国": ("America/", "Europe/", "Africa/", "Australia/", "Atlantic/", "Pacific/Honolulu"),
    "美国": ("Asia/", "Europe/", "Africa/", "Australia/"),
    "日本": ("America/", "Europe/", "Africa/", "Australia/"),
    "韩国": ("America/", "Europe/", "Africa/", "Australia/"),
    "英国": ("Asia/", "America/", "Australia/"),
    "德国": ("Asia/", "America/", "Australia/"),
    "法国": ("Asia/", "America/", "Australia/"),
    "新加坡": ("America/", "Europe/", "Africa/"),
    "澳大利亚": ("America/", "Europe/", "Asia/Shanghai", "Asia/Tokyo"),
    "俄罗斯": ("America/", "Australia/"),
    "加拿大": ("Asia/", "Europe/", "Africa/", "Australia/"),
    "印度": ("America/", "Europe/", "Australia/"),
}

TAG_HELP: dict[str, dict[str, str]] = {
    "uncommon_country": {
        "label": "非常见国家",
        "level": "warning",
        "help": "登录来自不常见的国家/地区。可能是出差，也可能是代理。只提示，不会自动封。",
    },
    "datacenter": {
        "label": "机房 IP",
        "level": "warning",
        "help": "运营商信息像云服务器或机房。不少代理走这里，也可能是正常云上办公。",
    },
    "tor": {
        "label": "Tor 出口",
        "level": "error",
        "help": "该 IP 出现在随发布带上的 Tor 出口快照里。应当高风险看待，不能单凭此定罪。",
    },
    "tz_mismatch": {
        "label": "时区对不上",
        "level": "warning",
        "help": "浏览器时区和国家/地区明显对不上。可能是改了系统时区，也可能经过代理。",
    },
    "new_device": {
        "label": "新设备摘要",
        "level": "info",
        "help": "这个账号以前没用过这个设备摘要。换浏览器、清站点数据、无痕窗口都会变成新摘要，高手也能假装。",
    },
    "shared_device": {
        "label": "多账号同摘要",
        "level": "warning",
        "help": "同一个设备摘要出现在多个账号上。可能是共用电脑，也可能是被仿冒。",
    },
}

_tor_ips: Optional[set[str]] = None
_tor_tried = False


def _common_country_set() -> set[str]:
    try:
        from app.settings.config import settings

        raw = (getattr(settings, "SECURITY_COMMON_COUNTRIES", "") or _DEFAULT_COMMON).strip()
    except Exception:
        raw = _DEFAULT_COMMON
    out: set[str] = set()
    for part in raw.split(","):
        name = (part or "").strip()
        if not name:
            continue
        out.add(name)
        out.add(_COUNTRY_ALIASES.get(name.upper(), name))
        out.add(_COUNTRY_ALIASES.get(name, name))
    out.add("中国")
    out.add("CN")
    return out


def normalize_country(country: str) -> str:
    c = (country or "").strip()
    if not c:
        return ""
    return _COUNTRY_ALIASES.get(c, _COUNTRY_ALIASES.get(c.upper(), c))


def parse_tags(raw: str | Iterable[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    else:
        parts = [str(p).strip() for p in raw]
    seen: list[str] = []
    for p in parts:
        if p and p in TAG_HELP and p not in seen:
            seen.append(p)
    return seen


def join_tags(tags: Iterable[str]) -> str:
    return ",".join(parse_tags(tags))[:255]


def is_common_country(country: str) -> bool:
    c = (country or "").strip()
    if not c or c in {"内网", "未知", "局域网"}:
        return True
    common = _common_country_set()
    if c in common:
        return True
    return normalize_country(c) in {normalize_country(x) for x in common}


def looks_like_datacenter(isp: str, region: str = "") -> bool:
    blob = f"{isp or ''} {region or ''}".lower()
    if not blob.strip():
        return False
    for kw in DATACENTER_KEYWORDS:
        if kw.lower() in blob:
            return True
    return False


def timezone_mismatch(country: str, timezone: str) -> bool:
    tz = (timezone or "").strip()
    c = normalize_country(country)
    if not tz or not c or c in {"内网", "未知"}:
        return False
    prefixes = _TZ_CONFLICT_PREFIX.get(c)
    if not prefixes:
        return False
    return any(tz.startswith(p) for p in prefixes)


def _tor_list_path() -> str:
    try:
        from app.settings.config import settings

        env_path = (getattr(settings, "TOR_EXIT_LIST_PATH", "") or "").strip()
        if env_path and os.path.isfile(env_path):
            return env_path
        base = getattr(settings, "BASE_DIR", "")
    except Exception:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    return os.path.join(base, "deploy", "data", "tor_exit_nodes.txt")


def load_tor_exits() -> set[str]:
    global _tor_ips, _tor_tried
    if _tor_ips is not None:
        return _tor_ips
    if _tor_tried:
        return set()
    _tor_tried = True
    path = _tor_list_path()
    ips: set[str] = set()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    ips.add(s.split()[0])
        except Exception:
            ips = set()
    _tor_ips = ips
    return ips


def reset_tor_cache() -> None:
    global _tor_ips, _tor_tried
    _tor_ips = None
    _tor_tried = False


def is_tor_exit(ip: str) -> bool:
    text = (ip or "").strip()
    if not text:
        return False
    return text in load_tor_exits()


def compute_risk_tags(
    *,
    ip: str = "",
    country: str = "",
    region: str = "",
    isp: str = "",
    timezone: str = "",
    extra: Iterable[str] | None = None,
) -> list[str]:
    """纯函数：根据 IP/地理/时区打标。不含设备画像（那要查库）。"""
    tags: list[str] = []
    c = (country or "").strip()
    if c and c not in {"内网", "未知"} and not is_common_country(c):
        tags.append("uncommon_country")
    if looks_like_datacenter(isp, region):
        tags.append("datacenter")
    if is_tor_exit(ip):
        tags.append("tor")
    if timezone_mismatch(c, timezone):
        tags.append("tz_mismatch")
    if extra:
        tags.extend(extra)
    return parse_tags(tags)


def tag_catalog() -> list[dict[str, str]]:
    return [{"code": k, **v} for k, v in TAG_HELP.items()]
