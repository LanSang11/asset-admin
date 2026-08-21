"""检查备份 SQLite 数据库完整性（只读）。"""
import sqlite3
import sys

db = sys.argv[1]
conn = sqlite3.connect(db, timeout=10)
cur = conn.cursor()
cur.execute("PRAGMA integrity_check")
print("integrity:", cur.fetchone())
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("tables:", tables)
for t in ["user", "menu", "notifications", "assets", "asset_uses", "aerich"]:
    if t in tables:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(t, cur.fetchone()[0])
conn.close()
