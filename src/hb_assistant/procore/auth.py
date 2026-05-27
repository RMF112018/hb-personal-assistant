"""Procore auth status — documented stub (no live call).

Live OAuth is deferred to a future prompt. This module:

- Inspects the *presence* of ``PROCORE_CLIENT_ID``, ``PROCORE_CLIENT_SECRET``,
  ``PROCORE_REFRESH_TOKEN`` env vars (never reads their values into the
  returned report — only reports which keys are set).
- Checks whether a token-cache file might exist at the canonical location
  under the sensitive auth directory. Existence is reported; the file is
  never opened or read.

The auth-status check never raises on missing credentials — it returns a
structured :class:`AuthStatusReport` so non-interactive callers can branch.
"""

from __future__ import annotations

import os

from hb_assistant.config.path_policy import PathPolicy

from .models import AuthStatusReport

REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "PROCORE_CLIENT_ID",
    "PROCORE_CLIENT_SECRET",
    "PROCORE_REFRESH_TOKEN",
)

AUTH_TOKEN_FILE_NAME = "procore_token.json"


def _token_cache_present() -> bool:
    try:
        auth_dir = PathPolicy().get_auth_dir()
    except Exception:  # noqa: BLE001 — non-critical, return False
        return False
    candidate = auth_dir / AUTH_TOKEN_FILE_NAME
    return candidate.exists()


def check_auth_status() -> AuthStatusReport:
    present = [k for k in REQUIRED_ENV_KEYS if os.environ.get(k)]
    missing = [k for k in REQUIRED_ENV_KEYS if not os.environ.get(k)]
    token_cache = _token_cache_present()

    if not present and not token_cache:
        status = "env_absent"
        hint = (
            "No Procore credentials detected. Live access is deferred — "
            "set PROCORE_CLIENT_ID / PROCORE_CLIENT_SECRET / "
            "PROCORE_REFRESH_TOKEN in the environment (or place a token "
            "cache under the sensitive auth directory) before any future "
            "live commands."
        )
        ready = False
    elif missing:
        status = "env_partial"
        hint = (
            "Some Procore credentials are present but the set is incomplete "
            f"(missing: {missing}). Live access remains gated."
        )
        ready = False
    else:
        status = "env_present"
        hint = (
            "All required Procore env keys are set. Live calls are still "
            "intentionally disabled — a live OAuth client is not wired in "
            "this prompt."
        )
        ready = False  # live access deferred regardless

    return AuthStatusReport(
        status=status,
        env_keys_present=present,
        env_keys_missing=missing,
        token_cache_present=token_cache,
        ready_for_live_calls=ready,
        hint=hint,
    )
