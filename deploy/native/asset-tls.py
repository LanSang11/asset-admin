#!/usr/bin/python3.11
"""asset-tls status|renew — root helper, no extra args."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "asset.example.com"
WEBROOT = Path("/var/www/asset-system/acme")
CERT_DIR = Path(f"/etc/letsencrypt/live/{DOMAIN}")
CERT_FILE = CERT_DIR / "fullchain.pem"
ACME = ["/usr/bin/python3", "/usr/bin/certbot"]
STATE_FILE = Path("/var/www/asset-system/data/tls-renew-state.json")
CRON_LOG = Path("/var/log/asset-tls-renew.log")


def emit(payload: dict, code: int = 0) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    return code


def parse_openssl_date(raw: str):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cert_info() -> dict:
    if not CERT_FILE.is_file():
        return {"installed": False}
    proc = subprocess.run(
        [
            "openssl",
            "x509",
            "-in",
            str(CERT_FILE),
            "-noout",
            "-subject",
            "-issuer",
            "-dates",
            "-ext",
            "subjectAltName",
        ],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    subject = issuer = ""
    not_before = not_after = None
    san = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("subject="):
            subject = line.split("=", 1)[1].strip()
        elif line.startswith("issuer="):
            issuer = line.split("=", 1)[1].strip()
        elif line.startswith("notBefore="):
            not_before = parse_openssl_date(line.split("=", 1)[1])
        elif line.startswith("notAfter="):
            not_after = parse_openssl_date(line.split("=", 1)[1])
        elif "DNS:" in line:
            san.extend(re.findall(r"DNS:([^,\s]+)", line))
    days = None
    if not_after:
        days = int((not_after - datetime.now(timezone.utc)).total_seconds() // 86400)
    return {
        "installed": True,
        "subject": subject,
        "issuer": issuer,
        "san": san,
        "not_before": not_before.isoformat() if not_before else None,
        "not_after": not_after.isoformat() if not_after else None,
        "days_left": days,
        "cert_path": str(CERT_FILE),
    }


def cron_info() -> dict:
    if not CRON_LOG.is_file():
        return {}
    text = CRON_LOG.read_text(encoding="utf-8", errors="replace")
    times = re.findall(r"★\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", text)
    tail = text[-1600:]
    window = None
    match = re.search(r"CA建议窗口为 ([^，\n]+至[^，\n]+)", tail)
    if match:
        window = match.group(1)
    return {
        "last_cron_at": times[-1] if times else None,
        "last_cron_skipped": "本次跳过" in tail,
        "suggested_window": window,
    }


def manual_info() -> dict:
    if not STATE_FILE.is_file():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "last_manual_renew_at": data.get("at"),
        "last_manual_result": data.get("message"),
        "last_manual_ok": data.get("ok"),
    }


def write_state(ok: bool, skipped: bool, message: str) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "ok": ok,
                "skipped": skipped,
                "message": message,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def reload_nginx() -> None:
    check = subprocess.run(["nginx", "-t"], capture_output=True, text=True, timeout=15, check=False)
    if check.returncode == 0:
        subprocess.run(["nginx", "-s", "reload"], capture_output=True, text=True, timeout=15, check=False)


def status_payload() -> dict:
    data = {
        "domain": DOMAIN,
        "https_url": f"https://{DOMAIN}",
        "http_fallback_url": "http://127.0.0.1:9999",
        "auto_renew_enabled": True,
        "auto_renew_mechanism": "宝塔每日定时续签（acme_v2），到期前约 30 天自动执行",
    }
    data.update(cert_info())
    data.update(cron_info())
    data.update(manual_info())
    return data


def apply_or_renew() -> dict:
    WEBROOT.joinpath(".well-known/acme-challenge").mkdir(parents=True, exist_ok=True)
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    if CERT_FILE.is_file():
        cmd = ACME + ["--renew_v2=1", "--cycle", "90"]
    else:
        cmd = ACME + ["--domain", DOMAIN, "--type", "http", "--path", str(WEBROOT)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=170, check=False)
    log = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if CERT_FILE.is_file():
        try:
            CERT_FILE.chmod(0o644)
        except OSError:
            pass
    key_file = CERT_DIR / "privkey.pem"
    if key_file.is_file():
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
    reload_nginx()
    skipped = "本次跳过" in log
    success = bool(re.search(r"成功|success|Renewed|已续签|申请成功", log, re.I))
    if skipped:
        return {"ok": True, "skipped": True, "message": "尚未到证书建议续签窗口，当前证书仍然有效", "log": log[-800:]}
    if success or (CERT_FILE.is_file() and proc.returncode == 0):
        return {"ok": True, "skipped": False, "message": "证书已续签或签发成功", "log": log[-800:]}
    return {"ok": False, "skipped": False, "message": "续签未完成，请查看续签日志", "log": log[-800:]}


def main(argv: list[str]) -> int:
    action = argv[1] if len(argv) > 1 else ""
    if action == "status":
        return emit({"ok": True, "data": status_payload()})
    if action == "renew":
        result = apply_or_renew()
        write_state(bool(result.get("ok")), bool(result.get("skipped")), result.get("message") or "")
        return emit(result, 0 if result.get("ok") else 1)
    return emit({"ok": False, "error": "bad_action"}, 2)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
