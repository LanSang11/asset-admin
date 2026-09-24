# -*- coding: utf-8 -*-
"""IMP-1 资产导入：列别名、预检明细与既有上限。"""
from decimal import Decimal
import unittest

from tortoise import Tortoise


class TestAssetImport(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.business"]},
        )
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_alias_headers_are_mapped_before_validation_and_commit(self):
        """删除任一已声明别名映射时，本测试应因缺必要列或价格归零而失败。"""
        from app.models.business import Asset
        from app.services.import_service import import_assets

        raw = "资产编码,名称,单价,状态\nA-001,设计笔记本,6999.50,闲置\n".encode("utf-8")

        result = await import_assets(raw, commit=True)

        self.assertEqual(result["created"], 1)
        self.assertEqual(
            result["header_mappings"],
            [
                {"source": "资产编码", "target": "资产编号"},
                {"source": "单价", "target": "价格(元)"},
            ],
        )
        asset = await Asset.get(asset_no="A-001")
        self.assertEqual(asset.price, Decimal("6999.50"))

    async def test_unmapped_required_header_becomes_downloadable_error_row(self):
        """恢复顶层“缺少必要列”异常时，本测试应失败。"""
        from app.models.business import Asset
        from app.services.import_service import import_assets

        raw = "设备编码,名称,状态\nA-002,会议平板,闲置\n".encode("utf-8")

        result = await import_assets(raw, commit=True)

        self.assertEqual(result["ok"], 0)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["error_rows"][0]["line"], 2)
        self.assertEqual(result["error_rows"][0]["asset_no"], "")
        self.assertIn("缺少必要列: 资产编号", result["error_rows"][0]["reason"])
        self.assertEqual(await Asset.all().count(), 0)

    async def test_header_only_missing_required_column_still_has_downloadable_error(self):
        """缺列文件没有数据行时，表头错误也必须能在预览中下载。"""
        from app.services.import_service import import_assets

        result = await import_assets("设备编码,名称\n".encode("utf-8"), commit=False)

        self.assertEqual(result["total"], 0)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(
            result["error_rows"],
            [{"line": 1, "asset_no": "", "reason": "缺少必要列: 资产编号"}],
        )

    async def test_preview_returns_every_error_row_within_500_row_limit(self):
        """把错误明细重新截成 50 行时，本测试应失败。"""
        from app.models.business import Asset
        from app.services.import_service import import_assets

        lines = ["资产编号,名称,状态"]
        lines.extend(f"ERR-{i:03d},错误资产{i},未知状态" for i in range(60))

        result = await import_assets(("\n".join(lines) + "\n").encode("utf-8"), commit=False)

        self.assertEqual(result["total"], 60)
        self.assertEqual(result["errors"], 60)
        self.assertEqual(len(result["error_rows"]), 60)
        self.assertEqual(result["error_rows"][-1]["line"], 61)
        self.assertEqual(await Asset.all().count(), 0)

    async def test_import_still_rejects_more_than_500_data_rows(self):
        """放宽既有 500 行上限时，本测试应失败。"""
        from app.services.import_service import import_assets

        lines = ["资产编号,名称,状态"]
        lines.extend(f"A-{i:03d},资产{i},闲置" for i in range(501))

        with self.assertRaisesRegex(ValueError, "超过单次上限 500 行"):
            await import_assets(("\n".join(lines) + "\n").encode("utf-8"), commit=False)


if __name__ == "__main__":
    unittest.main()
