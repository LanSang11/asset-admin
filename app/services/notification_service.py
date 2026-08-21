"""站内通知统一投递（ISO-A1/A3/A5）。

禁止业务代码直接 Notification.create；一律走本模块，保证：
- type 可审计可过滤
- route 按接收人 portal 映射 work/admin
- 受众由调用方显式传入（阶段投递在 asset_use 控制器编排）
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.models.admin import User
from app.models.business import Notification
from app.utils.identity import portal_for_user

# 通知类型（前端铃铛 / 自动化断言用）
TYPE_APPROVAL_TASK = "approval_task"  # 待审批任务（主管/超管）
TYPE_APPLICANT_PROGRESS = "applicant_progress"  # 申请人进度/结果
TYPE_WARRANTY = "warranty_alert"  # 质保即将到期 / 已过保

# 文案黑名单关键字（自动化与前端兜底）
APPROVAL_TASK_KEYWORDS = ("请审批", "新的审批申请", "待你审批", "待终审")


def route_for_recipient(portal: str, kind: str) -> str:
    """kind: approval | asset_use | repair | transfer | warranty"""
    if kind == "repair":
        return "/work/repair" if portal == "work" else "/business/repair"
    if kind == "transfer":
        return "/work/transfer" if portal == "work" else "/business/transfer"
    if kind == "warranty":
        return "/work/my-assets" if portal == "work" else "/business/asset"
    if portal == "work":
        return "/work/approval" if kind == "approval" else "/work/asset-use"
    return "/business/approval" if kind == "approval" else "/business/asset-use"


async def _recipient_portal(user_id: int) -> str:
    user = await User.get_or_none(id=user_id)
    if not user:
        return "work"
    role_objs = await user.roles
    role_names = [r.name for r in role_objs if getattr(r, "name", None)]
    return portal_for_user(user, role_names)


async def notify_user(
    user_id: Optional[int],
    *,
    title: str,
    content: str,
    ntype: str,
    route_kind: str,
) -> Optional[Notification]:
    """向单个用户写一条通知；user_id 空则跳过。"""
    if not user_id:
        return None
    portal = await _recipient_portal(user_id)
    route = route_for_recipient(portal, route_kind)
    return await Notification.create(
        user_id=user_id,
        title=title[:100],
        content=(content or "")[:500],
        route=route,
        type=ntype,
        is_read=False,
    )


async def notify_approver(
    user_id: Optional[int],
    *,
    applicant_name: str,
    action: str,
    asset_name: str,
    stage: str = "manager",
    route_kind: str = "approval",
) -> Optional[Notification]:
    """审批人待办。stage=manager|admin 仅影响文案。"""
    if stage == "admin":
        title = "待终审的审批申请"
        content = f"员工 {applicant_name} 申请{action}资产「{asset_name}」，请终审"
    else:
        title = "新的审批申请"
        content = f"员工 {applicant_name} 申请{action}资产「{asset_name}」，请审批"
    return await notify_user(
        user_id,
        title=title,
        content=content,
        ntype=TYPE_APPROVAL_TASK,
        route_kind=route_kind,
    )


async def notify_approvers(
    user_ids: Iterable[int],
    *,
    applicant_name: str,
    action: str,
    asset_name: str,
    stage: str = "manager",
    route_kind: str = "approval",
) -> int:
    n = 0
    seen = set()
    for uid in user_ids:
        if not uid or uid in seen:
            continue
        seen.add(uid)
        obj = await notify_approver(
            uid,
            applicant_name=applicant_name,
            action=action,
            asset_name=asset_name,
            stage=stage,
            route_kind=route_kind,
        )
        if obj:
            n += 1
    return n


async def notify_applicant(
    user_id: Optional[int],
    *,
    action: str,
    asset_name: str,
    msg: str,
    route_kind: str = "asset_use",
) -> Optional[Notification]:
    """申请人进度/结果。文案面向「你的申请」而非「你在审批别人」。"""
    # 进度句：避免「请审批」等待办语义
    title = f"你的{action}申请：{msg}"
    content = f"资产「{asset_name}」的{action}申请进度：{msg}"
    return await notify_user(
        user_id,
        title=title[:100],
        content=content[:500],
        ntype=TYPE_APPLICANT_PROGRESS,
        route_kind=route_kind,
    )


async def list_superuser_ids() -> list[int]:
    rows = await User.filter(is_superuser=True, is_active=True).values_list("id", flat=True)
    return list(rows)


def infer_type_from_legacy(title: str, content: str = "") -> str:
    """旧数据无 type 时按文案推断。"""
    text = f"{title or ''}{content or ''}"
    if any(k in text for k in APPROVAL_TASK_KEYWORDS):
        return TYPE_APPROVAL_TASK
    return TYPE_APPLICANT_PROGRESS
