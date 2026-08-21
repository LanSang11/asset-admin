import json
import re
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.dependency import AuthControl
from app.core.security import AUTH_SECRET_AUDIT_PATHS, truncate_sensitive
from app.models.admin import AuditLog, User

from .bgtask import BgTasks


class SimpleBaseMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)

        response = await self.before_request(request) or self.app
        await response(request.scope, request.receive, send)
        await self.after_request(request)

    async def before_request(self, request: Request):
        return self.app

    async def after_request(self, request: Request):
        return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """基础安全响应头（API 层兜底；静态资源建议 Nginx 同步配置）。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        return response


class BackGroundTaskMiddleware(SimpleBaseMiddleware):
    async def before_request(self, request):
        await BgTasks.init_bg_tasks_obj()

    async def after_request(self, request):
        await BgTasks.execute_tasks()


class HttpAuditLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, methods: list[str], exclude_paths: list[str]):
        super().__init__(app)
        self.methods = methods
        self.exclude_paths = exclude_paths
        self.audit_log_paths = ["/api/v1/auditlog/list"]
        self.max_body_size = 1024 * 1024  # 1MB 响应体大小限制
        # 文件下载/导出类路径：响应体非 JSON，跳过日志
        self.no_json_paths = ["/api/v1/export/"]
        # 认证秘密端点只记录元数据，不落请求/响应体。
        self.secret_body_paths = AUTH_SECRET_AUDIT_PATHS

    async def get_request_args(self, request: Request) -> dict:
        if request.url.path in self.secret_body_paths:
            return {}
        args = {}
        # 获取查询参数
        for key, value in request.query_params.items():
            args[key] = value

        # 获取请求体
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                args.update(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 修复：捕获 UnicodeDecodeError 等一切 body 解析失败
                # （原仅捕获 JSONDecodeError，非 UTF-8 编码的 body 会让整个请求 500）
                try:
                    body = await request.form()
                    # args.update(body)
                    for k, v in body.items():
                        if hasattr(v, "filename"):  # 文件上传行为
                            args[k] = v.filename
                        elif isinstance(v, list) and v and hasattr(v[0], "filename"):
                            args[k] = [file.filename for file in v]
                        else:
                            args[k] = v
                except Exception:
                    pass

        # 敏感字段脱敏：密码类字段一律不落审计日志
        SENSITIVE_KEYS = ("password", "old_password", "new_password", "confirm_password", "secret")
        for key in list(args.keys()):
            if key.lower() in SENSITIVE_KEYS:
                args[key] = "***"

        # 长文本截断（AI 对话全文、大段请求体等），避免敏感内容明文落库
        args = truncate_sensitive(args)

        return args

    async def get_response_body(self, request: Request, response: Response) -> Any:
        if request.url.path in self.secret_body_paths:
            return None
        # 导出/下载类路径：响应体非 JSON，不记录响应内容
        if any(request.url.path.startswith(path) for path in self.no_json_paths):
            return None
        # 检查Content-Length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return {"code": 0, "msg": "Response too large to log", "data": None}

        if hasattr(response, "body"):
            body = response.body
        else:
            body_chunks = []
            async for chunk in response.body_iterator:
                if not isinstance(chunk, bytes):
                    chunk = chunk.encode(response.charset)
                body_chunks.append(chunk)

            response.body_iterator = self._async_iter(body_chunks)
            body = b"".join(body_chunks)

        if any(request.url.path.startswith(path) for path in self.audit_log_paths):
            try:
                data = self.lenient_json(body)
                # 只保留基本信息，去除详细的响应内容
                if isinstance(data, dict):
                    data.pop("response_body", None)
                    if "data" in data and isinstance(data["data"], list):
                        for item in data["data"]:
                            item.pop("response_body", None)
                return truncate_sensitive(data)
            except Exception:
                return None

        return truncate_sensitive(self.lenient_json(body))

    def lenient_json(self, v: Any) -> Any:
        if isinstance(v, (str, bytes)):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                pass
        return v

    async def _async_iter(self, items: list[bytes]) -> AsyncGenerator[bytes, None]:
        for item in items:
            yield item

    async def get_request_log(self, request: Request, response: Response) -> dict:
        """
        根据request和response对象获取对应的日志记录数据
        """
        data: dict = {"path": request.url.path, "status": response.status_code, "method": request.method}
        # 路由信息
        app: FastAPI = request.app
        for route in app.routes:
            if (
                isinstance(route, APIRoute)
                and route.path_regex.match(request.url.path)
                and request.method in route.methods
            ):
                data["module"] = ",".join(route.tags)
                data["summary"] = route.summary
        # 客户端 IP / UA（安全审计）
        try:
            from app.utils.request_info import client_ip, user_agent

            data["ip"] = client_ip(request)
            data["user_agent"] = user_agent(request)
        except Exception:
            data["ip"] = ""
            data["user_agent"] = ""
        # 获取用户信息
        try:
            token = request.headers.get("token")
            user_obj = None
            if token:
                user_obj: User = await AuthControl.is_authed(request, token)
            data["user_id"] = user_obj.id if user_obj else 0
            data["username"] = user_obj.username if user_obj else ""
        except Exception:
            data["user_id"] = 0
            data["username"] = ""
        return data

    async def before_request(self, request: Request):
        request_args = await self.get_request_args(request)
        request.state.request_args = request_args

    async def after_request(self, request: Request, response: Response, process_time: int):
        # 修复：日志写入包 try/except——写日志失败不能破坏正常业务响应
        try:
            if request.method in self.methods:
                # 修复：exclude_paths 精确前缀匹配（原 re.search 子串匹配，
                # 如 /docs 会误排除任意含该子串的路径）
                for path in self.exclude_paths:
                    if request.url.path == path or request.url.path.startswith(path + "/"):
                        return
                data: dict = await self.get_request_log(request=request, response=response)
                data["response_time"] = process_time

                data["request_args"] = request.state.request_args
                data["response_body"] = await self.get_response_body(request, response)
                await AuditLog.create(**data)
        except Exception:
            pass

        return response

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time: datetime = datetime.now()
        await self.before_request(request)
        response = await call_next(request)
        end_time: datetime = datetime.now()
        process_time = int((end_time.timestamp() - start_time.timestamp()) * 1000)
        await self.after_request(request, response, process_time)
        return response
