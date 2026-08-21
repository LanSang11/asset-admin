from fastapi.routing import APIRoute

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import Api
from app.schemas.apis import ApiCreate, ApiUpdate


class ApiController(CRUDBase[Api, ApiCreate, ApiUpdate]):
    def __init__(self):
        super().__init__(model=Api)

    @staticmethod
    def _pick_method(methods: set) -> str:
        """修复：route.methods 是无序 set（Starlette 会为 GET 自动加 HEAD），
        list()[0] 可能取到 HEAD 导致权限表错乱（GET 请求全 403）。按优先级取主方法。"""
        for preferred in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            if preferred in methods:
                return preferred
        return sorted(methods)[0]

    async def refresh_api(self):
        from app import app

        # 删除废弃API数据
        all_api_list = []
        for route in app.routes:
            # 只更新有鉴权的API
            if isinstance(route, APIRoute) and len(route.dependencies) > 0:
                all_api_list.append((self._pick_method(route.methods), route.path_format))
        delete_api = []
        for api in await Api.all():
            if (api.method, api.path) not in all_api_list:
                delete_api.append((api.method, api.path))
        for item in delete_api:
            method, path = item
            logger.debug(f"API Deleted {method} {path}")
            await Api.filter(method=method, path=path).delete()

        for route in app.routes:
            if isinstance(route, APIRoute) and len(route.dependencies) > 0:
                method = self._pick_method(route.methods)
                path = route.path_format
                summary = route.summary
                tags = list(route.tags)[0] if route.tags else "未分组"
                api_obj = await Api.filter(method=method, path=path).first()
                if api_obj:
                    await api_obj.update_from_dict(dict(method=method, path=path, summary=summary, tags=tags)).save()
                else:
                    logger.debug(f"API Created {method} {path}")
                    await Api.create(**dict(method=method, path=path, summary=summary, tags=tags))


api_controller = ApiController()
