from fastapi.exceptions import (
    HTTPException,
    RequestValidationError,
    ResponseValidationError,
)
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from tortoise.exceptions import DoesNotExist, IntegrityError, ValidationError


class SettingNotFound(Exception):
    pass


async def DoesNotExistHandle(_: Request, exc: DoesNotExist) -> JSONResponse:
    content = dict(
        code=404,
        msg="资源不存在",
    )
    return JSONResponse(content=content, status_code=404)


async def IntegrityHandle(_: Request, exc: IntegrityError) -> JSONResponse:
    content = dict(
        code=500,
        msg="数据操作失败，请检查输入后重试",
    )
    return JSONResponse(content=content, status_code=500)


async def TortoiseValidationHandle(_: Request, exc: ValidationError) -> JSONResponse:
    """tortoise 字段校验失败按参数错误处理，不返回 500"""
    content = dict(code=422, msg="参数校验失败，请检查输入", data=None)
    return JSONResponse(content=content, status_code=422)


# Starlette/FastAPI 默认英文 detail → 中文白话（不泄 method/path/栈）
_HTTP_DETAIL_ZH = {
    "Not Found": "资源不存在",
    "Method Not Allowed": "请求方式不允许",
    "Forbidden": "无权访问",
    "Unauthorized": "未登录或登录已失效",
    "Internal Server Error": "服务器内部错误，请稍后重试",
    "Bad Request": "请求无效",
    "Too Many Requests": "请求过于频繁，请稍后再试",
}


async def HttpExcHandle(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        detail = _HTTP_DETAIL_ZH.get(detail, detail)
    content = dict(code=exc.status_code, msg=detail, data=None)
    return JSONResponse(content=content, status_code=exc.status_code)


async def RequestValidationHandle(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 仅回显字段定位信息（loc/msg/type），不回显原始请求体 input（可能含密码等敏感值）
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    content = dict(code=422, msg="参数校验失败", data=errors)
    return JSONResponse(content=content, status_code=422)


async def ResponseValidationHandle(_: Request, exc: ResponseValidationError) -> JSONResponse:
    content = dict(code=500, msg="服务响应异常，请稍后重试")
    return JSONResponse(content=content, status_code=500)


async def UnhandledExceptionHandle(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器（修复：原未注册，未知异常走 FastAPI 默认英文 500 且可能泄露堆栈/内部信息）。
    记录完整异常到日志，客户端只收到通用中文提示。"""
    import logging

    logging.getLogger("app.core.exceptions").error(
        "未处理异常: method=%s path=%s exc=%r", request.method, request.url.path, exc
    )
    return JSONResponse(content=dict(code=500, msg="服务器内部错误，请稍后重试", data=None), status_code=500)
