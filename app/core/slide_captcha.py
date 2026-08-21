# -*- coding: utf-8 -*-
"""登录用开源滑块验证码：每次登录强制；服务端出图 + 一次性校验。

设计：
- captcha_id 短时有效（默认 90s），校验后立即作废（无论对错）
- 只返回背景图 + 拼图块 + 纵向 y，不返回正确 x
- 允许 ± 容差像素（默认 5px）
- 缺口不做「整块纯黑遮罩」（降低简单像素差分一眼识破）
- 内存存储；每 IP 出题限流（防滥刷图）
"""
from __future__ import annotations

import base64
import io
import random
import secrets
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore
    ImageEnhance = None  # type: ignore


class SlideCaptchaStore:
    def __init__(
        self,
        ttl_seconds: int = 90,
        tolerance: int = 5,
        max_entries: int = 5000,
        width: int = 300,
        height: int = 150,
        piece: int = 42,
        issue_per_ip_per_min: int = 30,
    ):
        self.ttl_seconds = ttl_seconds
        self.tolerance = tolerance
        self.max_entries = max_entries
        self.width = width
        self.height = height
        self.piece = piece
        self.issue_per_ip_per_min = issue_per_ip_per_min
        self._items: Dict[str, dict] = {}
        self._tickets: Dict[str, dict] = {}
        self._issue_log: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def _purge_locked(self, now: float) -> None:
        dead = [k for k, v in self._items.items() if v["expire"] <= now]
        for k in dead:
            self._items.pop(k, None)
        dead_tickets = [k for k, v in self._tickets.items() if v["expire"] <= now]
        for k in dead_tickets:
            self._tickets.pop(k, None)
        if len(self._items) > self.max_entries:
            ordered = sorted(self._items.items(), key=lambda kv: kv[1]["expire"])
            for k, _ in ordered[: len(self._items) - self.max_entries]:
                self._items.pop(k, None)

    def allow_issue(self, ip: str) -> bool:
        """出题限流：每 IP 每分钟 issue_per_ip_per_min 次。"""
        now = time.time()
        with self._lock:
            dq = self._issue_log[ip or "unknown"]
            while dq and now - dq[0] > 60:
                dq.popleft()
            if len(dq) >= self.issue_per_ip_per_min:
                return False
            dq.append(now)
            return True

    def create(self, client_ip: str = "unknown") -> dict:
        if Image is None:
            raise RuntimeError("服务器未安装 Pillow，无法生成滑块验证码")
        if not self.allow_issue(client_ip):
            raise RuntimeError("验证码请求过于频繁，请稍后再试")

        w, h, p = self.width, self.height, self.piece
        gap_x = random.randint(p + 12, w - p - 18)
        gap_y = random.randint(14, h - p - 14)

        bg = self._make_background(w, h)
        piece_img = self._cut_piece(bg, gap_x, gap_y, p)
        bg = self._carve_slot(bg, gap_x, gap_y, p)

        captcha_id = secrets.token_urlsafe(18)
        now = time.time()
        with self._lock:
            self._purge_locked(now)
            self._items[captcha_id] = {
                "x": gap_x,
                "expire": now + self.ttl_seconds,
            }

        return {
            "captcha_id": captcha_id,
            "bg_base64": self._png_b64(bg),
            "piece_base64": self._png_b64(piece_img),
            "y": gap_y,
            "thumb_width": p,
            "bg_width": w,
            "bg_height": h,
            "ttl": self.ttl_seconds,
        }

    def verify_and_consume(self, captcha_id: Optional[str], captcha_x: Optional[float]) -> Tuple[bool, str]:
        """一次性校验。返回 (ok, reason)。无论成败都删除 id。"""
        if not captcha_id:
            return False, "请完成滑块验证"
        try:
            x = float(captcha_x) if captcha_x is not None else None
        except (TypeError, ValueError):
            x = None
        if x is None:
            return False, "请完成滑块验证"

        now = time.time()
        with self._lock:
            self._purge_locked(now)
            item = self._items.pop(captcha_id, None)
            if not item:
                return False, "验证码已失效，请刷新后重试"
            if item["expire"] <= now:
                return False, "验证码已过期，请刷新后重试"
            if abs(item["x"] - x) <= self.tolerance:
                return True, "ok"
            return False, "滑块位置不正确，请重试"

    def verify_and_issue_ticket(
        self,
        captcha_id: Optional[str],
        captcha_x: Optional[float],
        client_ip: str,
    ) -> Tuple[bool, str, Optional[str]]:
        ok, reason = self.verify_and_consume(captcha_id, captcha_x)
        if not ok:
            return False, reason, None
        ticket = secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            self._purge_locked(now)
            self._tickets[ticket] = {
                "ip": client_ip or "unknown",
                "expire": now + self.ttl_seconds,
            }
        return True, "ok", ticket

    def consume_ticket(self, ticket: Optional[str], client_ip: str) -> Tuple[bool, str]:
        if not ticket:
            return False, "请完成滑块验证"
        now = time.time()
        with self._lock:
            self._purge_locked(now)
            item = self._tickets.pop(ticket, None)
            if not item:
                return False, "滑块验证已失效，请重新验证"
            if item["expire"] <= now:
                return False, "滑块验证已过期，请重新验证"
            if item["ip"] != (client_ip or "unknown"):
                return False, "滑块验证环境已变化，请重新验证"
            return True, "ok"

    # ---- 绘图（降低「纯色缺口」一眼 CV 检出；非军用级）----
    def _make_background(self, w: int, h: int) -> "Image.Image":
        img = Image.new("RGB", (w, h))
        # 多色块底
        draw = ImageDraw.Draw(img)
        for _ in range(18):
            x1, y1 = random.randint(-20, w), random.randint(-20, h)
            x2, y2 = x1 + random.randint(40, 120), y1 + random.randint(30, 90)
            col = (
                random.randint(40, 200),
                random.randint(60, 200),
                random.randint(90, 230),
            )
            draw.ellipse((x1, y1, x2, y2), fill=col)
        # 细线干扰
        for _ in range(40):
            x1, y1 = random.randint(0, w), random.randint(0, h)
            x2, y2 = random.randint(0, w), random.randint(0, h)
            col = (random.randint(20, 255), random.randint(20, 255), random.randint(20, 255))
            draw.line((x1, y1, x2, y2), fill=col, width=random.randint(1, 2))
        # 点噪
        px = img.load()
        for _ in range(w * h // 8):
            x, y = random.randint(0, w - 1), random.randint(0, h - 1)
            n = random.randint(-30, 30)
            r, g, b = px[x, y]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
        img = img.filter(ImageFilter.SMOOTH_MORE)
        return img

    def _cut_piece(self, bg: "Image.Image", gx: int, gy: int, p: int) -> "Image.Image":
        rgba = bg.convert("RGBA")
        piece = rgba.crop((gx, gy, gx + p, gy + p)).copy()
        mask = Image.new("L", (p, p), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((1, 1, p - 2, p - 2), radius=8, fill=255)
        out = Image.new("RGBA", (p, p), (0, 0, 0, 0))
        out.paste(piece, (0, 0), mask)
        # 轻微描边（前端可辨，CV 仍可利用边缘——客观存在）
        border = ImageDraw.Draw(out)
        border.rounded_rectangle((1, 1, p - 2, p - 2), radius=8, outline=(255, 255, 255, 160), width=1)
        return out

    def _carve_slot(self, bg: "Image.Image", gx: int, gy: int, p: int) -> "Image.Image":
        """挖槽：用周围像素扰动填充，避免大块均匀半透明黑。"""
        rgba = bg.convert("RGBA")
        px = rgba.load()
        # 采样槽外颜色做底
        for yy in range(gy, gy + p):
            for xx in range(gx, gx + p):
                # 圆角区域外跳过（近似）
                if self._outside_rounded(xx - gx, yy - gy, p, 8):
                    continue
                # 从邻域取色 + 变暗少许 + 噪点
                sx = min(max(0, xx + random.randint(-8, 8)), rgba.width - 1)
                sy = min(max(0, yy + random.randint(-8, 8)), rgba.height - 1)
                # 尽量取槽外
                if gx <= sx < gx + p and gy <= sy < gy + p:
                    sx = min(rgba.width - 1, gx + p + random.randint(2, 10))
                r, g, b, a = px[sx, sy]
                dim = random.randint(18, 40)
                px[xx, yy] = (
                    max(0, r - dim + random.randint(-10, 10)),
                    max(0, g - dim + random.randint(-10, 10)),
                    max(0, b - dim + random.randint(-10, 10)),
                    255,
                )
        # 细边缘（帮助真人，也利于 CV——权衡已标明）
        draw = ImageDraw.Draw(rgba)
        draw.rounded_rectangle(
            (gx, gy, gx + p - 1, gy + p - 1),
            radius=8,
            outline=(255, 255, 255, 90),
            width=1,
        )
        return rgba

    @staticmethod
    def _outside_rounded(lx: int, ly: int, p: int, r: int) -> bool:
        # 简易圆角：四角外圆外则 true
        if r <= 0:
            return False
        corners = [
            (lx, ly, r, r),  # 相对圆心
        ]
        # top-left
        if lx < r and ly < r:
            return (lx - r) ** 2 + (ly - r) ** 2 > r * r
        # top-right
        if lx >= p - r and ly < r:
            return (lx - (p - 1 - r)) ** 2 + (ly - r) ** 2 > r * r
        # bottom-left
        if lx < r and ly >= p - r:
            return (lx - r) ** 2 + (ly - (p - 1 - r)) ** 2 > r * r
        # bottom-right
        if lx >= p - r and ly >= p - r:
            return (lx - (p - 1 - r)) ** 2 + (ly - (p - 1 - r)) ** 2 > r * r
        return False

    @staticmethod
    def _png_b64(img: "Image.Image") -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


slide_captcha = SlideCaptchaStore()
