# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import fastapi  # noqa: F401

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi")
class TestRagKb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from app.settings import config as cfg

        self._old = cfg.settings.BASE_DIR
        cfg.settings.BASE_DIR = self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, "db"), exist_ok=True)

    def tearDown(self):
        from app.settings import config as cfg

        cfg.settings.BASE_DIR = self._old
        self.tmp.cleanup()

    def test_chunk_and_secret_scan(self):
        from fastapi.exceptions import HTTPException

        from app.services.rag_service import chunk_text, lexical_score, scan_secrets

        parts = chunk_text("调拨只能改领用人。" * 80)
        self.assertGreaterEqual(len(parts), 2)
        related = lexical_score("调拨 领用人 在用", "调拨之后资产仍为在用，只换领用人")
        unrelated = lexical_score("调拨 领用人 在用", "完全无关的天气预报和股票行情")
        self.assertGreater(related, unrelated)
        with self.assertRaises(HTTPException):
            scan_secrets("password=abc123")
        scan_secrets("不要上传未公开内部资料")

    def test_heading_chunks_rank_section(self):
        from app.services.rag_service import chunk_text, rank_chunks

        text = (
            "# 说明\n总述本系统怎么用。\n\n"
            "## 调拨\n只能调拨在用资产，主管一级审批，管理员终审。\n\n"
            "## 盘点\n对账面资产逐项确认，盘点不是删除资产。"
        )
        parts = chunk_text(text)
        self.assertGreaterEqual(len(parts), 3)
        chunks = [{"title": "说明", "source": "builtin", "text": part, "embedding": []} for part in parts]
        self.assertIn("盘点", rank_chunks("盘点是干什么", chunks, top_k=1)[0]["text"])
        self.assertIn("调拨", rank_chunks("调拨怎么审批", chunks, top_k=1)[0]["text"])
        from app.services.rag_service import _section_title, _snippet

        self.assertEqual(_section_title("## 调拨\n只能调拨在用。", "操作说明"), "调拨")
        padded = ("无关前言。" * 18) + "只能调拨在用资产，主管一级审批。" + ("无关后记。" * 18)
        snip = _snippet(padded, "调拨怎么审批")
        self.assertIn("只能调拨", snip)
        self.assertLess(snip.find("调拨"), 12)

    def test_no_silent_hash_embedding(self):
        from app.services.rag_service import is_real_embedding

        with open(os.path.join(ROOT, "app", "services", "rag_service.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("def lexical_embed", src)
        self.assertNotIn("fallback lexical", src)
        self.assertFalse(is_real_embedding([0.1] * 128))
        self.assertFalse(is_real_embedding([]))
        self.assertTrue(is_real_embedding([0.01] * 256))

    def test_store_roundtrip(self):
        from app.services import rag_store

        doc_id = rag_store.insert_document(
            title="操作说明",
            source="test",
            sha256="a" * 32,
            created_by=1,
            chunks=[("调拨通过后资产仍为在用", [])],
            embed_kind="none",
        )
        rows = rag_store.list_documents()
        self.assertEqual(rows[0]["id"], doc_id)
        self.assertEqual(rows[0]["embed_kind"], "none")
        chunks = rag_store.all_chunks()
        self.assertEqual(chunks[0]["title"], "操作说明")
        self.assertEqual(chunks[0]["embedding"], [])
        rag_store.delete_document(doc_id)
        self.assertEqual(rag_store.list_documents(), [])

    def test_lexical_retrieve_ignores_fake_128d(self):
        from app.services import rag_store
        from app.services.rag_service import rank_chunks, index_status

        rag_store.insert_document(
            title="资产系统操作说明",
            source="builtin",
            sha256="b" * 32,
            created_by=1,
            chunks=[
                ("只能调拨在用且已有领用人的资产。通过后资产仍为在用，只更换领用人。", [0.2] * 128),
                ("打开资产系统地址，输入账号密码，拖完滑块才能登录。", [0.9] * 128),
            ],
            embed_kind="none",
        )
        status = index_status()
        self.assertTrue(status["degraded"])
        self.assertEqual(status["mode"], "lexical")
        self.assertIn("词面", status["notice"])
        hits = rank_chunks("调拨怎么审批", rag_store.all_chunks(), query_vec=[0.9] * 128, top_k=2)
        self.assertTrue(hits)
        self.assertIn("调拨", hits[0]["text"])
        self.assertEqual(hits[0]["semantic_score"], 0.0)

    def test_answer_includes_citations(self):
        from app.services import rag_store
        from app.services import rag_service

        rag_store.insert_document(
            title="资产系统操作说明",
            source="builtin",
            sha256="c" * 32,
            created_by=1,
            chunks=[("调拨通过后资产仍为在用，只更换领用人。普通员工只能申请调拨自己名下的资产。", [])],
            embed_kind="none",
        )
        result = asyncio.run(rag_service.answer("调拨通过后资产还是在用吗？"))
        self.assertIn("引用", result["answer"])
        self.assertTrue(result["citations"])
        self.assertEqual(result["citations"][0]["title"], "资产系统操作说明")
        self.assertTrue(result["retrieval"]["degraded"])
        self.assertIn("哈希", result["retrieval"]["notice"])

    def test_hybrid_ranks_with_real_vectors(self):
        from app.services.rag_service import rank_chunks

        related = [0.0, 1.0] + [0.0] * 254
        unrelated = [1.0, 0.0] + [0.0] * 254
        query = [0.0, 1.0] + [0.0] * 254
        chunks = [
            {"title": "天气", "source": "x", "text": "今日多云转晴，气温二十度。", "embedding": unrelated},
            {"title": "操作说明", "source": "builtin", "text": "调拨通过后资产仍为在用，只更换领用人。", "embedding": related},
        ]
        hits = rank_chunks("调拨之后还在用吗", chunks, query_vec=query, top_k=2)
        self.assertEqual(hits[0]["title"], "操作说明")
        self.assertGreater(hits[0]["semantic_score"], 0)

    def test_embed_failure_returns_none_not_hash(self):
        from app.services.rag_service import try_embed_texts

        vecs, status = asyncio.run(try_embed_texts(["调拨怎么审批"]))
        self.assertIsNone(vecs)
        self.assertIn(status, {"unavailable", "no_key"})

    def test_seed_builtin_upsert_and_search_kb(self):
        from app.services import rag_store
        from app.services import rag_service
        from app.services.ai_tools import tool_search_kb

        first = asyncio.run(rag_service.seed_builtin())
        self.assertGreater(first["chunk_count"], 1)
        self.assertEqual(first["embed_kind"], "none")
        second = asyncio.run(rag_service.seed_builtin())
        self.assertEqual(len(rag_store.list_documents()), 1)
        self.assertNotEqual(first["id"], second["id"])
        hits, meta = asyncio.run(rag_service.retrieve("调拨怎么审批"))
        self.assertTrue(hits)
        self.assertEqual(hits[0]["title"], "调拨")
        self.assertIn("调拨", hits[0]["text"])
        self.assertIn("审批", hits[0]["snippet"])
        self.assertTrue(meta["degraded"])
        rag_service.scan_secrets(rag_service.builtin_seed_path().read_text(encoding="utf-8"))
        tool = asyncio.run(tool_search_kb(user_text="调拨怎么审批"))
        self.assertGreater(tool["row_count"], 0)
        self.assertEqual(tool["cards"][0]["kind"], "kb")
        self.assertTrue(any("词面" in line for line in tool["blocks"][0]["lines"]))


if __name__ == "__main__":
    unittest.main()
