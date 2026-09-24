# -*- coding: utf-8 -*-
"""助手问句抽词：整句中文不能当资产编号/员工姓名。"""
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
class TestSearchKeywordPure(unittest.TestCase):
    def test_contract_table(self):
        from app.services.ai_tools import _ASSET_STOPWORDS, _EMPLOYEE_STOPWORDS, _search_keyword

        self.assertEqual(_search_keyword("我有哪些资产", _ASSET_STOPWORDS), "")
        self.assertEqual(_search_keyword("查员工", _EMPLOYEE_STOPWORDS), "")
        self.assertEqual(_search_keyword("查员工王强", _EMPLOYEE_STOPWORDS), "王强")
        self.assertEqual(_search_keyword("NB-01", _ASSET_STOPWORDS), "NB-01")
        self.assertEqual(_search_keyword("查员工张三", _EMPLOYEE_STOPWORDS), "张三")

    def test_punctuation_and_idle_phrase(self):
        from app.services.ai_tools import _ASSET_STOPWORDS, _search_keyword

        self.assertEqual(_search_keyword("我有哪些资产？", _ASSET_STOPWORDS), "")
        self.assertEqual(_search_keyword("闲置", _ASSET_STOPWORDS), "")
        self.assertEqual(_search_keyword("查一下资产 NB-01", _ASSET_STOPWORDS), "NB-01")


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise 依赖")
class TestAiQueryKeywordTools(unittest.IsolatedAsyncioTestCase):
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

        self.dept = await Dept.create(name="综合部")
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
        self.emp_wang = await Employee.create(
            emp_no="E001",
            name="王强",
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
        self.asset_nb = await Asset.create(
            asset_no="NB-01", name="ThinkPad", status=1, owner_emp_id=self.emp_wang.id
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_admin_list_assets_from_spoken_question(self):
        from app.core.ctx import CTX_USER_ID
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.admin_user.id)
        result = await run_tools(["list_assets"], user_text="我有哪些资产", page_context={})
        blob = _blob(result)
        self.assertGreater(result["row_count"], 0)
        self.assertIn("NB-01", blob)
        self.assertNotIn("没有匹配资产", blob)

    async def test_admin_lookup_employees_from_spoken_question(self):
        from app.core.ctx import CTX_USER_ID
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.admin_user.id)
        result = await run_tools(["lookup_employees"], user_text="查员工", page_context={})
        blob = _blob(result)
        self.assertGreater(result["row_count"], 0)
        self.assertIn("王强", blob)
        self.assertNotIn("没有匹配员工", blob)

    async def test_named_employee_and_asset_code_still_match(self):
        from app.core.ctx import CTX_USER_ID
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.admin_user.id)
        named = await run_tools(["lookup_employees"], user_text="查员工王强", page_context={})
        self.assertIn("王强", _blob(named))
        coded = await run_tools(["list_assets"], user_text="NB-01", page_context={})
        self.assertIn("NB-01", _blob(coded))
        self.assertEqual(coded["row_count"], 1)

    async def test_employee_b_cannot_see_employee_a_asset(self):
        from app.core.ctx import CTX_USER_ID
        from app.services.ai_tools import run_tools

        CTX_USER_ID.set(self.emp_b_user.id)
        result = await run_tools(["list_assets"], user_text="我有哪些资产", page_context={})
        blob = _blob(result)
        self.assertNotIn("NB-01", blob)
        self.assertEqual(result["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
