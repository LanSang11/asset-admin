from tortoise import fields

from app.schemas.menus import MenuType

from .base import BaseModel, TimestampMixin
from .enums import MethodType


class User(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=20, unique=True, description="用户名称", index=True)
    alias = fields.CharField(max_length=30, null=True, description="姓名", index=True)
    email = fields.CharField(max_length=255, unique=True, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, null=True, description="电话", index=True)
    password = fields.CharField(max_length=128, null=True, description="密码")
    must_change_password = fields.BooleanField(default=True, description="首次登录是否必须修改密码", index=True)
    password_changed_at = fields.DatetimeField(null=True, description="最近一次成功改密时间")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    is_superuser = fields.BooleanField(default=False, description="是否为超级管理员", index=True)
    last_login = fields.DatetimeField(null=True, description="最后登录时间", index=True)
    # 零成本 2FA：TOTP 密钥（Base32）与启用标记；仅本人/绑定流程读写
    totp_secret = fields.CharField(max_length=64, null=True, description="TOTP密钥Base32")
    totp_enabled = fields.BooleanField(default=False, description="是否启用TOTP二次验证", index=True)
    recovery_question = fields.CharField(max_length=120, null=True, description="TOTP恢复问题")
    recovery_answer_hash = fields.CharField(max_length=255, null=True, description="TOTP恢复答案哈希")
    recovery_fail_count = fields.IntField(default=0, description="TOTP恢复连续失败次数")
    recovery_locked_until = fields.DatetimeField(null=True, description="TOTP恢复锁定截止时间")
    # 改密/重置时递增；JWT 带同一计数，旧令牌立即失效。缺列/旧 token 按 0。
    auth_version = fields.IntField(default=0, description="认证版本，递增后旧JWT失效")
    # 四层架构第二层：用户自己的大模型 API 配置（加密存储，JSON: {provider, api_key_enc, model, base_url}）
    api_config = fields.JSONField(null=True, description="大模型API配置（加密）")
    roles = fields.ManyToManyField("models.Role", related_name="user_roles")
    dept_id = fields.IntField(null=True, description="部门ID", index=True)

    class Meta:
        table = "user"


class VerificationPolicy(BaseModel, TimestampMixin):
    operation_key = fields.CharField(max_length=64, unique=True, description="高危操作键", index=True)
    label = fields.CharField(max_length=80, description="高危操作名称")
    mode = fields.CharField(max_length=16, default="off", description="off/password/totp")

    class Meta:
        table = "verification_policy"


class VerificationSettings(BaseModel, TimestampMixin):
    force_superuser = fields.BooleanField(default=True, description="超级管理员登录强制TOTP")
    role_ids = fields.JSONField(default=list, description="登录强制TOTP角色ID")
    acceptance_until = fields.DatetimeField(null=True, description="登录TOTP验收模式截止时间UTC")
    password_max_days = fields.IntField(default=0, description="密码最长天数，0表示关闭周期换密")
    password_deadline = fields.DatetimeField(null=True, description="全员换密截止日期UTC，空表示关闭")

    class Meta:
        table = "verification_settings"


class Role(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="角色名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="角色描述")
    menus = fields.ManyToManyField("models.Menu", related_name="role_menus")
    apis = fields.ManyToManyField("models.Api", related_name="role_apis")

    class Meta:
        table = "role"


class Api(BaseModel, TimestampMixin):
    path = fields.CharField(max_length=100, description="API路径", index=True)
    method = fields.CharEnumField(MethodType, description="请求方法", index=True)
    summary = fields.CharField(max_length=500, description="请求简介", index=True)
    tags = fields.CharField(max_length=100, description="API标签", index=True)

    class Meta:
        table = "api"


class Menu(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, description="菜单名称", index=True)
    remark = fields.JSONField(null=True, description="保留字段")
    menu_type = fields.CharEnumField(MenuType, null=True, description="菜单类型")
    icon = fields.CharField(max_length=100, null=True, description="菜单图标")
    path = fields.CharField(max_length=100, description="菜单路径", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, description="父菜单ID", index=True)
    is_hidden = fields.BooleanField(default=False, description="是否隐藏")
    component = fields.CharField(max_length=100, description="组件")
    keepalive = fields.BooleanField(default=True, description="存活")
    redirect = fields.CharField(max_length=100, null=True, description="重定向")

    class Meta:
        table = "menu"


class Dept(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="部门名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="备注")
    is_deleted = fields.BooleanField(default=False, description="软删除标记", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, max_length=10, description="父部门ID", index=True)

    class Meta:
        table = "dept"


class DeptClosure(BaseModel, TimestampMixin):
    ancestor = fields.IntField(description="父代", index=True)
    descendant = fields.IntField(description="子代", index=True)
    level = fields.IntField(default=0, description="深度", index=True)


class AuditLog(BaseModel, TimestampMixin):
    user_id = fields.IntField(description="用户ID", index=True)
    username = fields.CharField(max_length=64, default="", description="用户名称", index=True)
    module = fields.CharField(max_length=64, default="", description="功能模块", index=True)
    summary = fields.CharField(max_length=128, default="", description="请求描述", index=True)
    method = fields.CharField(max_length=10, default="", description="请求方法", index=True)
    path = fields.CharField(max_length=255, default="", description="请求路径", index=True)
    status = fields.IntField(default=-1, description="状态码", index=True)
    response_time = fields.IntField(default=0, description="响应时间(单位ms)", index=True)
    request_args = fields.JSONField(null=True, description="请求参数")
    response_body = fields.JSONField(null=True, description="返回数据")
    ip = fields.CharField(max_length=64, default="", description="客户端IP", index=True)
    user_agent = fields.CharField(max_length=512, default="", description="User-Agent")


class SecurityEvent(BaseModel, TimestampMixin):
    """安全事件 / 登录审计（仅超管可查）。"""

    event_type = fields.CharField(max_length=40, description="事件类型", index=True)
    username = fields.CharField(max_length=64, default="", description="用户名", index=True)
    user_id = fields.IntField(null=True, description="用户ID", index=True)
    ip = fields.CharField(max_length=64, default="", description="客户端IP", index=True)
    user_agent = fields.CharField(max_length=512, default="", description="User-Agent")
    device_hash = fields.CharField(max_length=32, default="", description="轻量设备摘要", index=True)
    country = fields.CharField(max_length=64, default="", description="离线库国家")
    region = fields.CharField(max_length=64, default="", description="离线库省份/地区")
    isp = fields.CharField(max_length=128, default="", description="运营商/组织")
    risk_tags = fields.CharField(max_length=255, default="", description="风险标签逗号分隔")
    detail = fields.CharField(max_length=500, default="", description="详情")
    success = fields.BooleanField(default=True, description="是否成功", index=True)

    class Meta:
        table = "security_event"


class SecurityAggBucket(BaseModel, TimestampMixin):
    """Minute buckets for high-frequency attacks. Login/high-risk stay on SecurityEvent."""

    bucket_minute = fields.DatetimeField(description="分钟桶", index=True)
    event_type = fields.CharField(max_length=40, description="事件类型", index=True)
    source_key = fields.CharField(max_length=80, description="来源键 ip:x")
    ip = fields.CharField(max_length=64, default="", description="客户端IP", index=True)
    country = fields.CharField(max_length=64, default="", description="离线库国家")
    region = fields.CharField(max_length=64, default="", description="离线库省份/地区")
    hit_count = fields.IntField(default=0, description="桶内次数")
    first_seen = fields.DatetimeField(description="桶内首次")
    last_seen = fields.DatetimeField(description="桶内末次")

    class Meta:
        table = "security_agg_bucket"
        unique_together = (("bucket_minute", "event_type", "source_key"),)
