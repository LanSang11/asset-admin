"""资产质保到期：状态计算、筛选、站内提醒（不轰炸全员）。

对照常见 ITAM（Snipe-IT / shelf.nu）：用明确到期日，提前期 30 天。
提醒只发给超管 + 当前领用人；同一资产同一档（即将过保/已过保）只发一次。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional

from tortoise.expressions import Q

from app.models.business import Asset, Employee
from app.services.notification_service import (
    TYPE_WARRANTY,
    list_superuser_ids,
    notify_user,
)

WARRANTY_LEAD_DAYS = 30
ASSET_STATUS_SCRAPPED = 4
WARRANTY_LABELS = {
    "none": "",
    "ok": "在保",
    "expiring": "即将过保",
    "expired": "已过保",
}


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return date.fromisoformat(text[:10])
    return None


def warranty_days_left(warranty_until, today: Optional[date] = None) -> Optional[int]:
    until = _as_date(warranty_until)
    if until is None:
        return None
    current = today or date.today()
    return (until - current).days


def warranty_state(warranty_until, today: Optional[date] = None, lead_days: int = WARRANTY_LEAD_DAYS) -> str:
    until = _as_date(warranty_until)
    if until is None:
        return "none"
    days = warranty_days_left(until, today)
    if days is None:
        return "none"
    if days < 0:
        return "expired"
    if days <= lead_days:
        return "expiring"
    return "ok"


def warranty_q(state: str, today: Optional[date] = None) -> Q:
    """列表筛选。未知 state 不加条件。"""
    current = today or date.today()
    horizon = current + timedelta(days=WARRANTY_LEAD_DAYS)
    key = (state or "").strip().lower()
    if key == "expired":
        return Q(warranty_until__isnull=False) & Q(warranty_until__lt=current)
    if key == "expiring":
        return Q(warranty_until__gte=current) & Q(warranty_until__lte=horizon)
    if key == "due":
        return Q(warranty_until__isnull=False) & Q(warranty_until__lte=horizon)
    if key == "ok":
        return Q(warranty_until__gt=horizon)
    if key == "none":
        return Q(warranty_until__isnull=True)
    return Q()


def attach_warranty_fields(data: dict[str, Any], *, hide: bool = False) -> dict[str, Any]:
    if hide:
        data["warranty_until"] = None
        data["warranty_state"] = "none"
        data["warranty_days_left"] = None
        data["warranty_label"] = ""
        data.pop("warranty_notified_state", None)
        return data
    state = warranty_state(data.get("warranty_until"))
    data["warranty_state"] = state
    data["warranty_days_left"] = warranty_days_left(data.get("warranty_until"))
    data["warranty_label"] = WARRANTY_LABELS.get(state, "")
    data.pop("warranty_notified_state", None)
    return data


def summarize_warranty(assets: Iterable[Asset], today: Optional[date] = None) -> dict[str, Any]:
    current = today or date.today()
    due: list[Asset] = []
    expiring = 0
    expired = 0
    for asset in assets:
        if asset.status == ASSET_STATUS_SCRAPPED:
            continue
        state = warranty_state(asset.warranty_until, current)
        if state == "expiring":
            expiring += 1
        elif state == "expired":
            expired += 1
        else:
            continue
        due.append(asset)
    due.sort(
        key=lambda item: (
            0 if warranty_state(item.warranty_until, current) == "expired" else 1,
            _as_date(item.warranty_until) or date.max,
        )
    )
    return {
        "expiring": expiring,
        "expired": expired,
        "lead_days": WARRANTY_LEAD_DAYS,
        "list": [
            {
                "asset_no": item.asset_no,
                "name": item.name,
                "warranty_until": item.warranty_until.strftime("%Y-%m-%d") if item.warranty_until else "",
                "warranty_state": warranty_state(item.warranty_until, current),
                "warranty_days_left": warranty_days_left(item.warranty_until, current),
            }
            for item in due[:10]
        ],
    }


async def emit_warranty_alerts(assets: Iterable[Asset], today: Optional[date] = None) -> int:
    """同一资产同一档只通知一次；收件人=超管+领用人账号。"""
    current = today or date.today()
    rows = [item for item in assets]
    if not rows:
        return 0
    admin_ids = await list_superuser_ids()
    owner_ids = {item.owner_emp_id for item in rows if item.owner_emp_id}
    owners = {emp.id: emp for emp in await Employee.filter(id__in=list(owner_ids))} if owner_ids else {}
    sent = 0
    for asset in rows:
        if asset.status == ASSET_STATUS_SCRAPPED:
            continue
        state = warranty_state(asset.warranty_until, current)
        if state not in ("expiring", "expired"):
            if getattr(asset, "warranty_notified_state", ""):
                asset.warranty_notified_state = ""
                await asset.save()
            continue
        if (asset.warranty_notified_state or "") == state:
            continue
        recipients: set[int] = set(admin_ids)
        owner = owners.get(asset.owner_emp_id)
        if owner and owner.user_id:
            recipients.add(owner.user_id)
        until = asset.warranty_until.strftime("%Y-%m-%d") if asset.warranty_until else ""
        title = "资产已过保" if state == "expired" else "资产即将过保"
        content = f"「{asset.asset_no} {asset.name}」质保到期 {until}"
        for user_id in recipients:
            await notify_user(
                user_id,
                title=title,
                content=content,
                ntype=TYPE_WARRANTY,
                route_kind="warranty",
            )
            sent += 1
        asset.warranty_notified_state = state
        await asset.save()
    return sent
