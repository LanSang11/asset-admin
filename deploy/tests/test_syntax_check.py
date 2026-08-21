# -*- coding: utf-8 -*-
"""对安全修复涉及的全部 Python 文件做 AST 语法解析验证（纯标准库）。

用途：本机未安装 fastapi/tortoise 依赖、Docker daemon 不可用时，
确保所有修改过的源码文件语法正确、无笔误。
"""
import ast
import os
import unittest

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

CHECK_FILES = [
    "app/__init__.py",
    "app/settings/config.py",
    "app/core/init_app.py",
    "app/core/exceptions.py",
    "app/core/middlewares.py",
    "app/core/security.py",
    "app/core/dependency.py",
    "app/controllers/user.py",
    "app/controllers/api.py",
    "app/api/v1/ai/assistant.py",
    "app/schemas/users.py",
    "app/api/v1/users/users.py",
    "app/api/v1/security/security.py",
    "app/api/v1/base/base.py",
    "app/services/security_event_service.py",
    "app/services/security_agg.py",
    "app/services/ai_policy.py",
    "app/services/ai_tools.py",
    "app/api/v1/ai/assistant.py",
    "app/utils/request_info.py",
    "app/utils/geoip.py",
    "app/utils/ip2region_xdb.py",
    "app/utils/security_risk.py",
    "app/models/admin.py",
    "app/schemas/login.py",
    "deploy/reset_admin_password.py",
    "deploy/migrate_security.py",
    "deploy/init_demo_data.py",
]


class TestSyntax(unittest.TestCase):
    def test_all_modified_files_parse(self):
        for rel in CHECK_FILES:
            path = os.path.join(BASE, rel)
            with self.subTest(file=rel):
                self.assertTrue(os.path.exists(path), f"{rel} 文件不存在")
                with open(path, "r", encoding="utf-8") as f:
                    source = f.read()
                ast.parse(source, filename=rel)  # 语法错误会抛 SyntaxError


if __name__ == "__main__":
    unittest.main()
