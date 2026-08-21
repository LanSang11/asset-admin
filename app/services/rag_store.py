# -*- coding: utf-8 -*-
"""独立 RAG 库，不进业务 SQLite。"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app.settings.config import settings

_lock = threading.Lock()


def rag_db_path() -> Path:
    path = Path(settings.BASE_DIR) / "db" / "rag.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(rag_db_path()))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kb_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            sha256 TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES kb_documents(id)
        )
        """
    )
    doc_cols = _columns(con, "kb_documents")
    if "embed_kind" not in doc_cols:
        con.execute("ALTER TABLE kb_documents ADD COLUMN embed_kind TEXT NOT NULL DEFAULT 'none'")
    chunk_cols = _columns(con, "kb_chunks")
    if "embed_kind" not in chunk_cols:
        con.execute("ALTER TABLE kb_chunks ADD COLUMN embed_kind TEXT NOT NULL DEFAULT 'none'")
    return con


def insert_document(
    *,
    title: str,
    source: str,
    sha256: str,
    created_by: int | None,
    chunks: list[tuple[str, list[float]]],
    embed_kind: str = "none",
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    kind = embed_kind if embed_kind in {"api", "none"} else "none"
    with _lock:
        con = _connect()
        try:
            cur = con.execute(
                "INSERT INTO kb_documents(title, source, sha256, created_by, created_at, chunk_count, embed_kind) "
                "VALUES (?,?,?,?,?,?,?)",
                (title, source, sha256, created_by, now, len(chunks), kind),
            )
            doc_id = int(cur.lastrowid)
            con.executemany(
                "INSERT INTO kb_chunks(doc_id, chunk_index, text, embedding, embed_kind) VALUES (?,?,?,?,?)",
                [
                    (doc_id, idx, text, json.dumps(vec, ensure_ascii=False), kind)
                    for idx, (text, vec) in enumerate(chunks)
                ],
            )
            con.commit()
            return doc_id
        finally:
            con.close()


def list_documents() -> list[dict[str, Any]]:
    with _lock:
        con = _connect()
        try:
            rows = con.execute(
                "SELECT id, title, source, sha256, created_by, created_at, chunk_count, embed_kind "
                "FROM kb_documents ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def delete_document(doc_id: int) -> bool:
    with _lock:
        con = _connect()
        try:
            con.execute("DELETE FROM kb_chunks WHERE doc_id=?", (doc_id,))
            con.execute("DELETE FROM kb_documents WHERE id=?", (doc_id,))
            con.commit()
            return con.total_changes > 0
        finally:
            con.close()


def delete_by_source(source: str, keep_id: int | None = None) -> int:
    with _lock:
        con = _connect()
        try:
            if keep_id is None:
                rows = con.execute("SELECT id FROM kb_documents WHERE source=?", (source,)).fetchall()
            else:
                rows = con.execute(
                    "SELECT id FROM kb_documents WHERE source=? AND id<>?",
                    (source, keep_id),
                ).fetchall()
            ids = [int(r["id"]) for r in rows]
            for doc_id in ids:
                con.execute("DELETE FROM kb_chunks WHERE doc_id=?", (doc_id,))
                con.execute("DELETE FROM kb_documents WHERE id=?", (doc_id,))
            con.commit()
            return len(ids)
        finally:
            con.close()


def all_chunks() -> list[dict[str, Any]]:
    with _lock:
        con = _connect()
        try:
            rows = con.execute(
                """
                SELECT c.id, c.doc_id, c.chunk_index, c.text, c.embedding, c.embed_kind, d.title, d.source
                FROM kb_chunks c JOIN kb_documents d ON d.id=c.doc_id
                """
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["embedding"] = json.loads(item["embedding"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    item["embedding"] = []
                item["embed_kind"] = item.get("embed_kind") or "none"
                out.append(item)
            return out
        finally:
            con.close()
