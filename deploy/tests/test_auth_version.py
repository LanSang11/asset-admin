# -*- coding: utf-8 -*-
"""auth_version：旧 JWT 缺字段按 0；版本不匹配立即 401；其它账号不受影响。"""
from __future__ import annotations

import importlib.util
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

_HELPER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "app",
    "core",
    "auth_version.py",
)
_SPEC = importlib.util.spec_from_file_location("auth_version_helper", _HELPER_PATH)
_helper = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_helper)
auth_version_matches = _helper.auth_version_matches
bump_user_auth_version = _helper.bump_user_auth_version
next_auth_version = _helper.next_auth_version
token_auth_version = _helper.token_auth_version


class AuthVersionHelperTests(unittest.TestCase):
    def test_missing_claim_is_zero(self):
        self.assertEqual(token_auth_version({}), 0)
        self.assertEqual(token_auth_version({"user_id": 1}), 0)
        self.assertEqual(token_auth_version(None), 0)

    def test_invalid_claim_is_zero(self):
        self.assertEqual(token_auth_version({"auth_version": "nope"}), 0)
        self.assertEqual(token_auth_version({"auth_version": None}), 0)

    def test_old_token_matches_default_user(self):
        self.assertTrue(auth_version_matches({}, 0))
        self.assertTrue(auth_version_matches({"auth_version": 0}, 0))

    def test_stale_token_rejected_after_bump(self):
        self.assertFalse(auth_version_matches({"auth_version": 0}, 1))
        self.assertFalse(auth_version_matches({}, 1))
        self.assertTrue(auth_version_matches({"auth_version": 1}, 1))

    def test_other_user_stays_on_zero(self):
        self.assertTrue(auth_version_matches({"auth_version": 0}, 0))
        self.assertEqual(next_auth_version(0), 1)
        self.assertEqual(next_auth_version(None), 1)

    def test_bump_only_touches_target_user(self):
        class _User:
            def __init__(self, version=0):
                self.auth_version = version

        target = _User(0)
        other = _User(0)
        self.assertEqual(bump_user_auth_version(target), 1)
        self.assertEqual(target.auth_version, 1)
        self.assertEqual(other.auth_version, 0)


try:
    import fastapi  # noqa: F401
    import jwt
    from tortoise import Tortoise

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise/jwt 依赖")
class AuthControlVersionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()
        from app.models.admin import User

        self.rotated = await User.create(
            username="rotated1",
            email="rotated1@t.com",
            password="x",
            is_superuser=False,
            is_active=True,
            auth_version=1,
        )
        self.other = await User.create(
            username="other1",
            email="other1@t.com",
            password="x",
            is_superuser=False,
            is_active=True,
            auth_version=0,
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    def _token(self, user, version=None, include_version=True):
        from app.settings import settings

        payload = {
            "user_id": user.id,
            "username": user.username,
            "is_superuser": False,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        if include_version:
            payload["auth_version"] = 0 if version is None else version
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    async def _authed(self, token):
        from fastapi import Request

        from app.core.dependency import AuthControl

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/base/userinfo"
        return await AuthControl.is_authed(request, token)

    async def test_mismatched_version_is_401(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._authed(self._token(self.rotated, version=0))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "登录已过期")

    async def test_matching_version_accepted(self):
        user = await self._authed(self._token(self.rotated, version=1))
        self.assertEqual(user.id, self.rotated.id)

    async def test_legacy_token_without_claim_still_works_at_version_zero(self):
        user = await self._authed(self._token(self.other, include_version=False))
        self.assertEqual(user.id, self.other.id)

    async def test_legacy_token_rejected_after_target_rotation(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._authed(self._token(self.rotated, include_version=False))
        self.assertEqual(ctx.exception.status_code, 401)


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise/jwt 依赖")
class ForceLogoutTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()
        from app.models.admin import User

        self.admin = await User.create(
            username="admin",
            email="admin@t.com",
            password="x",
            is_superuser=True,
            is_active=True,
            must_change_password=False,
            totp_enabled=True,
            auth_version=0,
        )
        self.target = await User.create(
            username="qa01",
            email="qa01@t.com",
            password="x",
            is_superuser=False,
            is_active=True,
            must_change_password=False,
            totp_enabled=False,
            auth_version=0,
        )
        self.staff = await User.create(
            username="staff1",
            email="staff1@t.com",
            password="x",
            is_superuser=False,
            is_active=True,
            must_change_password=False,
            totp_enabled=False,
            auth_version=0,
        )

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    def _req(self, step_up_token=None):
        class _Client:
            host = "127.0.0.1"

        class _Req:
            def __init__(self, token):
                self.headers = {"user-agent": "auth1-test"}
                if token:
                    self.headers["X-Step-Up-Token"] = token
                self.client = _Client()

        return _Req(step_up_token)

    def _token(self, user, version=None, totp_verified=False):
        from app.settings import settings

        payload = {
            "user_id": user.id,
            "username": user.username,
            "is_superuser": bool(user.is_superuser),
            "auth_version": 0 if version is None else version,
            "totp_verified": totp_verified,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    async def _authed(self, token):
        from fastapi import Request

        from app.core.dependency import AuthControl

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/base/userinfo"
        return await AuthControl.is_authed(request, token)

    async def _force_logout(self, actor, target_id, with_step_up=True):
        from app.api.v1.users.users import force_logout
        from app.core.dependency import require_step_up
        from app.core.step_up import step_up_store

        token = None
        if with_step_up:
            token, _ = step_up_store.issue(actor.id, "user_update_security", "totp")
        request = self._req(token)
        if with_step_up:
            actor = await require_step_up("user_update_security", request, actor)
        return await force_logout(request, user_id=target_id, current_user=actor)

    async def test_force_logout_bumps_target_only_and_keeps_admin_session(self):
        from app.models.admin import SecurityEvent

        target_token = self._token(self.target, version=0)
        admin_token = self._token(self.admin, version=0, totp_verified=True)
        await self._authed(target_token)
        await self._authed(admin_token)

        resp = await self._force_logout(self.admin, self.target.id)
        self.assertEqual(resp.status_code, 200)

        await self.target.refresh_from_db()
        await self.admin.refresh_from_db()
        self.assertEqual(self.target.auth_version, 1)
        self.assertEqual(self.admin.auth_version, 0)

        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._authed(target_token)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "登录已过期")

        still_admin = await self._authed(admin_token)
        self.assertEqual(still_admin.id, self.admin.id)

        events = await SecurityEvent.filter(event_type="force_logout").all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].username, "admin")
        self.assertIn("qa01", events[0].detail)
        self.assertNotIn("totp", (events[0].detail or "").lower())

    async def test_cannot_kick_self(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._force_logout(self.admin, self.admin.id)
        self.assertEqual(ctx.exception.status_code, 400)
        await self.admin.refresh_from_db()
        self.assertEqual(self.admin.auth_version, 0)

    async def test_non_superuser_forbidden(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._force_logout(self.staff, self.target.id)
        self.assertEqual(ctx.exception.status_code, 403)
        await self.target.refresh_from_db()
        self.assertEqual(self.target.auth_version, 0)

    async def test_missing_step_up_is_403(self):
        from fastapi import HTTPException

        from app.core.dependency import require_step_up

        with self.assertRaises(HTTPException) as ctx:
            await require_step_up("user_update_security", self._req(None), self.admin)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_does_not_add_nineteenth_policy(self):
        from app.services.verification_policy import OPERATION_DEFINITIONS

        keys = [item[0] for item in OPERATION_DEFINITIONS]
        self.assertEqual(len(OPERATION_DEFINITIONS), 18)
        self.assertIn("user_update_security", keys)
        self.assertNotIn("user_force_logout", keys)


if __name__ == "__main__":
    unittest.main()
