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
class TestKbSteward(unittest.TestCase):
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

    def test_empty_index_all_missing(self):
        from app.services.kb_steward import analyze, canonical_topics

        topics = canonical_topics()
        self.assertIn("调拨", topics)
        self.assertIn("盘点", topics)
        report = analyze()
        self.assertEqual(report["doc_count"], 0)
        self.assertEqual(set(report["missing"]), set(topics))
        self.assertEqual(report["duplicates"], [])

    def test_seed_covers_core_topics(self):
        from app.services import rag_service
        from app.services.kb_steward import analyze

        asyncio.run(rag_service.seed_builtin())
        report = analyze()
        titles = {item["topic"] for item in report["covered"]}
        self.assertIn("调拨", titles)
        self.assertIn("盘点", titles)
        self.assertIn("质保到期", titles)
        self.assertFalse(report["missing"])

    def test_duplicates_and_confirmed_ingest(self):
        from fastapi.exceptions import HTTPException

        from app.services import rag_store
        from app.services.kb_steward import find_duplicates, ingest_confirmed

        text = "只能调拨在用且已有领用人的资产。通过后资产仍为在用，只更换领用人。"
        rag_store.insert_document(
            title="调拨A",
            source="upload",
            sha256="d" * 32,
            created_by=1,
            chunks=[(text, [])],
            embed_kind="none",
        )
        rag_store.insert_document(
            title="调拨B",
            source="upload",
            sha256="e" * 32,
            created_by=1,
            chunks=[(text, [])],
            embed_kind="none",
        )
        dups = find_duplicates()
        self.assertTrue(dups)
        self.assertEqual(dups[0]["left"], "调拨A")
        with self.assertRaises(HTTPException):
            asyncio.run(ingest_confirmed("坏", "password=abc123\n说明"))
        saved = asyncio.run(ingest_confirmed("补充扫码", "## 补充扫码\n手机打开资产码后要先登录，按权限看摘要。"))
        self.assertGreaterEqual(saved["chunk_count"], 1)
        self.assertEqual(saved["title"], "补充扫码")

    def test_routes_are_superuser_only(self):
        with open(os.path.join(ROOT, "app", "api", "v1", "knowledge", "knowledge.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("DependSuperUser", src)
        self.assertIn("/steward/analyze", src)
        self.assertIn("/steward/draft", src)
        self.assertIn("/steward/ingest", src)
        with open(os.path.join(ROOT, "web", "src", "views", "business", "kb", "index.vue"), encoding="utf-8") as fh:
            vue = fh.read()
        self.assertIn("isSuperUser", vue)
        self.assertIn("确认入库", vue)
        self.assertNotIn("v-html", vue)
        with open(os.path.join(ROOT, "deploy", "native", "backup_sqlite_daily.sh"), encoding="utf-8") as fh:
            sh = fh.read()
        self.assertIn("rag.sqlite3", sh)
        self.assertIn("rag-${TS}-daily.sqlite3", sh)


if __name__ == "__main__":
    unittest.main()
