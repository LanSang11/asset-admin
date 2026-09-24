import json
import unittest
from decimal import Decimal

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from tortoise.exceptions import IntegrityError, ValidationError as TortoiseValidationError

from app.core.exceptions import (
    IntegrityHandle,
    RequestValidationHandle,
    TortoiseValidationHandle,
)
from app.schemas.apis import ApiCreate
from app.schemas.asset_repairs import AssetRepairCreate
from app.schemas.assets import AssetCreate
from app.schemas.depts import DeptCreate
from app.schemas.employees import EmployeeCreate
from app.schemas.menus import MenuCreate
from app.schemas.roles import RoleCreate
from app.schemas.users import UpdatePassword, UserCreate, UserUpdate


def _validation_errors(model, payload):
    try:
        model.model_validate(payload)
    except PydanticValidationError as exc:
        return exc.errors()
    raise AssertionError("测试数据应触发 Pydantic 校验错误")


class RequestValidationContractTests(unittest.IsolatedAsyncioTestCase):
    async def _handle(self, model, payload):
        errors = _validation_errors(model, payload)
        response = await RequestValidationHandle(None, RequestValidationError(errors))
        return response, json.loads(response.body)

    async def test_password_error_is_actionable_chinese_and_does_not_echo_input(self):
        weak_password = "weakpass"
        response, body = await self._handle(
            UpdatePassword,
            {"old_password": "Old!Pass9", "new_password": weak_password},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["code"], 422)
        self.assertEqual(body["msg"], "提交内容有误，请按提示修改")
        self.assertEqual(
            body["data"][0]["msg"],
            "密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号",
        )
        self.assertNotIn("input", body["data"][0])
        self.assertNotIn(weak_password, response.body.decode("utf-8"))

    async def test_common_builtin_validation_errors_are_translated(self):
        cases = [
            (
                AssetCreate,
                {"asset_no": "A1", "name": "测试资产", "price": -1},
                "需大于或等于 0",
            ),
            (
                EmployeeCreate,
                {"emp_no": "E" * 21, "name": "测试员工"},
                "最多输入 20 个字符",
            ),
            (
                AssetRepairCreate,
                {"asset_id": 1, "reason": "短"},
                "至少输入 2 个字符",
            ),
        ]

        for model, payload, expected in cases:
            with self.subTest(model=model.__name__):
                _, body = await self._handle(model, payload)
                self.assertEqual(body["data"][0]["msg"], expected)

    async def test_database_validation_fallback_is_actionable(self):
        response = await TortoiseValidationHandle(
            None, TortoiseValidationError("value is too long")
        )
        body = json.loads(response.body)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["code"], 422)
        self.assertEqual(body["msg"], "字段内容超过长度或格式限制，请按页面提示修改")

    async def test_unique_conflict_uses_conflict_semantics(self):
        response = await IntegrityHandle(None, IntegrityError("unique constraint"))
        body = json.loads(response.body)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(body["code"], 409)
        self.assertEqual(body["msg"], "数据已存在或与现有记录冲突，请修改后重试")


class SchemaModelAlignmentTests(unittest.TestCase):
    def assert_invalid(self, model, payload):
        with self.assertRaises(PydanticValidationError):
            model.model_validate(payload)

    def test_user_name_limit_matches_database_model(self):
        long_name = "u" * 21
        common = {
            "email": "user01@example.com",
            "username": long_name,
            "password": "FxA!k9Qm2pL",
        }
        self.assert_invalid(UserCreate, common)
        self.assert_invalid(
            UserUpdate,
            {"id": 1, "email": "user01@example.com", "username": long_name},
        )

    def test_admin_schemas_reject_values_longer_than_database_fields(self):
        cases = [
            (DeptCreate, {"name": "部" * 21}),
            (RoleCreate, {"name": "角" * 21}),
            (MenuCreate, {"name": "菜" * 21, "path": "/menu", "order": 1}),
            (
                ApiCreate,
                {"path": "/" + "a" * 100, "method": "GET", "tags": "User"},
            ),
        ]
        for model, payload in cases:
            with self.subTest(model=model.__name__):
                self.assert_invalid(model, payload)

    def test_asset_price_precision_matches_database_field(self):
        self.assert_invalid(
            AssetCreate,
            {
                "asset_no": "A1",
                "name": "测试资产",
                "price": Decimal("123456789.12"),
            },
        )


if __name__ == "__main__":
    unittest.main()
