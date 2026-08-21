"""网络工具：大模型 base_url 安全校验（防 SSRF）。

规则：
- 仅允许 https scheme
- 拒绝本机/回环/内网/链路本地/保留/组播 IP
- 拒绝 localhost、.local、.internal、.intranet 等本机/内网域名

边界说明（如实标注）：当前为静态校验（URL 字面量/IP 形式）。
DNS 解析后指向内网的域名（DNS rebinding）不在本层防御范围，
生产环境建议在出口网关/NAT 层限制目标网段。
"""
import ipaddress
from urllib.parse import urlparse

# 内网域名后缀（大小写不敏感匹配）
_PRIVATE_DOMAIN_SUFFIXES = (
    ".local",
    ".internal",
    ".intranet",
    ".localhost",
    ".lan",
    ".home",
    ".corp",
)


def _looks_numeric_host(host: str) -> bool:
    """inet_aton 数字变形检测：127.1 / 2130706433 / 0177.0.0.1 / 0x7f.1 / 0x7f000001 等
    会被 getaddrinfo 按 inet_aton 语义解析回 loopback/内网，一律拒绝"""

    def _is_num(s: str) -> bool:
        # int(s, 0) 可解析：十进制 / 0x 十六进制均视为数字形态
        try:
            int(s, 0)
            return True
        except ValueError:
            pass
        # 前导零八进制（Python3 的 int(s,0) 不支持）：0177 -> inet_aton 按八进制 127
        return len(s) > 1 and s.startswith("0") and s[1:].isdigit()

    if _is_num(host):
        return True
    parts = host.split(".")
    if 2 <= len(parts) <= 4 and all(_is_num(p) for p in parts):
        return True
    return False


def validate_base_url(url: str) -> str:
    """校验大模型 API base_url，非法时抛 ValueError，合法返回规范化 URL（去尾部斜杠）"""
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("base_url 不能为空")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("base_url 仅支持 https 协议")
    host = parsed.hostname or ""
    # 尾点 FQDN 绕过：https://127.0.0.1./ 等尾点 host 会被 getaddrinfo 解析回本机/内网；
    # rstrip 后再判空，纯点 host（https://...../）一并拒绝
    host = host.rstrip(".")
    if not host:
        raise ValueError("base_url 缺少主机名")
    low = host.lower()
    if low in ("localhost", "localhost.localdomain"):
        raise ValueError("base_url 不允许指向本机")
    if low.endswith(_PRIVATE_DOMAIN_SUFFIXES):
        raise ValueError("base_url 不允许指向内网地址")
    # inet_aton 数字变形（127.1/2130706433/0177.0.0.1）一律拒绝
    if _looks_numeric_host(host):
        raise ValueError("base_url 不允许使用数字形态地址")
    # 字面 IP 形式校验（IPv4/IPv6）
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("base_url 不允许指向本机/内网/保留地址")
    return url
