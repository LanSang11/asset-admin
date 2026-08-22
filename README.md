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
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg">
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

| 核心能力 | 解决的问题 | 主要使用者 |
|---|---|---|
| 资产与员工台账 | 统一设备、人员、部门、位置、价格和质保信息 | 资产管理员 |
| 领用、归还与审批 | 让申请、初审、终审和结果全程留痕 | 员工、主管、管理员 |
| 调拨、报修与盘点 | 覆盖设备换人、维修和账实核对 | 全角色按权限参与 |
| 工作台与统计 | 聚合待办、资产状态、趋势和质保关注 | 主管、管理员 |
| 知识库与可选 AI | 基于自有资料检索、引用和辅助分析 | 业务用户 |
| 安全运营 | 汇总登录风险、验证策略、审计和证书状态 | 超级管理员 |
| 手机扫码 | 从资产标签进入轻量详情与后续操作 | 现场人员 |


## 系统架构：稳定六层，业务模块可扩展

<p align="center">
  <img src="deploy/sample-picture/architecture-overview.svg" alt="资产管理系统可扩展六层架构图" width="100%">
</p>

这张图描述的是当前代码的真实边界，而不是限制以后只能做这些功能：

- **第 1～4 层是稳定主干。** 用户入口、Vue 前端、FastAPI 接口和权限安全共同形成通用框架。
- **第 5 层是主要扩展区。** 新的资产业务通常按“页面 + API + Schema + Service/Controller + Model + Test”进入这一层。
- **第 6 层隔离数据与外部能力。** 业务数据、知识库、附件和可选模型服务各有明确入口，不把第三方配置写进业务页面。
- 架构图本身只用于说明项目，不参与编译和运行；以后增加功能时，按真实实现补充模块名称即可。

### 一次业务请求怎样走完？

以员工提交资产调拨为例，请求会依次经过：

1. **页面交互：** `web/src/views/business/` 收集表单，前端 API 封装通过 Axios 发出请求。
2. **路由与校验：** `app/api/v1/` 匹配领域路由，Pydantic Schema 校验输入字段和格式。
3. **身份与范围：** 依赖和中间件验证登录会话、角色/API 权限、部门或本人数据范围；高风险操作按策略增加 TOTP 或 Step-up Token。
4. **业务规则：** Controller / Service 判断资产状态、申请人范围和流程条件，再调用数据模型完成变更。
5. **持久化与留痕：** Tortoise ORM 写入业务 SQLite；审计日志、通知或安全事件按对应规则记录。
6. **统一响应：** FastAPI 返回结构化结果，前端刷新列表并用中文消息提示成功或具体错误。

前端隐藏按钮只是第一层体验控制，真正的数据范围和操作权限仍由后端再次判断。

### 技术栈与职责

| 层次 | 当前技术 | 在项目中负责什么 |
| --- | --- | --- |
| 页面与交互 | Vue 3、Vite、Naive UI、Vue Router、Pinia | 页面、导航、角色入口、表单表格和前端状态 |
| HTTP 通信 | Axios、统一 API 封装 | 附带登录令牌、发送请求、处理统一响应与错误 |
| Web API | FastAPI、Pydantic | 路由、依赖注入、输入校验和响应结构 |
| 权限与安全 | JWT、RBAC、数据范围、TOTP、Step-up、中间件 | 登录、角色/API 权限、部门隔离、高风险操作验证、限流和审计 |
| 业务实现 | Controller、Service、Tortoise Model | 资产流程、审批规则、统计、通知、知识库及安全运营 |
| 数据与迁移 | SQLite、Tortoise ORM、Aerich、独立 RAG Store | 业务数据、迁移、知识库文档与检索索引 |
| 运行与部署 | Uvicorn、可选 Nginx、Docker / 原生模板 | 启动 API、托管前端、反向代理、备份与部署参考 |

### 当前模块边界

| 模块组 | 当前包含 | 代码入口 |
| --- | --- | --- |
| 组织与权限 | 用户、角色、菜单、API、部门、员工与账号绑定 | `app/models/admin.py`、`app/api/v1/users/`、`roles/`、`depts/`、`employees/` |
| 资产主数据 | 资产台账、状态、分类、位置、质保和二维码 | `app/models/business.py`、`app/api/v1/assets/`、`web/src/views/business/asset/` |
| 资产流程 | 领用归还、审批、调拨、报修和盘点 | `app/api/v1/asset_uses/`、`asset_transfers/`、`asset_repairs/`、`inventorys/` |
| 运营辅助 | 工作台、统计看板、通知、质保提醒、导入导出 | `app/services/dashboard_service.py`、`notification_service.py`、`warranty.py`、`export_service.py` |
| 知识与 AI | 本地知识库、词面/RAG 检索、引用回答、可选模型适配 | `app/services/rag_service.py`、`rag_store.py`、`ai_service.py`、`app/api/v1/ai/` |
| 安全运营 | 登录事件、风险聚合、查询筛选、验证策略和审计 | `app/api/v1/security/`、`app/services/security_agg.py`、`security_query.py` |

### 数据保存在哪里？

- `db/db.sqlite3`：运行时业务数据库，由 Tortoise ORM 访问；数据库文件不进入 Git。
- `db/rag.sqlite3`：知识库文档和检索分块的独立存储；同样属于运行时文件。
- 员工附件和上传内容：保存在运行时目录，通过登录与权限校验后的接口读取。
- 模型服务：属于可选外部能力，只在运行时填写自己的服务地址、模型和密钥，仓库不预置凭据。
- `migrations/` 与 `deploy/native/backup_sqlite_daily.sh`：分别负责结构迁移记录和本地数据库快照参考。

## 这个项目是怎样做出来的

项目不是一次生成后就结束，而是沿着四个阶段持续收口：先搭出 Python / Web 骨架，再统一接口、分页与校验，然后补齐权限隔离和核心业务，最后把 AI、测试、部署、备份和复盘接成可交付闭环。

本轮整理开始前，项目沉淀了 **42 份真实问题、修复与复盘记录**：**32 份专项修复、6 份问题发现、4 份阶段复盘**。部分复盘包含多个缺陷，因此这里描述的是“记录数”，不是虚构成恰好 42 个独立 Bug。本轮边整理边实现，又新增了业务筛选栏、测试基线和发布脚本 3 份修复记录，该轮公开展示整理完成时共有 45 篇。本次 GitHub 渲染验收另补 1 份公开展示修复记录，达到 46 篇；本轮公开历史审计再补 1 份事实漂移修复记录，最终为 47 篇。下方踩坑图保留 45 篇时的阶段快照，42 条原始历史索引保持不变。

![从能跑到可交付：项目踩坑地图](deploy/sample-picture/project-challenge-map.png)

最有代表性的六类困难是：前后端契约、状态机与事务、权限与隔离、安全与凭据、AI/RAG、部署与运维。正文没有把 42 篇原文全部塞进首页，而是精讲 12 个能体现判断过程的案例，并提供 42 条脱敏索引：

- 为什么 7 个业务页明明写了筛选项，浏览器却完全看不到；
- 为什么菜单权限正确仍不等于数据行和敏感字段安全；
- 为什么 embedding 失败后生成“假向量”比直接报错更危险；
- 为什么迁移、证书目录、探针和备份脚本都会影响最终交付。

### 代表性修复：员工筛选与导出条件一致

| 修复前：筛选组件落在错误插槽 | 修复后：五类条件可见并进入真实请求 |
|--------------------------------|--------------------------------------|
| ![员工页筛选修复前](deploy/sample-picture/screenshots/employees-before-filter-fix.png) | ![员工页筛选修复后](deploy/sample-picture/screenshots/employees-filter-and-sort.png) |

修复采用测试先行：先让契约测试证明 7 个页面缺少 `#queryBar`，再做最小修改；员工列表与 CSV 导出现在共用关键词、部门、状态、排序字段和排序方向，服务端排序只接受固定白名单。公开树回归结果为 **Python 145 项通过（2 项可选依赖跳过）、Node 契约 60 项通过、Vite 2,825 个模块完成转换**。

完整的四阶段对照、12 个代表案例、AI/人工边界、测试证据和 42 条脱敏历史索引见 [`PROJECT-JOURNEY.md`](./PROJECT-JOURNEY.md)。

## 第一次打开后，建议这样使用

1. 管理员先建立部门和员工档案，并为员工绑定登录账号。
2. 在“资产管理”登记资产编号、分类、状态、位置、价格和质保到期日。
3. 员工从业务工作台提交领用、归还、调拨或报修申请。
4. 部门主管处理本部门初审，管理员在审批中心完成终审。
5. 定期发起盘点，在统计看板和安全中心检查运营与登录情况。

## 主要功能截图与操作说明

以下截图全部来自 `127.0.0.1` 本地演示环境，仅使用虚构姓名、`example.com` 和演示资产编号，不包含线上数据。相关模块按真实业务顺序分组，全部功能证据继续保留。

### 登录与入口

| 登录：每次先完成滑块校验 | 管理端工作台：先看全局，再进模块 |
|---|---|
| <img src="deploy/sample-picture/screenshots/login.png" alt="登录与滑块校验"> | <img src="deploy/sample-picture/screenshots/workbench.png" alt="管理端工作台"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 登录 | 所有用户；超级管理员按策略增加动态验证 | 完成滑块、填写账号信息并登录 |
| 管理端工作台 | 管理员 | 查看资产、质保和待办概况，进入高频模块 |

### 岗位与主数据

| 员工 / 主管工作台 | 资产台账 |
|---|---|
| <img src="deploy/sample-picture/screenshots/work-portal.png" alt="员工和主管业务工作台"> | <img src="deploy/sample-picture/screenshots/assets.png" alt="资产管理台账"> |
| 员工档案 | 我的资产 |
| <img src="deploy/sample-picture/screenshots/employees.png" alt="员工管理"> | <img src="deploy/sample-picture/screenshots/my-assets.png" alt="员工我的资产"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 业务工作台 | 员工、部门主管 | 处理个人资产、申请和本部门待办 |
| 资产台账 | 管理员及获授权岗位 | 登记、筛选、导入和导出设备记录 |
| 员工档案 | 管理员 | 维护工号、部门、岗位、在职状态和账号绑定 |
| 我的资产 | 员工、部门主管 | 查看本人设备并按状态发起报修或调拨 |

### 资产流转

| 领用与归还 | 审批中心 |
|---|---|
| <img src="deploy/sample-picture/screenshots/asset-use.png" alt="资产领用归还"> | <img src="deploy/sample-picture/screenshots/approval.png" alt="审批中心"> |
| 资产调拨 | 资产报修 |
| <img src="deploy/sample-picture/screenshots/transfer.png" alt="资产调拨"> | <img src="deploy/sample-picture/screenshots/repair.png" alt="资产报修"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 领用归还 | 员工发起，主管和管理员审批 | 选择资产、提交申请、记录审批结果 |
| 审批中心 | 部门主管、管理员 | 集中处理初审、终审和驳回原因 |
| 调拨 | 当前领用人发起，主管和管理员审批 | 选择调入人，保留资产在用状态和流转历史 |
| 报修 | 员工、主管、管理员 | 提交故障、登记送修并记录修好后的去向 |

### 运营与盘点

| 资产盘点 | 统计看板 |
|---|---|
| <img src="deploy/sample-picture/screenshots/inventory.png" alt="资产盘点明细"> | <img src="deploy/sample-picture/screenshots/dashboard.png" alt="资产统计看板"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 盘点 | 管理员或主管发起，相关岗位参与 | 固化账面快照，逐台标记相符、盘亏或不符 |
| 统计看板 | 管理员、管理者 | 查看分类、状态、部门分布和近期流转趋势 |

### 知识、智能与治理

| 知识库 | AI 助手 |
|---|---|
| <img src="deploy/sample-picture/screenshots/kb.png" alt="知识库问答与引用"> | <img src="deploy/sample-picture/screenshots/ai.png" alt="AI 助手"> |
| 安全中心 | 手机扫码 |
| <img src="deploy/sample-picture/screenshots/security.png" alt="安全中心"> | <img src="deploy/sample-picture/screenshots/scan.png" alt="手机扫码资产详情"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 知识库 | 需要查询制度和操作说明的用户 | 上传 UTF-8 `txt/md`，提问并核对引用片段 |
| AI 助手 | 需要业务问答或辅助分析的用户 | 使用自己的模型配置进行资产和流程问答 |
| 安全中心 | 超级管理员 | 查看登录风险、封禁、验证策略、审计和证书状态 |
| 手机扫码 | 现场员工、主管或管理员 | 扫描资产码，按岗位权限查看详情并进入后续操作 |

### 权限与现场

| 用户管理 | 角色管理 |
|---|---|
| <img src="deploy/sample-picture/screenshots/users.png" alt="用户管理"> | <img src="deploy/sample-picture/screenshots/roles.png" alt="角色管理"> |

| 模块 | 使用者 | 主要操作 |
|---|---|---|
| 用户管理 | 超级管理员 | 维护账号状态并绑定岗位角色 |
| 角色管理 | 超级管理员 | 分配菜单和接口能力，保持角色、行范围和字段范围一致 |

## 权限与安全边界

- 管理员、部门主管和普通员工看到的入口与数据范围不同，接口侧也会再次校验。
- 登录滑块固定启用；动态验证器和操作再次验证按角色与策略执行。
- 首次超级管理员验证器设置属于安全基线；不要用 SQL 去关二次验证。
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
app/
├─ api/v1/          FastAPI 领域路由：资产、员工、流程、知识库、安全等
├─ controllers/     通用查询与管理控制器
├─ core/            应用初始化、中间件、认证、权限、异常与网关控制
├─ models/          Tortoise ORM 数据模型
├─ schemas/         Pydantic 输入输出模型
├─ services/        看板、通知、质保、RAG、AI、安全和导入导出服务
├─ settings/        环境变量与 ORM 配置
└─ utils/           网络、地理、风险、时间等通用工具

web/src/
├─ api/             与后端路由对应的请求封装
├─ views/business/  资产、员工、审批、调拨、报修、盘点等业务页面
├─ router/          路由定义与动态导航
├─ store/           Pinia 登录、权限和应用状态
├─ components/      可复用组件
└─ composables/     页面共享逻辑与操作验证封装

deploy/
├─ data/            可公开的知识库初始化语料
├─ native/          原生部署、反向代理与备份模板
├─ tests/           Python 单元测试与前端契约测试
├─ tools/           发布前检查和辅助工具
└─ sample-picture/  README 图片与架构图

migrations/         Aerich 数据库迁移
run.py              Uvicorn 启动入口
```

### 建议的代码阅读顺序

1. 从 `run.py`、`app/__init__.py` 和 `app/core/init_app.py` 看应用如何启动、挂载中间件和注册路由。
2. 从 `app/api/v1/__init__.py` 看所有 API 领域，再进入一个具体模块跟踪请求。
3. 对照 `app/models/business.py` 与 `app/schemas/` 理解数据模型和接口字段。
4. 在 `app/services/` 查看跨接口复用的业务能力，例如看板、通知、质保和知识库。
5. 对照 `web/src/api/` 与 `web/src/views/business/` 查看前端怎样调用接口并呈现流程。
6. 最后运行 `deploy/tests/`，用现有测试确认理解和扩展没有改变既定边界。

第三方组件与许可证说明见 [`NOTICE`](./NOTICE)。
