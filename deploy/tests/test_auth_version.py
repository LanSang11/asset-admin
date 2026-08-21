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


if __name__ == "__main__":
    unittest.main()
