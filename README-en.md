<p align="center">
  <img alt="Asset Management System" width="96" src="web/public/resource/company-logo.jpg">
</p>

<h1 align="center">Asset Management System</h1>

<p align="center">
  <a href="./README.md">简体中文</a>
  ·
  <a href="./LICENSE">MIT License</a>
</p>

Employee and asset ledger: checkout, return, transfer, repair, inventory, approval, knowledge base, and security center.

## Screenshots

<p align="center">
  <img src="deploy/sample-picture/screenshots/login.png" alt="Login" width="720">
</p>

<p align="center">
  <img src="deploy/sample-picture/screenshots/workbench.png" alt="Admin workbench" width="900">
</p>

Screenshots use local demo data (`example.com`). They do not contain production hosts or credentials.

## Features

- Ledger, checkout/return, transfer, repair, inventory, dual portals
- Slider login, TOTP, step-up verification, security center
- Knowledge base and optional AI (bring your own key)

## Quick start

```bash
git clone https://github.com/LanSang11/asset-admin.git
cd asset-admin
python -m venv .venv
pip install -r requirements.txt
python run.py
```

See `README.md` for the full gallery and `README-部署与使用教程.md` for deployment.

### Directory
- `web/`: Vue3 front-end
- `app/`: FastAPI back-end
- `deploy/`: deployment templates
