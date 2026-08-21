# -*- coding: utf-8 -*-
"""质保到期：状态计算、列表筛选、提醒去重、员工闲置脱敏。"""
import os
import unittest
import warnings
from datetime import date, timedelta

warnings.filterwarnings("ignore")

try:
    import fastapi  # noqa: F401
    from tortoise import Tortoise

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestWarrantyPure(unittest.TestCase):
    def test_state_buckets(self):
        from app.services.warranty import warranty_days_left, warranty_state

        today = date(2026, 8, 19)
        self.assertEqual(warranty_state(None, today), "none")
        self.assertEqual(warranty_state("", today), "none")
        self.assertEqual(warranty_state(today - timedelta(days=1), today), "expired")
        self.assertEqual(warranty_state(today, today), "expiring")
        self.assertEqual(warranty_state(today + timedelta(days=30), today), "expiring")
        self.assertEqual(warranty_state(today + timedelta(days=31), today), "ok")
        self.assertEqual(warranty_days_left(today + timedelta(days=10), today), 10)

    def test_empty_date_schema(self):
        from app.schemas.assets import AssetCreate

        obj = AssetCreate(asset_no="A1", name="显示器", purchase_date="", warranty_until="")
        self.assertIsNone(obj.purchase_date)
        self.assertIsNone(obj.warranty_until)


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise 依赖")
class TestWarrantyPersist(unittest.IsolatedAsyncioTestCase):
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
        self.admin_user = await User.create(
            username="admin1", email="a@t.com", password="x", is_superuser=True, is_active=True
        )
        self.emp_user = await User.create(
            username="emp1", email="e@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp = await Employee.create(
            emp_no="E001",
            name="张三",
            dept_id=self.dept.id,
            is_manager=False,
            status=True,
            user_id=self.emp_user.id,
        )
        today = date.today()
        self.expired = await Asset.create(
            asset_no="AST-EXP",
            name="过保本",
            status=1,
            owner_emp_id=self.emp.id,
            warranty_until=today - timedelta(days=3),
        )
        self.expiring = await Asset.create(
            asset_no="AST-SOON",
            name="将过保",
            status=1,
            owner_emp_id=self.emp.id,
            warranty_until=today + timedelta(days=7),
        )
        self.ok = await Asset.create(
            asset_no="AST-OK",
            name="在保",
            status=2,
            owner_emp_id=None,
            warranty_until=today + timedelta(days=400),
        )
        self.idle_secret = await Asset.create(
            asset_no="AST-IDLE-W",
            name="闲置过保",
            status=2,
            owner_emp_id=None,
            warranty_until=today - timedelta(days=10),
        )
        self.scrapped = await Asset.create(
            asset_no="AST-DEAD",
            name="报废过保",
            status=4,
            owner_emp_id=None,
            warranty_until=today - timedelta(days=10),
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_filter_expired_and_due(self):
        from app.controllers.asset import asset_controller
        from app.core.ctx import CTX_USER_ID

        CTX_USER_ID.set(self.admin_user.id)
        total, items = await asset_controller.list_assets(1, 20, warranty_state="expired")
        nos = {a.asset_no for a in items}
        self.assertIn("AST-EXP", nos)
        self.assertIn("AST-IDLE-W", nos)
        self.assertIn("AST-DEAD", nos)
        self.assertNotIn("AST-SOON", nos)
        self.assertNotIn("AST-OK", nos)

        _, due_items = await asset_controller.list_assets(1, 20, warranty_state="due")
        due_nos = {a.asset_no for a in due_items}
        self.assertIn("AST-EXP", due_nos)
        self.assertIn("AST-SOON", due_nos)
        self.assertNotIn("AST-OK", due_nos)

    async def test_alert_once_and_skip_scrapped(self):
        from app.models.business import Notification
        from app.services.warranty import emit_warranty_alerts

        first = await emit_warranty_alerts([self.expired, self.scrapped])
        # 超管 + 领用人
        self.assertEqual(first, 2)
        second = await emit_warranty_alerts([self.expired, self.scrapped])
        self.assertEqual(second, 0)
        notes = await Notification.filter(type="warranty_alert").all()
        self.assertEqual(len(notes), 2)
        recipients = {n.user_id for n in notes}
        self.assertEqual(recipients, {self.admin_user.id, self.emp_user.id})
        self.assertTrue(all("/business/asset" in n.route or "/work/my-assets" in n.route for n in notes))

    async def test_employee_idle_hides_warranty(self):
        from app.controllers.asset import asset_controller

        data = await asset_controller.serialize_for_viewer(self.idle_secret, "employee", self.emp)
        self.assertIsNone(data.get("warranty_until"))
        self.assertEqual(data.get("warranty_state"), "none")
        own = await asset_controller.serialize_for_viewer(self.expired, "employee", self.emp)
        self.assertEqual(own.get("warranty_state"), "expired")
        self.assertEqual(own.get("warranty_label"), "已过保")

    async def test_summarize_skips_scrapped(self):
        from app.services.warranty import summarize_warranty

        summary = summarize_warranty(
            [self.expired, self.expiring, self.ok, self.idle_secret, self.scrapped]
        )
        self.assertEqual(summary["expired"], 2)
        self.assertEqual(summary["expiring"], 1)
        nos = {row["asset_no"] for row in summary["list"]}
        self.assertNotIn("AST-DEAD", nos)
        self.assertNotIn("AST-OK", nos)


if __name__ == "__main__":
    unittest.main()
