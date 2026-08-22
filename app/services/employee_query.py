from tortoise.expressions import Q


EMPLOYEE_SORT_FIELDS = {
    "created_at": "created_at",
    "emp_no": "emp_no",
    "name": "name",
    "hire_date": "hire_date",
}


def build_employee_filter(keyword: str = "", dept_id: int = 0, status: int = -1) -> Q:
    """构造员工列表与导出共用的筛选条件。"""
    query = Q()
    if keyword:
        query &= (
            Q(name__icontains=keyword)
            | Q(emp_no__icontains=keyword)
            | Q(phone__icontains=keyword)
        )
    if dept_id:
        query &= Q(dept_id=dept_id)
    if status in (0, 1):
        query &= Q(status=bool(status))
    return query


def resolve_employee_order(sort_by: str = "created_at", sort_order: str = "desc") -> str:
    """只允许预定义字段参与排序，非法输入回落到创建时间倒序。"""
    field = EMPLOYEE_SORT_FIELDS.get(sort_by)
    if field is None or sort_order not in {"asc", "desc"}:
        return "-created_at"
    return field if sort_order == "asc" else f"-{field}"
