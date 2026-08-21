"""阶段1迁移：user 表加 must_change_password 字段；admin 改为强密码并强制改密。

在容器内执行: python3 deploy/migrate_security.py
不 import app 包（避免循环依赖），内联 argon2 哈希。
"""
import os
import sqlite3
import sys

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

DB = "/opt/asset-management-system/db.sqlite3"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not ADMIN_PASSWORD:
    raise SystemExit("请通过环境变量 ADMIN_PASSWORD 或命令行参数指定新密码")

conn = sqlite3.connect(DB)
cur = conn.cursor()

# 1. 检查字段是否已存在
cols = [row[1] for row in cur.execute("PRAGMA table_info('user')").fetchall()]
if "must_change_password" not in cols:
    cur.execute("ALTER TABLE 'user' ADD COLUMN must_change_password INT NOT NULL DEFAULT 1")
    print("OK: 已添加 must_change_password 字段（默认 1=需改密）")
else:
    print("SKIP: 字段已存在")

# 2. admin 改强密码 + 强制改密
pwd_hash = pwd_context.hash(ADMIN_PASSWORD)
cur.execute(
    "UPDATE 'user' SET password=?, must_change_password=1 WHERE username='admin'",
    (pwd_hash,),
)
print(f"OK: admin 密码已更新为强密码，需首次改密（影响行数: {cur.rowcount}）")

conn.commit()
conn.close()
print("迁移完成")
