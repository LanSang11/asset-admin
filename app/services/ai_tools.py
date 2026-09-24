"""Read-only whitelist tools. Scope is always recomputed from the current user."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

from app.core.ctx import CTX_USER_ID
from app.models.admin import User
from app.models.business import Asset, AssetUse, Employee
from app.services.ai_policy import (
    ALL_TOOL_NAMES,
    SECURITY_TOOLS,
    refuse_message,
    summarize_attack_facts,
)
from app.utils.identity import resolve_biz_role

PAGE_HELP = {
    "Workbench": "管理端首页。上半是资产运营；超级管理员另有安全态势，点数字会带同一筛选进入安全中心。",
    "统计看板": "按你的角色看公司 / 部门 / 个人资产口径。超管还可看安全态势。",
    "安全中心": "仅超管。登录日志保留明细；扫描/限流/黑名单/权限拒绝按分钟聚合。排除上海时未知地区会单独留下。",
    "资产管理": "登记、编辑资产，可填写质保到期日，可生成给手机扫的资产二维码。看板和工作台会提示即将过保或已过保。员工通常只看本人名下和可领用闲置。",
    "领用归还": "发起或查看领用、归还。审批按主管一级、管理员终审。",
    "审批中心": "处理待审申请。主管看本部门一级，管理员做终审。",
    "工作台": "员工/主管入口。没有系统管理菜单。",
    "AI 助手": "独立对话页用你自己的 Key 闲聊。全站右上角抽屉才是主入口：先只读查询，再用你配置的模型把事实说成人话，默认关闭深度思考。",
    "知识库": "上传白名单文档后提问。中文先走词面检索，有合格向量再叠加语义。回答会列出引用；没有合格 embedding 时页面会说明降级。",
    "报修": "查看和提交报修。可问助手查自己权限内的单据。",
    "调拨": "查看和提交调拨。可问助手查自己权限内的单据。",
    "盘点": "查看盘点进度。可问助手查自己权限内的单据。",
}

_STATUS = {1: "在用", 2: "闲置", 3: "维修", 4: "报废"}
_USE_TYPE = {1: "领用", 2: "归还"}
_REPAIR_STATUS = {1: "待主管", 2: "待管理员", 3: "维修中", 4: "已修复", 5: "已驳回"}
_TRANSFER_STATUS = {1: "待主管", 2: "待管理员", 3: "通过", 4: "驳回"}
_INVENTORY_STATUS = {1: "进行中", 2: "已结束"}
_PENDING_HINTS = ("待审", "待我", "待审批")


async def _context() -> Tuple[User, Optional[Employee], str]:
    user_id = CTX_USER_ID.get()
    user = await User.get(id=user_id)
    emp = await Employee.filter(user_id=user_id).first()
    role = await resolve_biz_role(user, emp)
    return user, emp, role


def _scope_name(role: str) -> str:
    return {"admin": "company", "manager": "department"}.get(role, "self")


def _ticket_scope(user_text: str) -> str:
    text = user_text or ""
    if any(token in text for token in _PENDING_HINTS):
        return "pending"
    return "all"


def _empty_ticket(title: str, empty_line: str) -> dict[str, Any]:
    return {"blocks": [{"title": title, "lines": [empty_line]}], "cards": [], "row_count": 0}


def _ticket_unavailable(title: str) -> dict[str, Any]:
    return {"blocks": [{"title": title, "lines": ["暂时查不到单据"]}], "cards": [], "row_count": 0}


_ASSET_STOPWORDS = frozenset(
    {
        "我",
        "有",
        "哪些",
        "什么",
        "多少",
        "查",
        "查询",
        "看看",
        "一下",
        "资产",
        "流转",
        "最近",
        "谁",
        "借了",
        "闲置",
        "在用",
        "权限",
        "范围",
        "当前",
        "匹配",
        "记录",
        "的",
        "台",
    }
)
_EMPLOYEE_STOPWORDS = frozenset(
    {
        "我",
        "有",
        "哪些",
        "什么",
        "查",
        "查询",
        "看看",
        "一下",
        "员工",
        "人员",
        "工号",
        "谁是",
        "查人",
        "通讯录",
        "的",
    }
)


def _search_keyword(user_text: str, stopwords: set[str] | frozenset[str]) -> str:
    """Strip spoken question words; leftover is the real search term (or empty)."""
    text = user_text or ""
    for mark in "，,？?。！!":
        text = text.replace(mark, " ")
    ordered = sorted((word for word in stopwords if word), key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for word in ordered:
            if word in text:
                text = text.replace(word, " ")
                changed = True
    leftover = " ".join(text.split())
    return leftover


async def run_tools(tool_names: list[str], *, user_text: str, page_context: dict[str, str]) -> dict[str, Any]:
    user, emp, role = await _context()
    allowed = [name for name in tool_names if name in ALL_TOOL_NAMES]
    if not user.is_superuser:
        allowed = [name for name in allowed if name not in SECURITY_TOOLS]
    blocks: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    used: list[str] = []
    row_count = 0
    for name in allowed:
        fn = TOOLS.get(name)
        if not fn:
            continue
        result = await fn(user=user, emp=emp, role=role, user_text=user_text, page_context=page_context)
        used.append(name)
        blocks.extend(result.get("blocks") or [])
        cards.extend(result.get("cards") or [])
        row_count += int(result.get("row_count") or 0)
    return {
        "scope": _scope_name(role),
        "tools": used,
        "blocks": blocks,
        "cards": cards,
        "row_count": row_count,
        "is_superuser": bool(user.is_superuser),
        "role": role,
    }


async def tool_page_help(**kwargs) -> dict[str, Any]:
    page_context = kwargs.get("page_context") or {}
    route_name = str(page_context.get("route_name") or "")
    help_text = PAGE_HELP.get(route_name)
    if not help_text:
        help_text = "这是已登录业务页。你可以问本页怎么用、自己权限范围内的资产或流转。安全数据只对超级管理员开放。"
    return {
        "blocks": [{"title": "本页怎么用", "lines": [help_text]}],
        "row_count": 1,
    }


async def tool_list_assets(*, user, emp, role, user_text, page_context) -> dict[str, Any]:
    from app.controllers.asset import asset_controller

    keyword = _search_keyword(user_text, _ASSET_STOPWORDS)
    entity_id = str(page_context.get("entity_id") or "")
    if page_context.get("entity_type") == "asset" and entity_id.isdigit():
        keyword = ""
    total, items = await asset_controller.list_assets(1, 8, keyword=keyword)
    if entity_id.isdigit() and page_context.get("entity_type") == "asset":
        one = await Asset.filter(id=int(entity_id)).first()
        if one and await asset_controller.can_view_asset(one, role, emp):
            items = [one]
            total = 1
    lines = []
    cards = []
    for index, asset in enumerate(items, start=1):
        data = await asset_controller.serialize_for_viewer(asset, role, emp)
        alias = f"A{index}"
        name = str(data.get("name") or "")
        no = str(data.get("asset_no") or "")
        status = _STATUS.get(int(data.get("status") or 0), "未知")
        extra = data.get("warranty_label") if data.get("warranty_state") in ("expiring", "expired") else ""
        lines.append(f"{alias} {no} {status}{(' ' + extra) if extra else ''}")
        cards.append({"alias": alias, "kind": "asset", "name": name, "asset_no": no})
    return {
        "blocks": [{"title": f"资产（{total}）", "lines": lines or ["当前范围没有匹配资产"]}],
        "cards": cards,
        "row_count": total,
    }


async def tool_list_asset_flow(*, user, emp, role, user_text, page_context) -> dict[str, Any]:
    from app.controllers.asset import asset_controller
    from app.controllers.asset_use import asset_use_controller

    asset_id = 0
    entity_id = str(page_context.get("entity_id") or "")
    if page_context.get("entity_type") == "asset" and entity_id.isdigit():
        asset_id = int(entity_id)
    if not asset_id:
        _, items = await asset_controller.list_assets(1, 1, keyword="")
        if items:
            asset_id = items[0].id
    if not asset_id:
        return {"blocks": [{"title": "流转", "lines": ["没有可查的资产流转"]}], "row_count": 0}
    asset = await Asset.filter(id=asset_id).first()
    if not asset or not await asset_controller.can_view_asset(asset, role, emp):
        return {"blocks": [{"title": "流转", "lines": ["无权查看该资产流转"]}], "row_count": 0}
    try:
        history = await asset_use_controller.get_history(asset_id)
    except Exception:
        history = []
    lines = []
    cards = []
    for index, row in enumerate(list(history)[:8], start=1):
        alias = f"P{index}"
        stamp = getattr(row, "use_time", None) or getattr(row, "created_at", None)
        when = stamp.strftime("%Y-%m-%d %H:%M") if stamp else ""
        action = _USE_TYPE.get(getattr(row, "use_type", 0), "流转")
        who = await Employee.filter(id=row.employee_id).first() if getattr(row, "employee_id", None) else None
        lines.append(f"{alias} {when} {action}")
        cards.append({"alias": alias, "kind": "person", "name": who.name if who else ""})
    if not lines:
        uses = await AssetUse.filter(asset_id=asset_id).order_by("-created_at").limit(8)
        for index, row in enumerate(uses, start=1):
            alias = f"P{index}"
            who = await Employee.filter(id=row.employee_id).first()
            name = who.name if who else ""
            when = row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else ""
            action = _USE_TYPE.get(row.use_type, "流转")
            lines.append(f"{alias} {when} {action}")
            cards.append({"alias": alias, "kind": "person", "name": name})
    return {
        "blocks": [{"title": f"流转 {asset.asset_no}", "lines": lines or ["暂无流转记录"]}],
        "cards": cards,
        "row_count": len(lines),
    }


async def tool_asset_stats(*, user, emp, role, **_kwargs) -> dict[str, Any]:
    from app.services.dashboard_service import dashboard_stats

    stats = await dashboard_stats(user_id=user.id)
    total = stats.get("total") or {}
    lines = [
        f"范围 {stats.get('scope')}",
        f"资产 {total.get('assets', 0)}",
        f"在用 {total.get('in_use', 0)}",
        f"闲置 {total.get('idle', 0)}",
    ]
    return {"blocks": [{"title": "业务统计", "lines": lines}], "row_count": 1}


async def _security_or_refuse(*, user, **_kwargs) -> dict[str, Any] | None:
    if not user.is_superuser:
        return {"blocks": [{"title": "安全", "lines": [refuse_message("refuse_scope")]}], "row_count": 0}
    return None


async def tool_security_summary(*, user, **kwargs) -> dict[str, Any]:
    denied = await _security_or_refuse(user=user)
    if denied:
        return denied
    from app.services.security_agg import build_security_posture

    posture = await build_security_posture(hours=24)
    facts = summarize_attack_facts(
        categories=posture.get("categories") or [],
        top_sources=posture.get("top_sources") or [],
        hourly=posture.get("hourly") or [],
    )
    lines = [f"{item['label']} {item['count']}" for item in posture.get("categories") or []]
    cards = [{"alias": alias, "kind": "ip", "ip": meta.get("ip")} for alias, meta in facts["aliases"].items()]
    return {
        "blocks": [{"title": "近 24 小时安全汇总", "lines": lines or ["暂无事件"]}],
        "cards": cards,
        "row_count": sum(facts["totals"].values()),
        "model_view": facts["model_view"],
    }


async def tool_security_topk(*, user, **kwargs) -> dict[str, Any]:
    denied = await _security_or_refuse(user=user)
    if denied:
        return denied
    from app.services.security_agg import build_security_posture

    posture = await build_security_posture(hours=24)
    facts = summarize_attack_facts(
        categories=posture.get("categories") or [],
        top_sources=posture.get("top_sources") or [],
        hourly=posture.get("hourly") or [],
    )
    lines = [f"{alias} {row['count']} 次" for alias, row in zip(facts["aliases"], facts["top"])]
    cards = [{"alias": alias, "kind": "ip", "ip": meta.get("ip")} for alias, meta in facts["aliases"].items()]
    return {
        "blocks": [{"title": "来源 Top", "lines": lines or ["暂无来源"]}],
        "cards": cards,
        "row_count": len(facts["top"]),
        "model_view": facts["model_view"],
    }


async def tool_search_kb(*, user_text, **kwargs) -> dict[str, Any]:
    from fastapi.exceptions import HTTPException

    from app.services import rag_service

    question = (user_text or "").strip()
    if not question:
        return {"blocks": [{"title": "知识库", "lines": ["请先说明要查的操作问题。"]}], "row_count": 0}
    try:
        rag_service.scan_secrets(question)
        hits, meta = await rag_service.retrieve(question)
    except HTTPException:
        return {"blocks": [{"title": "知识库", "lines": ["这个问题不能查知识库。"]}], "row_count": 0}
    lines: list[str] = []
    if meta.get("notice"):
        lines.append(str(meta["notice"]))
    cards = []
    for index, hit in enumerate(hits, start=1):
        snippet = hit.get("snippet") or ""
        title = hit.get("title") or "资料"
        lines.append(f"K{index} 《{title}》 {snippet}")
        cards.append({"alias": f"K{index}", "kind": "kb", "name": title, "snippet": snippet})
    if not hits:
        lines.append("知识库没有相关资料。可到知识库页导入操作说明后再问。")
    return {
        "blocks": [{"title": "知识库资料", "lines": lines}],
        "cards": cards,
        "row_count": len(hits),
    }


async def tool_lookup_employees(*, user, emp, role, user_text, **kwargs) -> dict[str, Any]:
    from app.controllers.employee import employee_controller

    keyword = _search_keyword(user_text, _EMPLOYEE_STOPWORDS)
    total, items = await employee_controller.list_employees(1, 8, keyword=keyword)
    lines = []
    for index, person in enumerate(items, start=1):
        data = await employee_controller.serialize_for_viewer(person, role, emp)
        lines.append(f"E{index} {data.get('emp_no') or ''} {data.get('name') or ''}")
    return {
        "blocks": [{"title": f"员工（{total}）", "lines": lines or ["当前范围没有匹配员工"]}],
        "row_count": total,
    }


async def tool_security_trend(*, user, **kwargs) -> dict[str, Any]:
    denied = await _security_or_refuse(user=user)
    if denied:
        return denied
    from app.services.security_agg import build_security_posture

    posture = await build_security_posture(hours=24)
    hourly = posture.get("hourly") or []
    peak = max(hourly, key=lambda item: int(item.get("total") or 0), default=None)
    lines = [f"近 24 小时共 {sum(int(item.get('total') or 0) for item in hourly)} 次"]
    if peak:
        lines.append(f"峰值 {peak.get('hour')} 共 {peak.get('total')} 次")
    return {"blocks": [{"title": "攻击趋势", "lines": lines}], "row_count": len(hourly)}


async def tool_suggest_filter(*, user, user_text, **kwargs) -> dict[str, Any]:
    denied = await _security_or_refuse(user=user)
    if denied:
        return denied
    end = datetime.now().replace(microsecond=0)
    start = end - timedelta(hours=24)
    suggested = {
        "tab": "login" if "登录" in (user_text or "") else "attacks",
        "start_time": start.isoformat(timespec="seconds"),
        "end_time": end.isoformat(timespec="seconds"),
    }
    if "失败" in (user_text or ""):
        suggested["event_type"] = "login_failure"
        suggested["success"] = False
        suggested["tab"] = "login"
    if "扫描" in (user_text or ""):
        suggested["event_type"] = "scan"
        suggested["tab"] = "attacks"
    if "上海" in (user_text or "") and any(token in (user_text or "") for token in ("不是", "排除", "之外")):
        suggested["exclude_region"] = "上海"
    return {
        "blocks": [{"title": "建议筛选", "lines": [f"{k}={v}" for k, v in suggested.items()]}],
        "row_count": 1,
        "cards": [{"alias": "F1", "kind": "filter", **suggested}],
    }


async def tool_list_repairs(*, user_text, **_kwargs) -> dict[str, Any]:
    from fastapi.exceptions import HTTPException

    from app.controllers.asset_repair import asset_repair_controller
    from app.models.business import Asset

    try:
        _total, items = await asset_repair_controller.list_repairs(1, 8, status=0, scope=_ticket_scope(user_text))
    except HTTPException:
        return _empty_ticket("报修", "当前范围没有报修单")
    except Exception:
        return _ticket_unavailable("报修")
    lines: list[str] = []
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(items, start=1):
        asset = await Asset.filter(id=row.asset_id).first()
        asset_no = str(asset.asset_no) if asset else ""
        status_label = _REPAIR_STATUS.get(int(row.status or 0), "未知")
        reason = str(row.reason or "")[:20]
        alias = f"R{index}"
        lines.append(f"{alias} {asset_no} {status_label} {reason}".strip())
        cards.append({"alias": alias, "kind": "repair", "asset_no": asset_no, "status_label": status_label})
    if not lines:
        return _empty_ticket("报修", "当前范围没有报修单")
    return {"blocks": [{"title": "报修", "lines": lines}], "cards": cards, "row_count": len(lines)}


async def tool_list_transfers(*, user_text, **_kwargs) -> dict[str, Any]:
    from fastapi.exceptions import HTTPException

    from app.controllers.asset_transfer import asset_transfer_controller
    from app.models.business import Asset, Employee

    try:
        _total, items = await asset_transfer_controller.list_transfers(1, 8, status=0, scope=_ticket_scope(user_text))
    except HTTPException:
        return _empty_ticket("调拨", "当前范围没有调拨单")
    except Exception:
        return _ticket_unavailable("调拨")
    lines: list[str] = []
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(items, start=1):
        asset = await Asset.filter(id=row.asset_id).first()
        from_emp = await Employee.filter(id=row.from_employee_id).first()
        to_emp = await Employee.filter(id=row.to_employee_id).first()
        asset_no = str(asset.asset_no) if asset else ""
        status_label = _TRANSFER_STATUS.get(int(row.status or 0), "未知")
        from_name = from_emp.name if from_emp else ""
        to_name = to_emp.name if to_emp else ""
        alias = f"T{index}"
        lines.append(f"{alias} {asset_no} {status_label} {from_name}→{to_name}")
        cards.append({"alias": alias, "kind": "transfer", "asset_no": asset_no, "status_label": status_label})
    if not lines:
        return _empty_ticket("调拨", "当前范围没有调拨单")
    return {"blocks": [{"title": "调拨", "lines": lines}], "cards": cards, "row_count": len(lines)}


async def tool_list_inventory(**_kwargs) -> dict[str, Any]:
    from fastapi.exceptions import HTTPException

    from app.controllers.inventory import inventory_controller

    try:
        _total, items = await inventory_controller.list_sessions(1, 3, status=1)
        if not items:
            _total, items = await inventory_controller.list_sessions(1, 3, status=0)
    except HTTPException:
        return _empty_ticket("盘点", "当前范围没有盘点任务")
    except Exception:
        return _ticket_unavailable("盘点")
    lines: list[str] = []
    cards: list[dict[str, Any]] = []
    for index, session in enumerate(items[:3], start=1):
        try:
            data = await inventory_controller.get(session.id)
        except HTTPException:
            continue
        except Exception:
            continue
        summary = data.get("summary") or {}
        title = str(data.get("title") or getattr(session, "title", "") or "")
        status_label = _INVENTORY_STATUS.get(int(data.get("status") or getattr(session, "status", 0) or 0), "未知")
        total_n = int(summary.get("total") or 0)
        pending = int(summary.get("pending") or 0)
        found = int(summary.get("found") or 0)
        missing = int(summary.get("missing") or 0)
        mismatch = int(summary.get("mismatch") or 0)
        lines.append(
            f"盘点《{title}》 {status_label} 共{total_n} 未盘{pending} 相符{found} 盘亏{missing} 不符{mismatch}"
        )
        cards.append({"alias": f"I{index}", "kind": "inventory", "name": title, "status_label": status_label})
    if not lines:
        return _empty_ticket("盘点", "当前范围没有盘点任务")
    return {"blocks": [{"title": "盘点", "lines": lines}], "cards": cards, "row_count": len(lines)}


TOOLS = {
    "page_help": tool_page_help,
    "list_assets": tool_list_assets,
    "list_asset_flow": tool_list_asset_flow,
    "asset_stats": tool_asset_stats,
    "security_summary": tool_security_summary,
    "security_topk": tool_security_topk,
    "security_trend": tool_security_trend,
    "suggest_filter": tool_suggest_filter,
    "lookup_employees": tool_lookup_employees,
    "search_kb": tool_search_kb,
    "list_repairs": tool_list_repairs,
    "list_transfers": tool_list_transfers,
    "list_inventory": tool_list_inventory,
}
