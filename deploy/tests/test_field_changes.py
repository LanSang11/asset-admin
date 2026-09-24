# -*- coding: utf-8 -*-
"""DIFF-1 field-change storage and service contracts (isolated SQLite)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import unittest
from unittest.mock import AsyncMock, patch

from tortoise import Tortoise, connections


class TestFieldChanges(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            config={
                "connections": {"sqlite": "sqlite://:memory:"},
                "apps": {
                    "models": {
                        "models": ["app.models.admin", "app.models.business"],
                        "default_connection": "sqlite",
                    }
                },
            }
        )
        await Tortoise.generate_schemas()
        from app.models.admin import Dept, User
        from app.models.business import Employee

        self.admin_user = await User.create(
            username="field-admin", email="field-admin@example.test", password="x",
            is_active=True, is_superuser=True,
        )
        self.dept = await Dept.create(name="研发部")
        self.finance_dept = await Dept.create(name="财务部")
        self.manager_user = await User.create(
            username="field-manager", email="field-manager@example.test", password="x", is_active=True
        )
        self.emp_user = await User.create(
            username="field-employee", email="field-employee@example.test", password="x", is_active=True
        )
        self.finance_manager_user = await User.create(
            username="finance-manager", email="finance-manager@example.test", password="x", is_active=True
        )
        self.manager = await Employee.create(
            emp_no="M001", name="研发主管", dept_id=self.dept.id, is_manager=True,
            status=True, user_id=self.manager_user.id,
        )
        self.emp = await Employee.create(
            emp_no="E001", name="研发员工", dept_id=self.dept.id, phone="13800138000",
            email="employee@example.test", status=True, user_id=self.emp_user.id,
        )
        self.finance_manager = await Employee.create(
            emp_no="FM001", name="财务主管", dept_id=self.finance_dept.id, is_manager=True,
            status=True, user_id=self.finance_manager_user.id,
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()
        # Tortoise.init() merges into ConnectionHandler._db_config. Merely closing
        # connections leaves the "sqlite" alias behind, contaminating later test
        # modules that initialise a "default" connection in the same process.
        connections._clear_storage()
        connections._db_config = None
        await Tortoise._reset_apps()
        Tortoise._inited = False

    async def test_data_field_change_schema_and_indexes(self):
        from app.models.business import DataFieldChange

        row = await DataFieldChange.create(
            entity_type="asset",
            entity_id=12,
            field_name="location",
            old_value="A区",
            new_value="B区",
            operator_id=self.admin_user.id,
            operator_name=self.admin_user.username,
        )
        self.assertGreater(row.id, 0)
        conn = connections.get("sqlite")
        indexes = await conn.execute_query_dict("PRAGMA index_list(data_field_changes)")
        names = {item["name"] for item in indexes}
        self.assertIn("idx_data_field_changes_entity", names)
        self.assertIn("idx_data_field_changes_created", names)

    def test_existing_sqlite_patch_contains_idempotent_ddl(self):
        source = Path("app/core/init_app.py").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS data_field_changes", source)
        self.assertIn("idx_data_field_changes_entity", source)
        self.assertIn("idx_data_field_changes_created", source)

    async def test_asset_service_writes_only_changed_allowlisted_field(self):
        from app.models.business import Asset, DataFieldChange
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(
            asset_no="NB-01", name="笔记本", location="A区", status=2, price=Decimal("10.00")
        )
        updated = await update_with_field_changes(
            Asset, "asset", asset.id, {"location": "B区", "price": Decimal("10.00"), "ignored": "x"}, self.admin_user.id
        )
        self.assertEqual(updated.location, "B区")
        rows = await DataFieldChange.filter(entity_type="asset", entity_id=asset.id).all()
        self.assertEqual([(r.field_name, r.old_value, r.new_value) for r in rows], [("location", "A区", "B区")])

    async def test_noop_normalized_empty_value_writes_nothing(self):
        from app.models.business import Asset, DataFieldChange
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-NOOP", name="无变化资产", location="", status=2)
        await update_with_field_changes(Asset, "asset", asset.id, {"location": None, "ignored": "x"}, self.admin_user.id)
        self.assertEqual(await DataFieldChange.filter(entity_type="asset", entity_id=asset.id).count(), 0)

    async def test_employee_phone_and_email_are_masked_before_insert(self):
        from app.models.business import DataFieldChange, Employee
        from app.services.field_change_service import update_with_field_changes

        old_phone, new_phone = "13800138000", "13900139000"
        old_email, new_email = "old@example.com", "new@example.com"
        employee = await Employee.create(
            emp_no="E-PII", name="脱敏测试", phone=old_phone, email=old_email, status=True
        )
        await update_with_field_changes(
            Employee, "employee", employee.id,
            {"phone": new_phone, "email": new_email}, self.admin_user.id,
        )
        rows = await DataFieldChange.filter(entity_type="employee", entity_id=employee.id).order_by("field_name")
        values = {row.field_name: (row.old_value, row.new_value) for row in rows}
        self.assertEqual(values["phone"], ("138****8000", "139****9000"))
        self.assertEqual(values["email"], ("o***@example.com", "n***@example.com"))
        stored = " ".join(value for pair in values.values() for value in pair)
        plaintext_absent = all(
            plaintext not in stored for plaintext in (old_phone, new_phone, old_email, new_email)
        )
        self.assertTrue(plaintext_absent, "持久化字段不得包含测试 PII 明文")

    async def test_field_labels_are_complete_and_non_timeline_fields_remain_mutable(self):
        from app.models.business import Asset, DataFieldChange
        from app.services.field_change_service import (
            ASSET_FIELD_LABELS,
            EMPLOYEE_FIELD_LABELS,
            update_with_field_changes,
        )

        self.assertEqual(
            set(ASSET_FIELD_LABELS),
            {"asset_no", "name", "category", "model", "serial_no", "purchase_date", "warranty_until",
             "price", "status", "location", "owner_emp_id", "remark"},
        )
        self.assertEqual(len(ASSET_FIELD_LABELS), 12)
        self.assertEqual(
            set(EMPLOYEE_FIELD_LABELS),
            {"emp_no", "name", "gender", "dept_id", "position", "hire_date", "phone", "email",
             "user_id", "is_manager", "status"},
        )
        self.assertEqual(len(EMPLOYEE_FIELD_LABELS), 11)
        asset = await Asset.create(asset_no="NB-INTERNAL", name="内部字段", status=2)
        updated = await update_with_field_changes(
            Asset, "asset", asset.id, {"warranty_notified_state": "expiring"}, self.admin_user.id
        )
        self.assertEqual(updated.warranty_notified_state, "expiring")
        self.assertEqual(await DataFieldChange.filter(entity_id=asset.id).count(), 0)

    async def test_semantic_equivalent_boolean_and_enum_values_write_nothing(self):
        from app.models.business import Asset, DataFieldChange, Employee
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-EQUIV", name="枚举", status=2)
        employee = await Employee.create(emp_no="E-EQUIV", name="布尔", gender=0, status=False, is_manager=False)
        await update_with_field_changes(Asset, "asset", asset.id, {"status": "2"}, self.admin_user.id)
        await update_with_field_changes(
            Employee, "employee", employee.id, {"gender": "0", "status": 0, "is_manager": 0}, self.admin_user.id
        )
        self.assertEqual(await DataFieldChange.filter(entity_id__in=[asset.id, employee.id]).count(), 0)

    async def test_asset_and_employee_status_display_values_are_separate(self):
        from app.models.business import Asset, DataFieldChange, Employee
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-STATUS", name="状态", status=2)
        employee = await Employee.create(emp_no="E-STATUS", name="状态", status=True)
        await update_with_field_changes(Asset, "asset", asset.id, {"status": "1"}, 0)
        await update_with_field_changes(Employee, "employee", employee.id, {"status": False}, 0)
        asset_row = await DataFieldChange.get(entity_type="asset", entity_id=asset.id, field_name="status")
        employee_row = await DataFieldChange.get(entity_type="employee", entity_id=employee.id, field_name="status")
        self.assertEqual((asset_row.old_value, asset_row.new_value), ("闲置", "在用"))
        self.assertEqual((employee_row.old_value, employee_row.new_value), ("在职", "离职"))

    async def test_long_remark_is_truncated_only_for_persisted_timeline_value(self):
        from app.models.business import Asset, DataFieldChange
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-LONG", name="长备注", status=2)
        long_remark = "x" * 501
        # SQLite 的 VARCHAR 不强制长度；模拟历史库中已存在的超长旧值。
        conn = connections.get("sqlite")
        await conn.execute_query("UPDATE assets SET remark = ? WHERE id = ?", [long_remark, asset.id])
        await update_with_field_changes(Asset, "asset", asset.id, {"remark": "更新后备注"}, self.admin_user.id)
        row = await DataFieldChange.get(entity_type="asset", entity_id=asset.id, field_name="remark")
        self.assertEqual(len(row.old_value), 500)
        persisted = await Asset.get(id=asset.id)
        self.assertEqual(persisted.remark, "更新后备注")

    async def test_change_write_failure_rolls_back_business_update(self):
        from app.models.business import Asset, DataFieldChange
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-ROLLBACK", name="回滚资产", location="A区", status=2)
        with patch.object(DataFieldChange, "bulk_create", new=AsyncMock(side_effect=RuntimeError("timeline write failed"))):
            with self.assertRaisesRegex(RuntimeError, "timeline write failed"):
                await update_with_field_changes(
                    Asset, "asset", asset.id, {"location": "B区"}, self.admin_user.id
                )
        persisted = await Asset.get(id=asset.id)
        self.assertEqual(persisted.location, "A区")
        self.assertEqual(await DataFieldChange.filter(entity_id=asset.id).count(), 0)

    async def test_list_field_changes_pages_and_formats_shanghai_time(self):
        from app.models.business import DataFieldChange
        from app.services.field_change_service import format_shanghai_time, list_field_changes

        utc_time = datetime(2026, 8, 24, 5, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(format_shanghai_time(utc_time), "2026-08-24 13:30:00")
        for value in ("A", "B", "C"):
            row = await DataFieldChange.create(
                entity_type="asset", entity_id=87, field_name="location",
                old_value="旧", new_value=value, operator_id=self.admin_user.id,
                operator_name=self.admin_user.username,
            )
            await DataFieldChange.filter(id=row.id).update(created_at=utc_time + timedelta(seconds=ord(value)))
        result = await list_field_changes("asset", 87, page=2, page_size=2)
        self.assertEqual(result["total"], 3)
        self.assertEqual((result["page"], result["page_size"]), (2, 2))
        self.assertEqual(len(result["list"]), 1)
        self.assertEqual(result["list"][0]["new_value"], "A")
        self.assertRegex(result["list"][0]["changed_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    async def test_prune_field_changes_keeps_newest_rows_and_drops_old_rows(self):
        from app.models.business import DataFieldChange
        from app.services.field_change_service import prune_field_changes

        now = datetime.now(timezone.utc)
        for offset in range(3):
            row = await DataFieldChange.create(
                entity_type="asset", entity_id=99, field_name="location",
                old_value=str(offset), new_value=str(offset + 1), operator_id=self.admin_user.id,
                operator_name=self.admin_user.username,
            )
            await DataFieldChange.filter(id=row.id).update(created_at=now + timedelta(seconds=offset))
        by_rows = await prune_field_changes(retention_days=180, max_rows=2)
        self.assertEqual(await DataFieldChange.all().count(), 2)
        self.assertGreaterEqual(by_rows["by_rows"], 1)
        old_row = await DataFieldChange.create(
            entity_type="employee", entity_id=99, field_name="position",
            old_value="旧", new_value="新", operator_id=self.admin_user.id,
            operator_name=self.admin_user.username,
        )
        await DataFieldChange.filter(id=old_row.id).update(created_at=now - timedelta(days=181))
        by_days = await prune_field_changes(retention_days=180, max_rows=20)
        self.assertEqual(by_days["by_days"], 1)

    async def test_formatting_rules_for_dates_decimals_and_labels(self):
        from app.models.business import Asset, DataFieldChange, Employee
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(asset_no="NB-FMT", name="格式", status=2, purchase_date=date(2026, 8, 1), price=Decimal("1.00"))
        await update_with_field_changes(
            Asset, "asset", asset.id,
            {"purchase_date": date(2026, 8, 2), "price": Decimal("2.50"), "status": 1}, 0,
        )
        employee = await Employee.create(emp_no="E-FMT", name="格式", gender=0, status=True)
        await update_with_field_changes(Employee, "employee", employee.id, {"gender": 1, "status": False}, 0)
        values = {
            row.field_name: (row.old_value, row.new_value, row.operator_name)
            for row in await DataFieldChange.all()
        }
        self.assertEqual(values["purchase_date"][:2], ("2026-08-01", "2026-08-02"))
        self.assertEqual(values["price"][:2], ("1", "2.5"))
        self.assertEqual(values["status"][:2], ("在职", "离职"))
        self.assertEqual(values["gender"][:2], ("未知", "男"))
        self.assertTrue(all(value[2] == "系统" for value in values.values()))

    async def test_asset_change_visibility(self):
        from fastapi import HTTPException

        from app.api.v1.assets.assets import get_asset
        from app.controllers.asset import EMP_SENSITIVE_FIELDS, asset_controller
        from app.core.ctx import CTX_USER_ID
        from app.models.business import Asset
        from app.schemas.assets import AssetUpdate
        from app.services.field_change_service import update_with_field_changes

        asset = await Asset.create(
            asset_no="NB-01", name="笔记本", category="电脑", location="A区", status=2,
        )
        CTX_USER_ID.set(self.admin_user.id)
        await asset_controller.update_asset(
            AssetUpdate(
                id=asset.id, asset_no=asset.asset_no, name=asset.name, category=asset.category,
                location="B区", status=2,
            )
        )
        response = await get_asset(
            id=asset.id, asset_no="", include_changes=True, change_page=1, change_page_size=20
        )
        payload = json.loads(response.body)["data"]
        self.assertEqual(payload["changes"]["total"], 1)
        self.assertEqual(payload["changes"]["list"][0]["field_name"], "location")
        self.assertEqual(payload["changes"]["list"][0]["old_value"], "A区")
        self.assertEqual(payload["changes"]["list"][0]["new_value"], "B区")

        owned = await Asset.create(
            asset_no="NB-OWN", name="本人资产", category="电脑", location="工位A",
            status=1, owner_emp_id=self.emp.id,
        )
        await update_with_field_changes(
            Asset, "asset", owned.id, {"location": "工位B"}, self.admin_user.id
        )
        CTX_USER_ID.set(self.emp_user.id)
        own_response = await get_asset(
            id=owned.id, asset_no="", include_changes=True, change_page=1, change_page_size=20
        )
        own_changes = json.loads(own_response.body)["data"]["changes"]
        self.assertEqual(own_changes["total"], 1)
        self.assertEqual(own_changes["list"][0]["field_name"], "location")

        idle = await Asset.create(
            asset_no="NB-IDLE", name="共享闲置", category="电脑", serial_no="SN-OLD",
            price=Decimal("100.00"), status=2,
        )
        await update_with_field_changes(
            Asset, "asset", idle.id,
            {"serial_no": "SN-NEW", "price": Decimal("200.00"), "location": "公共区"},
            self.admin_user.id,
        )
        idle_response = await get_asset(
            id=idle.id, asset_no="", include_changes=True, change_page=1, change_page_size=20
        )
        idle_fields = {
            row["field_name"] for row in json.loads(idle_response.body)["data"]["changes"]["list"]
        }
        self.assertTrue(idle_fields)
        self.assertFalse(idle_fields & set(EMP_SENSITIVE_FIELDS))

        manager_owned = await Asset.create(
            asset_no="NB-MANAGER", name="主管资产", category="电脑", location="研发部",
            status=1, owner_emp_id=self.manager.id,
        )
        await update_with_field_changes(
            Asset, "asset", manager_owned.id, {"location": "研发部会议室"}, self.admin_user.id
        )
        with self.assertRaises(HTTPException) as other_in_use:
            await get_asset(
                id=manager_owned.id, asset_no="", include_changes=True,
                change_page=1, change_page_size=20,
            )
        self.assertEqual(other_in_use.exception.status_code, 403)

        CTX_USER_ID.set(self.manager_user.id)
        same_dept = await get_asset(
            id=owned.id, asset_no="", include_changes=True, change_page=1, change_page_size=20
        )
        self.assertEqual(json.loads(same_dept.body)["data"]["changes"]["total"], 1)

        CTX_USER_ID.set(self.finance_manager_user.id)
        with self.assertRaises(HTTPException) as cross_dept:
            await get_asset(
                id=owned.id, asset_no="", include_changes=True,
                change_page=1, change_page_size=20,
            )
        self.assertEqual(cross_dept.exception.status_code, 403)

    async def test_employee_change_visibility_and_masking(self):
        from fastapi import HTTPException

        from app.api.v1.employees.employees import get_employee
        from app.controllers.employee import employee_controller
        from app.core.ctx import CTX_USER_ID
        from app.schemas.employees import EmployeeUpdate

        CTX_USER_ID.set(self.admin_user.id)
        await employee_controller.update_employee(
            EmployeeUpdate(
                id=self.emp.id, emp_no=self.emp.emp_no, name=self.emp.name,
                dept_id=self.emp.dept_id, phone="13900139000", email=self.emp.email,
                status=True,
            )
        )
        admin_response = await get_employee(
            id=self.emp.id, include_changes=True, change_page=1, change_page_size=20
        )
        admin_json = json.loads(admin_response.body)["data"]
        phone_change = next(
            row for row in admin_json["changes"]["list"] if row["field_name"] == "phone"
        )
        self.assertEqual(
            (phone_change["old_value"], phone_change["new_value"]),
            ("138****8000", "139****9000"),
        )
        changes_json = json.dumps(admin_json["changes"], ensure_ascii=False)
        self.assertTrue(
            all(value not in changes_json for value in ("13800138000", "13900139000")),
            "变更历史不得包含测试 PII 明文",
        )
        self.assertEqual(admin_json["phone"], "13900139000")

        CTX_USER_ID.set(self.manager_user.id)
        same_dept = await get_employee(
            id=self.emp.id, include_changes=True, change_page=1, change_page_size=20
        )
        same_dept_changes = json.loads(same_dept.body)["data"]["changes"]
        self.assertEqual(same_dept_changes["total"], 1)
        self.assertEqual(
            (same_dept_changes["list"][0]["old_value"], same_dept_changes["list"][0]["new_value"]),
            ("138****8000", "139****9000"),
        )

        CTX_USER_ID.set(self.emp_user.id)
        self_view = await get_employee(
            id=self.emp.id, include_changes=True, change_page=1, change_page_size=20
        )
        self_changes = json.loads(self_view.body)["data"]["changes"]
        self.assertEqual(self_changes["total"], 1)
        self.assertEqual(
            (self_changes["list"][0]["old_value"], self_changes["list"][0]["new_value"]),
            ("138****8000", "139****9000"),
        )

        CTX_USER_ID.set(self.finance_manager_user.id)
        with self.assertRaises(HTTPException) as cross_dept:
            await get_employee(
                id=self.emp.id, include_changes=True, change_page=1, change_page_size=20
            )
        self.assertEqual(cross_dept.exception.status_code, 403)

        CTX_USER_ID.set(self.emp_user.id)
        with self.assertRaises(HTTPException) as other_employee:
            await get_employee(
                id=self.manager.id, include_changes=True, change_page=1, change_page_size=20
            )
        self.assertEqual(other_employee.exception.status_code, 403)

    async def test_controller_noop_and_create_delete_do_not_write_changes(self):
        from app.controllers.asset import asset_controller
        from app.controllers.employee import employee_controller
        from app.core.ctx import CTX_USER_ID
        from app.models.business import DataFieldChange
        from app.schemas.assets import AssetCreate, AssetUpdate
        from app.schemas.employees import EmployeeCreate, EmployeeUpdate

        CTX_USER_ID.set(self.admin_user.id)
        asset = await asset_controller.create_asset(
            AssetCreate(asset_no="NB-LIFECYCLE", name="生命周期", category="电脑", status=2)
        )
        employee = await employee_controller.create_employee(
            EmployeeCreate(emp_no="E-LIFECYCLE", name="生命周期员工")
        )
        self.assertEqual(await DataFieldChange.all().count(), 0)

        await asset_controller.update_asset(
            AssetUpdate(
                id=asset.id, asset_no=asset.asset_no, name=asset.name,
                category=asset.category, status=asset.status,
            )
        )
        await employee_controller.update_employee(
            EmployeeUpdate(
                id=employee.id, emp_no=employee.emp_no, name=employee.name,
                status=employee.status,
            )
        )
        self.assertEqual(await DataFieldChange.all().count(), 0)

        await asset_controller.delete_asset(asset.id)
        await employee_controller.delete_employee(employee.id)
        self.assertEqual(await DataFieldChange.all().count(), 0)


if __name__ == "__main__":
    unittest.main()
