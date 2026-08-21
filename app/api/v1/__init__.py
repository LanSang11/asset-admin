from fastapi import APIRouter

from app.core.dependency import DependAuth, DependPermission

from .apis import apis_router
from .ai import ai_router_all
from .ai.assistant import router as ai_assistant_router
from .api_config import api_config_router_all
from .assets import assets_router_all
from .asset_repairs import asset_repairs_router_all
from .asset_transfers import asset_transfers_router_all
from .inventorys import inventory_router_all
from .asset_uses import asset_uses_router_all
from .auditlog import auditlog_router
from .base import base_router
from .depts import depts_router
from .dashboard import dashboard_router_all
from .employees import employees_router_all
from .employee_attachments import employee_attachments_router_all
from .exports import exports_router_all
from .knowledge import knowledge_router_all
from .menus import menus_router
from .notifications import notifications_router_all
from .roles import roles_router
from .security import security_router
from .users import users_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
# 审计/安全：路由内 DependSuperUser 硬锁；仍挂 DependPermission 以进 API 表
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(security_router, prefix="/security", dependencies=[DependPermission])
# 业务模块统一接入权限体系（修复：原仅 DependAuth，任何登录用户可读全量敏感数据）
v1_router.include_router(employees_router_all, prefix="/employee", dependencies=[DependPermission])
v1_router.include_router(employee_attachments_router_all, prefix="/employee-attachment", dependencies=[DependPermission])
v1_router.include_router(knowledge_router_all, prefix="/kb", dependencies=[DependPermission])
v1_router.include_router(assets_router_all, prefix="/asset", dependencies=[DependPermission])
v1_router.include_router(asset_uses_router_all, prefix="/asset-use", dependencies=[DependPermission])
v1_router.include_router(asset_repairs_router_all, prefix="/asset-repair", dependencies=[DependPermission])
v1_router.include_router(asset_transfers_router_all, prefix="/asset-transfer", dependencies=[DependPermission])
v1_router.include_router(inventory_router_all, prefix="/inventory", dependencies=[DependPermission])
v1_router.include_router(notifications_router_all, prefix="/notification", dependencies=[DependPermission])
v1_router.include_router(exports_router_all, prefix="/export", dependencies=[DependPermission])
v1_router.include_router(dashboard_router_all, prefix="/dashboard", dependencies=[DependPermission])
v1_router.include_router(api_config_router_all, prefix="/api-config", dependencies=[DependPermission])
v1_router.include_router(ai_router_all, prefix="/ai", dependencies=[DependPermission])
# 全站抽屉：所有已登录用户可问；工具范围仍由服务端按角色重算
v1_router.include_router(ai_assistant_router, prefix="/ai", dependencies=[DependAuth])
