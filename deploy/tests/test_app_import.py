# -*- coding: utf-8 -*-
"""验证安全修复后 app 可全量导入、docs 默认关闭（M9）。

运行：python -m unittest deploy/tests/test_app_import.py
注意：需要本机已安装 requirements.txt 依赖（否则 ImportError 提示环境受限，改用容器验证）。
"""
import unittest

try:
    import fastapi  # noqa: F401

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi 等依赖，全量导入验证请在 Docker 容器或已装依赖环境执行")
class TestAppImport(unittest.TestCase):
    def test_app_creatable_and_docs_disabled(self):
        import app

        self.assertIsNotNone(app.app)
        # M9：生产默认关闭 /docs 与 /openapi.json
        self.assertIsNone(app.app.docs_url)
        self.assertIsNone(app.app.redoc_url)
        self.assertIsNone(app.app.openapi_url)

    def test_security_module_available(self):
        from app.core.security import gen_initial_password, truncate_sensitive, validate_password

        self.assertTrue(validate_password(gen_initial_password()))
        self.assertTrue(truncate_sensitive("x" * 600).endswith("...[已截断]"))


if __name__ == "__main__":
    unittest.main()
