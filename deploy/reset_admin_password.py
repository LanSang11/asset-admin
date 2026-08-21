"""重置 admin 密码并恢复强制改密标记（修复测试期间误改密码）。

用法：ADMIN_PASSWORD='新密码' python3 reset_admin_password.py
密码只通过环境变量传入（避免命令行参数泄露到进程列表/Shell 历史），不回显明文。
"""
import os
import sqlite3

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

DB = os.getenv("DB_PATH", "/opt/asset-management-system/db/db.sqlite3")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    raise SystemExit("请通过环境变量 ADMIN_PASSWORD 指定新密码（符合强密码策略：8~32 位含大小写/数字/符号）")

conn = sqlite3.connect(DB)
cur = conn.cursor()

pwd_hash = pwd_context.hash(ADMIN_PASSWORD)
cur.execute(
    "UPDATE 'user' SET password=?, must_change_password=1 WHERE username='admin'",
    (pwd_hash,),
)
print(f"OK: admin 密码已重置，需首次改密（影响行数: {cur.rowcount}）")
conn.commit()
conn.close()
