# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.core.ai_chat_payload import build_chat_payload, uses_deepseek_thinking
from app.services.ai_session import AssistantSessionStore


class ChatPayloadTests(unittest.TestCase):
    def test_deepseek_default_disables_thinking(self):
        payload = build_chat_payload(
            model="deepseek-v4-flash",
            provider="deepseek",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.2,
            thinking="disabled",
        )
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", payload)
        self.assertEqual(payload["temperature"], 0.2)
        self.assertFalse(payload["stream"])

    def test_deepseek_low_thinking_omits_temperature(self):
        payload = build_chat_payload(
            model="deepseek-v4-pro",
            provider="deepseek",
            messages=[{"role": "user", "content": None}],
            thinking="low",
        )
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["messages"][0]["content"], "")

    def test_openai_does_not_send_thinking(self):
        payload = build_chat_payload(
            model="gpt-4o-mini",
            provider="openai",
            messages=[{"role": "user", "content": "hi"}],
            thinking="disabled",
        )
        self.assertNotIn("thinking", payload)
        self.assertIn("temperature", payload)
        self.assertFalse(uses_deepseek_thinking("openai", "gpt-4o-mini"))


class SessionStoreTests(unittest.TestCase):
    def test_caps_and_isolates_users(self):
        store = AssistantSessionStore()
        for i in range(6):
            store.remember(1, "s1", f"u{i}", f"a{i}")
        hist = store.history(1, "s1")
        self.assertEqual(len(hist), 8)
        self.assertEqual(hist[0]["content"], "u2")
        self.assertEqual(store.history(2, "s1"), [])
        self.assertEqual(store.history(1, "other"), [])

    def test_blank_session_not_stored(self):
        store = AssistantSessionStore()
        store.remember(1, "", "hi", "ok")
        self.assertEqual(store.history(1, ""), [])


class SourceContractTests(unittest.TestCase):
    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_assistant_uses_user_model_not_client_system(self):
        src = self._read("app/api/v1/ai/assistant.py")
        self.assertIn("_maybe_generate_with_user_model", src)
        self.assertIn('thinking="disabled"', src)
        self.assertIn("validate_ask_payload", src)
        self.assertNotIn("FORBIDDEN", src)

    def test_chat_endpoint_hides_exception_type(self):
        src = self._read("app/api/v1/ai/ai.py")
        self.assertNotIn("type(e).__name__", src)
        self.assertIn('msg="AI 调用失败"', src)
        self.assertIn('msg="图片理解失败"', src)


if __name__ == "__main__":
    unittest.main()
