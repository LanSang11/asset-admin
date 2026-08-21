from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, Request

from app.core.auth_version import auth_version_matches
from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.models import Role, User
from app.settings import settings


class AuthControl:
    # 强制改密用户可访问的接口（精确匹配，均为 base 路由；新增路由须显式加入）
    MUST_CHANGE_PASSWORD_EXEMPT_PATHS = frozenset(
        {
            "/api/v1/base/update_password",  # 修改密码（改密动作本身）
            "/api/v1/base/userinfo",  # 用户信息（前端改密页展示所需）
            "/api/v1/base/usermenu",  # 用户菜单（改密完成后进入系统所需）
            "/api/v1/base/userapi",  # 用户 API 权限
        }
    )
    SECURITY_SETUP_EXEMPT_PATHS = frozenset(
        {
            "/api/v1/base/userinfo",
            "/api/v1/base/update_password",
            "/api/v1/base/totp/setup",
            "/api/v1/base/totp/confirm",
            "/api/v1/base/totp/recovery-question",
        }
    )
    TOTP_RECOVERY_EXEMPT_PATHS = frozenset(
        {
            "/api/v1/base/userinfo",
            "/api/v1/base/totp/setup",
            "/api/v1/base/totp/confirm",
            "/api/v1/base/totp/recovery-question",
        }
    )

    @classmethod
    async def is_authed(cls, request: Request, token: str = Header(..., description="token验证")) -> Optional["User"]:
        try:
            # 注意：已移除原作者留下的 "dev" 调试后门（任何请求带 Authorization: dev 即可伪装超管）
            decode_data = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.JWT_ALGORITHM)
            user_id = decode_data.get("user_id")
            user = await User.filter(id=user_id).first()
            if not user:
                raise HTTPException(status_code=401, detail="认证失败")
            # 修复：禁用账号的 token 立即失效（原实现不检查 is_active，
            # 被禁用的用户（含离职/违规）7 天内仍可凭旧 token 访问全部接口）
            if not user.is_active:
                raise HTTPException(status_code=401, detail="账号已被禁用，请联系管理员")
            if not auth_version_matches(decode_data, getattr(user, "auth_version", 0)):
                raise HTTPException(status_code=401, detail="登录已过期")
            from app.services.verification_policy import login_totp_required

            restricted_security_session = bool(
                decode_data.get("security_setup_only") is True
                or decode_data.get("totp_recovery_only") is True
            )
            if (
                await login_totp_required(user)
                and not restricted_security_session
                and decode_data.get("totp_verified") is not True
            ):
                from app.services.verification_policy import acceptance_mode_active

                if not await acceptance_mode_active():
                    raise HTTPException(status_code=401, detail="登录安全策略已更新，请使用动态验证码重新登录")
            # 受限声明必须严格为布尔值 True；路径使用精确白名单，拒绝前缀逃逸。
            if decode_data.get("totp_recovery_only") is True and request.url.path not in cls.TOTP_RECOVERY_EXEMPT_PATHS:
                raise HTTPException(status_code=403, detail="请先重新绑定动态验证器")
            if decode_data.get("security_setup_only") is True and request.url.path not in cls.SECURITY_SETUP_EXEMPT_PATHS:
                raise HTTPException(status_code=403, detail="请先完成管理员二次验证设置")
            # 强制改密（首次登录/密码被重置后）：除白名单接口外一律拒绝，
            # 防止公开默认初始密码被利用直接访问业务接口（后端强制，不依赖前端）
            if user.must_change_password and request.url.path not in cls.MUST_CHANGE_PASSWORD_EXEMPT_PATHS:
                raise HTTPException(status_code=403, detail="请先修改初始密码后再使用系统")
            request.state.auth_claims = decode_data
            CTX_USER_ID.set(int(user_id))
            return user
        except HTTPException:
            # 必须原样抛出：禁用账号 401、强制改密 403 等业务拒绝
            # （原实现落入下方 Exception，被包装成 500，前端/调用方无法区分）
            raise
        except jwt.DecodeError:
            raise HTTPException(status_code=401, detail="无效的Token")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="登录已过期")
        except jwt.InvalidTokenError:
            # 修复：其余 JWT 异常（算法不匹配/签名错误/载荷损坏等）统一按 401 处理，原实现落入 Exception 返回 500
            raise HTTPException(status_code=401, detail="无效的Token")
        except Exception as e:
            # 内部异常记日志，不向客户端回显细节（避免信息泄露）
            logger.error(f"AuthControl.is_authed 内部异常: {repr(e)}")
            raise HTTPException(status_code=500, detail="服务器内部错误")


class PermissionControl:
    @classmethod
    async def has_permission(cls, request: Request, current_user: User = Depends(AuthControl.is_authed)) -> None:
        if current_user.is_superuser:
            return
        method = (request.method or "").upper()
        path = request.url.path
        roles: list[Role] = await current_user.roles
        if not roles:
            # 方案 D：客户端仅中文白话，不返回 method/path 等侦察信息
            raise HTTPException(status_code=403, detail="账号尚未分配岗位权限，请联系管理员。")
        apis = [await role.apis for role in roles]
        # method 统一大写比较，避免枚举/原始字符串大小写不一致导致误拒
        permission_apis = list(set(((api.method or "").upper(), api.path) for api in sum(apis, [])))
        if (method, path) not in permission_apis:
            # 细节只写服务端日志，禁止把 method/path 回给客户端
            logger.warning(
                "权限拒绝 user_id=%s method=%s path=%s",
                getattr(current_user, "id", None),
                method,
                path,
            )
            try:
                from app.services.security_agg import record_attack
                from app.utils.request_info import client_ip

                record_attack("permission_denied", ip=client_ip(request))
            except Exception:
                pass
            raise HTTPException(
                status_code=403,
                detail="暂无权限执行此操作，如需开通请联系系统管理员。",
            )


DependAuth = Depends(AuthControl.is_authed)
DependPermission = Depends(PermissionControl.has_permission)


async def require_superuser(current_user: User = Depends(AuthControl.is_authed)) -> User:
    """接口级硬锁：仅 is_superuser（安全日志 / 黑名单管理等）。"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return current_user


async def require_step_up(
    operation_key: str,
    request: Request,
    current_user: User = Depends(AuthControl.is_authed),
) -> User:
    """Consume a token bound to one configured high-risk operation."""
    from app.core.step_up import step_up_store
    from app.services.security_event_service import log_security_event
    from app.services.verification_policy import operation_mode
    from app.utils.request_info import client_ip, device_hash, user_agent

    try:
        mode = await operation_mode(operation_key)
    except ValueError:
        raise HTTPException(status_code=500, detail="二次验证策略配置错误")
    if mode == "off":
        return current_user
    token = request.headers.get("X-Step-Up-Token") or request.headers.get("x-step-up-token")
    if not step_up_store.consume(current_user.id, operation_key, mode, token):
        await log_security_event(
            event_type="step_up_denied",
            username=current_user.username,
            user_id=current_user.id,
            ip=client_ip(request),
            user_agent=user_agent(request),
            device_hash=device_hash(request),
            detail=f"高危操作缺少有效二次验证 operation={operation_key}",
            success=False,
        )
        raise HTTPException(status_code=403, detail="请先完成此操作要求的二次验证")
    return current_user


def require_operation(operation_key: str):
    async def dependency(
        request: Request,
        current_user: User = Depends(AuthControl.is_authed),
    ) -> User:
        return await require_step_up(operation_key, request, current_user)

    return Depends(dependency)


DependSuperUser = Depends(require_superuser)
DependStepUp = require_operation
