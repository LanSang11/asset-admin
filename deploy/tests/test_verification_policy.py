import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.core.step_up import StepUpStore
from app.models.admin import VerificationSettings
from app.services.verification_policy import (
    ACCEPTANCE_DURATION_ERROR,
    ACCEPTANCE_MODE_HOURS,
    ACCEPTANCE_MODE_MINUTES_DEFAULT,
    OPERATION_DEFINITIONS,
    ROOT_OPERATION_KEYS,
    acceptance_window,
    compute_acceptance_until,
    login_totp_required,
    normalize_acceptance_duration_minutes,
    parse_acceptance_duration_from_detail,
    password_rotate_due,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestVerificationPolicy(unittest.TestCase):
    def test_step_up_token_is_bound_and_single_use(self):
        store = StepUpStore(expire_seconds=60)
        token, expires = store.issue(7, "asset_delete", "password")
        self.assertEqual(expires, 60)
        self.assertFalse(store.consume(7, "user_delete", "password", token))
        self.assertFalse(store.consume(7, "asset_delete", "password", token))

        token, _ = store.issue(7, "asset_delete", "password")
        self.assertFalse(store.consume(7, "asset_delete", "totp", token))

        token, _ = store.issue(7, "asset_delete", "password")
        self.assertTrue(store.consume(7, "asset_delete", "password", token))
        self.assertFalse(store.consume(7, "asset_delete", "password", token))

    def test_all_operation_keys_are_unique_and_modes_valid(self):
        keys = [item[0] for item in OPERATION_DEFINITIONS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(item[2] in {"off", "password", "totp"} for item in OPERATION_DEFINITIONS))
        self.assertTrue(ROOT_OPERATION_KEYS.isdisjoint(keys))

    def test_security_sensitive_defaults_use_totp(self):
        defaults = {key: mode for key, _label, mode in OPERATION_DEFINITIONS}
        for key in (
            "user_delete",
            "user_reset_password",
            "role_authorize",
            "blacklist_ban",
            "blacklist_unban",
            "export_employees",
            "export_assets",
            "export_asset_uses",
        ):
            self.assertEqual(defaults[key], "totp")
        self.assertEqual(defaults["asset_delete"], "password")
        self.assertEqual(defaults["employee_delete"], "password")
        self.assertIn("acceptance_mode_update", ROOT_OPERATION_KEYS)
        self.assertIn("tls_cert_renew", ROOT_OPERATION_KEYS)
        self.assertEqual(ACCEPTANCE_MODE_HOURS, 2)
        self.assertEqual(ACCEPTANCE_MODE_MINUTES_DEFAULT, 120)
        self.assertEqual(len(OPERATION_DEFINITIONS), 18)

    def test_no_high_risk_code_default_is_off(self):
        must_stay_on = {
            "user_create",
            "user_update_security",
            "user_delete",
            "user_reset_password",
            "role_delete",
            "role_authorize",
            "api_delete",
            "api_refresh",
            "dept_delete",
            "menu_delete",
            "blacklist_ban",
            "blacklist_unban",
            "export_employees",
            "export_assets",
            "export_asset_uses",
        }
        defaults = {key: mode for key, _label, mode in OPERATION_DEFINITIONS}
        for key in must_stay_on:
            self.assertNotEqual(defaults[key], "off", key)
        self.assertEqual(
            ROOT_OPERATION_KEYS,
            {
                "verification_policy_update",
                "user_totp_reset",
                "acceptance_mode_update",
                "tls_cert_renew",
            },
        )
        self.assertTrue(ROOT_OPERATION_KEYS.isdisjoint(defaults))

    def test_force_superuser_new_db_default_true(self):
        field = VerificationSettings._meta.fields_map["force_superuser"]
        self.assertIs(field.default, True)

    def test_missing_settings_superuser_totp_fail_closed(self):
        class _Empty:
            async def first(self):
                return None

        class _Super:
            is_superuser = True

        async def _run():
            with patch(
                "app.services.verification_policy.VerificationSettings.filter",
                return_value=_Empty(),
            ):
                self.assertTrue(await login_totp_required(_Super()))

        asyncio.run(_run())

    def test_superuser_login_totp_stays_on_even_if_flag_off(self):
        class _Off:
            force_superuser = False
            role_ids = []

            async def first(self):
                return self

        class _Super:
            is_superuser = True

        async def _run():
            with patch(
                "app.services.verification_policy.VerificationSettings.filter",
                return_value=_Off(),
            ):
                self.assertTrue(await login_totp_required(_Super()))

        asyncio.run(_run())

    def test_acceptance_window_expires_and_ignores_stale(self):
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        off = acceptance_window(None, now)
        self.assertFalse(off["active"])
        self.assertIsNone(off["expires_at"])
        self.assertEqual(off["remaining_seconds"], 0)
        self.assertEqual(off["duration_hours"], 2)
        self.assertEqual(off["duration_minutes"], 120)

        expired = acceptance_window(now - timedelta(minutes=1), now)
        self.assertFalse(expired["active"])
        self.assertEqual(expired["remaining_seconds"], 0)

        live = acceptance_window(now + timedelta(hours=1, minutes=5), now)
        self.assertTrue(live["active"])
        self.assertEqual(live["remaining_seconds"], 3900)
        self.assertTrue(live["expires_at"].startswith("2026-08-17T13:05:00"))

    def test_acceptance_duration_minutes_valid_and_rejected(self):
        now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(normalize_acceptance_duration_minutes(None), 120)
        for minutes in (15, 30, 60, 120, 240, 480):
            self.assertEqual(normalize_acceptance_duration_minutes(minutes), minutes)
            until, used = compute_acceptance_until(True, minutes, now)
            self.assertEqual(used, minutes)
            self.assertEqual(until, now + timedelta(minutes=minutes))
            window = acceptance_window(until, now, duration_minutes=minutes)
            self.assertTrue(window["active"])
            self.assertEqual(window["remaining_seconds"], minutes * 60)
            self.assertEqual(window["duration_minutes"], minutes)
            self.assertEqual(window["duration_hours"], minutes / 60 if minutes % 60 else minutes // 60)

        for bad in (0, -15, 481, 16, 1, 14, 500, True, False):
            with self.assertRaises(ValueError) as ctx:
                normalize_acceptance_duration_minutes(bad)
            self.assertEqual(str(ctx.exception), ACCEPTANCE_DURATION_ERROR)
            with self.assertRaises(ValueError):
                compute_acceptance_until(True, bad, now)

        closed, used = compute_acceptance_until(False, 16, now)
        self.assertIsNone(closed)
        self.assertEqual(used, 120)

    def test_acceptance_event_detail_parses_minutes(self):
        self.assertEqual(
            parse_acceptance_duration_from_detail("开启临时免登录动态码 120 分钟，到期 2026-08-23T12:00:00+00:00"),
            120,
        )
        self.assertEqual(parse_acceptance_duration_from_detail("开启临时免登录动态码 30 分钟，到期 2026-08-23T12:30:00+00:00"), 30)
        self.assertIsNone(parse_acceptance_duration_from_detail("关闭临时免登录动态码"))
        self.assertIsNone(parse_acceptance_duration_from_detail("开启临时免登录动态码 16 分钟，到期 x"))

    def test_enable_acceptance_requires_step_up_and_locks_force_superuser(self):
        src = (REPO_ROOT / "app/api/v1/security/security.py").read_text(encoding="utf-8")
        policy = (REPO_ROOT / "app/services/verification_policy.py").read_text(encoding="utf-8")
        self.assertIn('require_step_up("acceptance_mode_update"', src)
        self.assertIn("duration_minutes", src)
        self.assertIn("normalize_acceptance_duration_minutes", src)
        self.assertIn("settings_obj.force_superuser = True", src)
        self.assertNotIn("settings_obj.force_superuser = body.login.force_superuser", src)
        self.assertIn("已忽略关闭超级管理员登录强制 TOTP 的请求", src)
        self.assertEqual(
            ROOT_OPERATION_KEYS,
            {
                "verification_policy_update",
                "user_totp_reset",
                "acceptance_mode_update",
                "tls_cert_renew",
            },
        )
        self.assertIn('("user_create", "创建系统用户", "totp")', policy)
        self.assertNotIn("OPERATION_DEFINITIONS = (\n    (\"acceptance_mode_update\"", policy)

    def test_password_rotate_default_off(self):
        now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
        self.assertFalse(
            password_rotate_due(
                max_days=0,
                deadline=None,
                password_changed_at=now - timedelta(days=400),
                now=now,
            )
        )
        self.assertTrue(
            password_rotate_due(
                max_days=90,
                deadline=None,
                password_changed_at=now - timedelta(days=91),
                now=now,
            )
        )
        self.assertTrue(
            password_rotate_due(
                max_days=0,
                deadline=now - timedelta(hours=1),
                password_changed_at=now,
                now=now,
            )
        )
        self.assertFalse(
            password_rotate_due(
                max_days=90,
                deadline=None,
                password_changed_at=now - timedelta(days=10),
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
