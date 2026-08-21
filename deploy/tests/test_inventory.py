# -*- coding: utf-8 -*-
"""盘点：快照、权限、盘亏不改资产、结束锁。"""
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
class TestInventory(unittest.IsolatedAsyncioTestCase):
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
        self.emp_user = await User.create(
            username="emp1", email="e@t.com", password="x", is_superuser=False, is_active=True
        )
        self.mgr_user = await User.create(
            username="mgr1", email="m@t.com", password="x", is_superuser=False, is_active=True
        )
        self.emp = await Employee.create(
            emp_no="E001", name="员工甲", dept_id=self.dept.id, is_manager=False, status=True, user_id=self.emp_user.id
        )
        self.mgr = await Employee.create(
            emp_no="E002", name="主管乙", dept_id=self.dept.id, is_manager=True, status=True, user_id=self.mgr_user.id
        )
        self.outsider = await Employee.create(
            emp_no="E003", name="外人", dept_id=self.other.id, is_manager=False, status=True
        )
        self.mine = await Asset.create(asset_no="A-MINE", name="本人电脑", status=1, owner_emp_id=self.emp.id)
        self.idle = await Asset.create(asset_no="A-IDLE", name="闲置显示器", status=2, owner_emp_id=None)
        self.other_asset = await Asset.create(
            asset_no="A-OTH", name="外部门", status=1, owner_emp_id=self.outsider.id
        )
        self.dead = await Asset.create(asset_no="A-DEAD", name="报废", status=4, owner_emp_id=None)

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_admin_start_skips_scrap_and_counts(self):
        from fastapi.exceptions import HTTPException

        from app.controllers.inventory import inventory_controller
        from app.core.ctx import CTX_USER_ID
        from app.models.business import Asset, InventoryLine
        from app.schemas.inventory import InventoryClose, InventoryCount, InventoryStart

        CTX_USER_ID.set(self.admin_user.id)
        session = await inventory_controller.start(InventoryStart(title="全司盘", scope="all"))
        with self.assertRaises(HTTPException):
            await inventory_controller.start(InventoryStart(title="重复", scope="all"))
        data = await inventory_controller.get(session.id)
        nos = {r.asset_no for r in await InventoryLine.filter(session_id=session.id)}
        self.assertIn("A-MINE", nos)
        self.assertIn("A-IDLE", nos)
        self.assertIn("A-OTH", nos)
        self.assertNotIn("A-DEAD", nos)
        self.assertEqual(data["summary"]["total"], 3)

        mine_line = await InventoryLine.filter(session_id=session.id, asset_no="A-MINE").first()
        await inventory_controller.count(InventoryCount(line_id=mine_line.id, result="missing"))
        data = await inventory_controller.get(session.id)
        self.assertEqual(data["summary"]["missing"], 1)
        fresh = await Asset.get(id=self.mine.id)
        self.assertEqual(fresh.status, 1)
        self.assertEqual(fresh.owner_emp_id, self.emp.id)

        closed = await inventory_controller.close(InventoryClose(session_id=session.id))
        self.assertEqual(closed["status"], 2)
        with self.assertRaises(HTTPException):
            await inventory_controller.count(InventoryCount(line_id=mine_line.id, result="found"))
        session2 = await inventory_controller.start(InventoryStart(title="第二轮", scope="all"))
        self.assertEqual(session2.status, 1)

    async def test_employee_cannot_start_can_count_own(self):
        from fastapi.exceptions import HTTPException

        from app.controllers.inventory import inventory_controller
        from app.core.ctx import CTX_USER_ID
        from app.models.business import InventoryLine
        from app.schemas.inventory import InventoryCount, InventoryStart

        CTX_USER_ID.set(self.admin_user.id)
        session = await inventory_controller.start(InventoryStart(title="全司盘", scope="all"))
        CTX_USER_ID.set(self.emp_user.id)
        with self.assertRaises(HTTPException):
            await inventory_controller.start(InventoryStart(title="员工开", scope="all"))
        mine = await InventoryLine.filter(session_id=session.id, asset_no="A-MINE").first()
        other = await InventoryLine.filter(session_id=session.id, asset_no="A-OTH").first()
        await inventory_controller.count(InventoryCount(line_id=mine.id, result="found"))
        with self.assertRaises(HTTPException):
            await inventory_controller.count(InventoryCount(line_id=other.id, result="found"))
        total, items = await inventory_controller.list_lines(session.id, 1, 50)
        nos = {i.asset_no for i in items}
        self.assertEqual(nos, {"A-MINE"})

    async def test_manager_dept_scope(self):
        from app.controllers.inventory import inventory_controller
        from app.core.ctx import CTX_USER_ID
        from app.models.business import InventoryLine
        from app.schemas.inventory import InventoryStart

        CTX_USER_ID.set(self.mgr_user.id)
        session = await inventory_controller.start(InventoryStart(title="本部门", scope="all"))
        self.assertEqual(session.scope, "dept")
        self.assertEqual(session.dept_id, self.dept.id)
        nos = {r.asset_no for r in await InventoryLine.filter(session_id=session.id)}
        self.assertIn("A-MINE", nos)
        self.assertNotIn("A-OTH", nos)
        self.assertNotIn("A-IDLE", nos)
