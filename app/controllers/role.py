from typing import List

from fastapi.exceptions import HTTPException
from tortoise.transactions import in_transaction

from app.core.crud import CRUDBase
from app.models.admin import Api, Menu, Role
from app.schemas.roles import RoleCreate, RoleUpdate


class RoleController(CRUDBase[Role, RoleCreate, RoleUpdate]):
    def __init__(self):
        super().__init__(model=Role)

    async def is_exist(self, name: str) -> bool:
        return await self.model.filter(name=name).exists()

    async def update_roles(self, role: Role, menu_ids: List[int], api_infos: List[dict]) -> None:
        """更新角色权限：先批量校验存在性，再在事务内整体替换（防部分更新/半清空）。"""
        # 1) 批量校验菜单存在性（原实现逐条 first()，缺失时 add(None) 抛异常且已 clear）
        found_menus = []
        if menu_ids:
            found = await Menu.filter(id__in=menu_ids)
            found_ids = {m.id for m in found}
            missing = set(menu_ids) - found_ids
            if missing:
                raise HTTPException(status_code=400, detail=f"菜单不存在: {sorted(missing)}")
            found_menus = list({m.id: m for m in found}.values())

        # 2) 批量校验 API 存在性（path+method 精确匹配）
        api_objs = []
        for item in api_infos:
            api_obj = await Api.filter(path=item.get("path"), method=item.get("method")).first()
            if not api_obj:
                raise HTTPException(status_code=400, detail=f"API 不存在: {item.get('method')} {item.get('path')}")
            api_objs.append(api_obj)

        # 3) 事务内整体替换（任一失败整体回滚，权限不会半清空）
        async with in_transaction():
            await role.menus.clear()
            if found_menus:
                await role.menus.add(*found_menus)
            await role.apis.clear()
            if api_objs:
                await role.apis.add(*api_objs)


role_controller = RoleController()
