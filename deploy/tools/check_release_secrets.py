"""Fail closed when a deployable tree/archive contains credential material.

The scanner reports only finding codes, labels and file locations. Sensitive
values are kept in memory and are never included in stdout/stderr.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Iterable
import zipfile


SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
TEXT_LITERAL_RE = re.compile(r'''(?x)(?:"([^"\r\n]{4,128})"|'([^'\r\n]{4,128})')''')


# Unbounded substring match on these values floods the official package
# (role names, schema examples, comments). They are never current secrets.
GENERIC_USERNAMES = frozenset(
    {
        "admin",
        "root",
        "user",
        "test",
        "guest",
        "demo",
        "administrator",
        "mysql",
        "postgres",
        "ubuntu",
        "operator",
        "ftp",
    }
)
WEAK_SECRET_EXAMPLES = frozenset(
    {
        "123456",
        "1234567",
        "12345678",
        "123456789",
        "password",
        "admin123",
        "root123",
        "111111",
        "qwerty",
        "passw0rd",
    }
)
USERNAME_SUFFIXES = ("_USERNAME",)
SECRET_SUFFIXES = ("_PASSWORD", "_TOKEN", "_SECRET", "_API_KEY")
WORD_BOUNDARY_RE_TEMPLATE = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"


@dataclass(frozen=True)
class SensitiveValue:
    label: str
    value: bytes
    match_mode: str = "substring"


@dataclass(frozen=True)
class RetiredFingerprint:
    label: str
    length: int
    sha256: str


@dataclass(frozen=True)
class Finding:
    code: str
    location: str
    label: str = ""


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _charset_classes(value: str) -> int:
    classes = 0
    if any(ch.islower() for ch in value):
        classes += 1
    if any(ch.isupper() for ch in value):
        classes += 1
    if any(ch.isdigit() for ch in value):
        classes += 1
    if any(not ch.isalnum() for ch in value):
        classes += 1
    return classes


def _is_generic_username(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered in GENERIC_USERNAMES:
        return True
    return len(lowered) < 6


def _is_low_entropy_secret(value: str) -> bool:
    if len(value) < 8:
        return True
    if value.lower() in WEAK_SECRET_EXAMPLES:
        return True
    return _charset_classes(value) <= 1


def classify_sensitive_value(key: str, value: str) -> SensitiveValue | None:
    """Decide whether a fixture slot is scannable, and how.

    Usernames and low-entropy examples must not use unbounded byte
    substring matching. Target employee/manager secrets stay exact.
    """
    if not value or len(value) < 4:
        return None
    key = key.strip().upper()
    encoded = value.encode("utf-8")
    if key.endswith(USERNAME_SUFFIXES):
        if _is_generic_username(value):
            return None
        return SensitiveValue(label=key, value=encoded, match_mode="word_boundary")
    if key.endswith(SECRET_SUFFIXES):
        if _is_low_entropy_secret(value):
            return None
        return SensitiveValue(label=key, value=encoded, match_mode="substring")
    return None


def collect_sensitive_values(env_path: Path) -> list[SensitiveValue]:
    """Load credential fixture values without logging them."""
    values: list[SensitiveValue] = []
    for raw in Path(env_path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        classified = classify_sensitive_value(key, _unquote(raw_value))
        if classified is not None:
            values.append(classified)
    return values


def load_retired_fingerprints(path: Path | None) -> list[RetiredFingerprint]:
    if path is None or not Path(path).is_file():
        return []
    fingerprints: list[RetiredFingerprint] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            label, length, digest = line.split("|", 2)
            parsed = RetiredFingerprint(label=label, length=int(length), sha256=digest.lower())
        except (TypeError, ValueError):
            raise ValueError("retired credential fingerprint file has an invalid row") from None
        if parsed.length < 4 or not re.fullmatch(r"[0-9a-f]{64}", parsed.sha256):
            raise ValueError("retired credential fingerprint file has an invalid row")
        fingerprints.append(parsed)
    return fingerprints


def _forbidden_path(name: str) -> bool:
    normalized = name.replace("\\", "/").lstrip("./")
    parts = tuple(part.lower() for part in PurePosixPath(normalized).parts)
    if any(part in {"secrets", ".git"} for part in parts):
        return True
    basename = parts[-1] if parts else ""
    if basename in {".env", "accounts.env", "id_rsa", "id_ed25519"}:
        return True
    return basename.endswith((".sqlite", ".sqlite3", ".db", ".pem", ".p12", ".pfx"))


def _retired_matches(payload: bytes, fingerprints: list[RetiredFingerprint]) -> set[str]:
    if not fingerprints:
        return set()
    text = payload.decode("utf-8", "ignore")
    candidates = set()
    for match in TEXT_LITERAL_RE.finditer(text):
        candidate = match.group(1) if match.group(1) is not None else match.group(2)
        if candidate:
            candidates.add(candidate)
    matches: set[str] = set()
    for candidate in candidates:
        encoded = candidate.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        for fingerprint in fingerprints:
            if len(candidate) == fingerprint.length and digest == fingerprint.sha256:
                matches.add(fingerprint.label)
    return matches


def _word_boundary_hit(payload: bytes, value: bytes) -> bool:
    try:
        text = payload.decode("utf-8")
        needle = value.decode("utf-8")
    except UnicodeDecodeError:
        return False
    pattern = WORD_BOUNDARY_RE_TEMPLATE.format(re.escape(needle))
    return re.search(pattern, text) is not None


def _scan_payload(
    location: str,
    payload: bytes,
    values: list[SensitiveValue],
    retired: list[RetiredFingerprint],
) -> list[Finding]:
    findings: list[Finding] = []
    for item in values:
        if item.match_mode == "word_boundary":
            hit = _word_boundary_hit(payload, item.value)
        else:
            hit = item.value in payload
        if hit:
            findings.append(Finding(code="credential_value", location=location, label=item.label))
    for label in sorted(_retired_matches(payload, retired)):
        findings.append(Finding(code="retired_credential", location=location, label=label))
    return findings


def scan_archive(
    archive_path: Path,
    env_path: Path,
    retired_fingerprint_path: Path | None = None,
) -> list[Finding]:
    values = collect_sensitive_values(env_path)
    retired = load_retired_fingerprints(retired_fingerprint_path)
    findings: list[Finding] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if _forbidden_path(info.filename):
                findings.append(Finding(code="forbidden_path", location=info.filename))
            payload = archive.read(info)
            findings.extend(_scan_payload(info.filename, payload, values, retired))
    return findings


def _tree_files(root: Path) -> Iterable[Path]:
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def scan_tree(
    root: Path,
    env_path: Path,
    retired_fingerprint_path: Path | None = None,
) -> list[Finding]:
    values = collect_sensitive_values(env_path)
    retired = load_retired_fingerprints(retired_fingerprint_path)
    findings: list[Finding] = []
    for path in _tree_files(Path(root)):
        rel = path.relative_to(root).as_posix()
        if _forbidden_path(rel):
            findings.append(Finding(code="forbidden_path", location=rel))
        findings.extend(_scan_payload(rel, path.read_bytes(), values, retired))
    return findings


def render_findings(findings: Iterable[Finding]) -> str:
    rows = []
    for finding in findings:
        label = f" label={finding.label}" if finding.label else ""
        rows.append(f"{finding.code} location={finding.location}{label}")
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan release artifacts without echoing credential values")
    parser.add_argument("--secrets-env", type=Path, required=True)
    parser.add_argument("--retired-fingerprints", type=Path)
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--tree", type=Path, action="append", default=[])
    args = parser.parse_args()

    findings: list[Finding] = []
    for archive in args.archive:
        findings.extend(scan_archive(archive, args.secrets_env, args.retired_fingerprints))
    for tree in args.tree:
        findings.extend(scan_tree(tree, args.secrets_env, args.retired_fingerprints))
    if findings:
        print("RELEASE_SECRET_GATE=FAIL")
        print(render_findings(findings))
        return 1
    print("RELEASE_SECRET_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
