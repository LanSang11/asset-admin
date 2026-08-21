# 原生部署（无 Docker）— 本地审查 + 云端公网演示

> 适用：云主机内存小、不加钱扩容；本机改代码，云端同构运行。  
> 总现状见：`docs/03-部署运维/00-真实现状与双端策略.md`

---

## 架构（云端）

```
浏览器  https://asset.example.com
    → 系统 Nginx（443 SNI，与博客分站点）
         ├─ /        → web/dist 静态
         └─ /api/    → 127.0.0.1:8000（uvicorn）
兼容入口  http://公网IP:9999  仍保留
```

- **不改** 博客 `example.com` 的站点文件；只新增 `asset.example.com` 这个 server_name  
- **不使用** Docker 构建资产系统（蜜罐 cowrie 可继续单独用 Docker）

---

## 目录约定（本地 = 云端）

| 本地 | 云端 |
|------|------|
| `/path/to/workspace/asset-system\` | `/var/www/asset-system/` |

建议云端目录内容：

```
asset-system/
  app/
  web/dist/          # 本机构建后上传
  deploy/native/     # nginx / systemd 模板
  db/                # db.sqlite3（持久化）
  venv/              # 仅云端生成，勿从 Windows 拷贝
  run.py
  requirements.txt
```

---

## A. 本机运行（审查 / 开发）

### 后端

```bat
cd /d /path/to/workspace/asset-system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python run.py
```

浏览器：http://127.0.0.1:9999  
（若仅起了 API、静态未挂 Nginx：开发可用 `cd web && npm run dev`）

### 前端生产构建（改完 UI 后）

```bat
cd /d /path/to/workspace/asset-system\web
npm ci
npm run build
```

产物：`web/dist/`（上传云端用这个，**不要**传 `node_modules`）

### 数据库路径

配置使用：`项目根/db/db.sqlite3`  
请保证 `db` 目录存在；不要只依赖项目根零散的 `db.sqlite3` 文件名错位。

---

## B. 云端运行（公网审查）— 步骤概要

> 需服务器 **Python ≥ 3.10（推荐 3.11）**。系统自带 3.6 **不够**。

1. 安装 Python 3.11（宝塔 Python 项目管理器 / Miniconda / 官方包，任选）  
2. 上传精简树（或 zip）到 `/var/www/asset-system`  
3. 创建 venv 并 `pip install -r requirements.txt`  
4. 使用本目录 `nginx-asset-9999.conf` 挂到宝塔/ Nginx（listen **9999**）  
5. 使用 `asset-system.service` 托管 uvicorn（监听 **127.0.0.1:8000**）  
6. `curl -I http://127.0.0.1:9999/` 与公网访问验证  

详细命令以实施时 `deploy_native` 脚本或操作记录为准。

### 环境变量示例（云端 systemd）

```bash
# 公网 IP 换成你的
CORS_ORIGINS=["http://YOUR_PUBLIC_IP:9999","http://127.0.0.1:9999"]
PROXY_HEADERS=1
FORWARDED_ALLOW_IPS=127.0.0.1
# 可选：SHOW_DOCS=0
```

### 业务端口与进程

| 组件 | 地址 |
|------|------|
| 公网入口 | `0.0.0.0:9999`（Nginx） |
| 后端 API | `127.0.0.1:8000`（uvicorn，不直接暴露更佳） |
| 数据 | `/var/www/asset-system/db/db.sqlite3` |

---

## C. 同步清单（本地 → 云）

**上传：** `app/`、`web/dist/`、`run.py`、`requirements.txt`、`deploy/native/`、`db/`（按需）  

**禁止上传：** `web/node_modules/`、`.git/`、本机 `venv/`、私钥、`.env` 里的生产机密（若有）

---

## D. 模板文件

| 文件 | 说明 |
|------|------|
| `nginx-asset-9999.conf` | Nginx 站点片段（9999） |
| `asset-system.service` | systemd 用户服务模板（路径按服务器改） |
| `env.cloud.example` | 云端环境变量示例（无密钥） |

---

## E. 尚未自动执行

本文与模板仅方便**本地审查「云端将如何跑」**。  
真正连服务器安装 Python / 上传 / 启动，需你明确下令「开始原生上云」后再执行。
