"""Superuser knowledge-base steward: coverage, duplicates, draft gaps. No auto-ingest."""
from __future__ import annotations

import re
from typing import Any

from fastapi.exceptions import HTTPException

from app.services import rag_store
from app.services.rag_service import (
    builtin_seed_path,
    chunk_text,
    ingest_text,
    lexical_score,
    scan_secrets,
)

_HEADING = re.compile(r"(?m)^##\s+(.+?)\s*$")
COVERED_SCORE = 1.6
DUP_SCORE = 4.2


def canonical_topics() -> list[str]:
    path = builtin_seed_path()
    if not path.is_file():
        return []
    return [line.strip() for line in _HEADING.findall(path.read_text(encoding="utf-8"))]


def analyze() -> dict[str, Any]:
    topics = canonical_topics()
    docs = rag_store.list_documents()
    chunks = rag_store.all_chunks()
    covered: list[dict[str, Any]] = []
    missing: list[str] = []
    weak: list[dict[str, Any]] = []
    for topic in topics:
        best = 0.0
        best_title = ""
        for chunk in chunks:
            score = lexical_score(topic, f"{chunk.get('title') or ''} {chunk.get('text') or ''}")
            if topic and topic in (chunk.get("title") or ""):
                score += 3.0
            if score > best:
                best = score
                best_title = str(chunk.get("title") or "")
        item = {"topic": topic, "score": round(best, 2), "hit": best_title}
        if best >= COVERED_SCORE or (topic and any(topic == (c.get("title") or "") for c in chunks)):
            covered.append(item)
        elif best >= 0.8:
            weak.append(item)
        else:
            missing.append(topic)
    return {
        "topics": topics,
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "covered": covered,
        "weak": weak,
        "missing": missing,
        "duplicates": find_duplicates(chunks),
    }


def find_duplicates(chunks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = chunks if chunks is not None else rag_store.all_chunks()
    found: list[dict[str, Any]] = []
    for i, left in enumerate(rows):
        a = str(left.get("text") or "")
        if len(a) < 24:
            continue
        for right in rows[i + 1 :]:
            b = str(right.get("text") or "")
            if len(b) < 24:
                continue
            if a[:60] == b[:60]:
                score = 9.0
            else:
                score = min(lexical_score(a[:180], b), lexical_score(b[:180], a))
            if score >= DUP_SCORE:
                found.append(
                    {
                        "left": left.get("title") or "",
                        "right": right.get("title") or "",
                        "score": round(score, 2),
                        "snippet": a[:72],
                    }
                )
            if len(found) >= 12:
                return found
    return found


async def draft_missing(topics: list[str] | None = None) -> dict[str, Any]:
    report = analyze()
    wanted = [str(item).strip() for item in (topics or report["missing"] + [w["topic"] for w in report["weak"]]) if str(item).strip()]
    wanted = list(dict.fromkeys(wanted))[:6]
    if not wanted:
        return {"drafts": [], "notice": "没有缺章。"}
    existing = "、".join(report["topics"][:20])
    drafts: list[dict[str, str]] = []
    errors: list[str] = []
    for topic in wanted:
        prompt = [
            {
                "role": "system",
                "content": (
                    "你为资产管理系统写操作说明的一节。只用中文 Markdown。"
                    "禁止写口令、密钥、内网地址、服务器路径、公司客户或未公开流程。"
                    "只写登录用户在页面上能做的操作。不要编造菜单名以外的功能。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"已有章节：{existing}\n"
                    f"请写一节，标题必须是「## {topic}」，正文 4 到 8 句。"
                ),
            },
        ]
        try:
            from app.services.ai_service import chat_completion

            result = await chat_completion(prompt, 0.2, thinking="disabled", timeout=25)
            text = (result.get("content") or "").strip()
        except ValueError as exc:
            errors.append(f"{topic}：{exc}")
            continue
        except Exception:
            errors.append(f"{topic}：生成失败")
            continue
        if not text.startswith("## "):
            text = f"## {topic}\n\n{text}"
        try:
            scan_secrets(text)
        except HTTPException:
            errors.append(f"{topic}：草稿含敏感信息，已丢弃")
            continue
        if not chunk_text(text):
            errors.append(f"{topic}：草稿没有可用文字")
            continue
        drafts.append({"topic": topic, "title": topic, "text": text})
    return {"drafts": drafts, "errors": errors, "notice": "草稿不会自动入库，请点确认后再写入。"}


async def ingest_confirmed(title: str, text: str) -> dict[str, Any]:
    heading = (title or "").strip() or "补充说明"
    body = (text or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="草稿是空的")
    scan_secrets(body)
    if not body.lstrip().startswith("#"):
        body = f"## {heading}\n\n{body}"
    return await ingest_text(title=heading[:32], source="steward", text=body)
