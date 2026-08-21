"""用 VACUUM 后的干净主库覆盖 db.sqlite3（旧 WAL salt 不匹配会被 SQLite 自动忽略）。"""
import shutil
import sqlite3
import sys
import tempfile
import os

src_dir = r"D:\项目\开发\database\data"
tmp = tempfile.mkdtemp(prefix="sqlite_fix_")
for f in ("db.sqlite3", "db.sqlite3-wal", "db.sqlite3-shm"):
    p = os.path.join(src_dir, f)
    if os.path.exists(p):
        shutil.copy(p, os.path.join(tmp, f))

conn = sqlite3.connect(os.path.join(tmp, "db.sqlite3"), timeout=15)
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
print("integrity:", cur.fetchone())
out = os.path.join(tmp, "db_clean.sqlite3")
conn.execute(f"VACUUM INTO '{out.replace(chr(92), '/')}'")
conn.close()
print("clean db size:", os.path.getsize(out))

# 覆盖主库（若被 Navicat 锁定则失败，届时需用户关闭 Navicat）
try:
    shutil.copy2(out, os.path.join(src_dir, "db.sqlite3"))
    print("overwritten db.sqlite3 OK")
except PermissionError as e:
    print("LOCKED:", e)
    sys.exit(2)

# 验证
conn2 = sqlite3.connect(os.path.join(src_dir, "db.sqlite3"), timeout=10)
cur2 = conn2.cursor()
cur2.execute("PRAGMA integrity_check")
print("final integrity:", cur2.fetchone())
for t in ["user", "menu", "notifications", "assets", "asset_uses"]:
    cur2.execute(f"SELECT count(*) FROM {t}")
    print(t, cur2.fetchone()[0])
conn2.close()
shutil.rmtree(tmp, ignore_errors=True)
