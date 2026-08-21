-- 资产管理系统 · 业务表 SQL（MySQL 8 版）
-- 用途：培训演示 / 未来切换数据库 / 新环境初始化
-- 说明：系统默认运行在 SQLite（db.sqlite3），本脚本与业务模型结构一致

CREATE DATABASE IF NOT EXISTS asset_management DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE asset_management;

-- 员工表（与 user 账号 1:1 绑定，一人一号）
CREATE TABLE IF NOT EXISTS employees (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    emp_no VARCHAR(20) NOT NULL UNIQUE COMMENT '工号',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    gender TINYINT DEFAULT 0 COMMENT '性别：0未知 1男 2女',
    dept_id INT NULL COMMENT '部门ID（关联 dept.id）',
    position VARCHAR(100) DEFAULT '' COMMENT '职位',
    hire_date DATE NULL COMMENT '入职日期',
    phone VARCHAR(20) DEFAULT '' COMMENT '手机',
    email VARCHAR(100) DEFAULT '' COMMENT '邮箱',
    user_id INT NULL UNIQUE COMMENT '绑定登录账号ID（user.id）',
    is_manager TINYINT(1) DEFAULT 0 COMMENT '是否部门主管（审批用）',
    status TINYINT(1) DEFAULT 1 COMMENT '1在职 0离职',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_emp_dept (dept_id),
    INDEX idx_emp_name (name),
    INDEX idx_emp_manager (is_manager)
) ENGINE=InnoDB COMMENT='员工表';

-- 公司资产表
CREATE TABLE IF NOT EXISTS assets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    asset_no VARCHAR(50) NOT NULL UNIQUE COMMENT '资产编号',
    name VARCHAR(100) NOT NULL COMMENT '资产名称',
    category VARCHAR(50) DEFAULT '其他' COMMENT '分类：电脑/办公设备/办公用品/其他',
    model VARCHAR(100) DEFAULT '' COMMENT '型号',
    serial_no VARCHAR(100) DEFAULT '' COMMENT '序列号',
    purchase_date DATE NULL COMMENT '采购日期',
    price DECIMAL(10,2) DEFAULT 0.00 COMMENT '采购价格（元）',
    status TINYINT DEFAULT 2 COMMENT '1在用 2闲置 3维修 4报废',
    location VARCHAR(100) DEFAULT '' COMMENT '存放位置',
    owner_emp_id BIGINT NULL COMMENT '当前领用人（employees.id）',
    remark VARCHAR(255) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_asset_category (category),
    INDEX idx_asset_status (status),
    INDEX idx_asset_owner (owner_emp_id)
) ENGINE=InnoDB COMMENT='公司资产表';

-- 领用/归还申请记录（两级审批流程）
CREATE TABLE IF NOT EXISTS asset_uses (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    asset_id BIGINT NOT NULL COMMENT '资产ID',
    employee_id BIGINT NOT NULL COMMENT '员工ID（申请人）',
    use_type TINYINT NOT NULL COMMENT '1领用 2归还',
    apply_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
    status TINYINT DEFAULT 1 COMMENT '1待主管 2待管理员 3通过 4驳回',
    manager_approver_id BIGINT NULL COMMENT '主管审批人（user.id）',
    admin_approver_id BIGINT NULL COMMENT '管理员审批人（user.id）',
    manager_comment VARCHAR(255) DEFAULT '' COMMENT '主管审批意见',
    admin_comment VARCHAR(255) DEFAULT '' COMMENT '管理员审批意见',
    manager_time DATETIME NULL COMMENT '主管审批时间',
    admin_time DATETIME NULL COMMENT '管理员审批时间',
    return_time DATETIME NULL COMMENT '归还完成时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_use_asset (asset_id),
    INDEX idx_use_employee (employee_id),
    INDEX idx_use_status (status)
) ENGINE=InnoDB COMMENT='领用/归还申请记录';

-- 资产使用历史（每台资产完整生命周期追溯）
CREATE TABLE IF NOT EXISTS asset_use_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    asset_id BIGINT NOT NULL COMMENT '资产ID',
    employee_id BIGINT NOT NULL COMMENT '员工ID',
    use_type TINYINT NOT NULL COMMENT '1领用 2归还',
    use_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发生时间',
    operator_id BIGINT NULL COMMENT '操作人（user.id）',
    remark VARCHAR(255) DEFAULT '' COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_hist_asset (asset_id),
    INDEX idx_hist_employee (employee_id)
) ENGINE=InnoDB COMMENT='资产使用历史';

-- 站内通知表（铃铛提醒）
CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    user_id BIGINT NOT NULL COMMENT '接收人（user.id）',
    title VARCHAR(100) NOT NULL COMMENT '标题',
    content VARCHAR(500) DEFAULT '' COMMENT '内容',
    route VARCHAR(200) DEFAULT '' COMMENT '点击通知跳转的前端路由',
    is_read TINYINT(1) DEFAULT 0 COMMENT '是否已读',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_notify_user (user_id),
    INDEX idx_notify_read (is_read)
) ENGINE=InnoDB COMMENT='站内通知';
