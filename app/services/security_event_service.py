"""安全事件写入与日志保留清理（审计 + 安全事件，防日志打满盘）。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from app.log import logger
from app.models.admin import AuditLog, SecurityAggBucket, SecurityEvent
from app.settings.config import settings
from app.utils.geoip import format_location, lookup_ip
from app.utils.security_risk import compute_risk_tags, join_tags, parse_tags


async def _device_profile_tags(
    *,
    user_id: Optional[int],
    username: str,
    device_hash: str,
) -> list[str]:
    tags: list[str] = []
    dh = (device_hash or "").strip()
    if not dh:
        return tags
    try:
        if user_id is not None:
            seen = await SecurityEvent.filter(user_id=user_id, device_hash=dh).limit(1).exists()
            if not seen:
                tags.append("new_device")
            others = (
                await SecurityEvent.filter(device_hash=dh, user_id__not_isnull=True)
                .exclude(user_id=user_id)
                .limit(1)
                .exists()
            )
            if others:
                tags.append("shared_device")
        elif username:
            seen = await SecurityEvent.filter(username=username, device_hash=dh).limit(1).exists()
            if not seen:
                tags.append("new_device")
            others = (
                await SecurityEvent.filter(device_hash=dh)
                .exclude(username=username)
                .exclude(username="")
                .limit(1)
                .exists()
            )
            if others:
                tags.append("shared_device")
    except Exception as e:
        logger.warning(f"device profile tags skipped: {e!r}")
    return tags


def enrich_event_dict(row: dict[str, Any]) -> dict[str, Any]:
    """列表展示：旧行缺地理时用离线库现查，不回写。"""
    if not row.get("country") and row.get("ip"):
        geo = lookup_ip(str(row.get("ip") or ""))
        row["country"] = geo.get("country") or ""
        row["region"] = geo.get("region") or ""
        if not row.get("isp"):
            row["isp"] = geo.get("isp") or ""
        if not row.get("risk_tags"):
            row["risk_tags"] = join_tags(
                compute_risk_tags(
                    ip=str(row.get("ip") or ""),
                    country=row["country"],
                    region=row["region"],
                    isp=row["isp"],
                )
            )
    row["location"] = format_location(str(row.get("country") or ""), str(row.get("region") or ""))
    row["risk_tag_list"] = parse_tags(row.get("risk_tags") or "")
    return row


async def log_security_event(
    *,
    event_type: str,
    username: str = "",
    user_id: Optional[int] = None,
    ip: str = "",
    user_agent: str = "",
    device_hash: str = "",
    detail: str = "",
    success: bool = True,
    timezone: str = "",
    extra_tags: Optional[Iterable[str]] = None,
) -> None:
    """写安全事件；失败不影响主流程。只标记风险，绝不在此封禁。"""
    try:
        geo = lookup_ip(ip or "")
        device_tags = await _device_profile_tags(
            user_id=user_id, username=username or "", device_hash=device_hash or ""
        )
        tags = compute_risk_tags(
            ip=ip or "",
            country=geo.get("country") or "",
            region=geo.get("region") or "",
            isp=geo.get("isp") or "",
            timezone=timezone or "",
            extra=list(device_tags) + list(extra_tags or []),
        )
        await SecurityEvent.create(
            event_type=(event_type or "unknown")[:40],
            username=(username or "")[:64],
            user_id=user_id,
            ip=(ip or "")[:64],
            user_agent=(user_agent or "")[:512],
            device_hash=(device_hash or "")[:32],
            country=(geo.get("country") or "")[:64],
            region=(geo.get("region") or "")[:64],
            isp=(geo.get("isp") or "")[:128],
            risk_tags=join_tags(tags),
            detail=(detail or "")[:500],
            success=bool(success),
        )
    except Exception as e:
        logger.warning(f"security event write failed: {e!r}")


async def cleanup_logs() -> dict[str, Any]:
    """按天数 + 最大行数清理审计与安全事件。"""
    result = {
        "audit_by_days": 0,
        "audit_by_rows": 0,
        "sec_by_days": 0,
        "sec_by_rows": 0,
        "agg_by_days": 0,
        "agg_by_rows": 0,
    }
    try:
        audit_days = int(getattr(settings, "AUDIT_RETENTION_DAYS", 30))
        audit_max = int(getattr(settings, "AUDIT_MAX_ROWS", 100_000))
        sec_days = int(getattr(settings, "SECURITY_EVENT_RETENTION_DAYS", 30))
        sec_max = int(getattr(settings, "SECURITY_EVENT_MAX_ROWS", 50_000))

        if audit_days > 0:
            cutoff = datetime.now() - timedelta(days=audit_days)
            result["audit_by_days"] = await AuditLog.filter(created_at__lt=cutoff).delete()
        if sec_days > 0:
            cutoff = datetime.now() - timedelta(days=sec_days)
            result["sec_by_days"] = await SecurityEvent.filter(created_at__lt=cutoff).delete()

        # 行数上限：保留最新 N 条，删更旧的
        if audit_max > 0:
            total = await AuditLog.all().count()
            if total > audit_max:
                overflow = total - audit_max
                oldest_rows = await AuditLog.all().order_by("created_at").limit(overflow).values("id")
                ids = [r["id"] for r in oldest_rows]
                if ids:
                    result["audit_by_rows"] = await AuditLog.filter(id__in=ids).delete()
        if sec_max > 0:
            total = await SecurityEvent.all().count()
            if total > sec_max:
                overflow = total - sec_max
                oldest_rows = await SecurityEvent.all().order_by("created_at").limit(overflow).values("id")
                ids = [r["id"] for r in oldest_rows]
                if ids:
                    result["sec_by_rows"] = await SecurityEvent.filter(id__in=ids).delete()

        agg_days = int(getattr(settings, "SECURITY_AGG_RETENTION_DAYS", 180))
        agg_max = int(getattr(settings, "SECURITY_AGG_MAX_ROWS", 200_000))
        if agg_days > 0:
            cutoff = datetime.now() - timedelta(days=agg_days)
            result["agg_by_days"] = await SecurityAggBucket.filter(bucket_minute__lt=cutoff).delete()
        if agg_max > 0:
            total = await SecurityAggBucket.all().count()
            if total > agg_max:
                overflow = total - agg_max
                oldest_rows = (
                    await SecurityAggBucket.all().order_by("bucket_minute").limit(overflow).values("id")
                )
                ids = [r["id"] for r in oldest_rows]
                if ids:
                    result["agg_by_rows"] = await SecurityAggBucket.filter(id__in=ids).delete()
    except Exception as e:
        logger.warning(f"cleanup_logs failed: {e!r}")
    return result
