"""Per-user JWT generation counter.

Old tokens omit the claim and are treated as version 0. Incrementing
`user.auth_version` invalidates only that user's already-issued tokens.
Do not rotate SECRET_KEY for this: it also wraps user AI API keys.
"""

from __future__ import annotations


def token_auth_version(payload: dict | None) -> int:
    if not payload:
        return 0
    raw = payload.get("auth_version", 0)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def auth_version_matches(payload: dict | None, user_version) -> bool:
    try:
        current = int(user_version or 0)
    except (TypeError, ValueError):
        current = 0
    return token_auth_version(payload) == current


def next_auth_version(current) -> int:
    try:
        return int(current or 0) + 1
    except (TypeError, ValueError):
        return 1


def bump_user_auth_version(user) -> int:
    user.auth_version = next_auth_version(getattr(user, "auth_version", 0))
    return user.auth_version
