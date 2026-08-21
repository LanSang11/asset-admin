#!/bin/bash
# Daily hot backup for the application SQLite databases (WAL-safe backup API).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
DESTDIR="${BACKUP_DIR:-$APP_DIR/db/backups}"
KEEP_DAILY="${KEEP_DAILY:-14}"
PY="${PYTHON_BIN:-$APP_DIR/venv/bin/python}"

if [ ! -x "$PY" ]; then
  PY=python3
fi

mkdir -p "$DESTDIR"
TS="$(date +%Y%m%d-%H%M%S)"

backup_one() {
  local src="$1"
  local out="$2"
  if [ ! -f "$src" ]; then
    echo "skip missing $src"
    return 0
  fi
  SRC="$src" OUT="$out" "$PY" - <<'PY'
import os
import sqlite3

src = os.environ["SRC"]
out = os.environ["OUT"]
src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(out)
with dst_conn:
    src_conn.backup(dst_conn)
dst_conn.close()
src_conn.close()
print("OK", out, os.path.getsize(out))
PY
}

backup_one "$APP_DIR/db/db.sqlite3" "$DESTDIR/db-${TS}-daily.sqlite3"
backup_one "$APP_DIR/db/rag.sqlite3" "$DESTDIR/rag-${TS}-daily.sqlite3"

find "$DESTDIR" -name 'db-*-daily.sqlite3' -mtime +"$KEEP_DAILY" -delete
find "$DESTDIR" -name 'rag-*-daily.sqlite3' -mtime +"$KEEP_DAILY" -delete
echo "[$(date '+%F %T')] daily backup done" >> "$DESTDIR/backup.log"
