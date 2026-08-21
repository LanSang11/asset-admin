<p align="center">
  <img alt="资产管理系统" width="200" src="deploy/sample-picture/logo.svg">
</p>

<h1 align="center">资产管理系统</h1>

员工与资产台账后台。FastAPI + Vue3 + Naive UI：RBAC、动态路由、JWT；员工、资产、领用/归还/审批、操作日志、导出与看板。依赖组件见 `NOTICE`。

### 特性
- **技术栈**：Python 3.11 + FastAPI 高性能异步框架，Vue3 + Vite 前端。
- **动态路由**：后端动态路由，结合 RBAC 权限模型，提供精细的菜单路由控制。
- **JWT 鉴权**：使用 JSON Web Token 进行身份验证和授权。
- **细粒度权限控制**：按钮和接口级别的权限控制，不同角色（超级管理员 / 部门主管 / 普通员工）所见内容不同。
- **操作日志**：增删改查与登录行为全记录，可追溯。
- **AI 助手**：可接入兼容 OpenAI 协议的大模型（需自行配置 Key，仓库内不含密钥）。

### 二次验证

登录时**不会**根据用户名提前探测是否开了 TOTP。未绑定账号一次就能进；已绑定账号在滑块+密码通过后才会出现 6 位框。

空库第一个 `admin` 是超级管理员，必须先在个人中心按向导绑定验证器（Google / Microsoft Authenticator 等），再重新登录后才能进后台。仓库和演示脚本**不会**预置已绑定密钥。不要用 SQL 去关二次验证。

导出、删用户、改角色、封禁等默认还要动态码或密码；建员工/资产不用。完整首次步骤见 `README-部署与使用教程.md` 第七节。

### 到期换密

安全中心可以设置「密码最长天数」或「全员截止日期」，**默认关闭**。打开后，过期账号只能先改密（沿用已有 `must_change_password`）。

### AI 配置

在 AI 助手里选 DeepSeek / OpenAI 新地址 / OpenAI 旧兼容，一般只粘贴自己的 Key。默认模型是 `deepseek-v4-flash`。未填 Key 不能外呼。助手是只读笼子：不能跑 SQL、Shell、读盘，也不会把密钥送给模型。

### 开源假数据

本地空库可写入张三/李四（`example.com`）：

```bash
set DEMO_PASSWORD=你的演示密码
python deploy/init_oss_demo_data.py --db app.db
```

脚本会拒绝现网路径。不要对云端库跑，也不要把 Key 或密码写进仓库。

### 本地部署
```bash
docker run -d --restart=always --name=asset-system -p 127.0.0.1:9999:80 asset-system:local
```
访问 http://localhost:9999

更完整的步骤见 `README-部署与使用教程.md`。

### 目录结构
- `web/`：Vue3 前端
- `app/`：FastAPI 后端
- `deploy/`：部署模板与脚本
