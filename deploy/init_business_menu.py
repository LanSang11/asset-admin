"""阶段2 菜单初始化：插入「业务管理」一级菜单 + 员工/资产管理等子菜单。"""
import sqlite3

DB = "/opt/asset-management-system/db/db.sqlite3"

conn = sqlite3.connect(DB)
cur = conn.cursor()

# 检查是否已存在
exists = cur.execute("SELECT id FROM menu WHERE name='业务管理'").fetchone()
if exists:
    print("SKIP: 业务管理菜单已存在")
else:
    # 图标必须用 Iconify 的 collection:name（与系统管理一致），禁止 icon-mdi: 前缀
    cur.execute(
        "INSERT INTO menu (name, path, icon, \"order\", parent_id, is_hidden, component, keepalive, redirect) "
        "VALUES ('业务管理', '/business', 'mdi:briefcase-outline', 2, 0, 0, 'Layout', 1, NULL)"
    )
    parent_id = cur.lastrowid

    children = [
        ("员工管理", "employee", "/business/employee", "mdi:account-group-outline", 1),
        ("资产管理", "asset", "/business/asset", "mdi:desktop-classic", 2),
        ("领用归还", "asset_use", "/business/asset-use", "mdi:swap-horizontal", 3),
        ("审批中心", "approval", "/business/approval", "mdi:clipboard-check-outline", 4),
        ("统计看板", "dashboard", "/business/dashboard", "mdi:chart-pie", 5),
    ]
    for name, path, full_path, icon, order in children:
        cur.execute(
            "INSERT INTO menu (name, path, icon, \"order\", parent_id, is_hidden, component, keepalive, redirect) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, 1, NULL)",
            # 修复：path 用相对路径（拼接父级 /business 得到完整路由），
            # component 用完整路径（前端 vueModules['/src/views' + component + '/index.vue'] 才能命中组件）
            (name, path, icon, order, parent_id, full_path),
        )
        print(f"OK: 插入菜单 {name} -> {full_path}")
    print(f"OK: 插入一级菜单 业务管理 (id={parent_id})")

conn.commit()
conn.close()
print("菜单初始化完成")
