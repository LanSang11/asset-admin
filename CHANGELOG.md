# Changelog

Public, sanitized notes only. Internal runbooks, server paths, IPs, and secrets never belong here.

## 2026-09-14

- **SECRET_KEY rotation vs TOTP**: If `user.totp_secret` is stored as `enc:v1:` ciphertext derived from `SECRET_KEY`, rotating the key without re-encrypting that column makes login treat a bound authenticator as missing. A superuser can then pass password + captcha, skip the 6-digit code, and get stuck in a security-setup session whose UI still says TOTP is enabled (no re-bind button). Fix: decrypt with the previous key, encrypt with the new key, then log in again with the **existing** authenticator. Product source code was unchanged.

## 2026-08-22

- Public documentation and gallery refresh (`31f5e0d`). See `PROJECT-JOURNEY.md`.
