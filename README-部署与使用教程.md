# 资产管理系统

> 一个开箱即用的企业内部资产管理系统：员工管理、资产台账、领用归还、两级审批、站内通知、统计看板、AI 智能助手。
> 支持 **Windows / Linux / macOS** 三平台部署（Docker 方式或本地直接运行）。

---

## 一、系统简介

本系统面向企业内部资产管理场景，提供从「资产入库 → 员工领用 → 主管审批 → 管理员审批 → 归还」的完整闭环流程，
并内置安全防护（登录防爆破、接口权限、SSRF 防护、强密码策略、审计日志等）。

## 二、功能特性

| 模块 | 说明 |
|---|---|
| 登录/安全 | 首次登录强制改密、连续 5 次错误密码锁定 5 分钟、强密码策略（8~32 位含大小写/数字/符号） |
| 员工管理 | 员工增删改查、部门归属、在职状态 |
| 资产台账 | 资产登记、分类管理、状态流转（在用/闲置/维修/报废） |
| 领用归还 | 员工申请领用、归还登记、历史追溯（防越权：只能看自己的记录） |
| 两级审批 | 员工申请 → 主管审批 → 管理员审批 → 资产状态自动联动；任一级可驳回 |
| 站内通知 | 审批结果、系统消息实时通知（未读角标） |
| CSV 导出 | 员工/资产/领用记录导出（中文不乱码） |
| 统计看板 | 资产分类占比、状态分布、部门分布、7 天领用归还趋势、闲置列表、Top10 排行 |
| AI 助手 | 配置自己的 DeepSeek API Key（AES-256-GCM 加密存储），对话问答；相同提问命中语义缓存，不重复扣费 |

## 三、技术架构

```
浏览器 (Vue3 + Naive UI)
        │  http://127.0.0.1:9999
        ▼
Nginx（前端静态资源 + /api 反向代理，容器内 80 端口）
        │
        ▼
FastAPI 后端（Python 3.11，端口 9999）
   ├── Tortoise-ORM + SQLite（单文件数据库 db.sqlite3，拷走即迁移）
   ├── 网关层：限流 + 黑名单（持久化到 gateway_blacklist.json）
   ├── 业务层：API Key 加密、每用户并发锁、AI 调用频控
   ├── 权限层：角色→接口权限 + 服务端数据级兜底（防越权/IDOR）
   └── 语义缓存：AI 相同提问命中缓存（key 含 user_id+temperature+model）
```

## 四、环境要求

**方式 A（Docker，推荐）**
- Windows 10/11 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Linux 安装 Docker Engine（`sudo apt install docker.io` 或官方脚本）
- 建议内存 ≥ 2GB

**方式 B（本地直接运行）**
- Python 3.11+（Windows 从 python.org 安装，安装时勾选 Add to PATH）
- Node.js 18+（[nodejs.org](https://nodejs.org) 下载 LTS 版）
- 无需安装任何数据库（内置 SQLite）

## 五、部署方式一：Docker（推荐，最简单）

### 5.1 获取项目

把发布包解压到任意目录，或直接使用源码目录。以下命令在项目根目录执行。

### 5.2 方式 A：使用本地构建的镜像

> 本仓库不发布现成镜像。先按 5.3 构建，再用下面命令启动：

```bash
# Windows PowerShell / CMD 或 Linux 终端均可
docker run -d --restart=always --name=asset-system \
  -p 127.0.0.1:9999:80 \
  -v asset_data:/opt/asset-management-system/db \
  asset-system:local
```

- `-p 127.0.0.1:9999:80`：本机 9999 端口访问（只在本机开放，更安全；想对外访问改成 `-p 9999:80`）
- `-v asset_data:...`：数据卷持久化数据库（目录挂载，数据库为卷内 `db.sqlite3`），升级容器不丢数据

### 5.3 方式 B：从源码构建镜像

```bash
docker build -t asset-system:local .
docker run -d --restart=always --name=asset-system \
  -p 127.0.0.1:9999:80 \
  -v asset_data:/opt/asset-management-system/db \
  asset-system:local
```

> 构建使用国内镜像源（npm 淘宝源 + pip 清华源），通常 5~10 分钟完成。

### 5.4 获取初始登录密码（重要！）

**全新部署（数据库为空）时**，系统自动创建管理员账号 `admin`，密码为**随机生成的一次性密码**，
会打印在容器启动日志中：

```bash
docker logs asset-system
# 找到这一行（仅启动时出现一次）：
# 首次初始化超级管理员账号 admin，一次性初始密码（仅本次启动可见，首次登录后必须修改）：XXXXX
```

**已有数据（升级/迁移）时**：继续使用原系统账号密码，无需查看日志。

### 5.5 验证部署

浏览器打开 http://127.0.0.1:9999 ，看到登录页即部署成功。

## 六、部署方式二：本地直接运行（不装 Docker）

### 6.1 Windows 详细步骤

```bash
# 1. 打开 PowerShell / CMD，进入项目根目录
cd 项目根目录

# 2. 创建并激活 Python 虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装后端依赖（使用清华镜像加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 启动后端（终端 1）
python run.py

# 5. 另开一个终端，构建前端（终端 2）
cd web
npm ci
npm run build

# 6. 用 nginx 托管前端并代理 /api（见 deploy/web.conf 示例）
#    或开发调试时直接用开发服务器：
npm run dev    # 打开 http://127.0.0.1:3100 （已配置代理到后端 9999）
```

### 6.2 Linux 详细步骤

```bash
cd 项目根目录
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python run.py &

cd web
npm ci
npm run build
# 用 nginx 托管 web/dist，/api 反向代理到 127.0.0.1:9999（参考 deploy/web.conf）
```

## 七、首次登录与使用指南

空库第一个 `admin` 是超级管理员，**登录强制二次验证**。这是设计，不是故障。不要用 SQL 去关 `totp_enabled`。

1. **登录**：浏览器打开系统 → 完成滑块 → 输入 `admin` 与初始密码（见启动日志 / 5.4）
2. **强制改密**：首次登录会跳到修改密码页，设置自己的强密码（8~32 位，含大写/小写/数字/符号）
3. **绑定验证器（超管必做）**：改密后个人中心会落到「二次验证」
   - 手机安装 Google Authenticator / Microsoft Authenticator / 1Password
   - 点「开始绑定」，扫二维码（密钥只在本机画图，不会预置进仓库）
   - 自定义安全问题与答案，再填 App 里的 6 位动态码
   - 完成后重新登录
4. **之后每次登录**：滑块 + 密码 + 6 位动态码。未绑定的普通账号仍然一次就能进，系统不会按用户名提前探测
5. **建立基础数据**：系统管理 → 部门管理 → 员工管理 → 资产管理。建员工/资产不需要动态码
6. **日常流程**：
   - 员工登录 → 资产领用 → 提交申请
   - 主管登录 → 审批中心 → 通过/驳回（第一级）
   - 管理员登录 → 审批中心 → 通过（第二级）→ 资产自动变为"在用"
   - 员工归还 → 主管/管理员审批 → 资产变回"闲置"
7. **高危操作**：导出、删用户、改角色授权、封禁/解封会再要动态码；未绑定会提示去个人中心。本地想少弹窗：先绑定，再在安全中心逐项改（改策略本身仍要动态码）
8. **现网临时免登录动态码**（仅已上线的演示机）：安全中心开启「限时验收模式」2 小时，到期自动恢复。不要做成永久关闭
9. **AI 助手**：业务 → AI 助手 → 选厂商后只粘贴自己的 Key（仓库不含密钥）→ 开始对话

## 八、数据备份与迁移

- **Docker 部署**：数据库在数据卷 `asset_data` 的 `db/db.sqlite3` 中
  ```bash
  docker run --rm -v asset_data:/data -v %cd%:/backup alpine sh -c "cp /data/db/db.sqlite3 /backup/"
  ```
- **本地部署**：直接拷贝项目根目录 `db/` 目录下的 `db.sqlite3` 文件即可
- 迁移到新机器：拷贝 `db/db.sqlite3` → 新机器按上述方式启动 → 数据完整
- **旧版升级**：旧版数据库在项目根 `db.sqlite3`（单文件），升级到新版本前先把它复制到数据卷/数据目录并命名为 `db/db.sqlite3`，否则会初始化成空库
- **重要**：`db.sqlite3` 内含密码哈希与加密的 API Key，请妥善保管，不要外泄

## 九、环境变量配置表

| 变量 | 说明 | 默认值 |
|---|---|---|
| `SECRET_KEY` | JWT 签名与 API Key 加密密钥（生产强烈建议设置） | 自动生成到 `.secret_key` 文件 |
| `SHOW_DOCS` | 是否开放 Swagger 接口文档（`1` 开启） | 关闭（更安全） |
| `CORS_ORIGINS` | 跨域白名单（JSON 数组字符串） | `["http://127.0.0.1:9999","http://localhost:9999"]` |

示例（Docker 部署时传入）：
```bash
docker run -d --restart=always --name=asset-system \
  -p 127.0.0.1:9999:80 \
  -e SECRET_KEY=请换成自己的随机字符串 \
  -v asset_data:/opt/asset-management-system/db \
  asset-system:local
```

> 说明：新用户创建由管理员在系统内设置密码；密码被重置时系统生成**随机一次性密码**并打印到服务日志（无任何公开默认密码）。

## 十、安全说明（发布前必读）

1. **立即修改默认密码**：部署后第一时间登录并修改 `admin` 密码（初始密码为随机生成，见 5.4）
2. **生产环境设置 `SECRET_KEY`**：不要依赖自动生成的 `.secret_key` 文件（丢失后所有加密数据无法解密）
3. **对外暴露需谨慎**：默认只监听 `127.0.0.1`（本机）；公网部署请务必启用 HTTPS、修改默认端口
4. **内置防护**：登录防爆破（5 次锁定）、强密码策略、接口权限校验、SSRF 防护、CSV 注入防护、审计日志脱敏与截断、错误信息不回显内部细节
5. **已声明边界**：限流/并发锁为单进程实现（请保持单 worker 部署）；SSRF 为静态校验（DNS rebinding 需出口防火墙兜底）；语义缓存无 TTL（满 200 条自动清空）

## 十一、常见问题（FAQ）

**Q1：登录提示"用户名或密码错误"？**
初始密码见 5.4（全新部署）或使用原系统密码（已有数据）；连续输错 5 次会被锁定 5 分钟。

**Q2：忘记 admin 密码怎么办？**
用源码包中的重置脚本（脚本未打进 Docker 镜像，需在源码目录/已装依赖的环境执行；密码通过环境变量传入，不回显）：
```bash
# 方式一：本地源码运行环境
ADMIN_PASSWORD='你的新强密码' DB_PATH=./db/db.sqlite3 python3 deploy/reset_admin_password.py
# 方式二：Docker 场景（脚本已打进镜像，直接执行）
docker exec -e ADMIN_PASSWORD='你的新强密码' asset-system sh -c "cd /opt/asset-management-system && python deploy/reset_admin_password.py"
```
重置后 admin 需首次登录改密。

**Q3：端口 9999 被占用？**
改 `-p` 参数映射其他端口，如 `-p 8080:80`，访问 `http://127.0.0.1:8080`。

**Q4：CSV 导出中文乱码？**
系统已内置 UTF-8 BOM 导出（Excel 打开不乱码）；如仍乱码请用最新版浏览器/Office。

**Q5：AI 助手报错？**
确认已配置自己的 API Key；上游服务异常时系统只提示状态码，可查看后端日志定位。

**Q6：如何升级版本？**
停止旧容器 → 用新镜像重新 `docker run`（保持同一个数据卷名）→ 数据自动保留。

## 十二、目录结构说明

```
├── app/                    # 后端源码（FastAPI）
│   ├── api/v1/             # 接口层（路由）
│   ├── controllers/        # 业务控制层
│   ├── core/               # 安全核心（网关限流/登录防护/中间件/异常处理）
│   ├── models/             # 数据模型（Tortoise-ORM）
│   ├── services/           # 业务服务（AI/看板/导出）
│   └── utils/              # 工具（SSRF 校验/加密/密码）
├── web/                    # 前端源码（Vue3 + Vite + Naive UI）
├── deploy/                 # 部署相关（nginx 配置/脚本/单元测试）
├── db.sqlite3              # SQLite 数据库文件（运行时生成，勿提交）
├── Dockerfile              # 镜像构建文件
├── requirements.txt        # 后端依赖
└── run.py                  # 后端启动入口
```

---

> 资产管理系统 · 部署教程 v2.6.4
