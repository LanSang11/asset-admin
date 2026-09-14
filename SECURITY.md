# Security notes

- Never commit `.secret_key`, `.env`, `*.sqlite3`, or API keys.
- On first run the app creates `.secret_key` locally if `SECRET_KEY` is unset.
- Demo account passwords must come from `DEMO_PASSWORD` / `ADMIN_PASSWORD` environment variables.
- Replace `asset.example.com` and CORS origins before exposing the service.
- If TOTP secrets are stored as `enc:v1:` ciphertext derived from `SECRET_KEY`, **rotating `SECRET_KEY` requires re-encrypting `user.totp_secret`** (and any other field that uses the same helper) before you rely on login. After rotation, a superuser login must still challenge for the 6-digit authenticator code. See `CHANGELOG.md` (2026-09-14).
