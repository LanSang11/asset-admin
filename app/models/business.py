"""业务模型：员工/资产/领用归还/历史追溯/通知（阶段2 企业资产管理系统）"""
from tortoise import fields

from .base import BaseModel, TimestampMixin


class Employee(BaseModel, TimestampMixin):
    """员工表（与 user 账号 1:1 绑定，一人一号）"""
    emp_no = fields.CharField(max_length=20, unique=True, description="工号", index=True)
    name = fields.CharField(max_length=50, description="姓名", index=True)
    gender = fields.IntField(default=0, description="性别：0未知 1男 2女")
    dept_id = fields.IntField(null=True, description="部门ID（关联 dept.id）", index=True)
    position = fields.CharField(max_length=100, default="", description="职位")
    hire_date = fields.DateField(null=True, description="入职日期")
    phone = fields.CharField(max_length=20, default="", description="手机")
    email = fields.CharField(max_length=100, default="", description="邮箱")
    user_id = fields.IntField(null=True, unique=True, description="绑定登录账号ID（user.id）", index=True)
    is_manager = fields.BooleanField(default=False, description="是否部门主管（审批用）", index=True)
    status = fields.BooleanField(default=True, description="1在职 0离职", index=True)

    async def to_dict(self, m2m: bool = False, exclude_fields: list[str] | None = None):
        d = await super().to_dict(m2m=m2m, exclude_fields=exclude_fields)
        # date 类型转字符串，保证 JSON 可序列化
        if d.get("hire_date") and not isinstance(d["hire_date"], str):
            d["hire_date"] = d["hire_date"].strftime("%Y-%m-%d")
        return d

    class Meta:
        table = "employees"


class Asset(BaseModel, TimestampMixin):
    """公司资产表"""
    asset_no = fields.CharField(max_length=50, unique=True, description="资产编号", index=True)
    name = fields.CharField(max_length=100, description="资产名称", index=True)
    category = fields.CharField(max_length=50, default="其他", description="分类：电脑/办公设备/办公用品/其他", index=True)
    model = fields.CharField(max_length=100, default="", description="型号")
    serial_no = fields.CharField(max_length=100, default="", description="序列号")
    purchase_date = fields.DateField(null=True, description="采购日期")
    warranty_until = fields.DateField(null=True, description="质保到期日")
    warranty_notified_state = fields.CharField(
        max_length=20, default="", description="已提醒档：空/expiring/expired"
    )
    price = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="采购价格（元）")
    # 1在用 2闲置 3维修 4报废（领用后自动置在用，归还后置闲置）
    status = fields.IntField(default=2, description="状态：1在用 2闲置 3维修 4报废", index=True)
    location = fields.CharField(max_length=100, default="", description="存放位置")
    owner_emp_id = fields.IntField(null=True, description="当前领用人（employees.id）", index=True)
    remark = fields.CharField(max_length=255, default="", description="备注")

    async def to_dict(self, m2m: bool = False, exclude_fields: list[str] | None = None):
        blocked = list(exclude_fields or [])
        if "warranty_notified_state" not in blocked:
            blocked.append("warranty_notified_state")
        d = await super().to_dict(m2m=m2m, exclude_fields=blocked)
        if d.get("purchase_date") and not isinstance(d["purchase_date"], str):
            d["purchase_date"] = d["purchase_date"].strftime("%Y-%m-%d")
        if d.get("warranty_until") and not isinstance(d["warranty_until"], str):
            d["warranty_until"] = d["warranty_until"].strftime("%Y-%m-%d")
        if d.get("price") is not None:
            # 修复：format(f) 禁用科学计数法（SQLite REAL 读出 Decimal('5E+3') → 显示 5E+3）
            d["price"] = format(d["price"], "f")
        return d

    class Meta:
        table = "assets"


class AssetUse(BaseModel, TimestampMixin):
    """领用/归还申请记录（两级审批流程）"""
    asset_id = fields.IntField(description="资产ID", index=True)
    employee_id = fields.IntField(description="员工ID（申请人）", index=True)
    use_type = fields.IntField(description="1领用 2归还", index=True)
    apply_time = fields.DatetimeField(auto_now_add=True, description="申请时间", index=True)
    # 1待主管审批 2待管理员审批 3通过 4驳回
    status = fields.IntField(default=1, description="状态：1待主管 2待管理员 3通过 4驳回", index=True)
    manager_approver_id = fields.IntField(null=True, description="主管审批人（user.id）")
    admin_approver_id = fields.IntField(null=True, description="管理员审批人（user.id）")
    manager_comment = fields.CharField(max_length=255, default="", description="主管审批意见")
    admin_comment = fields.CharField(max_length=255, default="", description="管理员审批意见")
    manager_time = fields.DatetimeField(null=True, description="主管审批时间")
    admin_time = fields.DatetimeField(null=True, description="管理员审批时间")
    return_time = fields.DatetimeField(null=True, description="归还完成时间（归还流程通过时写入）")

    class Meta:
        table = "asset_uses"


class AssetUseHistory(BaseModel, TimestampMixin):
    """资产使用历史（每台资产完整生命周期追溯）"""
    asset_id = fields.IntField(description="资产ID", index=True)
    employee_id = fields.IntField(description="员工ID", index=True)
    use_type = fields.IntField(description="1领用 2归还", index=True)
    use_time = fields.DatetimeField(auto_now_add=True, description="发生时间", index=True)
    operator_id = fields.IntField(null=True, description="操作人（审批通过的管理员 user.id）")
    remark = fields.CharField(max_length=255, default="", description="备注")

    class Meta:
        table = "asset_use_history"


class AssetRepair(BaseModel, TimestampMixin):
    """资产报修单（独立于领用，避免污染 use_type）。

    status: 1待主管 2待管理员 3维修中 4已修复 5已驳回
    """

    asset_id = fields.IntField(description="资产ID", index=True)
    employee_id = fields.IntField(description="报修人（employees.id）", index=True)
    reason = fields.CharField(max_length=255, default="", description="故障说明")
    status = fields.IntField(default=1, description="状态", index=True)
    manager_approver_id = fields.IntField(null=True, description="主管审批人 user.id")
    admin_approver_id = fields.IntField(null=True, description="管理员审批人 user.id")
    manager_comment = fields.CharField(max_length=255, default="", description="主管意见")
    admin_comment = fields.CharField(max_length=255, default="", description="管理员意见")
    manager_time = fields.DatetimeField(null=True, description="主管审批时间")
    admin_time = fields.DatetimeField(null=True, description="管理员审批时间")
    complete_time = fields.DatetimeField(null=True, description="修好时间")
    complete_result = fields.CharField(max_length=20, default="", description="in_use|idle")

    class Meta:
        table = "asset_repairs"


class AssetTransfer(BaseModel, TimestampMixin):
    """在用资产调拨单（独立于领用，避免污染 use_type）。

    status: 1待主管 2待管理员 3通过 4驳回
    通过后资产保持在用，只改 owner_emp_id。
    """

    asset_id = fields.IntField(description="资产ID", index=True)
    from_employee_id = fields.IntField(description="调出人 employees.id", index=True)
    to_employee_id = fields.IntField(description="调入人 employees.id", index=True)
    applicant_id = fields.IntField(description="申请人 employees.id", index=True)
    reason = fields.CharField(max_length=255, default="", description="调拨说明")
    status = fields.IntField(default=1, description="状态", index=True)
    manager_approver_id = fields.IntField(null=True, description="主管审批人 user.id")
    admin_approver_id = fields.IntField(null=True, description="管理员审批人 user.id")
    manager_comment = fields.CharField(max_length=255, default="", description="主管意见")
    admin_comment = fields.CharField(max_length=255, default="", description="管理员意见")
    manager_time = fields.DatetimeField(null=True, description="主管审批时间")
    admin_time = fields.DatetimeField(null=True, description="管理员审批时间")

    class Meta:
        table = "asset_transfers"


class Notification(BaseModel, TimestampMixin):
    """站内通知（审批相关铃铛提醒）"""
    user_id = fields.IntField(description="接收人（user.id）", index=True)
    title = fields.CharField(max_length=100, description="标题")
    content = fields.CharField(max_length=500, default="", description="内容")
    # 点击通知跳转的前端路由（如 /business/approval、/work/approval）
    route = fields.CharField(max_length=200, default="", description="跳转路由")
    # ISO-A1：受众类型 approval_task | applicant_progress（空=历史数据，读侧可推断）
    type = fields.CharField(max_length=40, default="", description="通知类型", index=True)
    is_read = fields.BooleanField(default=False, description="是否已读", index=True)

    class Meta:
        table = "notifications"


class EmployeeAttachment(BaseModel, TimestampMixin):
    """员工附件。磁盘文件在 uploads/employee/，下载只走鉴权接口。"""

    employee_id = fields.IntField(index=True)
    original_name = fields.CharField(max_length=200)
    stored_name = fields.CharField(max_length=80)
    mime = fields.CharField(max_length=80, default="")
    size = fields.IntField(default=0)
    uploader_id = fields.IntField(null=True)

    class Meta:
        table = "employee_attachments"


class InventorySession(BaseModel, TimestampMixin):
    """资产盘点任务。status: 1进行中 2已结束。盘亏只记结果，不自动报废。"""

    title = fields.CharField(max_length=100, description="盘点名称")
    scope = fields.CharField(max_length=16, default="all", description="all/dept")
    dept_id = fields.IntField(null=True, description="部门范围")
    status = fields.IntField(default=1, description="1进行中 2已结束", index=True)
    created_by = fields.IntField(description="发起人 user.id")
    closed_by = fields.IntField(null=True, description="结束人 user.id")
    closed_at = fields.DatetimeField(null=True)
    note = fields.CharField(max_length=255, default="", description="备注")

    class Meta:
        table = "inventory_sessions"


class InventoryLine(BaseModel, TimestampMixin):
    """盘点行：账面快照 + 实盘结果。result 空=未盘 found=相符 missing=盘亏 mismatch=不符。"""

    session_id = fields.IntField(index=True)
    asset_id = fields.IntField(index=True)
    asset_no = fields.CharField(max_length=50)
    asset_name = fields.CharField(max_length=100)
    book_status = fields.IntField()
    book_owner_emp_id = fields.IntField(null=True)
    book_owner_name = fields.CharField(max_length=50, default="")
    book_dept_id = fields.IntField(null=True)
    result = fields.CharField(max_length=16, default="", index=True)
    counted_status = fields.IntField(null=True)
    note = fields.CharField(max_length=255, default="")
    counted_by = fields.IntField(null=True)
    counted_at = fields.DatetimeField(null=True)

    class Meta:
        table = "inventory_lines"
