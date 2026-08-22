from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _local_refs(text: str) -> list[str]:
    values = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
    values += re.findall(r'''(?:src|href)=["']([^"']+)["']''', text)
    return [
        value.split("#", 1)[0].split("?", 1)[0]
        for value in values
        if value and not re.match(r"^(?:https?:|mailto:|#)", value)
    ]


class PublicDocsTests(unittest.TestCase):
    def test_bilingual_documents_and_navigation(self):
        expected = {
            "README.md",
            "README-en.md",
            "PROJECT-JOURNEY.md",
            "PROJECT-JOURNEY-en.md",
        }
        self.assertTrue(all((ROOT / name).is_file() for name in expected))
        self.assertIn("./README-en.md", _read("README.md"))
        self.assertIn("./README.md", _read("README-en.md"))
        self.assertIn("./PROJECT-JOURNEY-en.md", _read("PROJECT-JOURNEY.md"))
        self.assertIn("./PROJECT-JOURNEY.md", _read("PROJECT-JOURNEY-en.md"))
        self.assertIn("./PROJECT-JOURNEY-en.md", _read("README-en.md"))

    def test_all_local_document_references_exist(self):
        for name in (
            "README.md",
            "README-en.md",
            "PROJECT-JOURNEY.md",
            "PROJECT-JOURNEY-en.md",
        ):
            for ref in _local_refs(_read(name)):
                with self.subTest(document=name, ref=ref):
                    self.assertTrue((ROOT / ref).exists(), ref)

    def test_both_journeys_keep_exactly_42_history_rows(self):
        for name in ("PROJECT-JOURNEY.md", "PROJECT-JOURNEY-en.md"):
            rows = re.findall(r"^\|\s*\d+\s*\|", _read(name), re.MULTILINE)
            self.assertEqual(len(rows), 42, name)

    def test_chinese_gallery_keeps_the_approved_order(self):
        text = _read("README.md")
        expected = [
            "登录与滑块校验",
            "管理端工作台",
            "员工和主管业务工作台",
            "资产管理台账",
            "员工管理",
            "员工我的资产",
            "资产领用归还",
            "审批中心",
            "资产调拨",
            "资产报修",
            "资产盘点明细",
            "资产统计看板",
            "知识库问答与引用",
            "AI 助手",
            "安全中心",
            "手机扫码资产详情",
            "用户管理",
            "角色管理",
        ]
        positions = [text.index(f'alt="{alt}"') for alt in expected]
        self.assertEqual(positions, sorted(positions))
        for heading in (
            "### 登录与入口",
            "### 岗位与主数据",
            "### 资产流转",
            "### 运营与盘点",
            "### 知识、智能与治理",
            "### 权限与现场",
        ):
            self.assertIn(heading, text)

    def test_english_readme_links_evidence_and_states_security_truth(self):
        text = _read("README-en.md")
        for value in (
            "License-MIT-yellow.svg",
            "./SECURITY.md",
            "./PROJECT-JOURNEY-en.md",
            "deploy/sample-picture/project-challenge-map.png",
            "deploy/sample-picture/screenshots/employees-before-filter-fix.png",
            "deploy/sample-picture/screenshots/employees-filter-and-sort.png",
            "The sign-in slider is always required",
            "47 records",
        ):
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
