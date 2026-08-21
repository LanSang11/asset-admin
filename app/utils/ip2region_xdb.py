"""ip2region xdb v2 IPv4 查询（自包含，无第三方依赖）。

格式与 lionsoul2014/ip2region 2.x 的 ip2region.xdb 一致。
文件缺失或查询失败时返回空串，不抛给登录主路径。
"""
from __future__ import annotations

import socket
import struct
from typing import Optional

HEADER_SIZE = 256
VECTOR_INDEX_ROWS = 256
VECTOR_INDEX_COLS = 256
VECTOR_INDEX_SIZE = 8
SEGMENT_INDEX_SIZE = 14


def _u32_le(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<I", buf, offset)[0]


def _u16_le(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<H", buf, offset)[0]


def ipv4_to_long(ip: str) -> Optional[int]:
    text = (ip or "").strip()
    if not text or ":" in text:
        return None
    if "%" in text:
        text = text.split("%", 1)[0]
    try:
        packed = socket.inet_aton(text)
    except OSError:
        return None
    return struct.unpack("!L", packed)[0]


class XdbSearcher:
    """内存加载整份 xdb，适合本机 10MB 级库。"""

    def __init__(self, content: bytes):
        if not content or len(content) < HEADER_SIZE + VECTOR_INDEX_SIZE:
            raise ValueError("invalid xdb buffer")
        self._buf = content

    @classmethod
    def from_file(cls, path: str) -> "XdbSearcher":
        with open(path, "rb") as f:
            return cls(f.read())

    def search(self, ip: str) -> str:
        ip_long = ipv4_to_long(ip)
        if ip_long is None:
            return ""
        il0 = (ip_long >> 24) & 0xFF
        il1 = (ip_long >> 16) & 0xFF
        idx = il0 * VECTOR_INDEX_COLS * VECTOR_INDEX_SIZE + il1 * VECTOR_INDEX_SIZE
        vi_off = HEADER_SIZE + idx
        if vi_off + 8 > len(self._buf):
            return ""
        start_ptr = _u32_le(self._buf, vi_off)
        end_ptr = _u32_le(self._buf, vi_off + 4)
        if end_ptr < start_ptr:
            return ""
        data_len = 0
        data_ptr = 0
        low = 0
        high = (end_ptr - start_ptr) // SEGMENT_INDEX_SIZE
        while low <= high:
            mid = (low + high) >> 1
            pos = start_ptr + mid * SEGMENT_INDEX_SIZE
            if pos + SEGMENT_INDEX_SIZE > len(self._buf):
                break
            sip = _u32_le(self._buf, pos)
            eip = _u32_le(self._buf, pos + 4)
            if ip_long < sip:
                high = mid - 1
            elif ip_long > eip:
                low = mid + 1
            else:
                data_len = _u16_le(self._buf, pos + 8)
                data_ptr = _u32_le(self._buf, pos + 10)
                break
        if data_len <= 0 or data_ptr <= 0:
            return ""
        end = data_ptr + data_len
        if end > len(self._buf):
            return ""
        try:
            return self._buf[data_ptr:end].decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""
