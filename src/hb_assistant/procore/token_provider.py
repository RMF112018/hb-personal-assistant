"""Procore OAuth token provider boundary (Phase 04 Prompt 02).

This module formalizes the boundary that keeps the OAuth client secret out of
the bearer-token path. The HTTP client consumes a :class:`ProcoreTokenProvider`
and never reads the client secret itself; the secret is reserved for the
(future) OAuth exchange / refresh path, which will populate the local token
cache that the providers here read from.

Providers exposed:

- :class:`MissingTokenProvider` — always returns ``None`` (explicit fail-closed
  default for environments without OAuth configured).
- :class:`EnvOrKeychainTokenProvider` — reads ``PROCORE_ACCESS_TOKEN`` (env)
  or the macOS Keychain ``access-token`` entry under service
  ``hb-assistant-procore`` via :func:`hb_assistant.procore.config.get_procore_access_token`.
- :class:`LocalOAuthCacheTokenProvider` — read-only consumer of a locally
  cached OAuth token JSON at
  ``PathPolicy().get_auth_dir() / AUTH_TOKEN_FILE_NAME``. Returns ``None`` on
  missing / unreadable / unsafe-permissions / malformed / missing-field /
  expired cache content. Never writes, never acquires, never refreshes.
- :func:`default_procore_token_provider` — composed chain (env/keychain →
  local cache → missing).

A small :class:`StaticTokenProvider` is provided for tests but is intentionally
not re-exported from the package; tests import it from this submodule directly.

Hard invariants enforced here:

- No provider ever reads ``PROCORE_CLIENT_SECRET`` or
  :func:`hb_assistant.procore.config.get_procore_client_secret`.
- No provider ever logs, prints, or stringifies a token value.
- :class:`LocalOAuthCacheTokenProvider` is strictly read-only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.procore.auth import AUTH_TOKEN_FILE_NAME
from hb_assistant.procore.config import get_procore_access_token


@runtime_checkable
class ProcoreTokenProvider(Protocol):
    """Read-only token source for the Procore HTTP client."""

    kind: str

    def get_access_token(self) -> Optional[str]: ...


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissingTokenProvider:
    """Always returns ``None``; the explicit fail-closed default."""

    kind: str = "missing"

    def get_access_token(self) -> Optional[str]:
        return None

    def __repr__(self) -> str:
        return "<MissingTokenProvider kind=missing>"


@dataclass(frozen=True)
class StaticTokenProvider:
    """Test-only provider that returns a fixed value verbatim.

    Not exported from the package surface; import from this submodule in
    tests when a deterministic provider is needed.
    """

    token: Optional[str]
    kind: str = "static"

    def get_access_token(self) -> Optional[str]:
        return self.token

    def __repr__(self) -> str:
        return f"<StaticTokenProvider kind=static token_present={self.token is not None}>"


@dataclass(frozen=True)
class EnvOrKeychainTokenProvider:
    """Reads ``PROCORE_ACCESS_TOKEN`` (env) or macOS Keychain access-token."""

    kind: str = "env_or_keychain"

    def get_access_token(self) -> Optional[str]:
        return get_procore_access_token()

    def __repr__(self) -> str:
        return "<EnvOrKeychainTokenProvider kind=env_or_keychain>"


@dataclass(frozen=True)
class LocalOAuthCacheTokenProvider:
    """Read-only consumer of a local OAuth token cache JSON.

    Expected file shape (any extra keys ignored)::

        {
          "access_token": "<token string>",
          "expires_at": "<ISO 8601 UTC timestamp>"
        }

    Returns ``None`` (never raises) on any of:

    - cache file missing,
    - file permissions allow group/other read (``stat.st_mode & 0o077``),
    - JSON parse error,
    - missing or empty ``access_token`` field,
    - ``expires_at`` parseable and in the past (≤ now).

    The provider is strictly read-only: it never writes, refreshes, or acquires.
    Populating the cache is the responsibility of a future OAuth exchange path.
    """

    kind: str = "oauth_cache"

    def _cache_path(self) -> Optional[Path]:
        try:
            return PathPolicy().get_auth_dir() / AUTH_TOKEN_FILE_NAME
        except Exception:  # noqa: BLE001 — non-critical, treat as no cache
            return None

    def get_access_token(self) -> Optional[str]:
        path = self._cache_path()
        if path is None or not path.exists():
            return None
        try:
            stat = path.stat()
            if stat.st_mode & 0o077:
                return None
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw) if raw.strip() else {}
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            return None
        expires_at = payload.get("expires_at")
        if isinstance(expires_at, str) and expires_at:
            try:
                deadline = datetime.fromisoformat(expires_at)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if deadline <= datetime.now(timezone.utc):
                    return None
            except ValueError:
                return None
        return token

    def __repr__(self) -> str:
        return "<LocalOAuthCacheTokenProvider kind=oauth_cache>"


# ---------------------------------------------------------------------------
# Composed default
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ChainedTokenProvider:
    """Returns the first non-``None`` token from an ordered provider list."""

    providers: tuple[ProcoreTokenProvider, ...]
    kind: str = "chained"

    def get_access_token(self) -> Optional[str]:
        for p in self.providers:
            token = p.get_access_token()
            if token:
                return token
        return None

    def __repr__(self) -> str:
        chain = ",".join(getattr(p, "kind", type(p).__name__) for p in self.providers)
        return f"<_ChainedTokenProvider kind=chained chain=[{chain}]>"


def default_procore_token_provider() -> ProcoreTokenProvider:
    """Composed default: env/keychain → local OAuth cache → missing."""
    return _ChainedTokenProvider(
        providers=(
            EnvOrKeychainTokenProvider(),
            LocalOAuthCacheTokenProvider(),
            MissingTokenProvider(),
        )
    )


# ---------------------------------------------------------------------------
# Callable adapter — keeps the existing Callable-shaped tests + call sites
# working without a sweep.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CallableTokenProvider:
    """Adapts a plain ``Callable[[], Optional[str]]`` to the protocol."""

    fn: Callable[[], Optional[str]]
    kind: str = "callable"

    def get_access_token(self) -> Optional[str]:
        return self.fn()

    def __repr__(self) -> str:
        return "<_CallableTokenProvider kind=callable>"


def adapt_token_source(source: Any) -> ProcoreTokenProvider:
    """Return a :class:`ProcoreTokenProvider`. Accepts a provider, a callable,
    or ``None`` (→ :func:`default_procore_token_provider`).
    """
    if source is None:
        return default_procore_token_provider()
    if isinstance(source, ProcoreTokenProvider):
        return source
    if callable(source):
        return _CallableTokenProvider(fn=source)
    raise TypeError(
        f"Cannot adapt {type(source).__name__} to ProcoreTokenProvider"
    )


__all__ = [
    "AUTH_TOKEN_FILE_NAME",
    "EnvOrKeychainTokenProvider",
    "LocalOAuthCacheTokenProvider",
    "MissingTokenProvider",
    "ProcoreTokenProvider",
    "StaticTokenProvider",
    "adapt_token_source",
    "default_procore_token_provider",
]
