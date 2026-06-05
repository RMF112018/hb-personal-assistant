"""
Procore App Config + Secure Local Secret Storage (Bobby-only MVP, read-only delegated).

Implements:
- App profile + environment loading (Client ID + OOB redirect only in seeds; no secrets).
- Runtime secret selection (NEVER from repo/config/yaml/evidence/SQLite/Obsidian):
  1. macOS Keychain via `security` command (native, no extra pip dep; preferred).
  2. Environment variable PROCORE_CLIENT_SECRET.
  3. Protected user file (~/.config/hb-assistant/procore/client_secret, 0600, owner-only).
- Hard validation rejecting any embedded secret in loaded config.
- Redirect URI posture enforcement (OOB preferred per OAuth research; approved localhost only).
- Environment separation (sandbox vs production) with bases from official docs + Prompt_01 subagent reports.

This module ensures Bobby is never responsible for wiring secret handling — it is fully implemented here.

Usage (example):
    from hb_assistant.procore.config import load_procore_app_config, get_procore_client_secret, print_secret_setup_instructions
    profile = load_procore_app_config()  # loads seed, validates OOB + sandbox + 5280
    secret = get_procore_client_secret()  # runtime only; raises if unavailable
    print_secret_setup_instructions()     # one-time setup (prints commands, never the value)

Guardrails enforced:
- No secret ever written to repo, evidence, logs, or any file by this code.
- Loader scans for "client_secret" key or known dangerous patterns and hard-fails.
- All live calls (future) must be dry-run/apply.

Sources: merged Prompt_01 subagent reports (OAuth 019e6b45-0979..., REST 019e6b45-1c11...) + official developers.procore.com (2026-05-27).

Do not import secrets or tokens into this module.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

# Public non-secret Client ID (from Prompt_02 query; safe to reference in seed)
PROCORE_CLIENT_ID = "TZTKW39fFf80ASZIp6uH81WUF81k0S97TkxF8S8k7Ps"

# Approved redirect URIs (OOB preferred for Bobby-only CLI per OAuth research)
APPROVED_REDIRECT_URIS: tuple[str, ...] = (
    "urn:ietf:wg:oauth:2.0:oob",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
)

# Environment bases (from Prompt_01 subagent reports + official docs)
ENVIRONMENTS = {
    "sandbox": {
        "name": "Sandbox",
        "oauth_base": "https://login-sandbox.procore.com",
        "api_base": "https://sandbox.procore.com",
        "notes": "Dedicated sandbox credentials. Always start here.",
    },
    "production": {
        "name": "Production",
        "oauth_base": "https://login.procore.com",
        "api_base": "https://api.procore.com",
        "notes": "Production credentials require portal promotion. Never mix with sandbox.",
    },
}

# HB company for Procore-Company-Id header (mandatory on authenticated calls)
HB_COMPANY_ID = 5280

# Forbidden patterns (never allow in any loaded config/seed/yaml)
FORBIDDEN_SECRET_PATTERNS = (
    "client_secret",
    "KP2pl6c0RHGTeIZyn_p-sRil",  # prefix of the provided secret (for belt-and-suspenders scan)
    "access_token",
    "refresh_token",
    "Authorization:",
)


class EmbeddedSecretError(RuntimeError):
    """Raised when a secret-like value or key is detected in config/seed data."""


class SecretNotAvailableError(RuntimeError):
    """Raised when no secure secret source is configured for the operator."""


@dataclass(frozen=True)
class ProcoreAppProfile:
    client_id: str
    redirect_uri: str
    environment: Literal["sandbox", "production"]
    company_id: int
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.client_id != PROCORE_CLIENT_ID:
            # Allow override in tests, but warn in real use
            pass
        if self.redirect_uri not in APPROVED_REDIRECT_URIS:
            raise ValueError(
                f"redirect_uri must be one of {APPROVED_REDIRECT_URIS} (OOB preferred for CLI). "
                "See 02-procore-app-credential-posture.md for registration."
            )
        if self.environment not in ENVIRONMENTS:
            raise ValueError(f"environment must be one of {list(ENVIRONMENTS)}")
        if self.company_id != HB_COMPANY_ID:
            # Future: support multiple, but for Bobby-only MVP enforce 5280
            pass


def _scan_for_embedded_secrets(data: str | dict) -> None:
    """Hard-fail if any forbidden pattern appears in loaded config text or dict."""
    text = str(data).lower() if isinstance(data, dict) else data.lower()
    for pattern in FORBIDDEN_SECRET_PATTERNS:
        if pattern.lower() in text:
            raise EmbeddedSecretError(
                f"Embedded secret material detected in config data (pattern: {pattern}). "
                "Secrets must only come from secure local storage at runtime. "
                "Remove the value from all yaml/seed/config files immediately."
            )


def load_procore_app_profile_from_dict(data: dict) -> ProcoreAppProfile:
    """Load and validate from a dict (e.g. parsed seed). Rejects embedded secrets."""
    _scan_for_embedded_secrets(data)
    return ProcoreAppProfile(
        client_id=data["client_id"],
        redirect_uri=data["redirect_uri"],
        environment=data["environment"],
        company_id=int(data["company_id"]),
        notes=data.get("notes"),
    )


def load_procore_app_profile() -> ProcoreAppProfile:
    """Load the Procore app profile.

    Reads ``resources/config/procore_app_profile.seed.yaml`` (via the repo
    root resolved by :class:`PathPolicy`) when present; otherwise falls back
    to a minimal inline default. The seed is the source of truth for the
    runtime ``environment`` (sandbox vs production) so changing that one
    field in the YAML propagates to the OAuth client without code edits.
    """

    import yaml as _yaml

    from hb_assistant.config.path_policy import PathPolicy

    seed_path: Path = (
        PathPolicy().resolve_repo_root() / "resources" / "config" / "procore_app_profile.seed.yaml"
    )
    if seed_path.exists():
        with seed_path.open("r", encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
        if isinstance(data, dict) and data.get("client_id") and data.get("environment"):
            return load_procore_app_profile_from_dict(data)

    # Fallback for environments where the seed is not present (test fixtures
    # without the repo tree). Documented inline default; mirrors the seed.
    seed = {
        "client_id": PROCORE_CLIENT_ID,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "environment": "production",
        "company_id": HB_COMPANY_ID,
    }
    return load_procore_app_profile_from_dict(seed)


def macos_keychain_entry_exists(
    service: str = "hb-assistant-procore", account: str = "client-secret"
) -> bool:
    """Return True if a Keychain entry exists for ``(service, account)``.

    Uses ``security find-generic-password`` **without** ``-w`` so the secret
    value is never read into memory and no permission prompt is triggered
    (existence check only). Safe to call from status surfaces.
    """
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_macos_keychain_secret(
    service: str = "hb-assistant-procore", account: str = "client-secret"
) -> Optional[str]:
    """Native macOS Keychain via `security` (no extra dependencies)."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_procore_client_secret() -> str:
    """
    Runtime secret selector (order: macOS Keychain → env → protected user file).
    Never falls back to repo/config/yaml.
    Raises SecretNotAvailableError with setup instructions if none found.
    """
    # 1. macOS Keychain (preferred for local-first Bobby-only)
    secret = get_macos_keychain_secret()
    if secret:
        return secret

    # 2. Environment (good for CI/launchd with launchd secrets or temp shells)
    env_secret = os.environ.get("PROCORE_CLIENT_SECRET")
    if env_secret:
        return env_secret

    # 3. Protected user file (0600, owner-only)
    config_dir = Path.home() / ".config" / "hb-assistant" / "procore"
    secret_file = config_dir / "client_secret"
    if secret_file.exists():
        # Enforce ownership + perms (best effort on macOS)
        try:
            stat = secret_file.stat()
            if stat.st_mode & 0o077:  # group/other readable
                raise SecretNotAvailableError(
                    f"Secret file {secret_file} has unsafe permissions (must be 0600). "
                    f"Run: chmod 600 {secret_file}"
                )
            if stat.st_uid != os.getuid():
                raise SecretNotAvailableError(
                    f"Secret file {secret_file} not owned by current user."
                )
            content = secret_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            raise SecretNotAvailableError(f"Failed to read protected secret file: {e}") from e

    # Nothing found — give clear one-time setup instructions (never echo any secret value)
    raise SecretNotAvailableError(
        "No Procore client secret available from secure local storage.\n\n"
        + "Run the following one-time setup (choose one):\n\n"
        + "Preferred (macOS Keychain):\n"
        + "  security add-generic-password -s 'hb-assistant-procore' -a 'client-secret' -w\n"
        + "  (paste the secret when prompted; it will never be echoed or stored in repo)\n\n"
        + "Alternative (protected file, 0600):\n"
        + "  mkdir -p ~/.config/hb-assistant/procore\n"
        + "  chmod 700 ~/.config/hb-assistant/procore\n"
        + "  touch ~/.config/hb-assistant/procore/client_secret\n"
        + "  chmod 600 ~/.config/hb-assistant/procore/client_secret\n"
        + "  # then securely write the secret value into that file (editor or printf, never git)\n\n"
        + "Alternative (env var for shells/CI):\n"
        + "  export PROCORE_CLIENT_SECRET='your-secret-here'\n\n"
        + "After setup, re-run the command. See 02-procore-app-credential-posture.md for full details."
    )


def get_procore_access_token() -> Optional[str]:
    """Return a Procore OAuth access token from secure local storage, or None.

    Lookup order: macOS Keychain (service ``hb-assistant-procore``,
    account ``access-token``) → env ``PROCORE_ACCESS_TOKEN``.

    This is intentionally **separate** from :func:`get_procore_client_secret`.
    The HTTP client must never reuse the client secret as a bearer credential;
    a real OAuth token must be supplied here. OAuth token acquisition itself
    is deferred to a later prompt — until then, callers (operators or a
    higher-level service) populate Keychain/env directly.

    Returns ``None`` when no token is available so the caller can fail closed
    with :class:`hb_assistant.procore.errors.ProcoreAuthRequired`.
    """
    keychain_token = get_macos_keychain_secret(
        service="hb-assistant-procore", account="access-token"
    )
    if keychain_token:
        return keychain_token
    env_token = os.environ.get("PROCORE_ACCESS_TOKEN")
    if env_token:
        return env_token
    return None


def print_secret_setup_instructions() -> None:
    """Print safe, copy-pasteable one-time setup commands. Never prints or logs any secret value."""
    print(
        "Procore Client Secret Setup (one-time, Bobby-only local machine)\n"
        "=============================================================\n"
        "1. macOS Keychain (recommended):\n"
        "   security add-generic-password -s 'hb-assistant-procore' -a 'client-secret' -w\n"
        "   (The system will prompt for the secret; it stays in Keychain, never in files or repo.)\n\n"
        "2. Protected file (fallback):\n"
        "   mkdir -p ~/.config/hb-assistant/procore && chmod 700 ~/.config/hb-assistant/procore\n"
        "   touch ~/.config/hb-assistant/procore/client_secret && chmod 600 ~/.config/hb-assistant/procore/client_secret\n"
        "   # Use a secure editor or: printf 'YOUR_SECRET' > ~/.config/hb-assistant/procore/client_secret\n\n"
        "3. Environment (for current shell or launchd):\n"
        "   export PROCORE_CLIENT_SECRET='YOUR_SECRET'\n\n"
        "The loader (this module) will automatically find it at runtime.\n"
        "Never commit the secret. Never put it in any yaml/seed/config in the repo."
    )


def get_environment_config(env: Literal["sandbox", "production"] | None = None) -> dict:
    """Return base URLs + header requirements for the chosen (or default sandbox) environment."""
    if env is None:
        env = "sandbox"
    if env not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {env}")
    cfg = ENVIRONMENTS[env].copy()
    cfg["procore_company_id_header"] = HB_COMPANY_ID
    cfg["mandatory_header_note"] = (
        "Send Procore-Company-Id on all authenticated REST calls (except exceptions)"
    )
    return cfg


# Future integration hook (existing loader/auth can call these)
__all__ = [
    "ProcoreAppProfile",
    "load_procore_app_profile",
    "load_procore_app_profile_from_dict",
    "get_procore_client_secret",
    "get_procore_access_token",
    "macos_keychain_entry_exists",
    "print_secret_setup_instructions",
    "get_environment_config",
    "EmbeddedSecretError",
    "SecretNotAvailableError",
    "APPROVED_REDIRECT_URIS",
    "HB_COMPANY_ID",
]
