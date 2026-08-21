# -*- coding: utf-8 -*-
import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.ai_presets import AI_PRESETS, DEFAULT_MODEL, apply_preset


class AiPresetTests(unittest.TestCase):
    def test_deepseek_default_is_v4_flash(self):
        self.assertEqual(DEFAULT_MODEL, "deepseek-v4-flash")
        self.assertEqual(apply_preset("deepseek")["base_url"], "https://api.deepseek.com")
        self.assertIn("openai", AI_PRESETS)
        self.assertIn("openai_legacy", AI_PRESETS)
        self.assertEqual(AI_PRESETS["openai"]["base_url"], "https://api.openai.com/v1")
        self.assertNotEqual(AI_PRESETS["openai"]["model"], "deepseek-chat")

    def test_unknown_provider_does_not_invent_key(self):
        other = apply_preset("other")
        self.assertEqual(other["provider"], "other")
        self.assertEqual(other["model"], "")


class OssDemoScriptTests(unittest.TestCase):
    def _load_mod(self):
        spec_path = os.path.join(ROOT, "deploy", "init_oss_demo_data.py")
        import importlib.util

        spec = importlib.util.spec_from_file_location("init_oss_demo_data", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_blocks_wwwroot_paths(self):
        mod = self._load_mod()
        self.assertTrue(mod._blocked(Path("/www/wwwroot/asset-system/db/db.sqlite3")))
        self.assertFalse(mod._blocked(Path(ROOT) / "app.db"))

    def test_bind_existing_roles_only(self):
        import sqlite3
        import tempfile

        mod = self._load_mod()
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "demo.db"
            conn = sqlite3.connect(str(db))
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE role (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE user_role (user_id INTEGER, role_id INTEGER);
                INSERT INTO role (id, name) VALUES (2, '普通员工'), (3, '部门主管');
                """
            )
            mod.bind_demo_roles(cur, {"demoemp": 11, "demomgr": 12})
            conn.commit()
            rows = set(cur.execute("SELECT user_id, role_id FROM user_role").fetchall())
            conn.close()
        self.assertEqual(rows, {(11, 2), (12, 3)})


if __name__ == "__main__":
    unittest.main()
