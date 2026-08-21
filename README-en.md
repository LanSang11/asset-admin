<p align="center">
  <img alt="Asset Management System" width="96" src="web/public/resource/company-logo.jpg">
</p>

<h1 align="center">Asset Management System</h1>

<p align="center">
  Turn scattered spreadsheets, chat messages, and paper records into a clear asset workflow for administrators, managers, and employees.
</p>

<p align="center">
  <a href="./README.md">简体中文</a>
  ·
  <a href="./README-部署与使用教程.md">Deployment Guide</a>
  ·
  <a href="./LICENSE">MIT License</a>
</p>

## Who is it for?

- **Asset administrators** maintain employees, devices, locations, prices, warranties, and lifecycle status in one place.
- **Employees** see their assigned devices and submit checkout, return, transfer, or repair requests.
- **Department managers** review requests from their own departments before final administrator approval.
- **Management** gets operational dashboards, inventory reconciliation, and security visibility.

## Typical workflow

1. Create departments and employee profiles.
2. Register assets and warranty dates.
3. Employees submit requests from the work portal.
4. Managers review department requests; administrators perform final approval.
5. Reconcile assets through inventory tasks and review the dashboards.

## Product tour

### Admin workbench

<p align="center">
  <img src="deploy/sample-picture/screenshots/workbench.png" alt="Admin workbench" width="900">
</p>

An administrator sees asset totals, lifecycle status, warranty attention, and shortcuts to daily operations.

### Employee and manager portal

<p align="center">
  <img src="deploy/sample-picture/screenshots/work-portal.png" alt="Employee and manager portal" width="900">
</p>

The portal focuses on personal assets, requests, and department approval tasks instead of exposing the full administration console.

### Asset ledger and employee directory

| Asset ledger | Employee directory |
| --- | --- |
| <img src="deploy/sample-picture/screenshots/assets.png" alt="Asset ledger"> | <img src="deploy/sample-picture/screenshots/employees.png" alt="Employee directory"> |

### Checkout, approval, transfer, and repair

| Checkout and return | Approval center |
| --- | --- |
| <img src="deploy/sample-picture/screenshots/asset-use.png" alt="Checkout and return"> | <img src="deploy/sample-picture/screenshots/approval.png" alt="Approval center"> |
| Transfer | Repair |
| <img src="deploy/sample-picture/screenshots/transfer.png" alt="Asset transfer"> | <img src="deploy/sample-picture/screenshots/repair.png" alt="Asset repair"> |

Requests retain the asset, applicant, reviewers, status, comments, and timestamps. An approved transfer keeps the asset in use while changing its assignee.

### Inventory reconciliation

<p align="center">
  <img src="deploy/sample-picture/screenshots/inventory.png" alt="Inventory reconciliation" width="900">
</p>

Start an inventory session, compare each asset with the recorded snapshot, and mark it as found, missing, or mismatched. A missing result is recorded for review and does not automatically retire an asset.

### Knowledge base and optional AI

| Knowledge base | AI assistant |
| --- | --- |
| <img src="deploy/sample-picture/screenshots/kb.png" alt="Knowledge base with citations"> | <img src="deploy/sample-picture/screenshots/ai.png" alt="Optional AI assistant"> |

Upload UTF-8 `.txt` or `.md` instructions, ask questions, and review citations. The optional AI assistant uses your own provider configuration; no model credential is included in the repository.

### Security center and mobile asset view

| Security center | Mobile asset detail |
| --- | --- |
| <img src="deploy/sample-picture/screenshots/security.png" alt="Security center"> | <img src="deploy/sample-picture/screenshots/scan.png" alt="Mobile asset detail"> |

The security center summarizes sign-in events, risk labels, verification policies, bans, and certificate status. QR codes open an asset-number detail route while preserving role-based data access.

The full 18-image walkthrough, including user/role management and personal assets, is available in the [Chinese README](./README.md).

## Quick start

Requirements: Python 3.11+ and Node.js 18+.

```bash
git clone https://github.com/LanSang11/asset-admin.git
cd asset-admin

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

In another terminal:

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:3100`. A new empty installation prints a one-time administrator credential in the backend log and guides the administrator through the required first-time setup.

See [`README-部署与使用教程.md`](./README-部署与使用教程.md) for Docker, local deployment, backup, and first-login details.

## Project structure

```text
app/        FastAPI backend and business services
web/        Vue 3 frontend
deploy/     Deployment templates, demo tools, tests, and screenshots
migrations/ Database migrations
```

Third-party notices are listed in [`NOTICE`](./NOTICE).
