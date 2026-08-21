# -*- coding: utf-8 -*-
"""知识库：切片 + 中文词面检索；仅在有合格 API embedding 时叠加语义。

禁止把哈希向量当成 embedding。向量不进业务库。
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import httpx
from fastapi.exceptions import HTTPException

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.services import rag_store
from app.settings.config import settings
from app.utils.crypto import decrypt_secret
from app.utils.net_utils import validate_base_url

logger = logging.getLogger(__name__)

MAX_KB_BYTES = 2 * 1024 * 1024
ALLOWED_KB_EXT = {".txt", ".md"}
CHUNK_SIZE = 400
CHUNK_OVERLAP = 60
MIN_REAL_EMBED_DIM = 256
SECRET_RE = re.compile(
    r"(BEGIN (RSA |OPENSSH )?PRIVATE KEY|SECRET_KEY|api[_-]?key\s*[:=]|password\s*[:=]|"
    r"totp_secret|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)",
    re.I,
)
_ASCII_TOKEN = re.compile(r"[a-z0-9]{2,}")
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff]")
_PUNCT = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]<>《》·…—\-]+")
_HEADING_SPLIT = re.compile(r"(?m)(?=^#{1,3} )")
_QUERY_STOP = {
    "怎么",
    "如何",
    "什么",
    "怎么用",
    "能不能",
    "可以",
    "是否",
    "有没有",
    "是不是",
    "一下",
    "这个",
    "那个",
    "请问",
    "告诉",
    "解释",
}

DEGRADED_NOTICE = (
    "当前没有合格语义向量（对话用的 Key 往往没有 embeddings 接口）。"
    "已用中文词面检索，不会用哈希假装向量。有合格 embedding 后再叠加语义。"
)
HYBRID_NOTICE = "词面检索为主，并已叠加合格语义向量。"
EMPTY_NOTICE = "知识库还没有文档。请先导入内置操作说明或上传自己写的 txt/md。"
QUERY_EMBED_FAIL_NOTICE = "本次未能取得合格语义向量，已仅用中文词面检索。"


def scan_secrets(text: str) -> None:
    if SECRET_RE.search(text or ""):
        raise HTTPException(status_code=400, detail="文档疑似含口令或内网信息，已拒绝入库")


def _window_chunks(raw: str) -> list[str]:
    parts: list[str] = []
    start = 0
    n = len(raw)
    while start < n:
        end = min(n, start + CHUNK_SIZE)
        piece = raw[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return parts


def chunk_text(text: str) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []
    sections = [part.strip() for part in _HEADING_SPLIT.split(raw) if part.strip()]
    if len(sections) <= 1:
        return _window_chunks(raw)
    parts: list[str] = []
    for section in sections:
        if len(section) <= CHUNK_SIZE:
            parts.append(section)
        else:
            parts.extend(_window_chunks(section))
    return parts


def is_real_embedding(vec: Any) -> bool:
    if not isinstance(vec, (list, tuple)) or len(vec) < MIN_REAL_EMBED_DIM:
        return False
    try:
        return any(float(x) != 0.0 for x in vec[:32])
    except (TypeError, ValueError):
        return False


def tokenize_zh(text: str, *, for_query: bool = False) -> list[str]:
    raw = (text or "").lower()
    tokens: list[str] = []
    tokens.extend(_ASCII_TOKEN.findall(raw))
    chars = _CJK_CHAR.findall(raw)
    tokens.extend(chars[i] + chars[i + 1] for i in range(len(chars) - 1))
    tokens.extend(chars[i] + chars[i + 1] + chars[i + 2] for i in range(len(chars) - 2))
    if for_query:
        tokens = [tok for tok in tokens if tok not in _QUERY_STOP]
    return tokens


def lexical_score(query: str, doc: str) -> float:
    q = (query or "").strip()
    d = doc or ""
    if not q or not d:
        return 0.0
    q_tokens = tokenize_zh(q, for_query=True)
    if not q_tokens:
        return 0.0
    d_tokens = tokenize_zh(d)
    d_counts = Counter(d_tokens)
    score = 0.0
    weight = 0.0
    q_counts = Counter(q_tokens)
    for token, qn in q_counts.items():
        is_cjk = bool(_CJK_CHAR.search(token))
        tw = 3.0 if is_cjk and len(token) >= 3 else (2.2 if is_cjk else 1.6)
        weight += tw * qn
        dc = d_counts.get(token, 0)
        if dc:
            score += tw * qn * (dc / (dc + 1.4))
    heading = d.split("\n", 1)[0]
    for token in q_counts:
        if len(token) >= 2 and token in heading:
            score += 1.8
    compact_q = _PUNCT.sub("", q)
    compact_d = _PUNCT.sub("", d)
    if len(compact_q) >= 2 and compact_q in compact_d:
        score += 2.4
    else:
        for piece in _PUNCT.split(q):
            piece = piece.strip()
            if piece in _QUERY_STOP:
                continue
            if len(piece) >= 2 and piece in d:
                score += 1.2
    return score / (weight or 1.0)


def cosine(a: Iterable[float], b: Iterable[float]) -> float:
    x = list(a)
    y = list(b)
    n = min(len(x), len(y))
    if not n or len(x) != len(y):
        return 0.0
    return sum(x[i] * y[i] for i in range(n))


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def try_embed_texts(texts: list[str]) -> tuple[list[list[float]] | None, str]:
    """只返回合格 API 向量。失败返回 (None, 原因)，绝不写哈希假向量。"""
    if not texts:
        return None, "empty"
    try:
        user = await User.get(id=CTX_USER_ID.get())
        cfg = user.api_config or {}
        api_key = decrypt_secret(cfg.get("api_key_enc", ""))
        if not api_key:
            return None, "no_key"
        base_url = validate_base_url(cfg.get("base_url") or "https://api.deepseek.com")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": cfg.get("embed_model") or "text-embedding-3-small", "input": texts},
            )
        if resp.status_code != 200:
            logger.info("embeddings API unavailable: status=%s", resp.status_code)
            return None, "unavailable"
        data = resp.json().get("data") or []
        vecs = [item.get("embedding") or [] for item in data]
        if len(vecs) != len(texts) or not all(is_real_embedding(v) for v in vecs):
            logger.info("embeddings API returned unusable vectors")
            return None, "unavailable"
        return [_l2_normalize([float(x) for x in v]) for v in vecs], "ok"
    except Exception as exc:
        logger.info("embeddings skipped, lexical-only: %s", exc)
        return None, "unavailable"


def builtin_seed_path() -> Path:
    name = "kb-seed-资产系统操作说明.md"
    roots = [Path(settings.BASE_DIR), Path(__file__).resolve().parents[2]]
    for root in roots:
        for rel in (Path("deploy") / "data" / name, Path("docs") / name):
            path = root / rel
            if path.is_file():
                return path
    return Path(settings.BASE_DIR) / "docs" / name


async def ingest_text(*, title: str, source: str, text: str) -> dict:
    scan_secrets(text)
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="文档没有可入库的文字")
    vecs, embed_status = await try_embed_texts(chunks)
    if vecs is None:
        pairs = [(piece, []) for piece in chunks]
        kind = "none"
    else:
        pairs = list(zip(chunks, vecs))
        kind = "api"
    sha = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()
    doc_id = rag_store.insert_document(
        title=title[:120],
        source=source[:80],
        sha256=sha,
        created_by=CTX_USER_ID.get(),
        chunks=pairs,
        embed_kind=kind,
    )
    return {
        "id": doc_id,
        "chunk_count": len(chunks),
        "title": title[:120],
        "embed_kind": kind,
        "embed_status": embed_status,
    }


async def ingest_upload(filename: str, data: bytes) -> dict:
    if not data or len(data) > MAX_KB_BYTES:
        raise HTTPException(status_code=400, detail="知识库文件须小于 2MB")
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_KB_EXT:
        raise HTTPException(status_code=400, detail="知识库只接受 .txt / .md")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="请上传 UTF-8 文本") from exc
    return await ingest_text(title=Path(filename).stem or "未命名", source="upload", text=text)


async def seed_builtin() -> dict:
    path = builtin_seed_path()
    if not path.is_file():
        raise HTTPException(status_code=400, detail="内置操作说明不存在")
    text = path.read_text(encoding="utf-8")
    result = await ingest_text(title="资产系统操作说明", source="builtin", text=text)
    rag_store.delete_by_source("builtin", keep_id=result["id"])
    return result


def _section_title(text: str, fallback: str = "") -> str:
    first_line = (text or "").lstrip().split("\n", 1)[0].strip()
    if not first_line.startswith("#"):
        return fallback or "资料"
    first = re.sub(r"^#{1,3}\s*", "", first_line).strip().strip("《》[]【】")
    if 2 <= len(first) <= 32:
        return first
    return fallback or "资料"


def _snippet(text: str, query: str = "", limit: int = 72) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    compact = re.sub(r"^#{1,3}\s*", "", compact)
    if not compact:
        return ""
    pos = -1
    for token in sorted(tokenize_zh(query, for_query=True), key=len, reverse=True):
        if len(token) >= 2:
            idx = compact.lower().find(token.lower())
            if idx >= 0:
                pos = idx
                break
    if pos < 0:
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "…"
    start = max(0, pos - 8)
    end = min(len(compact), pos + max(40, limit - 8))
    snippet = compact[start:end].strip()
    if start:
        snippet = "…" + snippet
    if end < len(compact):
        snippet = snippet.rstrip() + "…"
    return snippet


def rank_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    *,
    query_vec: list[float] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    lex_raw = [
        lexical_score(question, f"{row.get('title') or ''} {row.get('text') or ''}") for row in chunks
    ]
    max_lex = max(lex_raw) or 1.0
    use_semantic = bool(query_vec) and any(is_real_embedding(row.get("embedding")) for row in chunks)
    scored: list[tuple[float, float, float, dict]] = []
    for row, lex in zip(chunks, lex_raw):
        lex_n = lex / max_lex if max_lex else 0.0
        sem = 0.0
        vec = row.get("embedding") or []
        if use_semantic and is_real_embedding(vec) and query_vec and len(vec) == len(query_vec):
            sem = max(0.0, cosine(query_vec, vec))
        final = (0.7 * lex_n + 0.3 * sem) if use_semantic else lex
        if final > 0:
            scored.append((final, lex, sem, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = []
    for final, lex, sem, row in scored[:top_k]:
        body = row.get("text") or ""
        doc_title = row.get("title") or ""
        hits.append(
            {
                "score": round(final, 4),
                "lexical_score": round(lex, 4),
                "semantic_score": round(sem, 4),
                "title": _section_title(body, doc_title),
                "doc_title": doc_title,
                "source": row.get("source") or "",
                "text": body,
                "snippet": _snippet(body, question),
            }
        )
    return hits


def index_status() -> dict[str, Any]:
    docs = rag_store.list_documents()
    chunks = rag_store.all_chunks()
    real = sum(1 for row in chunks if is_real_embedding(row.get("embedding")))
    if not docs:
        return {
            "doc_count": 0,
            "chunk_count": 0,
            "real_embedding_chunks": 0,
            "mode": "lexical",
            "degraded": True,
            "notice": EMPTY_NOTICE,
        }
    degraded = real == 0
    return {
        "doc_count": len(docs),
        "chunk_count": len(chunks),
        "real_embedding_chunks": real,
        "mode": "hybrid" if not degraded else "lexical",
        "degraded": degraded,
        "notice": DEGRADED_NOTICE if degraded else HYBRID_NOTICE,
    }


async def retrieve(question: str, top_k: int = 5) -> tuple[list[dict], dict[str, Any]]:
    chunks = rag_store.all_chunks()
    status = index_status()
    q_vec = None
    embed_status = "none" if status["real_embedding_chunks"] == 0 else "skipped"
    if status["real_embedding_chunks"] > 0:
        vecs, embed_status = await try_embed_texts([question])
        if vecs:
            q_vec = vecs[0]
            status["mode"] = "hybrid"
            status["degraded"] = False
            status["notice"] = HYBRID_NOTICE
        else:
            status["mode"] = "lexical"
            status["degraded"] = True
            status["notice"] = QUERY_EMBED_FAIL_NOTICE
    status["embed_status"] = embed_status
    hits = rank_chunks(question, chunks, query_vec=q_vec, top_k=top_k)
    return hits, status


def _citations(hits: list[dict]) -> list[dict[str, Any]]:
    out = []
    for idx, hit in enumerate(hits, start=1):
        out.append(
            {
                "n": idx,
                "title": hit.get("title") or "",
                "source": hit.get("source") or "",
                "snippet": hit.get("snippet") or _snippet(hit.get("text") or ""),
            }
        )
    return out


def _format_citations(cites: list[dict]) -> str:
    if not cites:
        return ""
    lines = ["引用："]
    for item in cites:
        lines.append(f"{item['n']}. 《{item['title']}》{item['snippet']}")
    return "\n".join(lines)


async def answer(question: str) -> dict:
    q = (question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="请输入问题")
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="问题过长")
    scan_secrets(q)
    hits, retrieval = await retrieve(q)
    cites = _citations(hits)
    if not hits:
        empty = "知识库里还没有能回答这个问题的资料。请先上传白名单文档。"
        notice = retrieval.get("notice") or ""
        text = f"{notice}\n\n{empty}".strip() if retrieval.get("degraded") else empty
        return {"answer": text, "hits": [], "citations": [], "retrieval": retrieval}
    context = "\n\n".join(f"[{item['title']}]\n{item['text']}" for item in hits)
    prompt = [
        {
            "role": "system",
            "content": (
                "你是本系统知识库助手。只根据给定资料用中文回答。"
                "资料没有的就说不知道，不要编造。回答末尾不要自己编引用编号。"
            ),
        },
        {"role": "user", "content": f"资料：\n{context}\n\n问题：{q}"},
    ]
    top = hits[0]
    extract = f"根据《{top.get('title') or '资料'}》：{top.get('snippet') or _snippet(top.get('text') or '', q)}"
    if len(hits) > 1:
        extract += "\n另见：" + "；".join(f"《{item['title']}》" for item in hits[1:3])
    try:
        import asyncio

        from app.services.ai_service import chat_completion

        result = await asyncio.wait_for(chat_completion(prompt, 0.2), timeout=30)
        text = (result.get("content") or "").strip() or extract
    except ValueError:
        text = extract
    except asyncio.TimeoutError:
        text = "知识库问答超时，请稍后重试。"
    except httpx.TimeoutException:
        text = "知识库问答超时，请稍后重试。"
    except Exception:
        text = extract
    cite_block = _format_citations(cites)
    if cite_block and "引用：" not in text:
        text = text.rstrip() + "\n\n" + cite_block
    return {"answer": text, "hits": hits, "citations": cites, "retrieval": retrieval}
