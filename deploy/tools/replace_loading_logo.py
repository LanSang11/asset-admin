# -*- coding: utf-8 -*-
"""替换 web/public/resource/loading.js 中内嵌的原项目品牌 logo（超长 base64 JPEG）
为纯矢量"资"字图标，去除品牌痕迹。

用法：python deploy/tools/replace_loading_logo.py
"""
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
TARGET = os.path.join(BASE, "web", "public", "resource", "loading.js")

NEW_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">'
    '<circle cx="100" cy="100" r="98" fill="#2080F0"/>'
    '<circle cx="100" cy="100" r="74" fill="none" stroke="#ffffff" stroke-width="6" opacity="0.9"/>'
    '<text x="100" y="136" font-size="104" text-anchor="middle" fill="#ffffff" '
    'font-family="sans-serif" font-weight="bold">资</text></svg>'
)

with open(TARGET, "r", encoding="utf-8") as f:
    lines = f.readlines()

replaced = False
out = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("const svgStr = `"):
        out.append("  const svgStr = `%s`\n" % NEW_SVG)
        replaced = True
    else:
        out.append(line)

if not replaced:
    raise SystemExit("未找到 svgStr 行，脚本未修改任何内容")

with open(TARGET, "w", encoding="utf-8") as f:
    f.writelines(out)

print("loading.js logo 已替换为矢量图标，行数:", len(out))
