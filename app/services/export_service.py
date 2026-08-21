"""数据导出：员工/资产/领用记录 CSV（带 UTF-8 BOM，Excel 直接打开中文不乱码）。

CSV 用标准库实现（零依赖、跨平台）。后续如需 .xlsx 可加 openpyxl/xlsxwriter。
"""
import csv
import io
from typing import List

from fastapi.responses import StreamingResponse

from app.models.business import Asset, AssetUse, Employee

# CSV 公式注入防护：Excel 会执行以 = + - @ 开头的单元格
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# 导出行数上限（防全量导出内存/响应失控）
EXPORT_MAX_ROWS = 10000


def _sanitize_cell(value) -> str:
    """防止 CSV 公式注入（OWASP 建议：公式前缀前加单引号）"""
    s = str(value) if value is not None else ""
    if s.startswith(_FORMULA_PREFIXES):
        return "'" + s
    return s


def _csv_response(filename: str, headers: List[str], rows: List[list]) -> StreamingResponse:
    """生成带 UTF-8 BOM 的 CSV 流式响应（Excel 兼容）"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_sanitize_cell(c) for c in row])

    # BOM + UTF-8
    content = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def export_employees(keyword: str = "") -> StreamingResponse:
    from tortoise.expressions import Q
    q = Q()
    if keyword:
        q = Q(name__icontains=keyword) | Q(emp_no__icontains=keyword)
    # 修复：导出上限保护（原全量查询，数据量大时内存/响应失控）
    emps = await Employee.filter(q).order_by("emp_no").limit(EXPORT_MAX_ROWS)
    headers = ["工号", "姓名", "性别", "部门ID", "职位", "入职日期", "手机", "邮箱", "是否主管", "状态"]
    rows = []
    for e in emps:
        rows.append([
            e.emp_no, e.name,
            "男" if e.gender == 1 else ("女" if e.gender == 2 else "未知"),
            e.dept_id or "", e.position,
            e.hire_date.strftime("%Y-%m-%d") if e.hire_date else "",
            e.phone, e.email,
            "是" if e.is_manager else "否",
            "在职" if e.status else "离职",
        ])
    return _csv_response("employees.csv", headers, rows)


async def export_assets(keyword: str = "", category: str = "", status: int = 0) -> StreamingResponse:
    from tortoise.expressions import Q
    q = Q()
    if keyword:
        # 修复：加括号（& 优先级高于 |，原写法导致 category/status 导出筛选失效）
        q &= (
            Q(name__icontains=keyword)
            | Q(asset_no__icontains=keyword)
            | Q(serial_no__icontains=keyword)
        )
    if category:
        q &= Q(category=category)
    if status:
        q &= Q(status=status)
    # 修复：导出上限保护
    assets = await Asset.filter(q).order_by("asset_no").limit(EXPORT_MAX_ROWS)
    headers = ["资产编号", "名称", "分类", "型号", "序列号", "采购日期", "质保到期", "价格(元)", "状态", "存放位置", "领用人ID", "备注"]
    status_map = {1: "在用", 2: "闲置", 3: "维修", 4: "报废"}
    rows = []
    for a in assets:
        rows.append([
            a.asset_no, a.name, a.category, a.model, a.serial_no,
            a.purchase_date.strftime("%Y-%m-%d") if a.purchase_date else "",
            a.warranty_until.strftime("%Y-%m-%d") if a.warranty_until else "",
            str(a.price) if a.price is not None else "",
            status_map.get(a.status, a.status),
            a.location, a.owner_emp_id or "", a.remark,
        ])
    return _csv_response("assets.csv", headers, rows)


async def export_asset_uses(status: int = 0, use_type: int = 0) -> StreamingResponse:
    from tortoise.expressions import Q
    q = Q()
    if status:
        q &= Q(status=status)
    if use_type:
        q &= Q(use_type=use_type)
    # 修复：导出上限保护 + 批量预取（原每行两次查询的 N+1）
    uses = await AssetUse.filter(q).order_by("-created_at").limit(EXPORT_MAX_ROWS)
    asset_ids = {u.asset_id for u in uses}
    emp_ids = {u.employee_id for u in uses}
    assets = {a.id: a for a in await Asset.filter(id__in=list(asset_ids))}
    emps = {e.id: e for e in await Employee.filter(id__in=list(emp_ids))}
    headers = ["资产编号", "资产名称", "类型", "申请人", "状态", "申请时间", "主管意见", "管理员意见", "归还时间"]
    status_map = {1: "待主管审批", 2: "待管理员审批", 3: "已通过", 4: "已驳回"}
    rows = []
    for u in uses:
        asset = assets.get(u.asset_id)
        emp = emps.get(u.employee_id)
        rows.append([
            asset.asset_no if asset else "", asset.name if asset else "",
            "领用" if u.use_type == 1 else "归还",
            emp.name if emp else "",
            status_map.get(u.status, u.status),
            u.apply_time.strftime("%Y-%m-%d %H:%M:%S") if u.apply_time else "",
            u.manager_comment, u.admin_comment,
            u.return_time.strftime("%Y-%m-%d %H:%M:%S") if u.return_time else "",
        ])
    return _csv_response("asset_uses.csv", headers, rows)
