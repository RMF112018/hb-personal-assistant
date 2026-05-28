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

from .config import macos_keychain_entry_exists
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
    keychain_secret = macos_keychain_entry_exists()

    # Phase 04: a Keychain-installed client secret + a populated token cache
    # is the canonical operator posture and counts as fully configured even
    # when the env-var triad is absent.
    secret_available = bool(present or keychain_secret)
    fully_configured = token_cache and secret_available

    if fully_configured:
        status = "env_present"
        hint = (
            "OAuth cache populated and a client secret is available "
            f"({'Keychain' if keychain_secret else 'environment'}). "
            "Live calls are gated by the operator-controlled CLI surface."
        )
        ready = True
    elif not present and not token_cache and not keychain_secret:
        status = "env_absent"
        hint = (
            "No Procore credentials detected. Run 'hb-assistant procore auth "
            "login' (with the client secret installed in macOS Keychain), or "
            "set PROCORE_CLIENT_ID / PROCORE_CLIENT_SECRET / "
            "PROCORE_REFRESH_TOKEN in the environment, before any live "
            "commands."
        )
        ready = False
    elif keychain_secret and not token_cache:
        status = "env_partial"
        hint = (
            "macOS Keychain has the Procore client secret but no OAuth token "
            "cache exists yet. Run 'hb-assistant procore auth login' to "
            "complete the OOB exchange."
        )
        ready = False
    elif missing:
        status = "env_partial"
        hint = (
            "Some Procore env keys are present but the set is incomplete "
            f"(missing: {missing}). Live access remains gated."
        )
        ready = False
    else:
        status = "env_present"
        hint = (
            "All required Procore env keys are set; OAuth cache not yet "
            "populated. Run 'hb-assistant procore auth login' to mint tokens."
        )
        ready = False

    return AuthStatusReport(
        status=status,
        env_keys_present=present,
        env_keys_missing=missing,
        token_cache_present=token_cache,
        ready_for_live_calls=ready,
        hint=hint,
        keychain_secret_present=keychain_secret,
    )
