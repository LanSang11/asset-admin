# -*- coding: utf-8 -*-
"""资产 CSV 导入（表头与 export_assets 对齐）。默认 dry-run。"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.controllers.asset import ASSET_CATEGORIES
from app.models.business import Asset, Employee

IMPORT_MAX_ROWS = 500

HEADERS = ["资产编号", "名称", "分类", "型号", "序列号", "采购日期", "质保到期", "价格(元)", "状态", "存放位置", "领用人ID", "备注"]

STATUS_MAP = {"在用": 1, "闲置": 2, "维修": 3, "报废": 4, "1": 1, "2": 2, "3": 3, "4": 4}


def _parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"日期格式无效: {s}")


def _parse_price(s: str):
    s = (s or "").strip()
    if not s:
        return Decimal("0")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"价格无效: {s}") from e


def _parse_status(s: str) -> int:
    s = (s or "").strip()
    if s in STATUS_MAP:
        return STATUS_MAP[s]
    raise ValueError(f"状态无效: {s}")


def parse_csv_bytes(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 无表头")
    fields = [h.strip().lstrip("\ufeff") for h in reader.fieldnames]
    missing = [h for h in ("资产编号", "名称") if h not in fields]
    if missing:
        raise ValueError("缺少必要列: " + ",".join(missing))
    rows = []
    for i, row in enumerate(reader, start=2):
        if i - 1 > IMPORT_MAX_ROWS:
            raise ValueError(f"超过单次上限 {IMPORT_MAX_ROWS} 行")
        mapped = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        if not any(mapped.values()):
            continue
        rows.append({"line": i, "raw": mapped})
    return rows


async def import_assets(raw: bytes, *, commit: bool = False) -> dict[str, Any]:
    parsed = parse_csv_bytes(raw)
    existing = set(await Asset.all().values_list("asset_no", flat=True))
    ok, skipped, errors = [], [], []
    to_create = []

    for item in parsed:
        line = item["line"]
        r = item["raw"]
        no = (r.get("资产编号") or "").strip()
        name = (r.get("名称") or "").strip()
        try:
            if not no or not name:
                raise ValueError("资产编号和名称不能为空")
            if no in existing or any(x["asset_no"] == no for x in to_create):
                skipped.append({"line": line, "asset_no": no, "reason": "编号已存在，已跳过"})
                continue
            category = (r.get("分类") or "其他").strip() or "其他"
            if category not in ASSET_CATEGORIES:
                category = "其他"
            status = _parse_status(r.get("状态") or "闲置")
            owner_raw = (r.get("领用人ID") or "").strip()
            owner_id = int(owner_raw) if owner_raw else None
            if status == 1 and not owner_id:
                raise ValueError("在用必须填写领用人ID")
            if status in (2, 4):
                owner_id = None
            if owner_id and not await Employee.filter(id=owner_id).first():
                raise ValueError(f"领用人ID不存在: {owner_id}")
            rec = {
                "asset_no": no,
                "name": name,
                "category": category,
                "model": (r.get("型号") or "")[:100],
                "serial_no": (r.get("序列号") or "")[:100],
                "purchase_date": _parse_date(r.get("采购日期") or ""),
                "warranty_until": _parse_date(r.get("质保到期") or ""),
                "price": _parse_price(r.get("价格(元)") or ""),
                "status": status,
                "location": (r.get("存放位置") or "")[:100],
                "owner_emp_id": owner_id,
                "remark": (r.get("备注") or "")[:255],
            }
            to_create.append(rec)
            ok.append({"line": line, "asset_no": no, "name": name})
        except Exception as e:
            errors.append({"line": line, "asset_no": no, "reason": str(e)})

    created = 0
    if commit and to_create:
        for rec in to_create:
            await Asset.create(**rec)
            created += 1

    return {
        "commit": commit,
        "total": len(parsed),
        "ok": len(ok),
        "skipped": len(skipped),
        "errors": len(errors),
        "created": created,
        "ok_rows": ok[:50],
        "skipped_rows": skipped[:50],
        "error_rows": errors[:50],
    }
