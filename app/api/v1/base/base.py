from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from tortoise.transactions import in_transaction

from app.controllers.user import user_controller
from app.core.auth_version import bump_user_auth_version
from app.core.ctx import CTX_USER_ID
from app.core.dependency import DependAuth
from app.core.gateway import unban_ip_after_login
from app.core.login_guard import login_guard, step_up_guard
from app.core.slide_captcha import slide_captcha
from app.core.step_up import step_up_store
from app.core.totp_utils import generate_secret, provisioning_uri, verify_totp
from app.models.admin import Api, Menu, Role, User
from app.schemas.base import Fail, Success
from app.schemas.login import *
from app.schemas.users import UpdatePassword
from app.settings import settings
from app.services.security_event_service import log_security_event
from app.services.verification_policy import (
    acceptance_mode_active,
    acceptance_mode_status,
    login_totp_required,
    operation_mode,
    password_must_rotate,
)
from app.utils.jwt_utils import create_access_token
from app.utils.password import get_password_hash, verify_password
from app.utils.request_info import client_ip, device_hash, user_agent

router = APIRouter()


def _normalize_recovery_answer(value: str) -> str:
    return " ".join((value or "").strip().casefold().split())


def _token_payload(user: User, expire: datetime, **claims) -> JWTPayload:
    return JWTPayload(
        user_id=user.id,
        username=user.username,
        is_superuser=user.is_superuser,
        exp=expire,
        auth_version=int(getattr(user, "auth_version", 0) or 0),
        **claims,
    )


def _login_risk_data(username: str, ip: str) -> dict:
    st = login_guard.status(username, ip)
    return {
        # 策略：每次登录强制滑块（前端始终展示；后端硬校验）
        "require_captcha": True,
        "fail_count": st["fail_count"],
        "locked": st["locked"],
        "lock_minutes": st["lock_minutes"],
    }


@router.get("/captcha/slide", summary="获取登录滑块验证码（公开）")
async def get_slide_captcha(request: Request):
    """每次登录前拉取；图内不包含答案 x；校验一次性。"""
    try:
        data = slide_captcha.create(client_ip=client_ip(request))
    except RuntimeError as e:
        msg = str(e)
        code = 429 if "频繁" in msg else 500
        return Fail(code=code, msg=msg)
    return Success(data=data)


class SlideVerifyIn(BaseModel):
    captcha_id: str = Field(..., min_length=1, max_length=128)
    captcha_x: float


@router.post("/captcha/slide/verify", summary="预验证登录滑块（公开）")
async def verify_slide_captcha(body: SlideVerifyIn, request: Request):
    ok, reason, ticket = slide_captcha.verify_and_issue_ticket(
        body.captcha_id,
        body.captcha_x,
        client_ip(request),
    )
    if not ok:
        return Fail(code=400, msg=reason)
    return Success(
        data={"captcha_ticket": ticket, "expires_in": slide_captcha.ttl_seconds},
        msg="验证通过",
    )


@router.get("/captcha/status", summary="查询登录风控状态（公开）")
async def captcha_status(
    request: Request,
    username: str = Query("", description="用户名"),
):
    ip = client_ip(request)
    return Success(data=_login_risk_data(username or "", ip))


@router.post("/access_token", summary="获取token")
async def login_access_token(credentials: CredentialsSchema, request: Request):
    ip = client_ip(request)
    ua = user_agent(request)
    tz = getattr(credentials, "timezone", None) or ""
    plat = getattr(credentials, "platform", None) or ""
    langs = getattr(credentials, "languages", None) or ""
    dhash = device_hash(
        request,
        client_hint=getattr(credentials, "device_hint", None),
        timezone=tz,
        platform=plat,
        languages=langs,
    )
    username = (credentials.username or "").strip()

    async def _fail_event(detail: str, success: bool = False, uid: Optional[int] = None):
        await log_security_event(
            event_type="login_failure" if not success else "login_success",
            username=username,
            user_id=uid,
            ip=ip,
            user_agent=ua,
            device_hash=dhash,
            detail=detail,
            success=success,
            timezone=tz,
        )

    # 暴力破解防护：5 次失败锁定 5 分钟
    try:
        login_guard.check(username, ip)
    except HTTPException as e:
        await _fail_event(f"账号锁定: {e.detail}")
        return Fail(code=e.status_code, msg=e.detail, data=_login_risk_data(username, ip))

    # 严格：每次登录必须通过滑块。浏览器先预验证换取一次性票据；
    # 旧 captcha_id/x 提交仅保留给现有自动化验收脚本。
    if credentials.captcha_ticket:
        ok, reason = slide_captcha.consume_ticket(credentials.captcha_ticket, ip)
    else:
        ok, reason = slide_captcha.verify_and_consume(credentials.captcha_id, credentials.captcha_x)
    if not ok:
        # 缺/错滑块不记密码失败（避免拖滑块失败直接锁死账号），但绝不放行
        await _fail_event(f"滑块失败: {reason}")
        return Fail(code=400, msg=reason, data=_login_risk_data(username, ip))

    try:
        user: User = await user_controller.authenticate(credentials)
    except HTTPException as e:
        login_guard.record_failure(username, ip)
        await _fail_event(e.detail or "认证失败")
        return Fail(code=e.status_code, msg=e.detail, data=_login_risk_data(username, ip))
    except Exception:
        login_guard.record_failure(username, ip)
        await _fail_event("用户名或密码错误")
        return Fail(code=400, msg="用户名或密码错误", data=_login_risk_data(username, ip))

    forced_totp = await login_totp_required(user)
    has_totp = bool(getattr(user, "totp_enabled", False) and getattr(user, "totp_secret", None))
    has_recovery = bool(getattr(user, "recovery_question", None) and getattr(user, "recovery_answer_hash", None))
    security_setup_only = bool(forced_totp and not (has_totp and has_recovery))
    totp_verified = False

    # 已绑定账号仍需 TOTP；强制账号未完成绑定时只签发安全设置受限会话，避免锁死。
    # 限时验收模式只跳过登录动态码，JWT 不带 totp_verified，到期后旧会话立即失效。
    acceptance_login = False
    if has_totp and not security_setup_only:
        if await acceptance_mode_active():
            acceptance_login = True
            totp_verified = False
        else:
            code = (credentials.totp_code or "").strip()
            if not code:
                # 密码已对但不记失败锁定；前端进入第二步，不是登录失败
                return Fail(
                    code=400,
                    msg="请输入二次验证码",
                    data={
                        **_login_risk_data(username, ip),
                        "require_totp": True,
                        "totp_challenge": True,
                        "recovery_question": user.recovery_question if has_recovery else None,
                    },
                )
            if not verify_totp(user.totp_secret, code):
                login_guard.record_failure(username, ip)
                await _fail_event("TOTP 错误", uid=user.id)
                return Fail(
                    code=400,
                    msg="二次验证码错误",
                    data={
                        **_login_risk_data(username, ip),
                        "require_totp": True,
                        "recovery_question": user.recovery_question if has_recovery else None,
                    },
                )
            totp_verified = True

    login_guard.reset(username, ip)
    unban_ip_after_login(ip)
    await user_controller.update_last_login(user.id)
    await log_security_event(
        event_type="login_success",
        username=user.username,
        user_id=user.id,
        ip=ip,
        user_agent=ua,
        device_hash=dhash,
        detail=(
            "登录成功（仅安全设置）"
            if security_setup_only
            else "登录成功（验收模式，未校验动态码）"
            if acceptance_login
            else "登录成功"
        ),
        success=True,
        timezone=tz,
    )
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + access_token_expires

    data = JWTOut(
        access_token=create_access_token(
            data=_token_payload(
                user,
                expire,
                security_setup_only=security_setup_only,
                totp_verified=totp_verified,
            )
        ),
        username=user.username,
    )
    resp_data = data.model_dump()
    # 首次登录 / 管理员重置 / 到期换密（默认关）都走同一 must_change_password
    if await password_must_rotate(user) and not bool(getattr(user, "must_change_password", False)):
        user.must_change_password = True
        await user.save(update_fields=["must_change_password"])
    resp_data["must_change_password"] = bool(getattr(user, "must_change_password", False))
    resp_data["totp_enabled"] = bool(getattr(user, "totp_enabled", False))
    resp_data["recovery_question_set"] = has_recovery
    resp_data["security_setup_only"] = security_setup_only
    resp_data["acceptance_mode"] = await acceptance_mode_status()
    return Success(data=resp_data)


@router.get("/userinfo", summary="查看用户信息", dependencies=[DependAuth])
async def get_userinfo(request: Request):
    user_id = CTX_USER_ID.get()
    user_obj = await user_controller.get(id=user_id)
    data = await user_obj.to_dict(
        exclude_fields=[
            "password",
            "totp_secret",
            "recovery_answer_hash",
            "recovery_fail_count",
            "recovery_locked_until",
        ]
    )
    data["avatar"] = ""  # 修复：移除硬编码第三方 GitHub 头像地址（隐私/外链失效问题），前端使用默认头像
    data["totp_enabled"] = bool(getattr(user_obj, "totp_enabled", False))
    data["recovery_question_set"] = bool(
        getattr(user_obj, "recovery_question", None) and getattr(user_obj, "recovery_answer_hash", None)
    )
    claims = getattr(request.state, "auth_claims", {}) or {}
    data["security_setup_only"] = claims.get("security_setup_only") is True
    data["totp_recovery_only"] = claims.get("totp_recovery_only") is True
    data["acceptance_mode"] = await acceptance_mode_status()
    # 方案 B：稳定 portal 字段，供前端登录分流（admin=管理后台，work=员工/主管工作台）
    role_objs: list[Role] = await user_obj.roles
    role_names = [r.name for r in role_objs if getattr(r, "name", None)]
    data["role_names"] = role_names
    if user_obj.is_superuser or "管理员" in role_names:
        data["portal"] = "admin"
    else:
        data["portal"] = "work"
    return Success(data=data)


@router.get("/usermenu", summary="查看用户菜单", dependencies=[DependAuth])
async def get_user_menu():
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    menus: list[Menu] = []
    if user_obj.is_superuser:
        menus = await Menu.all()
    else:
        role_objs: list[Role] = await user_obj.roles
        for role_obj in role_objs:
            menu = await role_obj.menus
            menus.extend(menu)
        menus = list(set(menus))
    parent_menus: list[Menu] = []
    for menu in menus:
        if menu.parent_id == 0:
            parent_menus.append(menu)
    res = []
    for parent_menu in parent_menus:
        parent_menu_dict = await parent_menu.to_dict()
        parent_menu_dict["children"] = []
        for menu in menus:
            if menu.parent_id == parent_menu.id:
                parent_menu_dict["children"].append(await menu.to_dict())
        res.append(parent_menu_dict)
    return Success(data=res)


@router.get("/userapi", summary="查看用户API", dependencies=[DependAuth])
async def get_user_api():
    user_id = CTX_USER_ID.get()
    user_obj = await User.filter(id=user_id).first()
    if user_obj.is_superuser:
        api_objs: list[Api] = await Api.all()
        apis = [api.method.lower() + api.path for api in api_objs]
        return Success(data=apis)
    role_objs: list[Role] = await user_obj.roles
    apis = []
    for role_obj in role_objs:
        api_objs: list[Api] = await role_obj.apis
        apis.extend([api.method.lower() + api.path for api in api_objs])
    apis = list(set(apis))
    return Success(data=apis)


@router.post("/update_password", summary="修改密码", dependencies=[DependAuth])
async def update_user_password(req_in: UpdatePassword, request: Request):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    verified = verify_password(req_in.old_password, user.password)
    if not verified:
        await log_security_event(
            event_type="password_change",
            username=user.username,
            user_id=user.id,
            ip=client_ip(request),
            user_agent=user_agent(request),
            device_hash=device_hash(request),
            detail="旧密码错误",
            success=False,
        )
        return Fail(msg="旧密码验证错误！")
    user.password = get_password_hash(req_in.new_password)
    user.must_change_password = False  # 改密成功后解除强制改密标记
    user.password_changed_at = datetime.now(timezone.utc)
    bump_user_auth_version(user)
    await user.save()
    await log_security_event(
        event_type="password_change",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="修改密码成功",
        success=True,
    )
    return Success(msg="修改成功")


# ---------- 高危 step-up / TOTP ----------


class StepUpIn(BaseModel):
    operation_key: str = Field(..., min_length=1, max_length=64)
    password: Optional[str] = Field(None, min_length=1, max_length=128, description="当前登录密码")
    totp_code: Optional[str] = Field(None, min_length=6, max_length=8, description="验证器 6 位码")


class TotpConfirmIn(BaseModel):
    code: str = Field(..., min_length=6, max_length=8, description="验证器 6 位码")
    secret: Optional[str] = Field(None, description="setup 返回的 secret（确认绑定时必填）")
    recovery_question: str = Field(..., min_length=4, max_length=120)
    recovery_answer: str = Field(..., min_length=8, max_length=128)


class TotpDisableIn(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=6, max_length=8)


class RecoveryQuestionIn(BaseModel):
    question: str = Field(..., min_length=4, max_length=120)
    answer: str = Field(..., min_length=8, max_length=128)
    totp_code: str = Field(..., min_length=6, max_length=8)


class TotpRecoverIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)
    answer: str = Field(..., min_length=1, max_length=128)
    captcha_ticket: Optional[str] = Field(None, max_length=128)
    captcha_id: Optional[str] = Field(None, max_length=128)
    captcha_x: Optional[float] = None
    device_hint: Optional[str] = Field(None, max_length=128)
    timezone: Optional[str] = Field(None, max_length=64)
    platform: Optional[str] = Field(None, max_length=64)
    languages: Optional[str] = Field(None, max_length=128)


@router.get("/step_up/requirement", summary="查询某项高危操作的二次验证要求", dependencies=[DependAuth])
async def step_up_requirement(operation_key: str = Query(..., min_length=1, max_length=64)):
    try:
        mode = await operation_mode(operation_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="未配置该操作的二次验证策略")
    user = await user_controller.get(CTX_USER_ID.get())
    return Success(
        data={
            "operation_key": operation_key,
            "mode": mode,
            "totp_enabled": bool(user.totp_enabled and user.totp_secret),
        }
    )


@router.post("/step_up", summary="按操作执行高危二次验证", dependencies=[DependAuth])
async def step_up_verify(body: StepUpIn, request: Request):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    try:
        mode = await operation_mode(body.operation_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="未配置该操作的二次验证策略")
    if mode == "off":
        return Success(data={"operation_key": body.operation_key, "mode": mode}, msg="该操作未启用二次验证")
    ip = client_ip(request)
    try:
        step_up_guard.check(user.username, ip)
    except HTTPException:
        raise HTTPException(status_code=429, detail="二次验证失败次数过多，请 5 分钟后再试")
    verified = False
    if mode == "password":
        verified = bool(body.password and verify_password(body.password, user.password))
    elif mode == "totp":
        if not user.totp_enabled or not user.totp_secret:
            raise HTTPException(status_code=403, detail="请先绑定动态验证器后再执行此操作")
        verified = bool(body.totp_code and verify_totp(user.totp_secret, body.totp_code))
    if not verified:
        step_up_guard.record_failure(user.username, ip)
        await log_security_event(
            event_type="step_up",
            username=user.username,
            user_id=user.id,
            ip=client_ip(request),
            user_agent=user_agent(request),
            device_hash=device_hash(request),
            detail=f"二次验证失败 operation={body.operation_key} mode={mode}",
            success=False,
        )
        return Fail(code=400, msg="二次验证信息不正确")
    step_up_guard.reset(user.username, ip)
    token, expires_in = step_up_store.issue(user.id, body.operation_key, mode)
    await log_security_event(
        event_type="step_up",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail=f"二次验证通过 operation={body.operation_key} mode={mode}",
        success=True,
    )
    return Success(
        data={
            "step_up_token": token,
            "expires_in": expires_in,
            "operation_key": body.operation_key,
            "mode": mode,
        },
        msg="验证成功",
    )


@router.post("/totp/setup", summary="开始绑定 TOTP（获取密钥与二维码 URI）", dependencies=[DependAuth])
async def totp_setup():
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    # 任意登录用户可绑定；演示重点是超管
    secret = generate_secret()
    uri = provisioning_uri(secret, user.username, issuer=settings.APP_TITLE or "企业资产管理系统")
    # 暂存 secret 到用户字段但未启用，直到 confirm；若已启用则拒绝
    if user.totp_enabled:
        return Fail(msg="已启用二次验证，请先关闭后再重新绑定")
    user.totp_secret = secret
    user.totp_enabled = False
    await user.save()
    return Success(
        data={"secret": secret, "otpauth_uri": uri, "username": user.username},
        msg="请用验证器扫码或手动输入密钥，并提交一次动态码完成绑定",
    )


@router.post("/totp/confirm", summary="确认绑定 TOTP", dependencies=[DependAuth])
async def totp_confirm(body: TotpConfirmIn, request: Request):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    if user.totp_enabled:
        return Fail(msg="动态验证器已启用，不能通过确认接口替换现有绑定")
    secret = (body.secret or user.totp_secret or "").strip()
    if not secret:
        return Fail(msg="请先调用 setup 获取密钥")
    if not verify_totp(secret, body.code):
        return Fail(msg="验证码错误，请重试")
    answer = _normalize_recovery_answer(body.recovery_answer)
    if len(answer) < 8:
        return Fail(msg="安全答案至少需要 8 个字符")
    user.totp_secret = secret
    user.totp_enabled = True
    user.recovery_question = body.recovery_question.strip()
    user.recovery_answer_hash = get_password_hash(answer)
    user.recovery_fail_count = 0
    user.recovery_locked_until = None
    bump_user_auth_version(user)
    await user.save()
    await log_security_event(
        event_type="totp_bind",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="绑定 TOTP 成功",
        success=True,
    )
    return Success(data={"relogin_required": True}, msg="动态验证器与安全问题已启用，请重新登录")


@router.post("/totp/recovery-question", summary="设置 TOTP 恢复安全问题", dependencies=[DependAuth])
async def set_totp_recovery_question(body: RecoveryQuestionIn, request: Request):
    user = await user_controller.get(CTX_USER_ID.get())
    if not user.totp_enabled or not user.totp_secret:
        return Fail(msg="请先绑定动态验证器")
    if not verify_totp(user.totp_secret, body.totp_code):
        return Fail(msg="动态验证码错误")
    answer = _normalize_recovery_answer(body.answer)
    if len(answer) < 8:
        return Fail(msg="安全答案至少需要 8 个字符")
    user.recovery_question = body.question.strip()
    user.recovery_answer_hash = get_password_hash(answer)
    user.recovery_fail_count = 0
    user.recovery_locked_until = None
    bump_user_auth_version(user)
    await user.save()
    await log_security_event(
        event_type="totp_recovery_question",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="设置 TOTP 恢复安全问题",
        success=True,
    )
    return Success(data={"relogin_required": True}, msg="安全问题已保存，请重新登录")


@router.post("/totp/recover", summary="通过密码、滑块和安全答案恢复 TOTP（公开）")
async def recover_totp(body: TotpRecoverIn, request: Request):
    ip = client_ip(request)
    ua = user_agent(request)
    username = body.username.strip()
    if body.captcha_ticket:
        ok, _ = slide_captcha.consume_ticket(body.captcha_ticket, ip)
    else:
        ok, _ = slide_captcha.verify_and_consume(body.captcha_id, body.captcha_x)
    user = await User.filter(username=username).first()

    async def _audit(target: Optional[User], detail: str, success: bool):
        await log_security_event(
            event_type="totp_recovery",
            username=username,
            user_id=target.id if target else None,
            ip=ip,
            user_agent=ua,
            device_hash=device_hash(
                request,
                client_hint=body.device_hint,
                timezone=body.timezone or "",
                platform=body.platform or "",
                languages=body.languages or "",
            ),
            detail=detail,
            success=success,
            timezone=body.timezone or "",
        )

    # 统一返回，避免枚举账号、密码、滑块或安全答案中究竟哪项错误。
    if not ok or not user or not user.is_active or not user.recovery_answer_hash:
        await _audit(user, "TOTP 恢复信息不正确", False)
        return Fail(code=400, msg="恢复信息不正确")

    now = datetime.now(timezone.utc)
    lock_until = now + timedelta(minutes=30)
    async with in_transaction() as connection:
        affected, _ = await connection.execute_query(
            """
            UPDATE user
            SET recovery_locked_until = CASE
                    WHEN recovery_fail_count + 1 >= 5 THEN ?
                    ELSE recovery_locked_until
                END,
                recovery_fail_count = CASE
                    WHEN recovery_fail_count + 1 >= 5 THEN 0
                    ELSE recovery_fail_count + 1
                END
            WHERE id = ?
              AND (recovery_locked_until IS NULL OR recovery_locked_until <= ?)
            """,
            [lock_until, user.id, now],
        )
    if affected != 1:
        await _audit(user, "TOTP 恢复处于锁定期", False)
        return Fail(code=429, msg="恢复尝试次数过多，请稍后再试")

    answer = _normalize_recovery_answer(body.answer)
    valid_password = bool(user.password and verify_password(body.password, user.password))
    valid_answer = bool(answer and verify_password(answer, user.recovery_answer_hash))
    if not (valid_password and valid_answer):
        await _audit(user, "TOTP 恢复信息不正确", False)
        return Fail(code=400, msg="恢复信息不正确")

    user.totp_secret = None
    user.totp_enabled = False
    user.recovery_question = None
    user.recovery_answer_hash = None
    user.recovery_fail_count = 0
    user.recovery_locked_until = None
    bump_user_auth_version(user)
    await user.save()
    expire = now + timedelta(minutes=15)
    token = create_access_token(data=_token_payload(user, expire, totp_recovery_only=True))
    unban_ip_after_login(ip)
    await _audit(user, "TOTP 恢复验证通过，进入受限重绑会话", True)
    return Success(
        data={
            "access_token": token,
            "username": user.username,
            "totp_recovery_only": True,
            "expires_in": 900,
        },
        msg="恢复验证通过，请重新绑定动态验证器",
    )


@router.post("/totp/disable", summary="关闭 TOTP", dependencies=[DependAuth])
async def totp_disable(body: TotpDisableIn, request: Request):
    user_id = CTX_USER_ID.get()
    user = await user_controller.get(user_id)
    if user.is_superuser:
        raise HTTPException(status_code=403, detail="超级管理员的动态验证器受根保护，不能自行解绑")
    if await login_totp_required(user):
        raise HTTPException(status_code=403, detail="该账号受登录二次验证策略保护，不能自行关闭")
    if not verify_password(body.password, user.password):
        return Fail(msg="密码错误")
    if user.totp_enabled and user.totp_secret and not verify_totp(user.totp_secret, body.code):
        return Fail(msg="验证码错误")
    user.totp_secret = None
    user.totp_enabled = False
    user.recovery_question = None
    user.recovery_answer_hash = None
    user.recovery_fail_count = 0
    user.recovery_locked_until = None
    bump_user_auth_version(user)
    await user.save()
    await log_security_event(
        event_type="totp_disable",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_hash=device_hash(request),
        detail="关闭 TOTP",
        success=True,
    )
    return Success(data={"relogin_required": True}, msg="二次验证已关闭，请重新登录")