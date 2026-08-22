# -*- coding: utf-8 -*-
"""业务核心逻辑单元测试（培训阶段2要求：员工/资产新增+分页+筛选；另覆盖审批状态机/封禁逻辑）。

运行（需已安装 requirements.txt 依赖，建议在 Docker 容器或 venv 中）：
    python -m unittest deploy/tests/test_business_api.py
    pytest deploy/tests/test_business_api.py -v

依赖 fastapi/tortoise 未安装时自动跳过（本机可用 test_net_utils.py 等无依赖用例）。
"""
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


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise 依赖，请在容器或 venv 中执行")
class TestBusinessCore(unittest.IsolatedAsyncioTestCase):
    """员工/资产/领用审批核心业务（内存 SQLite，不污染真实数据库）"""

    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()

        # 基础数据：部门/员工/主管账号/超管
        from app.models.admin import Dept, User
        from app.models.business import Asset, Employee

        self.dept = await Dept.create(name="研发部")
        self.manager_user = await User.create(username="demomgr", email="m@t.com", password="x", is_superuser=False, is_active=True)
        self.emp_user = await User.create(username="emp1", email="e@t.com", password="x", is_superuser=False, is_active=True)
        self.admin_user = await User.create(username="admin1", email="a@t.com", password="x", is_superuser=True, is_active=True)
        self.manager = await Employee.create(
            emp_no="M001", name="主管", dept_id=self.dept.id, is_manager=True, status=True, user_id=self.manager_user.id,
        )
        self.emp = await Employee.create(
            emp_no="E001", name="张三", dept_id=self.dept.id, is_manager=False, status=True, user_id=self.emp_user.id,
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    # ---------- 员工 ----------
    async def test_employee_create_and_duplicate(self):
        from app.controllers.employee import employee_controller
        from app.schemas.employees import EmployeeCreate

        emp = await employee_controller.create_employee(EmployeeCreate(emp_no="E002", name="李四"))
        self.assertEqual(emp.emp_no, "E002")
        # 工号重复被拒
        with self.assertRaises(Exception) as ctx:
            await employee_controller.create_employee(EmployeeCreate(emp_no="E002", name="王五"))
        self.assertIn("已存在", str(ctx.exception))

    async def test_employee_bind_nonexistent_user_rejected(self):
        from app.controllers.employee import employee_controller
        from app.schemas.employees import EmployeeCreate

        with self.assertRaises(Exception) as ctx:
            await employee_controller.create_employee(EmployeeCreate(emp_no="E003", name="赵六", user_id=99999))
        self.assertIn("登录账号不存在", str(ctx.exception))

    async def test_employee_list_pagination_and_filter(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.employee import employee_controller
        from app.schemas.employees import EmployeeCreate

        for i in range(15):
            await employee_controller.create_employee(
                EmployeeCreate(emp_no=f"B{i:03d}", name=f"批量员工{i}", dept_id=self.dept.id)
            )
        # ISO-B2：列表按当前用户角色缩圈；本测以超管看全量
        CTX_USER_ID.set(self.admin_user.id)
        # 分页
        total, items = await employee_controller.list_employees(1, 10)
        self.assertEqual(total, 17)  # 主管 M001 + 张三 E001 + 15 批量
        self.assertEqual(len(items), 10)
        _, page2 = await employee_controller.list_employees(2, 10)
        self.assertEqual(len(page2), 7)
        # 关键词筛选（姓名）
        _, matched = await employee_controller.list_employees(1, 10, keyword="批量员工1")
        self.assertEqual(len(matched), 6)  # 1,10-14
        # 部门筛选
        _, dept_matched = await employee_controller.list_employees(1, 10, dept_id=self.dept.id)
        self.assertEqual(len(dept_matched), 10)

        from app.models.business import Employee

        await Employee.create(emp_no="A001", name="阿尔法", dept_id=self.dept.id, status=False)
        await Employee.create(emp_no="Z999", name="终点", dept_id=self.dept.id, status=True)

        total_active, active_items = await employee_controller.list_employees(
            1, 100, status=1, sort_by="emp_no", sort_order="asc"
        )
        self.assertGreaterEqual(total_active, 1)
        self.assertTrue(all(item.status for item in active_items))
        self.assertEqual(
            [item.emp_no for item in active_items],
            sorted(item.emp_no for item in active_items),
        )

        total_inactive, inactive_items = await employee_controller.list_employees(
            1, 100, status=0, sort_by="name", sort_order="desc"
        )
        self.assertEqual(total_inactive, 1)
        self.assertEqual(inactive_items[0].emp_no, "A001")

        # 普通员工只能看见本人
        CTX_USER_ID.set(self.emp_user.id)
        total_self, items_self = await employee_controller.list_employees(1, 10)
        self.assertEqual(total_self, 1)
        self.assertEqual(items_self[0].id, self.emp.id)

    async def test_employee_sort_allowlist_defaults_safely(self):
        from app.services.employee_query import resolve_employee_order

        self.assertEqual(resolve_employee_order("emp_no", "asc"), "emp_no")
        self.assertEqual(resolve_employee_order("name", "desc"), "-name")
        self.assertEqual(resolve_employee_order("password", "asc"), "-created_at")
        self.assertEqual(resolve_employee_order("created_at", "sideways"), "-created_at")

    async def test_employee_export_uses_filters_sort_and_csv_guards(self):
        from app.models.business import Employee
        from app.services.export_service import export_employees

        await Employee.create(emp_no="E900", name="=风险姓名", dept_id=self.dept.id, status=False)
        await Employee.create(emp_no="E800", name="正常员工", dept_id=self.dept.id, status=True)
        response = await export_employees(
            keyword="风险", dept_id=self.dept.id, status=0, sort_by="emp_no", sort_order="asc"
        )
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
        content = b"".join(chunks).decode("utf-8-sig")
        self.assertIn("E900", content)
        self.assertNotIn("E800", content)
        self.assertIn("'=风险姓名", content)

    # ---------- 资产 ----------
    async def test_asset_create_and_validation(self):
        from app.controllers.asset import asset_controller
        from app.schemas.assets import AssetCreate

        asset = await asset_controller.create_asset(AssetCreate(asset_no="AST001", name="笔记本", status=2))
        self.assertEqual(asset.status, 2)
        # 编号重复
        with self.assertRaises(Exception) as ctx:
            await asset_controller.create_asset(AssetCreate(asset_no="AST001", name="另一台"))
        self.assertIn("已存在", str(ctx.exception))
        # 分类非法
        with self.assertRaises(Exception) as ctx:
            await asset_controller.create_asset(AssetCreate(asset_no="AST002", name="x", category="外星科技"))
        self.assertIn("分类不合法", str(ctx.exception))
        # 状态=在用但没有领用人 → 矛盾数据被拒
        with self.assertRaises(Exception) as ctx:
            await asset_controller.create_asset(AssetCreate(asset_no="AST003", name="x", status=1))
        self.assertIn("在用", str(ctx.exception))
        # 领用人不存在
        with self.assertRaises(Exception) as ctx:
            await asset_controller.create_asset(AssetCreate(asset_no="AST004", name="x", status=1, owner_emp_id=99999))
        self.assertIn("领用人不存在", str(ctx.exception))

    async def test_asset_delete_guard(self):
        from app.controllers.asset import asset_controller
        from app.schemas.assets import AssetCreate

        asset = await asset_controller.create_asset(
            AssetCreate(asset_no="AST010", name="在用资产", status=1, owner_emp_id=self.emp.id)
        )
        # 在用资产不可删除
        with self.assertRaises(Exception) as ctx:
            await asset_controller.delete_asset(asset.id)
        self.assertIn("在用", str(ctx.exception))
        # 闲置资产可删除
        idle = await asset_controller.create_asset(AssetCreate(asset_no="AST011", name="闲置资产", status=2))
        await asset_controller.delete_asset(idle.id)

    # ---------- 领用/归还审批状态机 ----------
    async def _apply_and_approve_take(self):
        """完整领用流程：申请→主管一级通过→管理员二级通过"""
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.models.business import Asset, AssetUse
        from app.schemas.asset_uses import AssetUseCreate

        asset = await Asset.create(asset_no="AST100", name="测试资产", status=2)
        CTX_USER_ID.set(self.emp_user.id)
        app = await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=1))
        self.assertEqual(app.status, 1)  # 待主管

        CTX_USER_ID.set(self.manager_user.id)
        passed = await asset_use_controller.approve(app.id, True, "同意")
        self.assertEqual(passed.status, 2)  # 待管理员

        CTX_USER_ID.set(self.admin_user.id)
        final = await asset_use_controller.approve(app.id, True, "最终同意")
        self.assertEqual(final.status, 3)  # 已通过

        fresh_asset = await Asset.get(id=asset.id)
        self.assertEqual(fresh_asset.status, 1)  # 在用
        self.assertEqual(fresh_asset.owner_emp_id, self.emp.id)  # 领用人=申请人

        # 重复审批被拒
        CTX_USER_ID.set(self.admin_user.id)
        with self.assertRaises(Exception) as ctx:
            await asset_use_controller.approve(app.id, True, "再批一次")
        self.assertIn("不能重复审批", str(ctx.exception))
        return asset

    async def test_take_flow_and_double_apply_rejected(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.schemas.asset_uses import AssetUseCreate

        asset = await self._apply_and_approve_take()
        # 已通过后资产在用，再申请领用被拒
        CTX_USER_ID.set(self.emp_user.id)
        with self.assertRaises(Exception) as ctx:
            await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=1))
        self.assertIn("不可领用", str(ctx.exception))

    async def test_return_flow(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.models.business import Asset
        from app.schemas.asset_uses import AssetUseCreate

        asset = await self._apply_and_approve_take()
        # 归还：必须是自己名下的资产
        CTX_USER_ID.set(self.emp_user.id)
        ret = await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=2))
        self.assertEqual(ret.status, 1)
        # 超管在一级点通过 = 一次终审（不再需要点两次）
        CTX_USER_ID.set(self.admin_user.id)
        final = await asset_use_controller.approve(ret.id, True, "同意归还")
        self.assertEqual(final.status, 3)
        self.assertEqual(final.manager_approver_id, self.admin_user.id)
        self.assertEqual(final.admin_approver_id, self.admin_user.id)
        fresh = await Asset.get(id=asset.id)
        self.assertEqual(fresh.status, 2)  # 闲置
        self.assertIsNone(fresh.owner_emp_id)

    async def test_superuser_one_shot_take_approve(self):
        """超管对「待主管」申请点一次通过，资产应立即在用（修复双击才生效的体验bug）"""
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.models.business import Asset
        from app.schemas.asset_uses import AssetUseCreate

        asset = await Asset.create(asset_no="AST101", name="超管一键领用", status=2)
        CTX_USER_ID.set(self.emp_user.id)
        app = await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=1))
        self.assertEqual(app.status, 1)

        CTX_USER_ID.set(self.admin_user.id)
        final = await asset_use_controller.approve(app.id, True, "超管通过")
        self.assertEqual(final.status, 3)
        fresh = await Asset.get(id=asset.id)
        self.assertEqual(fresh.status, 1)
        self.assertEqual(fresh.owner_emp_id, self.emp.id)

    async def test_resigned_employee_cannot_apply(self):
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.models.business import Asset
        from app.schemas.asset_uses import AssetUseCreate

        from app.models.business import Employee

        self.emp.status = False
        await self.emp.save()
        asset = await Asset.create(asset_no="AST200", name="x", status=2)
        CTX_USER_ID.set(self.emp_user.id)
        with self.assertRaises(Exception) as ctx:
            await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=1))
        self.assertIn("离职", str(ctx.exception))

    async def test_use_type_schema_enum(self):
        """use_type 枚举校验（0/3/99 必须被 pydantic 拒绝）"""
        from pydantic import ValidationError
        from app.schemas.asset_uses import AssetUseCreate

        with self.assertRaises(ValidationError):
            AssetUseCreate(asset_id=1, use_type=0)
        with self.assertRaises(ValidationError):
            AssetUseCreate(asset_id=1, use_type=99)

    async def test_notification_stage_delivery_iso_a2(self):
        """ISO-A2/A3：提交只通知主管；主管通过后再通知超管；申请人无请审批。"""
        from app.core.ctx import CTX_USER_ID
        from app.controllers.asset_use import asset_use_controller
        from app.models.business import Asset, Notification
        from app.schemas.asset_uses import AssetUseCreate
        from app.services.notification_service import TYPE_APPROVAL_TASK, TYPE_APPLICANT_PROGRESS

        asset = await Asset.create(asset_no="AST-ISO-A", name="隔离测资产", status=2)
        CTX_USER_ID.set(self.emp_user.id)
        app = await asset_use_controller.create_application(AssetUseCreate(asset_id=asset.id, use_type=1))

        mgr_notes = await Notification.filter(user_id=self.manager_user.id).all()
        adm_notes = await Notification.filter(user_id=self.admin_user.id).all()
        emp_notes = await Notification.filter(user_id=self.emp_user.id).all()
        self.assertTrue(any(n.type == TYPE_APPROVAL_TASK for n in mgr_notes))
        self.assertFalse(any(n.type == TYPE_APPROVAL_TASK for n in adm_notes))
        self.assertFalse(any("请审批" in (n.title or "") for n in emp_notes))

        CTX_USER_ID.set(self.manager_user.id)
        await asset_use_controller.approve(app.id, True, "主管通过")
        adm_notes2 = await Notification.filter(user_id=self.admin_user.id).all()
        self.assertTrue(any(n.type == TYPE_APPROVAL_TASK for n in adm_notes2))
        emp_notes2 = await Notification.filter(user_id=self.emp_user.id).all()
        self.assertTrue(any(n.type == TYPE_APPLICANT_PROGRESS for n in emp_notes2))
        self.assertTrue(any("你的领用申请" in (n.title or "") for n in emp_notes2))

    # ---------- 登录防爆破 ----------
    async def test_login_guard_reset_clears_ip_counter(self):
        from app.core.login_guard import LoginGuard

        guard = LoginGuard(max_attempts=5, lock_seconds=300, ip_max_attempts=20)
        # 同 IP 下多个用户名各失败 5 次 → IP 计数 10
        for u in ("u1", "u2"):
            for _ in range(5):
                guard.record_failure(u, "1.2.3.4")
        # 任一用户名在该 IP 再失败 → 已达 IP 上限（10<20 未触发，再凑）
        for u in ("u3", "u4"):
            for _ in range(5):
                guard.record_failure(u, "1.2.3.4")
        # IP 计数 20 → 任意用户名 check 被锁
        with self.assertRaises(Exception):
            guard.check("u5", "1.2.3.4")
        # 修复验证：某用户名登录成功后 reset 应清空整个 IP 的失败计数
        guard.reset("u1", "1.2.3.4")
        guard.check("u5", "1.2.3.4")  # 不再被锁

    # ---------- 网关限流 ----------
    async def test_gateway_rate_limit_buckets(self):
        """网关 v3：已登录（uid）宽松限流且不进黑名单；未登录严格限流进黑名单"""
        from app.core.gateway import GatewayRateLimitMiddleware, ANON_MAX_REQUESTS, AUTH_MAX_REQUESTS

        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        def isolated_gateway(filename: str):
            gateway = GatewayRateLimitMiddleware(None)
            gateway._blacklist_db = os.path.join(temp_dir.name, filename)
            gateway._blacklist = {}
            return gateway

        gw = isolated_gateway("auth.json")
        uid = "42"
        # 已登录：超过账号上限（1000）才拒绝，且不产生黑名单
        for _ in range(AUTH_MAX_REQUESTS + 5):
            ok = gw._check(gw._auth_requests, f"uid:{uid}", 300, AUTH_MAX_REQUESTS, blacklist_on_overflow=False)
        self.assertFalse(ok)
        self.assertNotIn(f"uid:{uid}", gw.list_blacklist())
        # 未登录：超限即黑名单（爆破特征）
        gw2 = isolated_gateway("anonymous.json")
        for i in range(ANON_MAX_REQUESTS + 3):
            last_ok = gw2._check(gw2._anon_requests, "ip:9.9.9.9", 60, ANON_MAX_REQUESTS, blacklist_on_overflow=True)
        self.assertFalse(last_ok)
        self.assertIn("ip:9.9.9.9", gw2.list_blacklist())
        # 解封
        self.assertTrue(gw2.remove_blacklist("ip:9.9.9.9"))
        self.assertNotIn("ip:9.9.9.9", gw2.list_blacklist())


if __name__ == "__main__":
    unittest.main()
