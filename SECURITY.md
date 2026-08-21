# Security notes

- Never commit `.secret_key`, `.env`, `*.sqlite3`, or API keys.
- On first run the app creates `.secret_key` locally if `SECRET_KEY` is unset.
- Demo account passwords must come from `DEMO_PASSWORD` / `ADMIN_PASSWORD` environment variables.
- Replace `asset.example.com` and CORS origins before exposing the service.
