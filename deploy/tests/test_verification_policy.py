import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.step_up import StepUpStore
from app.models.admin import VerificationSettings
from app.services.verification_policy import (
    ACCEPTANCE_MODE_HOURS,
    OPERATION_DEFINITIONS,
    ROOT_OPERATION_KEYS,
    acceptance_window,
    login_totp_required,
    password_rotate_due,
)


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

    def test_acceptance_window_expires_and_ignores_stale(self):
        now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        off = acceptance_window(None, now)
        self.assertFalse(off["active"])
        self.assertIsNone(off["expires_at"])
        self.assertEqual(off["remaining_seconds"], 0)
        self.assertEqual(off["duration_hours"], 2)

        expired = acceptance_window(now - timedelta(minutes=1), now)
        self.assertFalse(expired["active"])
        self.assertEqual(expired["remaining_seconds"], 0)

        live = acceptance_window(now + timedelta(hours=1, minutes=5), now)
        self.assertTrue(live["active"])
        self.assertEqual(live["remaining_seconds"], 3900)
        self.assertTrue(live["expires_at"].startswith("2026-08-17T13:05:00"))

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
