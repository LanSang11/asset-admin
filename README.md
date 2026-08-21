<p align="center">
  <img alt="资产管理系统" width="96" src="web/public/resource/company-logo.jpg">
</p>

<h1 align="center">资产管理系统</h1>

<p align="center">
  把散落在表格、聊天记录和纸质单据里的资产信息，整理成一套每个人都知道下一步该做什么的工作台。
</p>

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white">
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white">
  <img alt="Naive UI" src="https://img.shields.io/badge/Naive%20UI-2-36ad6a">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-yellow">
</p>

<p align="center">
  <a href="./README-en.md">English</a>
  ·
  <a href="./README-部署与使用教程.md">部署与使用教程</a>
  ·
  <a href="./SECURITY.md">安全说明</a>
  ·
  <a href="./LICENSE">MIT License</a>
</p>

---

## 这套系统解决什么问题？

它面向需要管理电脑、显示器、办公设备等内部资产的小型团队和企业：

- **行政 / 资产管理员**不再反复核对多份表格，可以统一登记资产、员工、位置、价格和质保时间。
- **员工**能看到自己名下的设备，直接提交领用、归还、调拨或报修申请。
- **部门主管**只处理本部门的待办，管理员完成最终审批，过程和结果都有记录。
- **管理者**从工作台和统计看板掌握在用、闲置、维修、临期质保及流程待办情况。

系统覆盖从资产入库到领用、归还、调拨、报修、盘点的日常闭环，同时提供知识库、可选 AI 助手、安全中心和手机扫码入口。

## 第一次打开后，建议这样使用

1. 管理员先建立部门和员工档案，并为员工绑定登录账号。
2. 在“资产管理”登记资产编号、分类、状态、位置、价格和质保到期日。
3. 员工从业务工作台提交领用、归还、调拨或报修申请。
4. 部门主管处理本部门初审，管理员在审批中心完成终审。
5. 定期发起盘点，在统计看板和安全中心检查运营与登录情况。

## 主要功能截图与操作说明

以下截图全部来自 `127.0.0.1` 本地演示环境，仅使用张三、李四、`example.com` 和演示资产编号，不包含线上数据。

### 1. 登录：每次先完成滑块校验

<p align="center">
  <img src="deploy/sample-picture/screenshots/login.png" alt="登录与滑块校验" width="760">
</p>

- **谁在用：** 所有用户。
- **这一步做什么：** 滑块完成后再提交账号信息；管理员还可按策略使用动态验证器。
- **点哪里：** 拖动滑块到目标位置，填写账号信息，然后点击“登录”。

### 2. 管理端工作台：先看全局，再进具体模块

<p align="center">
  <img src="deploy/sample-picture/screenshots/workbench.png" alt="管理端工作台" width="920">
</p>

- **谁在用：** 管理员。
- **这一步做什么：** 查看资产总数、在用、闲置、维修、报废和临期质保，并快速进入高频功能。
- **点哪里：** 从右侧“快捷操作”进入资产、员工、审批或统计页面；下方可继续查看资产状态趋势。

### 3. 员工 / 主管工作台：只展示和自己岗位有关的事

<p align="center">
  <img src="deploy/sample-picture/screenshots/work-portal.png" alt="员工和主管业务工作台" width="920">
</p>

- **谁在用：** 普通员工和部门主管。
- **这一步做什么：** 员工处理自己的资产与申请；主管同时看到本部门待办和审批入口。
- **点哪里：** 从“快速入口”打开领用归还、我的资产、调拨、报修、盘点或审批中心。

### 4. 资产台账：一台设备一条记录

<p align="center">
  <img src="deploy/sample-picture/screenshots/assets.png" alt="资产管理台账" width="920">
</p>

- **谁在用：** 管理员和有查看权限的岗位。
- **这一步做什么：** 统一维护资产编号、名称、分类、型号、序列号、价格、状态、位置和领用人。
- **点哪里：** 点击右上角“新增资产”登记单台设备；已有数据可使用 CSV 导入或导出。

### 5. 员工档案：把人员、部门和登录账号关联起来

<p align="center">
  <img src="deploy/sample-picture/screenshots/employees.png" alt="员工管理" width="920">
</p>

- **谁在用：** 管理员。
- **这一步做什么：** 管理工号、姓名、部门、岗位、联系方式、主管标记和在职状态。
- **点哪里：** 点击“新增员工”建档；需要登录系统时，再为员工绑定对应账号。

### 6. 我的资产：员工只看自己名下的设备

<p align="center">
  <img src="deploy/sample-picture/screenshots/my-assets.png" alt="员工我的资产" width="920">
</p>

- **谁在用：** 员工和部门主管。
- **这一步做什么：** 查看自己正在使用或维修中的设备，不必在全公司资产里查找。
- **点哪里：** 在符合状态时，可直接从右侧操作区发起报修或调拨。

### 7. 领用与归还：申请、审批、结果都留痕

<p align="center">
  <img src="deploy/sample-picture/screenshots/asset-use.png" alt="资产领用归还" width="920">
</p>

- **谁在用：** 员工发起，主管和管理员审批。
- **这一步做什么：** 记录资产、申请人、类型、状态、申请时间和审批意见。
- **点哪里：** 员工点击“申请领用”或“申请归还”；管理员可从该页查看历史记录。

### 8. 审批中心：把待办集中到一个地方

<p align="center">
  <img src="deploy/sample-picture/screenshots/approval.png" alt="审批中心" width="920">
</p>

- **谁在用：** 部门主管和管理员。
- **这一步做什么：** 主管先核对本部门申请，管理员完成终审；驳回时保留原因。
- **点哪里：** 对待处理记录点击“通过”或“驳回”，处理后状态会回写到申请与资产台账。

### 9. 资产调拨：设备换人使用，历史不丢

<p align="center">
  <img src="deploy/sample-picture/screenshots/transfer.png" alt="资产调拨" width="920">
</p>

- **谁在用：** 当前领用人发起，主管和管理员审批。
- **这一步做什么：** 记录调出人、调入人、调拨原因和审批状态；通过后资产仍保持“在用”。
- **点哪里：** 点击“申请调拨”选择在用资产和调入员工，审批人再点击“通过”或“驳回”。

### 10. 报修：从故障说明到修好登记

<p align="center">
  <img src="deploy/sample-picture/screenshots/repair.png" alt="资产报修" width="920">
</p>

- **谁在用：** 员工、主管和管理员。
- **这一步做什么：** 记录故障、报修人和维修状态，避免报修信息散落在聊天记录里。
- **点哪里：** 员工点击“我要报修”；管理员也可“登记送修”，维修结束后点击“修好”登记去向。

### 11. 盘点：逐台标记相符、盘亏或不符

<p align="center">
  <img src="deploy/sample-picture/screenshots/inventory.png" alt="资产盘点明细" width="920">
</p>

- **谁在用：** 管理员或部门主管发起，相关岗位参与核对。
- **这一步做什么：** 固化盘点时的账面快照，再逐台登记实盘结果。盘亏只记录，不会自动报废资产。
- **点哪里：** 点击“发起盘点”创建任务，进入“明细”后对每台资产选择“相符”“盘亏”或“不符”，确认后再结束盘点。

### 12. 统计看板：用图表理解资产结构

<p align="center">
  <img src="deploy/sample-picture/screenshots/dashboard.png" alt="资产统计看板" width="920">
</p>

- **谁在用：** 管理员和管理者。
- **这一步做什么：** 查看资产分类、状态、部门分布以及近期流转情况，快速发现闲置或维修设备。
- **点哪里：** 从业务管理进入“统计看板”；数据随台账和审批结果更新。

### 13. 知识库：上传自己的说明，再按资料提问

<p align="center">
  <img src="deploy/sample-picture/screenshots/kb.png" alt="知识库问答与引用" width="920">
</p>

- **谁在用：** 需要查询制度、流程和操作说明的用户。
- **这一步做什么：** 上传 UTF-8 的 `.txt` / `.md` 文档，按已入库资料回答，并显示引用片段。
- **点哪里：** 点击“上传 txt/md”入库资料；输入问题或点击示例问题，再点击“提问”。没有合格向量服务时会明确使用中文词面检索。

### 14. AI 助手：可选接入自己的模型服务

<p align="center">
  <img src="deploy/sample-picture/screenshots/ai.png" alt="AI 助手" width="920">
</p>

- **谁在用：** 需要业务问答或数据分析辅助的用户。
- **这一步做什么：** 进行资产、员工、审批相关问答；模型服务为可选配置，仓库不包含任何模型密钥。
- **点哪里：** 点击“配置 API”选择服务商并填写自己的配置，保存后在输入框提问。图片理解需要单独配置视觉模型。

### 15. 安全中心：看登录、风险和验证策略

<p align="center">
  <img src="deploy/sample-picture/screenshots/security.png" alt="安全中心" width="920">
</p>

- **谁在用：** 超级管理员。
- **这一步做什么：** 汇总登录事件、风险标签、封禁记录、验证策略和证书状态，帮助管理员判断异常情况。
- **点哪里：** 使用顶部标签切换登录日志、风险事件、封禁、二次验证和 HTTPS 信息；策略修改按配置要求再次验证。

### 16. 用户与角色：账号、岗位和权限分开维护

| 用户管理 | 角色管理 |
| --- | --- |
| <img src="deploy/sample-picture/screenshots/users.png" alt="用户管理"> | <img src="deploy/sample-picture/screenshots/roles.png" alt="角色管理"> |

- **谁在用：** 超级管理员。
- **这一步做什么：** 用户页管理账号状态和角色绑定；角色页维护管理员、部门主管、普通用户等岗位权限。
- **点哪里：** 在用户行点击“编辑”分配角色；在角色行点击“分配权限”调整菜单和接口能力。

### 17. 手机扫码：从资产标签直接打开详情

<p align="center">
  <img src="deploy/sample-picture/screenshots/scan.png" alt="手机扫码资产详情" width="760">
</p>

- **谁在用：** 现场查看设备的员工、主管或管理员。
- **这一步做什么：** 二维码按资产编号打开轻量详情页；登录后仍按岗位权限读取数据。
- **点哪里：** 用手机扫描资产二维码，查看状态和领用人；符合条件时可继续进入报修或调拨。

## 权限与安全边界

- 管理员、部门主管和普通员工看到的入口与数据范围不同，接口侧也会再次校验。
- 登录滑块、动态验证器、操作再次验证均可按策略启用。
- AI 与知识库不会在仓库中预置模型密钥；运行时数据库、上传文件和本地密钥均已加入忽略规则。
- 安全中心用于辅助判断和审计，不代替 HTTPS、反向代理、主机防火墙与日常备份。

## 快速开始

环境要求：Python 3.11+、Node.js 18+。

```bash
git clone https://github.com/LanSang11/asset-admin.git
cd asset-admin

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

另开一个终端启动前端：

```bash
cd web
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:3100`。空库首次启动会在后端日志中生成管理员一次性初始凭据；首次进入后按页面引导修改并完成管理员验证器设置。

如需写入纯本地演示账号和假数据，请先设置自己的演示密码，再执行：

```bash
# Windows PowerShell
$env:DEMO_PASSWORD="请设置一个本地演示密码"
python deploy/init_oss_demo_data.py --db db/db.sqlite3
```

完整的 Docker、本地运行、备份和首次登录步骤见 [`README-部署与使用教程.md`](./README-部署与使用教程.md)。

## 项目目录

```text
app/        FastAPI 后端与业务服务
web/        Vue 3 前端
deploy/     部署模板、演示脚本、测试与截图
migrations/ 数据库迁移
```

第三方组件与许可证说明见 [`NOTICE`](./NOTICE)。
