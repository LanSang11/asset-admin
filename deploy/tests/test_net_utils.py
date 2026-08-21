# -*- coding: utf-8 -*-
"""net_utils SSRF 防护单元测试（importlib 直接加载模块，不触发 app 包依赖）。

运行：python -m unittest deploy/tests/test_net_utils.py
或：python -m unittest discover -s deploy/tests
"""
import importlib.util
import os
import unittest

_SPEC = importlib.util.spec_from_file_location(
    "net_utils",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app", "utils", "net_utils.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)

_looks_numeric_host = _mod._looks_numeric_host
validate_base_url = _mod.validate_base_url

# inet_aton 数字变形（会被 getaddrinfo 解析回 loopback/内网，必须识别为数字形态）
NUMERIC_HOSTS = [
    "127.1",
    "2130706433",
    "0177.0.0.1",
    "0x7f.1",
    "0x7f000001",
    "0X7F.1",
    "127.0.0.1",
    "10.0.0.1",
]

# 正常域名/主机名（不得误判）
DOMAIN_HOSTS = [
    "api.deepseek.com",
    "api.openai.com",
    "model.example.org",
    "2001:db8::1",
]

# 必须被 validate_base_url 拒绝的 URL
BLOCK_URLS = [
    "https://127.1",
    "https://2130706433",
    "https://0x7f.1",
    "https://0x7f000001",
    "https://0177.0.0.1",
    "http://api.deepseek.com",
    "https://localhost",
    "https://api.internal",
    "https://192.168.1.1",
    "https://169.254.169.254",
    # 尾点 FQDN 绕过（getaddrinfo 解析尾点直连本机/内网）
    "https://127.0.0.1./",
    "https://localhost./",
    "https://2130706433./",
    "https://0./",
    "https://0x7f000001./",
]


class TestNumericHost(unittest.TestCase):
    def test_numeric_hosts_detected(self):
        for h in NUMERIC_HOSTS:
            with self.subTest(host=h):
                self.assertTrue(_looks_numeric_host(h), f"{h} 应识别为数字形态")

    def test_domain_hosts_not_detected(self):
        for h in DOMAIN_HOSTS:
            with self.subTest(host=h):
                self.assertFalse(_looks_numeric_host(h), f"{h} 不应误判为数字形态")


class TestValidateBaseUrl(unittest.TestCase):
    def test_block_urls(self):
        for u in BLOCK_URLS:
            with self.subTest(url=u):
                with self.assertRaises(ValueError, msg=f"{u} 应被拒绝"):
                    validate_base_url(u)

    def test_allow_legit(self):
        self.assertEqual(
            validate_base_url("https://api.deepseek.com"),
            "https://api.deepseek.com",
        )


if __name__ == "__main__":
    unittest.main()
