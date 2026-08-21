"""统计看板：按业务角色缩圈（ISO-B3）。

- admin：全公司看板
- manager：本部门口径 + 待审数（本部门一级）
- employee：个人摘要 + 闲置列表摘要；无全员排行/全公司待审
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.models.admin import Dept, User
from app.models.business import Asset, AssetUse, Employee
from app.services.warranty import emit_warranty_alerts, summarize_warranty
from app.utils.identity import resolve_biz_role


async def dashboard_stats(user_id: Optional[int] = None) -> Dict[str, Any]:
    """看板核心数据。传入 user_id 时按角色裁剪。"""
    role = "admin"
    me: Optional[Employee] = None
    if user_id is not None:
        user = await User.get(id=user_id)
        me = await Employee.filter(user_id=user_id).first()
        role = await resolve_biz_role(user, me)

    if role == "employee":
        return await _employee_dashboard(me)
    if role == "manager":
        return await _manager_dashboard(me)
    return await _admin_dashboard()


async def _admin_dashboard() -> Dict[str, Any]:
    assets = await Asset.all()
    emps = await Employee.filter(status=True)

    category_counter = Counter(a.category or "其他" for a in assets)
    category_stats = [{"name": k, "value": v} for k, v in category_counter.items()]

    status_counter = Counter(a.status for a in assets)
    status_map = {1: "在用", 2: "闲置", 3: "维修", 4: "报废"}
    status_stats = [{"name": status_map.get(k, str(k)), "value": v} for k, v in status_counter.items()]

    dept_counter = Counter()
    owner_ids = {a.owner_emp_id for a in assets if a.owner_emp_id}
    owner_emps = {e.id: e for e in await Employee.filter(id__in=list(owner_ids))} if owner_ids else {}
    for a in assets:
        if a.owner_emp_id:
            emp = owner_emps.get(a.owner_emp_id)
            if emp and emp.dept_id:
                dept_counter[emp.dept_id] += 1
    dept_ids = set(dept_counter)
    depts = {d.id: d for d in await Dept.filter(id__in=list(dept_ids))} if dept_ids else {}
    dept_stats = [{"name": depts[k].name if k in depts else f"部门{k}", "value": v} for k, v in dept_counter.items()]

    trend = await _trend_last_7_days()
    idle_list = await _idle_list()
    ranking = await _owner_ranking(assets)

    pending_manager = await AssetUse.filter(status=1).count()
    pending_admin = await AssetUse.filter(status=2).count()
    warranty = summarize_warranty(assets)
    await emit_warranty_alerts(assets)

    return {
        "scope": "company",
        "category_stats": category_stats,
        "status_stats": status_stats,
        "dept_stats": dept_stats,
        "trend": trend,
        "idle_list": idle_list,
        "ranking": ranking,
        "pending": {"manager": pending_manager, "admin": pending_admin, "total": pending_manager + pending_admin},
        "total": {
            "assets": len(assets),
            "employees": len(emps),
            "in_use": status_counter.get(1, 0),
            "idle": status_counter.get(2, 0),
        },
        "warranty": warranty,
    }


async def _manager_dashboard(me: Optional[Employee]) -> Dict[str, Any]:
    if not me or not me.dept_id:
        return await _employee_dashboard(me)

    dept_emp_ids = list(await Employee.filter(dept_id=me.dept_id, status=True).values_list("id", flat=True))
    assets_owned = await Asset.filter(owner_emp_id__in=dept_emp_ids) if dept_emp_ids else []
    idle_assets = await Asset.filter(status=2)
    # 部门视图：在用按本部门 + 全司闲置数（领用相关）
    status_counter = Counter(a.status for a in assets_owned)
    status_counter[2] = len(idle_assets)
    status_map = {1: "在用", 2: "闲置", 3: "维修", 4: "报废"}
    status_stats = [{"name": status_map.get(k, str(k)), "value": v} for k, v in status_counter.items()]

    category_counter = Counter(a.category or "其他" for a in assets_owned)
    category_stats = [{"name": k, "value": v} for k, v in category_counter.items()]

    trend = await _trend_last_7_days(employee_ids=dept_emp_ids)
    idle_list = await _idle_list()
    ranking = await _owner_ranking(assets_owned, limit=5)

    pending_manager = await AssetUse.filter(status=1, employee_id__in=dept_emp_ids).count() if dept_emp_ids else 0
    pending_admin = 0  # 终审不归部门主管
    visible = list(assets_owned) + list(idle_assets)
    warranty = summarize_warranty(visible)
    await emit_warranty_alerts(visible)

    return {
        "scope": "department",
        "category_stats": category_stats,
        "status_stats": status_stats,
        "dept_stats": [],  # 非全司部门对比
        "trend": trend,
        "idle_list": idle_list,
        "ranking": ranking,
        "pending": {"manager": pending_manager, "admin": pending_admin, "total": pending_manager},
        "total": {
            "assets": len(assets_owned) + len(idle_assets),
            "employees": len(dept_emp_ids),
            "in_use": status_counter.get(1, 0),
            "idle": len(idle_assets),
            "my_assets": await Asset.filter(owner_emp_id=me.id, status=1).count(),
        },
        "warranty": warranty,
    }


async def _employee_dashboard(me: Optional[Employee]) -> Dict[str, Any]:
    my_assets = []
    if me:
        my_assets = await Asset.filter(owner_emp_id=me.id)
    status_counter = Counter(a.status for a in my_assets)
    idle_list = await _idle_list(limit=5)
    # 个人进度：仅本人在途申请数
    my_pending = 0
    if me:
        my_pending = await AssetUse.filter(employee_id=me.id, status__in=[1, 2]).count()
    warranty = summarize_warranty(my_assets)
    await emit_warranty_alerts(my_assets)

    return {
        "scope": "self",
        "category_stats": [],
        "status_stats": [
            {"name": "我的在用", "value": status_counter.get(1, 0)},
            {"name": "可领用闲置(摘要)", "value": len(idle_list)},
        ],
        "dept_stats": [],
        "trend": [],
        "idle_list": idle_list,
        "ranking": [],  # 禁止全员排行
        "pending": {"manager": 0, "admin": 0, "total": 0, "my_applications": my_pending},
        "total": {
            "assets": len(my_assets),
            "employees": 1 if me else 0,
            "in_use": status_counter.get(1, 0),
            "idle": len(idle_list),
            "my_assets": status_counter.get(1, 0),
        },
        "warranty": warranty,
    }


async def _trend_last_7_days(employee_ids: Optional[list] = None):
    trend = []
    today = datetime.now().date()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        base_t = AssetUse.filter(use_type=1, status=3, apply_time__gte=day_start, apply_time__lt=day_end)
        base_r = AssetUse.filter(use_type=2, status=3, apply_time__gte=day_start, apply_time__lt=day_end)
        if employee_ids is not None:
            base_t = base_t.filter(employee_id__in=employee_ids)
            base_r = base_r.filter(employee_id__in=employee_ids)
        takes = await base_t.count()
        returns = await base_r.count()
        trend.append({"date": day.strftime("%m-%d"), "领用": takes, "归还": returns})
    return trend


async def _idle_list(limit: int = 10):
    pending_asset_ids = await AssetUse.filter(status__in=[1, 2]).values_list("asset_id", flat=True)
    idle_assets = (
        await Asset.filter(status=2)
        .exclude(id__in=list(pending_asset_ids))
        .order_by("-created_at")
        .limit(limit)
    )
    # 摘要字段：无价格/序列号
    return [
        {"asset_no": a.asset_no, "name": a.name, "category": a.category, "location": a.location}
        for a in idle_assets
    ]


async def _owner_ranking(assets, limit: int = 10):
    owner_counter = Counter(a.owner_emp_id for a in assets if a.owner_emp_id)
    top_owner_ids = [eid for eid, _ in owner_counter.most_common(limit)]
    emp_map = {e.id: e for e in await Employee.filter(id__in=top_owner_ids)} if top_owner_ids else {}
    return [
        {"name": emp_map[eid].name if eid in emp_map else f"员工{eid}", "count": cnt}
        for eid, cnt in owner_counter.most_common(limit)
    ]
