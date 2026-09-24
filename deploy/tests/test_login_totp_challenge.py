# -*- coding: utf-8 -*-
"""LOGIN-TOTP-STATE-1：缺/错/过期/重放挑战不签发 token；正确动态码 totp_verified=true。"""
from __future__ import annotations

import json
import os
import secrets
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.login_totp_challenge import LoginTotpChallengeStore, challenge_payload
from app.core.totp_utils import generate_secret, totp_at

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestLoginChallengeStore(unittest.TestCase):
    def test_issue_payload_has_no_token(self):
        store = LoginTotpChallengeStore(ttl_seconds=120, max_fails=3)
        ch = store.issue(user_id=1, username="admin", ip="127.0.0.1", auth_version=0)
        data = challenge_payload(ch)
        self.assertEqual(data["next_step"], "totp")
        self.assertEqual(data["login_challenge"], ch.token)
        self.assertNotIn("access_token", data)
        self.assertTrue(0 < data["expires_in"] <= 120)

    def test_consume_is_single_use(self):
        store = LoginTotpChallengeStore()
        ch = store.issue(user_id=2, username="u2", ip="10.0.0.1", auth_version=1)
        self.assertIsNotNone(store.consume(ch.token))
        self.assertIsNone(store.consume(ch.token))
        self.assertIsNone(store.get(ch.token))

    def test_expire_and_replay(self):
        store = LoginTotpChallengeStore(ttl_seconds=1)
        now = time.time()
        ch = store.issue(user_id=3, username="u3", ip="10.0.0.1", auth_version=0, now=now)
        self.assertIsNone(store.get(ch.token, now=now + 2))
        self.assertIsNone(store.consume(ch.token, now=now + 2))

    def test_three_failures_exhaust_challenge(self):
        store = LoginTotpChallengeStore(max_fails=3)
        ch = store.issue(user_id=4, username="u4", ip="10.0.0.1", auth_version=0)
        self.assertEqual(store.record_failure(ch.token), "ok")
        self.assertEqual(store.record_failure(ch.token), "ok")
        self.assertEqual(store.record_failure(ch.token), "exhausted")
        self.assertEqual(store.record_failure(ch.token), "missing")

    def test_new_issue_replaces_old_for_same_user(self):
        store = LoginTotpChallengeStore()
        first = store.issue(user_id=5, username="u5", ip="10.0.0.1", auth_version=0)
        second = store.issue(user_id=5, username="u5", ip="10.0.0.1", auth_version=0)
        self.assertIsNone(store.get(first.token))
        self.assertIsNotNone(store.get(second.token))


class TestLoginTotpSourceContract(unittest.TestCase):
    def test_login_page_uses_challenge_not_fake_failure(self):
        login = (REPO_ROOT / "web/src/views/login/index.vue").read_text(encoding="utf-8")
        backend = (REPO_ROOT / "app/api/v1/base/base.py").read_text(encoding="utf-8")
        self.assertIn("next_step === 'totp'", login)
        self.assertIn("login_challenge", login)
        self.assertNotIn("并重新完成滑块", login)
        self.assertIn("enterTotpStep", login)
        self.assertIn("stopVerifyMsg", login)
        self.assertIn("返回重新登录", login)
        self.assertIn("登录未完成，请重试", login)
        self.assertNotIn("watch(", login)
        self.assertIn("challenge_payload", backend)
        self.assertIn("login_totp_challenge", backend)
        self.assertIn("login_challenge", (REPO_ROOT / "app/core/security.py").read_text(encoding="utf-8"))


try:
    import fastapi  # noqa: F401
    import jwt
    from tortoise import Tortoise

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


@unittest.skipUnless(HAS_DEPS, "本机未安装 fastapi/tortoise/jwt 依赖")
class TestLoginTotpAccessToken(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("SHOW_DOCS", "1")
        from app.models import admin  # noqa: F401
        from app.models import business  # noqa: F401

        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.admin", "app.models.business"]},
        )
        await Tortoise.generate_schemas()

        from app.core.login_guard import login_guard
        from app.core.login_totp_challenge import login_totp_challenge
        from app.models.admin import User
        from app.utils.password import get_password_hash

        login_totp_challenge.clear()
        login_guard._failures.clear()
        login_guard._ip_failures.clear()

        self.secret = generate_secret()
        self.password = "LoginTotp@123"
        self.user = await User.create(
            username="totpuser",
            email="totpuser@t.com",
            password=get_password_hash(self.password),
            is_superuser=False,
            is_active=True,
            must_change_password=False,
            totp_enabled=True,
            totp_secret=self.secret,
            recovery_question="测试恢复问题不少于八字",
            recovery_answer_hash=get_password_hash("answer-is-long-enough"),
            auth_version=0,
        )
        self.plain = await User.create(
            username="plainuser",
            email="plainuser@t.com",
            password=get_password_hash(self.password),
            is_superuser=False,
            is_active=True,
            must_change_password=False,
            totp_enabled=False,
        )

    async def asyncTearDown(self):
        from app.core.login_totp_challenge import login_totp_challenge

        login_totp_challenge.clear()
        await Tortoise.close_connections()

    def _request(self, ip="127.0.0.1"):
        class _Client:
            def __init__(self, host):
                self.host = host

        class _Req:
            def __init__(self, host):
                self.headers = {"user-agent": "login-totp-test", "accept-language": "zh-CN"}
                self.client = _Client(host)

        return _Req(ip)

    def _ticket(self, ip="127.0.0.1"):
        from app.core.slide_captcha import slide_captcha

        ticket = secrets.token_urlsafe(24)
        slide_captcha._tickets[ticket] = {"ip": ip, "expire": time.time() + 90}
        return ticket

    def _creds(self, **kwargs):
        from app.schemas.login import CredentialsSchema

        payload = {
            "username": "totpuser",
            "password": self.password,
            "captcha_ticket": kwargs.pop("captcha_ticket", None),
            "totp_code": kwargs.pop("totp_code", None),
            "login_challenge": kwargs.pop("login_challenge", None),
        }
        payload.update(kwargs)
        return CredentialsSchema(**payload)

    def _body(self, resp):
        return json.loads(resp.body)

    def _claims(self, token):
        from app.settings import settings

        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    async def _login(self, creds, ip="127.0.0.1"):
        from app.api.v1.base.base import login_access_token

        return await login_access_token(creds, self._request(ip))

    async def test_missing_totp_returns_challenge_without_token(self):
        resp = await self._login(self._creds(captcha_ticket=self._ticket()))
        body = self._body(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["code"], 200)
        data = body["data"]
        self.assertEqual(data["next_step"], "totp")
        self.assertTrue(data["login_challenge"])
        self.assertNotIn("access_token", data)

    async def test_wrong_totp_on_challenge_has_no_token(self):
        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        challenge = first["data"]["login_challenge"]
        resp = await self._login(
            self._creds(login_challenge=challenge, totp_code="000000", captcha_ticket=None)
        )
        body = self._body(resp)
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("access_token", body.get("data") or {})
        self.assertTrue((body.get("data") or {}).get("require_totp"))

    async def test_correct_totp_sets_verified_claim(self):
        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        challenge = first["data"]["login_challenge"]
        resp = await self._login(
            self._creds(
                login_challenge=challenge,
                totp_code=totp_at(self.secret),
                captcha_ticket=None,
            )
        )
        body = self._body(resp)
        self.assertEqual(resp.status_code, 200)
        token = body["data"]["access_token"]
        self.assertTrue(token)
        self.assertIs(self._claims(token)["totp_verified"], True)

    async def test_replay_challenge_has_no_token(self):
        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        challenge = first["data"]["login_challenge"]
        code = totp_at(self.secret)
        ok = self._body(
            await self._login(self._creds(login_challenge=challenge, totp_code=code, captcha_ticket=None))
        )
        self.assertIn("access_token", ok["data"])
        replay = self._body(
            await self._login(self._creds(login_challenge=challenge, totp_code=code, captcha_ticket=None))
        )
        self.assertEqual(replay["code"], 400)
        self.assertNotIn("access_token", replay.get("data") or {})

    async def test_ip_change_does_not_block_correct_totp(self):
        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket()), ip="127.0.0.1"))
        challenge = first["data"]["login_challenge"]
        resp = await self._login(
            self._creds(
                login_challenge=challenge,
                totp_code=totp_at(self.secret),
                captcha_ticket=None,
            ),
            ip="10.0.0.8",
        )
        body = self._body(resp)
        self.assertEqual(body["code"], 200)
        self.assertIn("access_token", body["data"])
        self.assertIs(self._claims(body["data"]["access_token"])["totp_verified"], True)

    async def test_auth_version_change_invalidates_challenge(self):
        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        challenge = first["data"]["login_challenge"]
        self.user.auth_version = 3
        await self.user.save(update_fields=["auth_version"])
        body = self._body(
            await self._login(
                self._creds(
                    login_challenge=challenge,
                    totp_code=totp_at(self.secret),
                    captcha_ticket=None,
                )
            )
        )
        self.assertEqual(body["code"], 400)
        self.assertNotIn("access_token", body.get("data") or {})

    async def test_expired_challenge_has_no_token(self):
        from app.core.login_totp_challenge import login_totp_challenge

        first = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        challenge = first["data"]["login_challenge"]
        item = login_totp_challenge.get(challenge)
        item.expire = time.time() - 1
        body = self._body(
            await self._login(
                self._creds(
                    login_challenge=challenge,
                    totp_code=totp_at(self.secret),
                    captcha_ticket=None,
                )
            )
        )
        self.assertEqual(body["code"], 400)
        self.assertNotIn("access_token", body.get("data") or {})

    async def test_one_shot_wrong_totp_has_no_token(self):
        body = self._body(
            await self._login(self._creds(captcha_ticket=self._ticket(), totp_code="111111"))
        )
        self.assertEqual(body["code"], 400)
        self.assertNotIn("access_token", body.get("data") or {})

    async def test_plain_account_still_gets_token_without_totp(self):
        body = self._body(
            await self._login(
                self._creds(
                    username="plainuser",
                    captcha_ticket=self._ticket(),
                )
            )
        )
        self.assertEqual(body["code"], 200)
        self.assertIn("access_token", body["data"])
        self.assertNotEqual(body["data"].get("next_step"), "totp")

    async def test_acceptance_window_skips_login_totp_without_verified_claim(self):
        from app.models.admin import VerificationSettings

        await VerificationSettings.create(
            id=1,
            force_superuser=True,
            role_ids=[],
            acceptance_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        body = self._body(await self._login(self._creds(captcha_ticket=self._ticket())))
        self.assertEqual(body["code"], 200)
        token = body["data"]["access_token"]
        self.assertIsNot(self._claims(token).get("totp_verified"), True)


if __name__ == "__main__":
    unittest.main()
