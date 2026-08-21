"""阶段2 演示数据初始化：部门/员工/主管/资产/普通账号（测试两级审批用）。

创建：
- 部门：研发部(id=1)
- 员工：张三(普通员工, 绑定 demoemp), 李四(部门主管, 绑定 demomgr)
- 资产：AST001(闲置)
- 账号：demoemp/demomgr（密码由 DEMO_PASSWORD 环境变量或命令行参数传入）
"""
import asyncio
import sqlite3

import os
import sqlite3
import sys

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

DB = "/opt/asset-management-system/db/db.sqlite3"
# 演示账号初始密码：从环境变量/命令行参数读取（不硬编码，避免随镜像分发泄露）
DEFAULT_PWD = os.getenv("DEMO_PASSWORD") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not DEFAULT_PWD:
    raise SystemExit("请通过环境变量 DEMO_PASSWORD 或命令行参数指定演示账号初始密码")


def hash_pwd(p):
    return pwd_context.hash(p)


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 部门
    cur.execute("SELECT COUNT(*) FROM dept")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO dept (name, desc, is_deleted, \"order\", parent_id) VALUES ('研发部', '技术研发', 0, 1, 0)")
        print("OK: 部门 研发部")

    # 用户（一人一号）
    users = {}
    for uname in ("demoemp", "demomgr"):
        cur.execute("SELECT id FROM user WHERE username=?", (uname,))
        row = cur.fetchone()
        if row:
            users[uname] = row[0]
        else:
            cur.execute(
                "INSERT INTO user (username, email, password, is_active, is_superuser, must_change_password) VALUES (?, ?, ?, 1, 0, 1)",
                (uname, f"{uname}@example.com", hash_pwd(DEFAULT_PWD)),
            )
            users[uname] = cur.lastrowid
            print(f"OK: 账号 {uname}")

    # 员工
    cur.execute("SELECT id FROM dept WHERE name='研发部'")
    dept_id = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM employees WHERE emp_no='E001'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO employees (emp_no, name, gender, dept_id, position, phone, email, user_id, is_manager, status) "
            "VALUES ('E001', '张三', 1, ?, '工程师', '13800000001', 'zhangsan@example.com', ?, 0, 1)",
            (dept_id, users["demoemp"]),
        )
        print("OK: 员工 张三 (普通员工)")
    cur.execute("SELECT COUNT(*) FROM employees WHERE emp_no='E002'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO employees (emp_no, name, gender, dept_id, position, phone, email, user_id, is_manager, status) "
            "VALUES ('E002', '李四', 1, ?, '研发主管', '13800000002', 'lisi@example.com', ?, 1, 1)",
            (dept_id, users["demomgr"]),
        )
        print("OK: 员工 李四 (部门主管)")

    # 资产
    cur.execute("SELECT COUNT(*) FROM assets WHERE asset_no='AST001'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO assets (asset_no, name, category, model, serial_no, purchase_date, price, status, location) "
            "VALUES ('AST001', '联想笔记本', '电脑', 'ThinkPad X1', 'SN001', '2026-01-15', 8999.00, 2, '仓库A')"
        )
        print("OK: 资产 联想笔记本(闲置)")

    conn.commit()
    conn.close()
    print("演示数据初始化完成")
    print("演示账号已创建；密码来自 DEMO_PASSWORD，日志不回显凭据")
    print("admin 账号密码为随机生成的一次性密码，请查看服务启动日志获取")


main()
