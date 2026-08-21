# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore")

try:
    import fastapi  # noqa: F401
    from tortoise import Tortoise

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise 依赖")
class TestEmployeeAttachment(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        self.tmp = tempfile.TemporaryDirectory()
        from app.settings import config as cfg

        self._old_base = cfg.settings.BASE_DIR
        cfg.settings.BASE_DIR = self.tmp.name
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()
        from app.models.admin import User
        from app.models.business import Employee

        self.u1 = await User.create(username="e1", email="e1@t.com", password="x", is_superuser=False, is_active=True)
        self.u2 = await User.create(username="e2", email="e2@t.com", password="x", is_superuser=False, is_active=True)
        self.emp1 = await Employee.create(emp_no="E1", name="甲", status=True, user_id=self.u1.id)
        self.emp2 = await Employee.create(emp_no="E2", name="乙", status=True, user_id=self.u2.id)

    async def asyncTearDown(self):
        await Tortoise.close_connections()
        from app.settings import config as cfg

        cfg.settings.BASE_DIR = self._old_base
        self.tmp.cleanup()

    async def test_owner_upload_other_forbidden_and_type_check(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.employee_attachment import employee_attachment_controller

        CTX_USER_ID.set(self.u1.id)
        obj = await employee_attachment_controller.upload(self.emp1.id, "note.txt", "hello".encode("utf-8"))
        self.assertTrue(obj.stored_name.endswith(".txt"))

        with self.assertRaises(Exception) as ctx:
            await employee_attachment_controller.upload(self.emp2.id, "note.txt", b"hello")
        self.assertIn("权限范围内", str(ctx.exception))

        with self.assertRaises(Exception):
            await employee_attachment_controller.upload(self.emp1.id, "x.exe", b"MZ")


if __name__ == "__main__":
    unittest.main()
