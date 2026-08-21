"""Read and renew the public HTTPS certificate via a root helper."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Optional

from app.settings import settings

_OPENSSL_DATE_FMT = "%b %d %H:%M:%S %Y %Z"


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_openssl_date(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, _OPENSSL_DATE_FMT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def days_left(expires: Optional[datetime], now: Optional[datetime] = None) -> Optional[int]:
    aware_exp = _aware(expires)
    if aware_exp is None:
        return None
    current = _aware(now) or datetime.now(timezone.utc)
    return int((aware_exp - current).total_seconds() // 86400)


def parse_openssl_text(text: str) -> dict[str, Any]:
    subject = issuer = not_before = not_after = ""
    san: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("subject="):
            subject = line.split("=", 1)[1].strip()
        elif line.startswith("issuer="):
            issuer = line.split("=", 1)[1].strip()
        elif line.startswith("notBefore="):
            not_before = line.split("=", 1)[1].strip()
        elif line.startswith("notAfter="):
            not_after = line.split("=", 1)[1].strip()
        elif "DNS:" in line:
            for part in line.split(","):
                part = part.strip()
                if part.startswith("DNS:"):
                    san.append(part[4:].strip())
    before = parse_openssl_date(not_before)
    after = parse_openssl_date(not_after)
    return {
        "subject": subject,
        "issuer": issuer,
        "san": san,
        "not_before": before.isoformat() if before else None,
        "not_after": after.isoformat() if after else None,
        "days_left": days_left(after),
    }


def _read_cert_file(path: str) -> Optional[dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    try:
        proc = subprocess.run(
            ["openssl", "x509", "-in", path, "-noout", "-subject", "-issuer", "-dates", "-ext", "subjectAltName"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if "notAfter=" not in blob:
        return None
    parsed = parse_openssl_text(blob)
    parsed["cert_path"] = path
    parsed["readable"] = True
    return parsed


def _run_helper(action: str) -> dict[str, Any]:
    helper = getattr(settings, "TLS_HELPER", "") or ""
    if not helper or not os.path.isfile(helper):
        return {"ok": False, "error": "helper_missing"}
    try:
        proc = subprocess.run(
            ["sudo", "-n", helper, action],
            capture_output=True,
            text=True,
            timeout=180 if action == "renew" else 20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": "helper_failed", "detail": str(exc)[:240]}
    raw = (proc.stdout or "").strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"ok": False, "error": "helper_bad_json", "detail": raw[:400]}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "helper_bad_json"}
    if proc.returncode != 0 and payload.get("ok") is not False:
        payload["ok"] = False
        payload.setdefault("error", "helper_exit")
        payload.setdefault("detail", (proc.stderr or "")[:400])
    return payload


def _base_payload() -> dict[str, Any]:
    return {
        "domain": getattr(settings, "TLS_DOMAIN", "asset.example.com"),
        "https_url": getattr(settings, "TLS_HTTPS_URL", "https://asset.example.com"),
        "http_fallback_url": getattr(settings, "TLS_HTTP_FALLBACK_URL", "http://127.0.0.1:9999"),
        "installed": False,
        "auto_renew_enabled": True,
        "auto_renew_mechanism": "宝塔每日定时续签（acme_v2），到期前约 30 天自动执行",
    }


def tls_status() -> dict[str, Any]:
    data = _base_payload()
    cert = _read_cert_file(getattr(settings, "TLS_CERT_PATH", "") or "")
    helper = _run_helper("status")
    if helper.get("ok") and isinstance(helper.get("data"), dict):
        data.update(helper["data"])
    elif cert:
        data.update(cert)
        data["installed"] = True
    elif helper.get("error") == "helper_missing":
        data["detail"] = "本机未安装续签助手，只显示已配置的证书路径"
    else:
        data["detail"] = helper.get("detail") or helper.get("error") or "尚未读取到证书"
    if data.get("not_after") and data.get("days_left") is None:
        try:
            data["days_left"] = days_left(datetime.fromisoformat(str(data["not_after"])))
        except ValueError:
            pass
    if data.get("not_after"):
        data["installed"] = True
    return data


def tls_renew() -> dict[str, Any]:
    helper = _run_helper("renew")
    status = tls_status()
    status["renew"] = {
        "ok": bool(helper.get("ok")),
        "skipped": bool(helper.get("skipped")),
        "message": helper.get("message") or helper.get("detail") or helper.get("error") or "",
        "raw_excerpt": (helper.get("log") or "")[:600],
    }
    return status
