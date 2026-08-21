"""开源克隆用假数据（张三/李四 + example.com）。

禁止对现网库执行。不会写入 TOTP 密钥，不会清库。

用法（在业务仓根目录）：
  set DEMO_PASSWORD=你的演示密码
  python deploy/init_oss_demo_data.py --db app.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path



BLOCKED_PATH_MARKERS = (
    "/www/wwwroot",
    "\\www\\wwwroot",
)

# 角色若已由系统初始化存在则绑定；不新建角色，以免空授权。
ROLE_CANDIDATES = {
    "demoemp": ("普通员工", "普通用户"),
    "demomgr": ("部门主管",),
}


def _blocked(db_path: Path) -> bool:
    text = str(db_path.resolve()).replace("/", "\\").lower()
    posix = str(db_path.resolve()).replace("\\", "/").lower()
    return any(marker.lower() in text or marker.lower() in posix for marker in BLOCKED_PATH_MARKERS)


def hash_pwd(password: str) -> str:
    from passlib.context import CryptContext

    return CryptContext(schemes=["argon2"], deprecated="auto").hash(password)


def bind_demo_roles(cur, users: dict) -> None:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_role'")
    if not cur.fetchone():
        return
    for uname, names in ROLE_CANDIDATES.items():
        uid = users.get(uname)
        if not uid:
            continue
        role_id = None
        for name in names:
            cur.execute("SELECT id FROM role WHERE name=?", (name,))
            row = cur.fetchone()
            if row:
                role_id = row[0]
                break
        if not role_id:
            continue
        cur.execute("SELECT 1 FROM user_role WHERE user_id=? AND role_id=?", (uid, role_id))
        if cur.fetchone():
            continue
        cur.execute("INSERT INTO user_role (user_id, role_id) VALUES (?, ?)", (uid, role_id))


def main() -> int:
    parser = argparse.ArgumentParser(description="写入开源假数据，不碰现网库")
    parser.add_argument("--db", required=True, help="本地 SQLite 路径")
    args = parser.parse_args()
    db_path = Path(args.db)
    if _blocked(db_path):
        print("拒绝：看起来像现网库路径。本脚本只允许本地开源演示库。")
        return 2
    password = os.getenv("DEMO_PASSWORD") or ""
    if not password:
        print("请设置环境变量 DEMO_PASSWORD，不要把密码写进仓库")
        return 2
    if not db_path.exists():
        print(f"数据库不存在：{db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM dept")
    if cur.fetchone()[0] == 0:
        cur.execute(
            'INSERT INTO dept (name, desc, is_deleted, "order", parent_id) VALUES (?, ?, 0, 1, 0)',
            ("研发部", "开源演示部门"),
        )

    users = {}
    for uname in ("demoemp", "demomgr"):
        cur.execute("SELECT id FROM user WHERE username=?", (uname,))
        row = cur.fetchone()
        if row:
            users[uname] = row[0]
            continue
        cur.execute(
            "INSERT INTO user (username, email, password, is_active, is_superuser, must_change_password) "
            "VALUES (?, ?, ?, 1, 0, 1)",
            (uname, f"{uname}@example.com", hash_pwd(password)),
        )
        users[uname] = cur.lastrowid

    cur.execute("SELECT id FROM dept WHERE name='研发部'")
    dept_id = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM employees WHERE emp_no='E001'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO employees (emp_no, name, gender, dept_id, position, phone, email, user_id, is_manager, status) "
            "VALUES ('E001', '张三', 1, ?, '工程师', '13800000001', 'zhangsan@example.com', ?, 0, 1)",
            (dept_id, users["demoemp"]),
        )
    cur.execute("SELECT COUNT(*) FROM employees WHERE emp_no='E002'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO employees (emp_no, name, gender, dept_id, position, phone, email, user_id, is_manager, status) "
            "VALUES ('E002', '李四', 1, ?, '研发主管', '13800000002', 'lisi@example.com', ?, 1, 1)",
            (dept_id, users["demomgr"]),
        )

    cur.execute("SELECT COUNT(*) FROM assets WHERE asset_no='AST001'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO assets (asset_no, name, category, model, serial_no, purchase_date, price, status, location) "
            "VALUES ('AST001', '演示笔记本', '电脑', 'DemoBook', 'SN-DEMO-001', '2026-01-15', 5999.00, 2, '仓库A')"
        )

    bind_demo_roles(cur, users)
    conn.commit()
    conn.close()
    print("开源假数据已写入本地库（example.com / 张三 / 李四）。密码不回显。未写入 TOTP 密钥。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
