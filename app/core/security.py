# -*- coding: utf-8 -*-
"""安全策略纯函数模块（仅依赖标准库，便于单元测试与复用）。

- 强密码策略：8~32 位，同时包含大写字母、小写字母、数字、特殊符号
- 随机初始密码生成（符合上述策略）
- 审计日志长文本递归截断（防止 AI 对话等敏感内容明文落库）
"""
import re
import secrets
import string

# 强密码策略：8~32 位，必须同时包含大写字母、小写字母、数字、特殊符号
PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,32}$"
_PASSWORD_RE = re.compile(PASSWORD_PATTERN)

# 审计落库时必须脱敏的敏感字段名（大小写不敏感，递归匹配任意层级）
SENSITIVE_KEY_NAMES = (
    "password",
    "old_password",
    "new_password",
    "confirm_password",
    "temporary_password",
    "secret",
    "totp_secret",
    "otpauth_uri",
    "totp_code",
    "answer",
    "recovery_answer",
    "recovery_answer_hash",
    "step_up_token",
    "captcha_ticket",
    "access_token",
    "api_key",
    "apikey",
    "authorization",
)
# 归一化匹配（去下划线/连字符、转小写），兼容 NewPassword / new-password 等变体写法
_SENSITIVE_NORM = tuple(k.lower().replace("_", "").replace("-", "") for k in SENSITIVE_KEY_NAMES)

AUTH_SECRET_AUDIT_PATHS = frozenset(
    {
        "/api/v1/base/access_token",
        "/api/v1/base/step_up",
        "/api/v1/base/totp/setup",
        "/api/v1/base/totp/confirm",
        "/api/v1/base/totp/recovery-question",
        "/api/v1/base/totp/recover",
        "/api/v1/base/totp/disable",
        "/api/v1/user/reset_password",
        "/api/v1/user/reset_totp",
    }
)


def validate_password(password: str) -> bool:
    """校验密码是否符合强密码策略"""
    if not isinstance(password, str):
        return False
    return bool(_PASSWORD_RE.match(password))


def gen_initial_password(length: int = 16) -> str:
    """生成符合强密码策略的随机密码：大小写字母+数字+特殊符号"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if validate_password(pwd):
            return pwd


def truncate_sensitive(obj, max_len: int = 500, sensitive_keys=_SENSITIVE_NORM):
    """递归处理审计日志内容：
    1. 敏感字段（任意嵌套层级）值替换为 "***"
    2. 超长字符串字段截断（默认 500 字符），防止 AI 对话等敏感内容明文落库
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower().replace("_", "").replace("-", "") in sensitive_keys:
                result[k] = "***"
            else:
                result[k] = truncate_sensitive(v, max_len, sensitive_keys)
        return result
    if isinstance(obj, list):
        return [truncate_sensitive(v, max_len, sensitive_keys) for v in obj]
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + "...[已截断]"
    return obj
