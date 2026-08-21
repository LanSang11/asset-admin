# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.utils.request_info import client_ip, is_unusable_client_ip


class _Req:
    def __init__(self, xff=None, host=None):
        self.headers = {}
        if xff is not None:
            self.headers["x-forwarded-for"] = xff
        self.client = type("C", (), {"host": host})() if host is not None else None


class RequestInfoTests(unittest.TestCase):
    def test_docnet_unusable(self):
        self.assertTrue(is_unusable_client_ip("203.0.113.89"))
        self.assertTrue(is_unusable_client_ip("192.0.2.1"))
        self.assertTrue(is_unusable_client_ip("unknown"))
        self.assertTrue(is_unusable_client_ip(""))
        self.assertTrue(is_unusable_client_ip("203.0.113.1"))
        self.assertFalse(is_unusable_client_ip("8.8.8.8"))
        self.assertFalse(is_unusable_client_ip("127.0.0.1"))

    def test_xff_prefers_rightmost_real_ip(self):
        req = _Req(xff="203.0.113.89, 203.0.113.1, 8.8.8.8", host="127.0.0.1")
        self.assertEqual(client_ip(req), "8.8.8.8")

    def test_single_docnet_falls_back_to_socket(self):
        req = _Req(xff="203.0.113.89", host="1.2.3.4")
        self.assertEqual(client_ip(req), "1.2.3.4")

    def test_all_unusable_returns_unknown(self):
        req = _Req(xff="203.0.113.89", host="192.0.2.1")
        self.assertEqual(client_ip(req), "unknown")


if __name__ == "__main__":
    unittest.main()
