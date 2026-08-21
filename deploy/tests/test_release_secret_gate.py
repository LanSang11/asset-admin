from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile


from deploy.tools.check_release_secrets import (
    classify_sensitive_value,
    collect_sensitive_values,
    render_findings,
    scan_archive,
    scan_tree,
)


class ReleaseSecretGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env_path = self.root / "accounts.env"
        self.employee_password = "FixtureA!Qz9_xM7"
        self.manager_password = "FixtureB!654321"
        self.employee_username = "fixture_employee"
        self.manager_username = "fixture_manager"
        self.env_path.write_text(
            "\n".join(
                [
                    f"EMPLOYEE_USERNAME={self.employee_username}",
                    f"EMPLOYEE_PASSWORD={self.employee_password}",
                    f"MANAGER_USERNAME={self.manager_username}",
                    f"MANAGER_PASSWORD={self.manager_password}",
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _zip(self, name: str, entries: dict[str, str | bytes]) -> Path:
        path = self.root / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry, payload in entries.items():
                archive.writestr(entry, payload)
        return path

    def test_collects_only_nonempty_sensitive_fixture_slots(self):
        values = collect_sensitive_values(self.env_path)
        by_label = {item.label: item for item in values}

        self.assertEqual(
            set(by_label),
            {
                "EMPLOYEE_USERNAME",
                "EMPLOYEE_PASSWORD",
                "MANAGER_USERNAME",
                "MANAGER_PASSWORD",
            },
        )
        self.assertTrue(all(item.value for item in values))
        self.assertEqual(by_label["EMPLOYEE_PASSWORD"].match_mode, "substring")
        self.assertEqual(by_label["EMPLOYEE_USERNAME"].match_mode, "word_boundary")

    def test_skips_generic_usernames_and_low_entropy_examples(self):
        admin = classify_sensitive_value("ADMIN_USERNAME", "admin")
        weak = classify_sensitive_value("MYSQL_ROOT_PASSWORD", "123456")
        look = classify_sensitive_value("LOOK1_USERNAME", "look1")

        self.assertIsNone(admin)
        self.assertIsNone(weak)
        self.assertIsNone(look)

    def test_generic_admin_and_weak_example_do_not_fail_official_style_archive(self):
        self.env_path.write_text(
            "\n".join(
                [
                    "ADMIN_USERNAME=admin",
                    "ADMIN_PASSWORD=AdminStrong!9xQ",
                    "EMPLOYEE_USERNAME=fixture_employee",
                    f"EMPLOYEE_PASSWORD={self.employee_password}",
                    "MANAGER_USERNAME=fixture_manager",
                    f"MANAGER_PASSWORD={self.manager_password}",
                    "LOOK1_USERNAME=look1",
                    "MYSQL_ROOT_PASSWORD=123456",
                ]
            ),
            encoding="utf-8",
        )
        archive = self._zip(
            "official-style.zip",
            {
                "app/schemas/login.py": (
                    "# 示例禁止使用 admin/123456 等弱口令（信息暴露门禁）\n"
                    "username: str\n"
                ),
                "app/core/init_app.py": "username='admin'\n",
                "web/dist/assets/index.js": "portal:'admin',role:'admin'\n",
            },
        )

        findings = scan_archive(archive, self.env_path)

        self.assertEqual([], findings)

    def test_distinctive_username_uses_word_boundary_not_substring(self):
        archive_hit = self._zip(
            "user-hit.zip",
            {"app/note.py": f'username = "{self.employee_username}"\n'},
        )
        archive_miss = self._zip(
            "user-miss.zip",
            {"app/note.py": f"token = 'xx{self.employee_username}yy'\n"},
        )

        self.assertIn("credential_value", {item.code for item in scan_archive(archive_hit, self.env_path)})
        self.assertEqual([], scan_archive(archive_miss, self.env_path))

    def test_rejects_secret_paths_even_when_content_is_empty(self):
        archive = self._zip("bad-path.zip", {"secrets/accounts.env": b""})

        findings = scan_archive(archive, self.env_path)

        self.assertIn("forbidden_path", {finding.code for finding in findings})

    def test_rejects_current_fixture_value_without_echoing_it(self):
        archive = self._zip(
            "bad-value.zip",
            {"deploy/example.py": f'PASSWORD = "{self.employee_password}"\n'},
        )

        findings = scan_archive(archive, self.env_path)
        report = render_findings(findings)

        self.assertIn("credential_value", {finding.code for finding in findings})
        self.assertNotIn(self.employee_password, report)

    def test_rejects_retired_credential_literal_by_fingerprint(self):
        retired = "RetiredC!987654"
        fingerprint_file = self.root / "retired-credential-sha256.txt"
        fingerprint_file.write_text(
            f"RETIRED_PASSWORD|{len(retired)}|{hashlib.sha256(retired.encode()).hexdigest()}\n",
            encoding="utf-8",
        )
        archive = self._zip(
            "retired.zip",
            {"deploy/old_fixture.py": f'DEFAULT_PASSWORD = "{retired}"\n'},
        )

        findings = scan_archive(archive, self.env_path, fingerprint_file)

        self.assertIn("retired_credential", {finding.code for finding in findings})

    def test_clean_archive_and_tree_pass(self):
        archive = self._zip(
            "clean.zip",
            {
                "app/main.py": "PASSWORD = os.environ['APP_PASSWORD']\n",
                "web/dist/index.html": "<!doctype html><title>APP</title>",
            },
        )
        tree = self.root / "clean-tree"
        tree.mkdir()
        (tree / "main.py").write_text("token = request.headers.get('token')\n", encoding="utf-8")

        archive_findings = scan_archive(archive, self.env_path)
        tree_findings = scan_tree(tree, self.env_path)

        self.assertEqual([], archive_findings)
        self.assertEqual([], tree_findings)

    def test_demo_initializer_never_prints_password_variable(self):
        source = (Path(__file__).parents[1] / "init_demo_data.py").read_text(encoding="utf-8")

        self.assertNotRegex(source, r"print\s*\(\s*f?[\"'][^\r\n]*DEFAULT_PWD")

    def test_active_publish_script_runs_secret_gate_before_upload(self):
        publish_script = Path(r"/path/to/ops\scripts\publish_asset_code.py")
        if not publish_script.is_file():
            self.skipTest("private publish script absent from public tree")
        source = publish_script.read_text(encoding="utf-8")

        gate_pos = source.index("check_release_secrets.py")
        upload_pos = source.index("sftp.put")
        self.assertLess(gate_pos, upload_pos)
        self.assertIn("RETIRED_CREDENTIAL_FINGERPRINTS", source)


if __name__ == "__main__":
    unittest.main()
