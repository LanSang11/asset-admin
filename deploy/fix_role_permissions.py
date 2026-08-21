# -*- coding: utf-8 -*-
"""部署后执行：修复已有数据库的角色权限数据（配合代码升级）。

背景（2026-08-10 安全升级）：
1. refresh_api 同步路由表（新增 /asset/my、/base/blacklist 等，删除历史 HEAD 错乱记录）
2. 原「普通用户」角色被初始化授予了全部 GET 接口（含全量导出）——
   收窄为仅业务读接口（基础/员工/资产/领用/通知/看板 GET），导出与系统管理不授予
3. 「管理员」角色同步为全部 API（含新路由）

运行（容器内）：python deploy/fix_role_permissions.py
"""
import asyncio

from tortoise import Tortoise

from app.controllers.api import api_controller
from app.models.admin import Api, Role
from app.settings.config import settings

# 普通用户可保留的读接口模块
USER_READ_TAGS = ("基础模块", "员工模块", "资产模块", "领用归还模块", "通知模块", "统计看板模块")


async def main():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    await api_controller.refresh_api()
    print("API 表刷新完成")

    all_apis = await Api.all()

    # 普通用户保留：业务模块读接口 + 业务闭环必要写接口（申请/审批/标已读）
    USER_TAGS = ("基础模块", "员工模块", "资产模块", "领用归还模块", "通知模块", "统计看板模块")
    USER_POST_PATHS = (
        "/api/v1/asset-use/apply",
        "/api/v1/asset-use/approve",
        "/api/v1/notification/read",
        "/api/v1/notification/read_all",
    )

    user_role = await Role.filter(name="普通用户").first()
    if user_role:
        keep = [
            a for a in all_apis
            if (a.method == "GET" and a.tags in USER_TAGS)
            or (a.method == "POST" and a.path in USER_POST_PATHS)
        ]
        await user_role.apis.clear()
        await user_role.apis.add(*keep)
        print(f"普通用户角色权限已收窄：{len(keep)} 个接口")

    admin_role = await Role.filter(name="管理员").first()
    if admin_role:
        await admin_role.apis.clear()
        await admin_role.apis.add(*all_apis)
        print(f"管理员角色权限已同步：{len(all_apis)} 个接口")

    await Tortoise.close_connections()
    print("角色权限修复完成")


if __name__ == "__main__":
    asyncio.run(main())
