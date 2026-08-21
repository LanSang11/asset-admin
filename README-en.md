<p align="center">
  <img alt="Asset Management System" width="200" src="deploy/sample-picture/logo.svg">
</p>

<h1 align="center">Asset Management System</h1>

English | [简体中文](./README.md)

Employee and asset ledger admin. FastAPI + Vue3 + Naive UI: RBAC, dynamic routing, JWT; employees, assets, use/return/approval, audit logs, export, and dashboards. Third-party components are listed in `NOTICE`.

### Features
- **Tech Stack**: Python 3.11 + FastAPI async framework, Vue3 + Vite front-end.
- **Dynamic Routing**: Backend-driven dynamic routing combined with RBAC.
- **JWT Authentication**: Identity verification and authorization via JSON Web Tokens.
- **Granular Permission Control**: Button and API level permissions for Super Admin / Department Manager / Employee.
- **Operation Logs**: Audit trail of CRUD operations and login events.
- **AI Assistant**: Optional OpenAI-compatible LLM (bring your own key; no keys in the repo).

### Local Deployment
```bash
docker run -d --restart=always --name=asset-system -p 127.0.0.1:9999:80 asset-system:local
```
Visit http://localhost:9999

### Directory
- `web/`: Vue3 front-end
- `app/`: FastAPI back-end
- `deploy/`: deployment templates
