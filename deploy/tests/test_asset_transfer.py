# -*- coding: utf-8 -*-
"""在用资产调拨：本人可申请、他人不可、通过后只换领用人。"""
import os
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
class TestAssetTransfer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()
        from app.models.admin import Dept, User
        from app.models.business import Asset, Employee

        self.dept = await Dept.create(name="研发部")
        self.manager_user = await User.create(
            username="xfermgr", email="m@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp_user = await User.create(
            username="emp1", email="e@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp2_user = await User.create(
            username="emp2", email="e2@t.com", password="x", is_superuser=False, is_active=True
        )
        self.admin_user = await User.create(
            username="admin1", email="a@t.com", password="x", is_superuser=True, is_active=True
        )
        self.manager = await Employee.create(
            emp_no="M001",
            name="主管",
            dept_id=self.dept.id,
            is_manager=True,
            status=True,
            user_id=self.manager_user.id,
        )
        self.emp = await Employee.create(
            emp_no="E001",
            name="张三",
            dept_id=self.dept.id,
            is_manager=False,
            status=True,
            user_id=self.emp_user.id,
        )
        self.emp2 = await Employee.create(
            emp_no="E002",
            name="李四",
            dept_id=self.dept.id,
            is_manager=False,
            status=True,
            user_id=self.emp2_user.id,
        )
        self.asset = await Asset.create(
            asset_no="AST-T1",
            name="测试笔记本",
            status=1,
            owner_emp_id=self.emp.id,
        )
        self.idle = await Asset.create(
            asset_no="AST-IDLE",
            name="闲置显示器",
            status=2,
            owner_emp_id=None,
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_owner_can_apply_other_cannot(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_transfer import asset_transfer_controller
        from app.schemas.asset_transfers import AssetTransferCreate

        CTX_USER_ID.set(self.emp_user.id)
        obj = await asset_transfer_controller.apply(
            AssetTransferCreate(asset_id=self.asset.id, to_employee_id=self.emp2.id, reason="换人用")
        )
        self.assertEqual(obj.status, 1)
        self.assertEqual(obj.from_employee_id, self.emp.id)

        CTX_USER_ID.set(self.emp2_user.id)
        with self.assertRaises(Exception) as ctx:
            await asset_transfer_controller.apply(
                AssetTransferCreate(asset_id=self.asset.id, to_employee_id=self.manager.id, reason="抢别人的")
            )
        self.assertIn("自己名下", str(ctx.exception))

    async def test_idle_rejected(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_transfer import asset_transfer_controller
        from app.schemas.asset_transfers import AssetTransferCreate

        CTX_USER_ID.set(self.emp_user.id)
        with self.assertRaises(Exception) as ctx:
            await asset_transfer_controller.apply(
                AssetTransferCreate(asset_id=self.idle.id, to_employee_id=self.emp2.id, reason="闲置")
            )
        self.assertIn("在用", str(ctx.exception))

    async def test_superuser_oneshot_keeps_in_use(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_transfer import asset_transfer_controller
        from app.models.business import Asset, AssetUseHistory
        from app.schemas.asset_transfers import AssetTransferCreate

        CTX_USER_ID.set(self.emp_user.id)
        obj = await asset_transfer_controller.apply(
            AssetTransferCreate(asset_id=self.asset.id, to_employee_id=self.emp2.id, reason="换人用")
        )
        CTX_USER_ID.set(self.admin_user.id)
        done = await asset_transfer_controller.approve(obj.id, True, "超管过")
        self.assertEqual(done.status, 3)
        fresh = await Asset.get(id=self.asset.id)
        self.assertEqual(fresh.status, 1)
        self.assertEqual(fresh.owner_emp_id, self.emp2.id)
        hist = await AssetUseHistory.filter(asset_id=self.asset.id, use_type=3).first()
        self.assertIsNotNone(hist)

    async def test_candidates_no_phone(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_transfer import asset_transfer_controller

        CTX_USER_ID.set(self.emp_user.id)
        rows = await asset_transfer_controller.candidates()
        self.assertTrue(rows)
        self.assertNotIn("phone", rows[0])
        self.assertNotIn("email", rows[0])
        ids = {r["id"] for r in rows}
        self.assertIn(self.emp2.id, ids)
        self.assertNotIn(self.emp.id, ids)


if __name__ == "__main__":
    unittest.main()
