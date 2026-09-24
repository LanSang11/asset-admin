# -*- coding: utf-8 -*-
"""助手只读查报修/调拨/盘点：走现有 list_*，员工看不到别人的单。"""
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


def _blob(result):
    return str(result)


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise 依赖")
class TestAiTicketTools(unittest.IsolatedAsyncioTestCase):
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
        self.other = await Dept.create(name="行政")
        self.admin_user = await User.create(
            username="admin1", email="a@t.com", password="x", is_superuser=True, is_active=True
        )
        self.emp_a_user = await User.create(
            username="empa", email="aemp@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp_b_user = await User.create(
            username="empb", email="bemp@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp_c_user = await User.create(
            username="empc", email="cemp@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp_a = await Employee.create(
            emp_no="E001",
            name="员工甲",
            dept_id=self.dept.id,
            is_manager=False,
            status=True,
            user_id=self.emp_a_user.id,
        )
        self.emp_b = await Employee.create(
            emp_no="E002",
            name="员工乙",
            dept_id=self.other.id,
            is_manager=False,
            status=True,
            user_id=self.emp_b_user.id,
        )
        self.emp_c = await Employee.create(
            emp_no="E003",
            name="员工丙",
            dept_id=self.dept.id,
            is_manager=False,
            status=True,
            user_id=self.emp_c_user.id,
        )
        self.asset_a = await Asset.create(asset_no="AST-A", name="甲的电脑", status=1, owner_emp_id=self.emp_a.id)

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_registered_read_only_tools(self):
        from app.services.ai_tools import TOOLS

        self.assertIn("list_repairs", TOOLS)
        self.assertIn("list_transfers", TOOLS)
        self.assertIn("list_inventory", TOOLS)

    async def test_empty_repairs_has_no_fake_number(self):
        from app.core.ctx import CTX_USER_ID
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.admin_user.id)
        result = await run_tools(["list_repairs"], user_text="我的报修到哪了", page_context={})
        blob = _blob(result)
        self.assertEqual(result["row_count"], 0)
        self.assertIn("没有", blob)
        self.assertNotIn("NB-02", blob)
        self.assertNotIn("NB-99", blob)
        self.assertNotIn("AST-A", blob)

    async def test_admin_sees_repair_asset_no(self):
        from app.core.ctx import CTX_USER_ID
        from app.models.business import AssetRepair
        from app.services.ai_tools import run_tools

        await AssetRepair.create(asset_id=self.asset_a.id, employee_id=self.emp_a.id, reason="风扇响", status=1)
        CTX_USER_ID.set(self.admin_user.id)
        result = await run_tools(["list_repairs"], user_text="我的报修到哪了", page_context={})
        blob = _blob(result)
        self.assertGreater(result["row_count"], 0)
        self.assertIn("AST-A", blob)
        self.assertIn("待主管", blob)
        self.assertTrue(any(card.get("kind") == "repair" for card in result.get("cards") or []))

    async def test_employee_cannot_see_others_repair(self):
        from app.core.ctx import CTX_USER_ID
        from app.models.business import AssetRepair
        from app.services.ai_tools import run_tools

        await AssetRepair.create(asset_id=self.asset_a.id, employee_id=self.emp_a.id, reason="风扇响", status=1)
        CTX_USER_ID.set(self.emp_b_user.id)
        result = await run_tools(["list_repairs"], user_text="我的报修到哪了", page_context={})
        blob = _blob(result)
        self.assertNotIn("AST-A", blob)
        self.assertEqual(result["row_count"], 0)
        self.assertIn("没有", blob)

    async def test_transfer_visible_to_party_hidden_from_outsider(self):
        from app.core.ctx import CTX_USER_ID
        from app.models.business import AssetTransfer
        from app.services.ai_tools import run_tools

        await AssetTransfer.create(
            asset_id=self.asset_a.id,
            from_employee_id=self.emp_a.id,
            to_employee_id=self.emp_c.id,
            applicant_id=self.emp_a.id,
            reason="换人用",
            status=1,
        )
        CTX_USER_ID.set(self.emp_a_user.id)
        mine = await run_tools(["list_transfers"], user_text="有没有调拨", page_context={})
        self.assertIn("AST-A", _blob(mine))
        self.assertGreater(mine["row_count"], 0)
        self.assertTrue(any(card.get("kind") == "transfer" for card in mine.get("cards") or []))

        CTX_USER_ID.set(self.emp_b_user.id)
        other = await run_tools(["list_transfers"], user_text="有没有调拨", page_context={})
        self.assertNotIn("AST-A", _blob(other))
        self.assertEqual(other["row_count"], 0)
        self.assertIn("没有", _blob(other))

    async def test_inventory_visible_to_owner_hidden_from_outsider(self):
        from app.controllers.inventory import inventory_controller
        from app.core.ctx import CTX_USER_ID
        from app.schemas.inventory import InventoryStart
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.admin_user.id)
        session = await inventory_controller.start(InventoryStart(title="全司盘ASSIST", scope="all"))
        self.assertEqual(session.status, 1)

        CTX_USER_ID.set(self.emp_a_user.id)
        mine = await run_tools(["list_inventory"], user_text="盘点还剩几台", page_context={})
        blob = _blob(mine)
        self.assertGreater(mine["row_count"], 0)
        self.assertIn("全司盘ASSIST", blob)
        self.assertNotIn("AST-A", blob)
        self.assertTrue(any(card.get("kind") == "inventory" for card in mine.get("cards") or []))

        CTX_USER_ID.set(self.emp_b_user.id)
        hidden = await run_tools(["list_inventory"], user_text="盘点还剩几台", page_context={})
        self.assertNotIn("全司盘ASSIST", _blob(hidden))
        self.assertEqual(hidden["row_count"], 0)
        self.assertIn("没有", _blob(hidden))


if __name__ == "__main__":
    unittest.main()
