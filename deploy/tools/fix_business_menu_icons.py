"""把业务菜单图标修正为与系统管理一致的 Iconify 格式（collection:name）。

用法（本机或云端，在项目根或指定 DB）：
  python deploy/tools/fix_business_menu_icons.py
  python deploy/tools/fix_business_menu_icons.py /path/to/db.sqlite3
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# 与 SideMenu 渲染一致：Iconify collection:name；侧栏折叠 size 由前端统一 18/22
ICON_MAP = {
    "业务管理": "mdi:briefcase-outline",
    "员工管理": "mdi:account-group-outline",
    "资产管理": "mdi:desktop-classic",
    "领用归还": "mdi:swap-horizontal",
    "审批中心": "mdi:clipboard-check-outline",
    "统计看板": "mdi:chart-pie",
    "AI助手": "mdi:robot-outline",
}


def resolve_db(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            raise SystemExit(f"DB 不存在: {p}")
        return p
    candidates = [
        Path("db/db.sqlite3"),
        Path("db.sqlite3"),
        Path("/var/www/asset-system/db/db.sqlite3"),
        Path(r"/path/to/workspace/database\data\db.sqlite3"),
        Path(r"/path/to/workspace/asset-system\db\db.sqlite3"),
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            return c
    raise SystemExit("未找到可用 db.sqlite3，请显式传入路径")


def main() -> None:
    db = resolve_db(sys.argv[1] if len(sys.argv) > 1 else None)
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    updated = 0
    for name, icon in ICON_MAP.items():
        row = cur.execute("SELECT id, icon FROM menu WHERE name=?", (name,)).fetchone()
        if not row:
            print(f"SKIP missing: {name}")
            continue
        mid, old = row
        if old == icon:
            print(f"OK unchanged: {name} -> {icon}")
            continue
        cur.execute("UPDATE menu SET icon=? WHERE id=?", (icon, mid))
        updated += 1
        print(f"FIX {name}: {old!r} -> {icon!r}")
    conn.commit()
    conn.close()
    print(f"DONE db={db} updated={updated}")


if __name__ == "__main__":
    main()
