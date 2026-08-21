import shutil

from aerich import Command
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from tortoise.expressions import Q

from app.api import api_router
from app.controllers.api import api_controller
from app.controllers.user import UserCreate, user_controller
from app.core.exceptions import (
    DoesNotExist,
    DoesNotExistHandle,
    HTTPException,
    HttpExcHandle,
    IntegrityError,
    IntegrityHandle,
    RequestValidationError,
    RequestValidationHandle,
    ResponseValidationError,
    ResponseValidationHandle,
    StarletteHTTPException,
    TortoiseValidationHandle,
    UnhandledExceptionHandle,
    ValidationError,
)
from app.core.security import gen_initial_password
from app.log import logger
from app.models.admin import Api, Menu, Role
from app.schemas.menus import MenuType
from app.settings.config import settings

from .middlewares import BackGroundTaskMiddleware, HttpAuditLogMiddleware, SecurityHeadersMiddleware
from .gateway import GatewayRateLimitMiddleware


def make_middlewares():
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        ),
        Middleware(SecurityHeadersMiddleware),
        Middleware(GatewayRateLimitMiddleware),
        Middleware(BackGroundTaskMiddleware),
        Middleware(
            HttpAuditLogMiddleware,
            methods=["GET", "POST", "PUT", "DELETE"],
            exclude_paths=[
                "/api/v1/base/access_token",
                "/api/v1/base/captcha/",
                "/api/v1/base/update_password",
                "/api/v1/user/reset_password",
                "/docs",
                "/openapi.json",
            ],
        ),
    ]
    return middleware


def register_exceptions(app: FastAPI):
    app.add_exception_handler(DoesNotExist, DoesNotExistHandle)
    # 405 Method Not Allowed 等由 Starlette 抛出基类；FastAPI.HTTPException 是其子类
    app.add_exception_handler(StarletteHTTPException, HttpExcHandle)
    app.add_exception_handler(HTTPException, HttpExcHandle)
    app.add_exception_handler(IntegrityError, IntegrityHandle)
    app.add_exception_handler(ValidationError, TortoiseValidationHandle)
    app.add_exception_handler(RequestValidationError, RequestValidationHandle)
    app.add_exception_handler(ResponseValidationError, ResponseValidationHandle)
    # 兜底：未捕获的未知异常统一转中文 500（修复：原缺失，未知异常返回英文堆栈/默认 500）
    app.add_exception_handler(Exception, UnhandledExceptionHandle)


def register_routers(app: FastAPI, prefix: str = "/api"):
    app.include_router(api_router, prefix=prefix)


async def init_superuser():
    user = await user_controller.model.exists()
    if not user:
        # 初始超管密码：随机生成一次性密码（符合强密码策略），仅打印到启动日志，
        # 首次登录强制改密（模型默认 must_change_password=True），避免公开默认凭据被接管
        initial_password = gen_initial_password()
        await user_controller.create_user(
            UserCreate(
                username="admin",
                email="admin@admin.com",
                password=initial_password,
                is_active=True,
                is_superuser=True,
            )
        )
        # 修复：loguru 用 {} 占位符，原 %s 写法导致密码不打印（无法登录）
        logger.warning(
            "首次初始化超级管理员账号 admin，一次性初始密码（仅本次启动可见，首次登录后必须修改）：{}",
            initial_password,
        )


async def init_menus():
    menus = await Menu.exists()
    if not menus:
        parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=1,
            parent_id=0,
            icon="carbon:gui-management",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
        children_menu = [
            Menu(
                menu_type=MenuType.MENU,
                name="用户管理",
                path="user",
                order=1,
                parent_id=parent_menu.id,
                icon="material-symbols:person-outline-rounded",
                is_hidden=False,
                component="/system/user",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="角色管理",
                path="role",
                order=2,
                parent_id=parent_menu.id,
                icon="carbon:user-role",
                is_hidden=False,
                component="/system/role",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="菜单管理",
                path="menu",
                order=3,
                parent_id=parent_menu.id,
                icon="material-symbols:list-alt-outline",
                is_hidden=False,
                component="/system/menu",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="API管理",
                path="api",
                order=4,
                parent_id=parent_menu.id,
                icon="ant-design:api-outlined",
                is_hidden=False,
                component="/system/api",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="部门管理",
                path="dept",
                order=5,
                parent_id=parent_menu.id,
                icon="mingcute:department-line",
                is_hidden=False,
                component="/system/dept",
                keepalive=False,
            ),
            Menu(
                menu_type=MenuType.MENU,
                name="审计日志",
                path="auditlog",
                order=6,
                parent_id=parent_menu.id,
                icon="ph:clipboard-text-bold",
                is_hidden=False,
                component="/system/auditlog",
                keepalive=False,
            ),
        ]
        await Menu.bulk_create(children_menu)
        await Menu.create(
            menu_type=MenuType.MENU,
            name="一级菜单",
            path="/top-menu",
            order=2,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="/top-menu",
            keepalive=False,
            redirect="",
        )


async def init_apis():
    # 修复：每次启动刷新 API 表（原仅在表为空时执行——已有库升级后新路由
    # 如 /asset/my、/base/blacklist 不进权限表，非超管全部 403）。
    # refresh_api 幂等：删除已废弃路由记录、同步新增路由；不会清空角色的自定义授权。
    await api_controller.refresh_api()


async def ensure_schema_patches():
    """轻量补列/建表：云端已有 SQLite 时 aerich 历史可能不全，用 PRAGMA 兜底。"""
    try:
        from tortoise import Tortoise, connections

        # TORTOISE_ORM 连接别名是 sqlite（不是 default）
        try:
            conn = connections.get("sqlite")
        except Exception:
            conn = Tortoise.get_connection("sqlite")

        async def _cols(table: str) -> set:
            rows = await conn.execute_query_dict(f"PRAGMA table_info({table})")
            return {c.get("name") for c in rows}

        # ISO-A1
        names = await _cols("notifications")
        if "type" not in names:
            await conn.execute_script(
                "ALTER TABLE notifications ADD COLUMN type VARCHAR(40) NOT NULL DEFAULT ''"
            )
            logger.info("schema patch applied: notifications.type")

        # 用户 TOTP
        unames = await _cols("user")
        if "totp_secret" not in unames:
            await conn.execute_script("ALTER TABLE user ADD COLUMN totp_secret VARCHAR(64)")
            logger.info("schema patch applied: user.totp_secret")
        if "totp_enabled" not in unames:
            await conn.execute_script(
                "ALTER TABLE user ADD COLUMN totp_enabled INT NOT NULL DEFAULT 0"
            )
            logger.info("schema patch applied: user.totp_enabled")
        if "auth_version" not in unames:
            await conn.execute_script(
                "ALTER TABLE user ADD COLUMN auth_version INT NOT NULL DEFAULT 0"
            )
            logger.info("schema patch applied: user.auth_version")
        user_security_alters = {
            "recovery_question": "ALTER TABLE user ADD COLUMN recovery_question VARCHAR(120)",
            "recovery_answer_hash": "ALTER TABLE user ADD COLUMN recovery_answer_hash VARCHAR(255)",
            "recovery_fail_count": "ALTER TABLE user ADD COLUMN recovery_fail_count INT NOT NULL DEFAULT 0",
            "recovery_locked_until": "ALTER TABLE user ADD COLUMN recovery_locked_until TIMESTAMP",
            "password_changed_at": "ALTER TABLE user ADD COLUMN password_changed_at TIMESTAMP",
        }
        for col, ddl in user_security_alters.items():
            if col not in unames:
                await conn.execute_script(ddl)
                logger.info(f"schema patch applied: user.{col}")

        await conn.execute_script(
            """
            CREATE TABLE IF NOT EXISTS verification_policy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_key VARCHAR(64) NOT NULL UNIQUE,
                label VARCHAR(80) NOT NULL,
                mode VARCHAR(16) NOT NULL DEFAULT 'off',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_verification_policy_key
                ON verification_policy(operation_key);
            CREATE TABLE IF NOT EXISTS verification_settings (
                id INTEGER PRIMARY KEY,
                force_superuser INT NOT NULL DEFAULT 1,
                role_ids JSON NOT NULL DEFAULT '[]',
                acceptance_until TIMESTAMP,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            );
            """
        )
        vset_cols = await _cols("verification_settings")
        if vset_cols and "acceptance_until" not in vset_cols:
            await conn.execute_script(
                "ALTER TABLE verification_settings ADD COLUMN acceptance_until TIMESTAMP"
            )
            logger.info("schema patch applied: verification_settings.acceptance_until")
        if vset_cols and "password_max_days" not in vset_cols:
            await conn.execute_script(
                "ALTER TABLE verification_settings ADD COLUMN password_max_days INT NOT NULL DEFAULT 0"
            )
            logger.info("schema patch applied: verification_settings.password_max_days")
        if vset_cols and "password_deadline" not in vset_cols:
            await conn.execute_script(
                "ALTER TABLE verification_settings ADD COLUMN password_deadline TIMESTAMP"
            )
            logger.info("schema patch applied: verification_settings.password_deadline")

        from app.services.verification_policy import ensure_verification_defaults

        await ensure_verification_defaults()

        # 审计日志 IP / UA
        anames = await _cols("auditlog")
        # tortoise 默认表名可能是 auditlog
        if not anames:
            anames = await _cols("audit_log")
            audit_table = "audit_log" if anames else "auditlog"
        else:
            audit_table = "auditlog"
        anames = await _cols(audit_table)
        if anames:
            # 历史版本曾记录认证端点正文；清空秘密正文但保留路径、用户、状态和耗时。
            if {"path", "request_args", "response_body"}.issubset(anames):
                from app.core.security import AUTH_SECRET_AUDIT_PATHS

                placeholders = ",".join("?" for _ in AUTH_SECRET_AUDIT_PATHS)
                await conn.execute_query(
                    f"UPDATE {audit_table} SET request_args = NULL, response_body = NULL "
                    f"WHERE path IN ({placeholders})",
                    list(AUTH_SECRET_AUDIT_PATHS),
                )
            if "ip" not in anames:
                await conn.execute_script(
                    f"ALTER TABLE {audit_table} ADD COLUMN ip VARCHAR(64) NOT NULL DEFAULT ''"
                )
                logger.info(f"schema patch applied: {audit_table}.ip")
            if "user_agent" not in anames:
                await conn.execute_script(
                    f"ALTER TABLE {audit_table} ADD COLUMN user_agent VARCHAR(512) NOT NULL DEFAULT ''"
                )
                logger.info(f"schema patch applied: {audit_table}.user_agent")

        # 安全事件表
        sec_cols = await _cols("security_event")
        if not sec_cols:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS security_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type VARCHAR(40) NOT NULL,
                    username VARCHAR(64) NOT NULL DEFAULT '',
                    user_id INT,
                    ip VARCHAR(64) NOT NULL DEFAULT '',
                    user_agent VARCHAR(512) NOT NULL DEFAULT '',
                    device_hash VARCHAR(32) NOT NULL DEFAULT '',
                    country VARCHAR(64) NOT NULL DEFAULT '',
                    region VARCHAR(64) NOT NULL DEFAULT '',
                    isp VARCHAR(128) NOT NULL DEFAULT '',
                    risk_tags VARCHAR(255) NOT NULL DEFAULT '',
                    detail VARCHAR(500) NOT NULL DEFAULT '',
                    success INT NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_security_event_type ON security_event(event_type);
                CREATE INDEX IF NOT EXISTS idx_security_event_username ON security_event(username);
                CREATE INDEX IF NOT EXISTS idx_security_event_ip ON security_event(ip);
                CREATE INDEX IF NOT EXISTS idx_security_event_created ON security_event(created_at);
                CREATE INDEX IF NOT EXISTS idx_security_event_device ON security_event(device_hash);
                """
            )
            logger.info("schema patch applied: security_event table")
            sec_cols = await _cols("security_event")
        if sec_cols:
            _sec_alters = {
                "country": "ALTER TABLE security_event ADD COLUMN country VARCHAR(64) NOT NULL DEFAULT ''",
                "region": "ALTER TABLE security_event ADD COLUMN region VARCHAR(64) NOT NULL DEFAULT ''",
                "isp": "ALTER TABLE security_event ADD COLUMN isp VARCHAR(128) NOT NULL DEFAULT ''",
                "risk_tags": "ALTER TABLE security_event ADD COLUMN risk_tags VARCHAR(255) NOT NULL DEFAULT ''",
            }
            for col, ddl in _sec_alters.items():
                if col not in sec_cols:
                    await conn.execute_script(ddl)
                    logger.info(f"schema patch applied: security_event.{col}")
            await conn.execute_script(
                "CREATE INDEX IF NOT EXISTS idx_security_event_device ON security_event(device_hash);"
            )

        agg_cols = await _cols("security_agg_bucket")
        if not agg_cols:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS security_agg_bucket (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket_minute TIMESTAMP NOT NULL,
                    event_type VARCHAR(40) NOT NULL,
                    source_key VARCHAR(80) NOT NULL,
                    ip VARCHAR(64) NOT NULL DEFAULT '',
                    country VARCHAR(64) NOT NULL DEFAULT '',
                    region VARCHAR(64) NOT NULL DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_agg_bucket_uniq
                    ON security_agg_bucket(bucket_minute, event_type, source_key);
                CREATE INDEX IF NOT EXISTS idx_sec_agg_type_minute
                    ON security_agg_bucket(event_type, bucket_minute);
                CREATE INDEX IF NOT EXISTS idx_sec_agg_ip_minute
                    ON security_agg_bucket(ip, bucket_minute);
                """
            )
            logger.info("schema patch applied: security_agg_bucket table")
        await conn.execute_script(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sec_agg_bucket_uniq
                ON security_agg_bucket(bucket_minute, event_type, source_key);
            CREATE INDEX IF NOT EXISTS idx_sec_agg_type_minute
                ON security_agg_bucket(event_type, bucket_minute);
            CREATE INDEX IF NOT EXISTS idx_sec_agg_ip_minute
                ON security_agg_bucket(ip, bucket_minute);
            """
        )

        # 报修单表
        repair_cols = await _cols("asset_repairs")
        if not repair_cols:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS asset_repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INT NOT NULL,
                    employee_id INT NOT NULL,
                    reason VARCHAR(255) NOT NULL DEFAULT '',
                    status INT NOT NULL DEFAULT 1,
                    manager_approver_id INT,
                    admin_approver_id INT,
                    manager_comment VARCHAR(255) NOT NULL DEFAULT '',
                    admin_comment VARCHAR(255) NOT NULL DEFAULT '',
                    manager_time TIMESTAMP,
                    admin_time TIMESTAMP,
                    complete_time TIMESTAMP,
                    complete_result VARCHAR(20) NOT NULL DEFAULT '',
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_asset_repairs_asset ON asset_repairs(asset_id);
                CREATE INDEX IF NOT EXISTS idx_asset_repairs_emp ON asset_repairs(employee_id);
                CREATE INDEX IF NOT EXISTS idx_asset_repairs_status ON asset_repairs(status);
                """
            )
            logger.info("schema patch applied: asset_repairs table")

        transfer_cols = await _cols("asset_transfers")
        if not transfer_cols:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS asset_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INT NOT NULL,
                    from_employee_id INT NOT NULL,
                    to_employee_id INT NOT NULL,
                    applicant_id INT NOT NULL,
                    reason VARCHAR(255) NOT NULL DEFAULT '',
                    status INT NOT NULL DEFAULT 1,
                    manager_approver_id INT,
                    admin_approver_id INT,
                    manager_comment VARCHAR(255) NOT NULL DEFAULT '',
                    admin_comment VARCHAR(255) NOT NULL DEFAULT '',
                    manager_time TIMESTAMP,
                    admin_time TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_asset_transfers_asset ON asset_transfers(asset_id);
                CREATE INDEX IF NOT EXISTS idx_asset_transfers_from ON asset_transfers(from_employee_id);
                CREATE INDEX IF NOT EXISTS idx_asset_transfers_to ON asset_transfers(to_employee_id);
                CREATE INDEX IF NOT EXISTS idx_asset_transfers_status ON asset_transfers(status);
                """
            )
            logger.info("schema patch applied: asset_transfers table")

        attach_cols = await _cols("employee_attachments")
        if not attach_cols:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS employee_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INT NOT NULL,
                    original_name VARCHAR(200) NOT NULL,
                    stored_name VARCHAR(80) NOT NULL,
                    mime VARCHAR(80) NOT NULL DEFAULT '',
                    size INT NOT NULL DEFAULT 0,
                    uploader_id INT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_employee_attachments_emp ON employee_attachments(employee_id);
                """
            )
            logger.info("schema patch applied: employee_attachments table")

        asset_cols = await _cols("assets")
        if asset_cols:
            if "warranty_until" not in asset_cols:
                await conn.execute_script("ALTER TABLE assets ADD COLUMN warranty_until DATE")
                logger.info("schema patch applied: assets.warranty_until")
            if "warranty_notified_state" not in asset_cols:
                await conn.execute_script(
                    "ALTER TABLE assets ADD COLUMN warranty_notified_state VARCHAR(20) NOT NULL DEFAULT ''"
                )
                logger.info("schema patch applied: assets.warranty_notified_state")

        inv_sess = await _cols("inventory_sessions")
        if not inv_sess:
            await conn.execute_script(
                """
                CREATE TABLE IF NOT EXISTS inventory_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(100) NOT NULL,
                    scope VARCHAR(16) NOT NULL DEFAULT 'all',
                    dept_id INT,
                    status INT NOT NULL DEFAULT 1,
                    created_by INT NOT NULL,
                    closed_by INT,
                    closed_at TIMESTAMP,
                    note VARCHAR(255) NOT NULL DEFAULT '',
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS inventory_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INT NOT NULL,
                    asset_id INT NOT NULL,
                    asset_no VARCHAR(50) NOT NULL,
                    asset_name VARCHAR(100) NOT NULL,
                    book_status INT NOT NULL,
                    book_owner_emp_id INT,
                    book_owner_name VARCHAR(50) NOT NULL DEFAULT '',
                    book_dept_id INT,
                    result VARCHAR(16) NOT NULL DEFAULT '',
                    counted_status INT,
                    note VARCHAR(255) NOT NULL DEFAULT '',
                    counted_by INT,
                    counted_at TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_inventory_lines_session ON inventory_lines(session_id);
                CREATE INDEX IF NOT EXISTS idx_inventory_lines_asset ON inventory_lines(asset_id);
                """
            )
            logger.info("schema patch applied: inventory_sessions/lines")

        await ensure_repair_menu()
        await ensure_transfer_menu()
        await ensure_kb_menu()
        await ensure_inventory_menu()

        # 安全中心菜单（挂在系统管理下）
        await ensure_security_menu()
    except Exception as e:
        logger.warning(f"ensure_schema_patches skipped: {e!r}")


async def ensure_repair_menu():
    """幂等：业务管理下增加「报修管理」。"""
    try:
        from app.models.admin import Menu, MenuType

        parent = await Menu.filter(name="业务管理").first()
        if not parent:
            return
        exists = await Menu.filter(path="repair", parent_id=parent.id).first()
        if exists:
            return
        await Menu.create(
            menu_type=MenuType.MENU,
            name="报修管理",
            path="repair",
            order=8,
            parent_id=parent.id,
            icon="mdi:wrench-outline",
            is_hidden=False,
            component="/business/repair",
            keepalive=False,
        )
        logger.info("menu patch applied: 报修管理")
    except Exception as e:
        logger.warning(f"ensure_repair_menu skipped: {e!r}")


async def ensure_transfer_menu():
    """幂等：业务管理下增加「调拨管理」。"""
    try:
        from app.models.admin import Menu, MenuType

        parent = await Menu.filter(name="业务管理").first()
        if not parent:
            return
        exists = await Menu.filter(path="transfer", parent_id=parent.id).first()
        if exists:
            return
        await Menu.create(
            menu_type=MenuType.MENU,
            name="调拨管理",
            path="transfer",
            order=9,
            parent_id=parent.id,
            icon="mdi:swap-horizontal-circle-outline",
            is_hidden=False,
            component="/business/transfer",
            keepalive=False,
        )
        logger.info("menu patch applied: 调拨管理")
    except Exception as e:
        logger.warning(f"ensure_transfer_menu skipped: {e!r}")


async def ensure_kb_menu():
    """幂等：业务管理下增加「知识库」。"""
    try:
        from app.models.admin import Menu, MenuType

        parent = await Menu.filter(name="业务管理").first()
        if not parent:
            return
        exists = await Menu.filter(path="kb", parent_id=parent.id).first()
        if exists:
            return
        await Menu.create(
            menu_type=MenuType.MENU,
            name="知识库",
            path="kb",
            order=10,
            parent_id=parent.id,
            icon="mdi:book-open-page-variant-outline",
            is_hidden=False,
            component="/business/kb",
            keepalive=False,
        )
        logger.info("menu patch applied: 知识库")
    except Exception as e:
        logger.warning(f"ensure_kb_menu skipped: {e!r}")


async def ensure_inventory_menu():
    """幂等：业务管理下增加「盘点」。"""
    try:
        from app.models.admin import Menu, MenuType

        parent = await Menu.filter(name="业务管理").first()
        if not parent:
            return
        exists = await Menu.filter(path="inventory", parent_id=parent.id).first()
        if exists:
            return
        await Menu.create(
            menu_type=MenuType.MENU,
            name="盘点",
            path="inventory",
            order=11,
            parent_id=parent.id,
            icon="mdi:clipboard-text-outline",
            is_hidden=False,
            component="/business/inventory",
            keepalive=False,
        )
        logger.info("menu patch applied: 盘点")
    except Exception as e:
        logger.warning(f"ensure_inventory_menu skipped: {e!r}")


async def ensure_security_menu():
    """幂等：系统管理下增加「安全中心」菜单。"""
    try:
        parent = await Menu.filter(name="系统管理", parent_id=0).first()
        if not parent:
            return
        exists = await Menu.filter(path="security", parent_id=parent.id).first()
        if exists:
            return
        await Menu.create(
            menu_type=MenuType.MENU,
            name="安全中心",
            path="security",
            order=7,
            parent_id=parent.id,
            icon="mdi:shield-lock-outline",
            is_hidden=False,
            component="/system/security",
            keepalive=False,
        )
        logger.info("menu patch applied: 安全中心")
    except Exception as e:
        logger.warning(f"ensure_security_menu skipped: {e!r}")


async def init_db():
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    try:
        await command.init_db(safe=True)
    except FileExistsError:
        pass

    await command.init()
    try:
        await command.migrate()
    except AttributeError:
        logger.warning("unable to retrieve model history from database, model history will be created from scratch")
        shutil.rmtree("migrations")
        await command.init_db(safe=True)
    except Exception as e:
        # SQLite 不能 ALTER 列注释；字段 description 变化会让 aerich 拖垮启动
        msg = str(e)
        if "Alter column comment" in msg or e.__class__.__name__ == "NotSupportError":
            logger.warning("aerich migrate skipped (sqlite cannot alter column comment): {}", e)
        else:
            raise

    await command.upgrade(run_in_transaction=True)
    await ensure_schema_patches()


async def init_roles():
    roles = await Role.exists()
    if not roles:
        admin_role = await Role.create(
            name="管理员",
            desc="管理员角色",
        )
        user_role = await Role.create(
            name="普通用户",
            desc="普通用户角色",
        )

        # 分配所有API给管理员角色
        all_apis = await Api.all()
        await admin_role.apis.add(*all_apis)
        # 分配所有菜单给管理员和普通用户
        all_menus = await Menu.all()
        await admin_role.menus.add(*all_menus)
        await user_role.menus.add(*all_menus)

        # 为普通用户分配基本API（修复：原 `Q(method__in=["GET"]) | Q(tags="基础模块")` 是 OR，
        # 导致普通用户默认拥有全部 GET 接口（含全量导出）。现改为：
        # ① 业务模块读接口（员工/资产/领用/通知/看板/基础 的 GET）
        # ② 业务闭环必要的写接口（申请、审批、通知标已读——后端均有属主/主管/超管二次校验）
        # 数据导出模块与系统管理接口默认不授予普通用户
        USER_TAGS = ("基础模块", "员工模块", "资产模块", "领用归还模块", "通知模块", "统计看板模块")
        USER_POST_PATHS = (
            "/api/v1/asset-use/apply",
            "/api/v1/asset-use/approve",
            "/api/v1/notification/read",
            "/api/v1/notification/read_all",
        )
        all_apis = await Api.all()
        basic_apis = [
            a for a in all_apis
            if (a.method == "GET" and a.tags in USER_TAGS)
            or (a.method == "POST" and a.path in USER_POST_PATHS)
        ]
        await user_role.apis.add(*basic_apis)


async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await init_roles()
