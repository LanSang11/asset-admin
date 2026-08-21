"""插入 AI 助手菜单（业务管理下第 6 个子菜单）。"""
import sqlite3

DB = "/opt/asset-management-system/db/db.sqlite3"
conn = sqlite3.connect(DB)
cur = conn.cursor()

row = cur.execute("SELECT id FROM menu WHERE name='AI助手'").fetchone()
if row:
    print("SKIP: AI助手菜单已存在")
else:
    parent = cur.execute("SELECT id FROM menu WHERE name='业务管理'").fetchone()
    parent_id = parent[0] if parent else 9
    cur.execute(
        "INSERT INTO menu (name, path, icon, \"order\", parent_id, is_hidden, component, keepalive, redirect) "
        # 修复：path 用相对路径，component 用完整路径（与业务管理子菜单一致，否则前端组件无法命中）
        "VALUES ('AI助手', 'ai-assistant', 'mdi:robot-outline', 6, ?, 0, '/business/ai-assistant', 1, NULL)",
        (parent_id,),
    )
    print(f"OK: 插入菜单 AI助手 (parent={parent_id})")

conn.commit()
conn.close()
