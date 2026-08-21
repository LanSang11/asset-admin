from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "api" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "path" VARCHAR(100) NOT NULL  /* API路径 */,
    "method" VARCHAR(6) NOT NULL  /* 请求方法 */,
    "summary" VARCHAR(500) NOT NULL  /* 请求简介 */,
    "tags" VARCHAR(100) NOT NULL  /* API标签 */
);
CREATE INDEX IF NOT EXISTS "idx_api_created_78d19f" ON "api" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_api_updated_643c8b" ON "api" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_api_path_9ed611" ON "api" ("path");
CREATE INDEX IF NOT EXISTS "idx_api_method_a46dfb" ON "api" ("method");
CREATE INDEX IF NOT EXISTS "idx_api_summary_400f73" ON "api" ("summary");
CREATE INDEX IF NOT EXISTS "idx_api_tags_04ae27" ON "api" ("tags");
CREATE TABLE IF NOT EXISTS "assets" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "asset_no" VARCHAR(50) NOT NULL UNIQUE /* 资产编号 */,
    "name" VARCHAR(100) NOT NULL  /* 资产名称 */,
    "category" VARCHAR(50) NOT NULL  DEFAULT '其他' /* 分类：电脑\/办公设备\/办公用品\/其他 */,
    "model" VARCHAR(100) NOT NULL  DEFAULT '' /* 型号 */,
    "serial_no" VARCHAR(100) NOT NULL  DEFAULT '' /* 序列号 */,
    "purchase_date" DATE   /* 采购日期 */,
    "price" VARCHAR(40) NOT NULL  DEFAULT '0' /* 采购价格（元） */,
    "status" INT NOT NULL  DEFAULT 2 /* 状态：1在用 2闲置 3维修 4报废 */,
    "location" VARCHAR(100) NOT NULL  DEFAULT '' /* 存放位置 */,
    "owner_emp_id" INT   /* 当前领用人（employees.id） */,
    "remark" VARCHAR(255) NOT NULL  DEFAULT '' /* 备注 */
) /* 公司资产表 */;
CREATE INDEX IF NOT EXISTS "idx_assets_created_ec37b5" ON "assets" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_assets_updated_fdd9d3" ON "assets" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_assets_asset_n_dc4de2" ON "assets" ("asset_no");
CREATE INDEX IF NOT EXISTS "idx_assets_name_2ded3d" ON "assets" ("name");
CREATE INDEX IF NOT EXISTS "idx_assets_categor_5d44cf" ON "assets" ("category");
CREATE INDEX IF NOT EXISTS "idx_assets_status_d82817" ON "assets" ("status");
CREATE INDEX IF NOT EXISTS "idx_assets_owner_e_6cdfe4" ON "assets" ("owner_emp_id");
CREATE TABLE IF NOT EXISTS "asset_repairs" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "asset_id" INT NOT NULL  /* 资产ID */,
    "employee_id" INT NOT NULL  /* 报修人（employees.id） */,
    "reason" VARCHAR(255) NOT NULL  DEFAULT '' /* 故障说明 */,
    "status" INT NOT NULL  DEFAULT 1 /* 状态 */,
    "manager_approver_id" INT   /* 主管审批人 user.id */,
    "admin_approver_id" INT   /* 管理员审批人 user.id */,
    "manager_comment" VARCHAR(255) NOT NULL  DEFAULT '' /* 主管意见 */,
    "admin_comment" VARCHAR(255) NOT NULL  DEFAULT '' /* 管理员意见 */,
    "manager_time" TIMESTAMP   /* 主管审批时间 */,
    "admin_time" TIMESTAMP   /* 管理员审批时间 */,
    "complete_time" TIMESTAMP   /* 修好时间 */,
    "complete_result" VARCHAR(20) NOT NULL  DEFAULT '' /* in_use|idle */
) /* 资产报修单（独立于领用，避免污染 use_type）。 */;
CREATE INDEX IF NOT EXISTS "idx_asset_repai_created_4a0dd2" ON "asset_repairs" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_asset_repai_updated_722cb4" ON "asset_repairs" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_asset_repai_asset_i_5b3012" ON "asset_repairs" ("asset_id");
CREATE INDEX IF NOT EXISTS "idx_asset_repai_employe_c57b91" ON "asset_repairs" ("employee_id");
CREATE INDEX IF NOT EXISTS "idx_asset_repai_status_5da3bf" ON "asset_repairs" ("status");
CREATE TABLE IF NOT EXISTS "asset_uses" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "asset_id" INT NOT NULL  /* 资产ID */,
    "employee_id" INT NOT NULL  /* 员工ID（申请人） */,
    "use_type" INT NOT NULL  /* 1领用 2归还 */,
    "apply_time" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP /* 申请时间 */,
    "status" INT NOT NULL  DEFAULT 1 /* 状态：1待主管 2待管理员 3通过 4驳回 */,
    "manager_approver_id" INT   /* 主管审批人（user.id） */,
    "admin_approver_id" INT   /* 管理员审批人（user.id） */,
    "manager_comment" VARCHAR(255) NOT NULL  DEFAULT '' /* 主管审批意见 */,
    "admin_comment" VARCHAR(255) NOT NULL  DEFAULT '' /* 管理员审批意见 */,
    "manager_time" TIMESTAMP   /* 主管审批时间 */,
    "admin_time" TIMESTAMP   /* 管理员审批时间 */,
    "return_time" TIMESTAMP   /* 归还完成时间（归还流程通过时写入） */
) /* 领用\/归还申请记录（两级审批流程） */;
CREATE INDEX IF NOT EXISTS "idx_asset_uses_created_915088" ON "asset_uses" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_updated_e3b73b" ON "asset_uses" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_asset_i_c82a9a" ON "asset_uses" ("asset_id");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_employe_fc0109" ON "asset_uses" ("employee_id");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_use_typ_4436f5" ON "asset_uses" ("use_type");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_apply_t_047e22" ON "asset_uses" ("apply_time");
CREATE INDEX IF NOT EXISTS "idx_asset_uses_status_d21189" ON "asset_uses" ("status");
CREATE TABLE IF NOT EXISTS "asset_use_history" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "asset_id" INT NOT NULL  /* 资产ID */,
    "employee_id" INT NOT NULL  /* 员工ID */,
    "use_type" INT NOT NULL  /* 1领用 2归还 */,
    "use_time" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP /* 发生时间 */,
    "operator_id" INT   /* 操作人（审批通过的管理员 user.id） */,
    "remark" VARCHAR(255) NOT NULL  DEFAULT '' /* 备注 */
) /* 资产使用历史（每台资产完整生命周期追溯） */;
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_created_80e85f" ON "asset_use_history" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_updated_eda5c3" ON "asset_use_history" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_asset_i_bbd9f2" ON "asset_use_history" ("asset_id");
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_employe_d77c7d" ON "asset_use_history" ("employee_id");
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_use_typ_9b8ccb" ON "asset_use_history" ("use_type");
CREATE INDEX IF NOT EXISTS "idx_asset_use_h_use_tim_86ef5a" ON "asset_use_history" ("use_time");
CREATE TABLE IF NOT EXISTS "auditlog" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL  /* 用户ID */,
    "username" VARCHAR(64) NOT NULL  DEFAULT '' /* 用户名称 */,
    "module" VARCHAR(64) NOT NULL  DEFAULT '' /* 功能模块 */,
    "summary" VARCHAR(128) NOT NULL  DEFAULT '' /* 请求描述 */,
    "method" VARCHAR(10) NOT NULL  DEFAULT '' /* 请求方法 */,
    "path" VARCHAR(255) NOT NULL  DEFAULT '' /* 请求路径 */,
    "status" INT NOT NULL  DEFAULT -1 /* 状态码 */,
    "response_time" INT NOT NULL  DEFAULT 0 /* 响应时间(单位ms) */,
    "request_args" JSON   /* 请求参数 */,
    "response_body" JSON   /* 返回数据 */,
    "ip" VARCHAR(64) NOT NULL  DEFAULT '' /* 客户端IP */,
    "user_agent" VARCHAR(512) NOT NULL  DEFAULT '' /* User-Agent */
);
CREATE INDEX IF NOT EXISTS "idx_auditlog_created_cc33d0" ON "auditlog" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_auditlog_updated_2f871f" ON "auditlog" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_auditlog_user_id_4b93fa" ON "auditlog" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_auditlog_usernam_b187b3" ON "auditlog" ("username");
CREATE INDEX IF NOT EXISTS "idx_auditlog_module_04058b" ON "auditlog" ("module");
CREATE INDEX IF NOT EXISTS "idx_auditlog_summary_3e27da" ON "auditlog" ("summary");
CREATE INDEX IF NOT EXISTS "idx_auditlog_method_4270a2" ON "auditlog" ("method");
CREATE INDEX IF NOT EXISTS "idx_auditlog_path_b99502" ON "auditlog" ("path");
CREATE INDEX IF NOT EXISTS "idx_auditlog_status_2a72d2" ON "auditlog" ("status");
CREATE INDEX IF NOT EXISTS "idx_auditlog_respons_8caa87" ON "auditlog" ("response_time");
CREATE INDEX IF NOT EXISTS "idx_auditlog_ip_3645f9" ON "auditlog" ("ip");
CREATE TABLE IF NOT EXISTS "dept" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(20) NOT NULL UNIQUE /* 部门名称 */,
    "desc" VARCHAR(500)   /* 备注 */,
    "is_deleted" INT NOT NULL  DEFAULT 0 /* 软删除标记 */,
    "order" INT NOT NULL  DEFAULT 0 /* 排序 */,
    "parent_id" INT NOT NULL  DEFAULT 0 /* 父部门ID */
);
CREATE INDEX IF NOT EXISTS "idx_dept_created_4b11cf" ON "dept" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_dept_updated_0c0bd1" ON "dept" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_dept_name_c2b9da" ON "dept" ("name");
CREATE INDEX IF NOT EXISTS "idx_dept_is_dele_466228" ON "dept" ("is_deleted");
CREATE INDEX IF NOT EXISTS "idx_dept_order_ddabe1" ON "dept" ("order");
CREATE INDEX IF NOT EXISTS "idx_dept_parent__a71a57" ON "dept" ("parent_id");
CREATE TABLE IF NOT EXISTS "deptclosure" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "ancestor" INT NOT NULL  /* 父代 */,
    "descendant" INT NOT NULL  /* 子代 */,
    "level" INT NOT NULL  DEFAULT 0 /* 深度 */
);
CREATE INDEX IF NOT EXISTS "idx_deptclosure_created_96f6ef" ON "deptclosure" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_deptclosure_updated_41fc08" ON "deptclosure" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_deptclosure_ancesto_fbc4ce" ON "deptclosure" ("ancestor");
CREATE INDEX IF NOT EXISTS "idx_deptclosure_descend_2ae8b1" ON "deptclosure" ("descendant");
CREATE INDEX IF NOT EXISTS "idx_deptclosure_level_ae16b2" ON "deptclosure" ("level");
CREATE TABLE IF NOT EXISTS "employees" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "emp_no" VARCHAR(20) NOT NULL UNIQUE /* 工号 */,
    "name" VARCHAR(50) NOT NULL  /* 姓名 */,
    "gender" INT NOT NULL  DEFAULT 0 /* 性别：0未知 1男 2女 */,
    "dept_id" INT   /* 部门ID（关联 dept.id） */,
    "position" VARCHAR(100) NOT NULL  DEFAULT '' /* 职位 */,
    "hire_date" DATE   /* 入职日期 */,
    "phone" VARCHAR(20) NOT NULL  DEFAULT '' /* 手机 */,
    "email" VARCHAR(100) NOT NULL  DEFAULT '' /* 邮箱 */,
    "user_id" INT  UNIQUE /* 绑定登录账号ID（user.id） */,
    "is_manager" INT NOT NULL  DEFAULT 0 /* 是否部门主管（审批用） */,
    "status" INT NOT NULL  DEFAULT 1 /* 1在职 0离职 */
) /* 员工表（与 user 账号 1:1 绑定，一人一号） */;
CREATE INDEX IF NOT EXISTS "idx_employees_created_fdd4c9" ON "employees" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_employees_updated_f0d2fb" ON "employees" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_employees_emp_no_676ec2" ON "employees" ("emp_no");
CREATE INDEX IF NOT EXISTS "idx_employees_name_72b737" ON "employees" ("name");
CREATE INDEX IF NOT EXISTS "idx_employees_dept_id_edb17e" ON "employees" ("dept_id");
CREATE INDEX IF NOT EXISTS "idx_employees_user_id_05f44f" ON "employees" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_employees_is_mana_cea9fe" ON "employees" ("is_manager");
CREATE INDEX IF NOT EXISTS "idx_employees_status_1ca7f1" ON "employees" ("status");
CREATE TABLE IF NOT EXISTS "menu" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(20) NOT NULL  /* 菜单名称 */,
    "remark" JSON   /* 保留字段 */,
    "menu_type" VARCHAR(7)   /* 菜单类型 */,
    "icon" VARCHAR(100)   /* 菜单图标 */,
    "path" VARCHAR(100) NOT NULL  /* 菜单路径 */,
    "order" INT NOT NULL  DEFAULT 0 /* 排序 */,
    "parent_id" INT NOT NULL  DEFAULT 0 /* 父菜单ID */,
    "is_hidden" INT NOT NULL  DEFAULT 0 /* 是否隐藏 */,
    "component" VARCHAR(100) NOT NULL  /* 组件 */,
    "keepalive" INT NOT NULL  DEFAULT 1 /* 存活 */,
    "redirect" VARCHAR(100)   /* 重定向 */
);
CREATE INDEX IF NOT EXISTS "idx_menu_created_b6922b" ON "menu" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_menu_updated_e6b0a1" ON "menu" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_menu_name_b9b853" ON "menu" ("name");
CREATE INDEX IF NOT EXISTS "idx_menu_path_bf95b2" ON "menu" ("path");
CREATE INDEX IF NOT EXISTS "idx_menu_order_606068" ON "menu" ("order");
CREATE INDEX IF NOT EXISTS "idx_menu_parent__bebd15" ON "menu" ("parent_id");
CREATE TABLE IF NOT EXISTS "notifications" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL  /* 接收人（user.id） */,
    "title" VARCHAR(100) NOT NULL  /* 标题 */,
    "content" VARCHAR(500) NOT NULL  DEFAULT '' /* 内容 */,
    "route" VARCHAR(200) NOT NULL  DEFAULT '' /* 跳转路由 */,
    "type" VARCHAR(40) NOT NULL  DEFAULT '' /* 通知类型 */,
    "is_read" INT NOT NULL  DEFAULT 0 /* 是否已读 */
) /* 站内通知（审批相关铃铛提醒） */;
CREATE INDEX IF NOT EXISTS "idx_notificatio_created_5f34f1" ON "notifications" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_notificatio_updated_1e50c2" ON "notifications" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_notificatio_user_id_daa173" ON "notifications" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_notificatio_type_40b578" ON "notifications" ("type");
CREATE INDEX IF NOT EXISTS "idx_notificatio_is_read_9d9b95" ON "notifications" ("is_read");
CREATE TABLE IF NOT EXISTS "role" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(20) NOT NULL UNIQUE /* 角色名称 */,
    "desc" VARCHAR(500)   /* 角色描述 */
);
CREATE INDEX IF NOT EXISTS "idx_role_created_7f5f71" ON "role" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_role_updated_5dd337" ON "role" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_role_name_e5618b" ON "role" ("name");
CREATE TABLE IF NOT EXISTS "security_event" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "event_type" VARCHAR(40) NOT NULL  /* 事件类型 */,
    "username" VARCHAR(64) NOT NULL  DEFAULT '' /* 用户名 */,
    "user_id" INT   /* 用户ID */,
    "ip" VARCHAR(64) NOT NULL  DEFAULT '' /* 客户端IP */,
    "user_agent" VARCHAR(512) NOT NULL  DEFAULT '' /* User-Agent */,
    "device_hash" VARCHAR(32) NOT NULL  DEFAULT '' /* 轻量设备摘要 */,
    "country" VARCHAR(64) NOT NULL  DEFAULT '' /* 离线库国家 */,
    "region" VARCHAR(64) NOT NULL  DEFAULT '' /* 离线库省份\/地区 */,
    "isp" VARCHAR(128) NOT NULL  DEFAULT '' /* 运营商\/组织 */,
    "risk_tags" VARCHAR(255) NOT NULL  DEFAULT '' /* 风险标签逗号分隔 */,
    "detail" VARCHAR(500) NOT NULL  DEFAULT '' /* 详情 */,
    "success" INT NOT NULL  DEFAULT 1 /* 是否成功 */
) /* 安全事件 \/ 登录审计（仅超管可查）。 */;
CREATE INDEX IF NOT EXISTS "idx_security_ev_created_f6f2b9" ON "security_event" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_security_ev_updated_e130c1" ON "security_event" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_security_ev_event_t_45c67d" ON "security_event" ("event_type");
CREATE INDEX IF NOT EXISTS "idx_security_ev_usernam_4a4831" ON "security_event" ("username");
CREATE INDEX IF NOT EXISTS "idx_security_ev_user_id_727d8d" ON "security_event" ("user_id");
CREATE INDEX IF NOT EXISTS "idx_security_ev_ip_a03038" ON "security_event" ("ip");
CREATE INDEX IF NOT EXISTS "idx_security_ev_device__afc19e" ON "security_event" ("device_hash");
CREATE INDEX IF NOT EXISTS "idx_security_ev_success_619cf5" ON "security_event" ("success");
CREATE TABLE IF NOT EXISTS "user" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "created_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "username" VARCHAR(20) NOT NULL UNIQUE /* 用户名称 */,
    "alias" VARCHAR(30)   /* 姓名 */,
    "email" VARCHAR(255) NOT NULL UNIQUE /* 邮箱 */,
    "phone" VARCHAR(20)   /* 电话 */,
    "password" VARCHAR(128)   /* 密码 */,
    "must_change_password" INT NOT NULL  DEFAULT 1 /* 首次登录是否必须修改密码 */,
    "is_active" INT NOT NULL  DEFAULT 1 /* 是否激活 */,
    "is_superuser" INT NOT NULL  DEFAULT 0 /* 是否为超级管理员 */,
    "last_login" TIMESTAMP   /* 最后登录时间 */,
    "totp_secret" VARCHAR(64)   /* TOTP密钥Base32 */,
    "totp_enabled" INT NOT NULL  DEFAULT 0 /* 是否启用TOTP二次验证 */,
    "api_config" JSON   /* 大模型API配置（加密） */,
    "dept_id" INT   /* 部门ID */
);
CREATE INDEX IF NOT EXISTS "idx_user_created_b19d59" ON "user" ("created_at");
CREATE INDEX IF NOT EXISTS "idx_user_updated_dfdb43" ON "user" ("updated_at");
CREATE INDEX IF NOT EXISTS "idx_user_usernam_9987ab" ON "user" ("username");
CREATE INDEX IF NOT EXISTS "idx_user_alias_6f9868" ON "user" ("alias");
CREATE INDEX IF NOT EXISTS "idx_user_email_1b4f1c" ON "user" ("email");
CREATE INDEX IF NOT EXISTS "idx_user_phone_4e3ecc" ON "user" ("phone");
CREATE INDEX IF NOT EXISTS "idx_user_must_ch_883295" ON "user" ("must_change_password");
CREATE INDEX IF NOT EXISTS "idx_user_is_acti_83722a" ON "user" ("is_active");
CREATE INDEX IF NOT EXISTS "idx_user_is_supe_b8a218" ON "user" ("is_superuser");
CREATE INDEX IF NOT EXISTS "idx_user_last_lo_af118a" ON "user" ("last_login");
CREATE INDEX IF NOT EXISTS "idx_user_totp_en_6b9676" ON "user" ("totp_enabled");
CREATE INDEX IF NOT EXISTS "idx_user_dept_id_d4490b" ON "user" ("dept_id");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS "role_menu" (
    "role_id" BIGINT NOT NULL REFERENCES "role" ("id") ON DELETE CASCADE,
    "menu_id" BIGINT NOT NULL REFERENCES "menu" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_role_menu_role_id_90801c" ON "role_menu" ("role_id", "menu_id");
CREATE TABLE IF NOT EXISTS "role_api" (
    "role_id" BIGINT NOT NULL REFERENCES "role" ("id") ON DELETE CASCADE,
    "api_id" BIGINT NOT NULL REFERENCES "api" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_role_api_role_id_ba4286" ON "role_api" ("role_id", "api_id");
CREATE TABLE IF NOT EXISTS "user_role" (
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "role_id" BIGINT NOT NULL REFERENCES "role" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_user_role_user_id_d0bad3" ON "user_role" ("user_id", "role_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
