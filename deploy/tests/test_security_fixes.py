# -*- coding: utf-8 -*-
"""安全修复回归测试（importlib 直接加载 security 纯函数模块，不触发 app 包依赖）。

覆盖：
1. 强密码策略（H1/M1）：validate_password 强弱密码判定
2. 随机初始密码生成（H1）：符合强密码策略
3. 审计日志长文本截断（M4）：truncate_sensitive 递归截断
"""
import importlib.util
import os
import unittest

_SPEC = importlib.util.spec_from_file_location(
    "security",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "app", "core", "security.py"),
)
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)

validate_password = _mod.validate_password
gen_initial_password = _mod.gen_initial_password
truncate_sensitive = _mod.truncate_sensitive

# 必须通过强密码策略的密码（大小写+数字+符号，8~32 位）
# 禁止使用任何业务演示账号的真实口令作夹具。
STRONG_PASSWORDS = [
    "FxA!k9Qm2pL",
    "FxB#n4Rt8wS",
    "Abc@12Zz99",
    "Str0ng!PassFx",
    "aB3$dEfGh1",
]

# 必须被拒绝的弱密码
WEAK_PASSWORDS = [
    "123456",           # 纯数字、过短
    "abcdefgh",         # 纯小写
    "ABCDEFGH",         # 纯大写
    "Abcdef12",         # 无特殊符号
    "Abc@12",           # 过短（6 位）
    "A" * 33 + "b1@",   # 超过 32 位
    "",
]


class TestPasswordPolicy(unittest.TestCase):
    def test_strong_passwords_accepted(self):
        for pwd in STRONG_PASSWORDS:
            with self.subTest(pwd=pwd):
                self.assertTrue(validate_password(pwd), f"{pwd} 应通过强密码策略")

    def test_weak_passwords_rejected(self):
        for pwd in WEAK_PASSWORDS:
            with self.subTest(pwd=pwd):
                self.assertFalse(validate_password(pwd), f"{pwd} 应被强密码策略拒绝")

    def test_generated_password_matches_policy(self):
        for _ in range(20):
            pwd = gen_initial_password()
            self.assertTrue(validate_password(pwd), f"生成的随机密码 {pwd} 必须符合强密码策略")
            self.assertEqual(len(pwd), 16)


class TestTruncateSensitive(unittest.TestCase):
    def test_long_string_truncated(self):
        long_text = "x" * 1000
        result = truncate_sensitive(long_text)
        self.assertEqual(len(result), 500 + len("...[已截断]"))
        self.assertTrue(result.endswith("...[已截断]"))

    def test_short_string_unchanged(self):
        self.assertEqual(truncate_sensitive("你好"), "你好")

    def test_nested_dict_and_list(self):
        data = {
            "messages": [
                {"role": "user", "content": "y" * 800},
                {"role": "assistant", "content": "ok"},
            ],
            "count": 3,
            "flag": True,
        }
        result = truncate_sensitive(data)
        self.assertEqual(len(result["messages"][0]["content"]), 500 + len("...[已截断]"))
        self.assertEqual(result["messages"][1]["content"], "ok")
        self.assertEqual(result["count"], 3)
        self.assertIs(result["flag"], True)

    def test_non_string_types_unchanged(self):
        self.assertIsNone(truncate_sensitive(None))
        self.assertEqual(truncate_sensitive(123), 123)

    def test_nested_sensitive_keys_masked(self):
        data = {
            "user": {"password": "MySecret@123", "name": "张三"},
            "payload": {"nested": {"api_key": "sk-abcdef"}},
            "NewPassword": "Abc@12345",
        }
        result = truncate_sensitive(data)
        self.assertEqual(result["user"]["password"], "***")
        self.assertEqual(result["user"]["name"], "张三")
        self.assertEqual(result["payload"]["nested"]["api_key"], "***")
        self.assertEqual(result["NewPassword"], "***")  # 大小写不敏感

    def test_sensitive_key_in_list(self):
        data = {"messages": [{"role": "user", "content": "hi"}, {"secret": "sk-xyz"}]}
        result = truncate_sensitive(data)
        self.assertEqual(result["messages"][1]["secret"], "***")
        self.assertEqual(result["messages"][0]["content"], "hi")


if __name__ == "__main__":
    unittest.main()
