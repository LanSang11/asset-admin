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
        code=409,
        msg="数据已存在或与现有记录冲突，请修改后重试",
    )
    return JSONResponse(content=content, status_code=409)


async def TortoiseValidationHandle(_: Request, exc: ValidationError) -> JSONResponse:
    """tortoise 字段校验失败按参数错误处理，不返回 500"""
    content = dict(code=422, msg="字段内容超过长度或格式限制，请按页面提示修改", data=None)
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


def _request_validation_message(error: dict) -> str:
    """把 Pydantic 内部英文错误转换成稳定的终端用户中文提示。"""
    error_type = str(error.get("type", ""))
    context = error.get("ctx") or {}
    location = error.get("loc") or []
    field_name = str(location[-1]) if location else ""

    if error_type == "missing":
        return "不能为空"
    if error_type == "string_too_short":
        return f"至少输入 {context.get('min_length')} 个字符"
    if error_type == "string_too_long":
        return f"最多输入 {context.get('max_length')} 个字符"
    if error_type == "greater_than_equal":
        return f"需大于或等于 {context.get('ge')}"
    if error_type == "greater_than":
        return f"需大于 {context.get('gt')}"
    if error_type == "less_than_equal":
        return f"需小于或等于 {context.get('le')}"
    if error_type == "less_than":
        return f"需小于 {context.get('lt')}"
    if error_type == "decimal_max_digits":
        return f"最多输入 {context.get('max_digits')} 位数字"
    if error_type == "decimal_whole_digits":
        return f"整数部分最多输入 {context.get('whole_digits')} 位"
    if error_type == "decimal_max_places":
        return f"小数部分最多输入 {context.get('decimal_places')} 位"
    if error_type in {"int_parsing", "int_type"}:
        return "请输入整数"
    if error_type in {"float_parsing", "float_type", "decimal_parsing", "decimal_type"}:
        return "请输入有效数字"
    if error_type in {"bool_parsing", "bool_type"}:
        return "请选择有效状态"
    if error_type in {"date_from_datetime_parsing", "date_parsing", "date_type"}:
        return "请输入有效日期"
    if error_type in {"enum", "literal_error"}:
        return "请选择有效选项"
    if error_type == "string_pattern_mismatch":
        return "格式不正确"
    if error_type == "string_type":
        return "请输入文本"
    if error_type in {"list_type", "set_type", "tuple_type"}:
        return "请选择有效内容"
    if field_name == "email":
        return "邮箱格式不正确"

    # 当前仅密码强度校验使用自定义 ValueError；只放行已知固定文案，避免回显内部细节。
    raw_message = str(error.get("msg", ""))
    password_message = "密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号"
    if error_type == "value_error" and password_message in raw_message:
        return password_message
    return "填写内容不符合要求"


async def RequestValidationHandle(_: Request, exc: RequestValidationError) -> JSONResponse:
    # 仅回显字段定位信息（loc/msg/type），不回显 input/ctx（可能含密码等敏感值或内部对象）。
    errors = [
        {
            "loc": list(err.get("loc", [])),
            "msg": _request_validation_message(err),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    content = dict(code=422, msg="提交内容有误，请按提示修改", data=errors)
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
