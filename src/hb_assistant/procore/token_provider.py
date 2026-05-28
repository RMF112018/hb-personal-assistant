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

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.procore.auth import AUTH_TOKEN_FILE_NAME
from hb_assistant.procore.config import get_procore_access_token

# OAuth surfaces are imported lazily inside RefreshingOAuthTokenProvider
# to keep import-time side effects minimal for callers that don't need them.


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
# Cache I/O (Phase 04 Prompt 02 acquisition remediation)
# ---------------------------------------------------------------------------


def _resolve_cache_path(path: Optional[Path]) -> Optional[Path]:
    if path is not None:
        return path
    try:
        return PathPolicy().get_auth_dir() / AUTH_TOKEN_FILE_NAME
    except Exception:  # noqa: BLE001 — non-critical
        return None


def write_token_cache(token_set: Any, path: Optional[Path] = None) -> Path:
    """Write a token set to the local OAuth cache file.

    Atomic + permission-tightening:

    - Parent directory is created and forced to ``0o700``.
    - JSON body is written to a tempfile alongside the destination, ``fchmod``'d
      to ``0o600`` **before** ``os.replace`` to the final path.
    - Existing cache contents are not corrupted on partial write failure.

    Accepts a :class:`hb_assistant.procore.oauth.TokenSet` (any object exposing
    ``access_token``, ``refresh_token``, ``expires_at``, ``obtained_at``).
    """
    resolved = _resolve_cache_path(path)
    if resolved is None:
        raise RuntimeError("Cannot resolve token cache path (PathPolicy unavailable)")
    auth_dir = resolved.parent
    auth_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        auth_dir.chmod(0o700)

    expires_at = getattr(token_set, "expires_at", None)
    obtained_at = getattr(token_set, "obtained_at", None)
    payload = {
        "access_token": getattr(token_set, "access_token", ""),
        "refresh_token": getattr(token_set, "refresh_token", None),
        "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else None,
        "obtained_at": obtained_at.isoformat() if isinstance(obtained_at, datetime) else None,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".procore_token_", dir=str(auth_dir))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
        os.replace(tmp_path, resolved)
        with contextlib.suppress(OSError):
            os.chmod(resolved, 0o600)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    return resolved


def clear_token_cache(path: Optional[Path] = None) -> bool:
    """Remove the local OAuth cache file if it exists. Returns whether a file
    was removed.
    """
    resolved = _resolve_cache_path(path)
    if resolved is None or not resolved.exists():
        return False
    try:
        resolved.unlink()
    except FileNotFoundError:
        return False
    return True


def read_token_cache_payload(path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Return the full cache payload as a dict (``access_token``,
    ``refresh_token``, ``expires_at``, ``obtained_at``) or ``None``.

    Performs the same permission and shape checks as
    :class:`LocalOAuthCacheTokenProvider` so callers see exactly what the
    provider chain would observe.
    """
    resolved = _resolve_cache_path(path)
    if resolved is None or not resolved.exists():
        return None
    try:
        stat = resolved.stat()
        if stat.st_mode & 0o077:
            return None
        raw = resolved.read_text(encoding="utf-8")
        payload = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


# ---------------------------------------------------------------------------
# Refreshing provider (Phase 04 Prompt 02 acquisition remediation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefreshingOAuthTokenProvider:
    """Token provider that automatically refreshes via :class:`ProcoreOAuthClient`.

    Behavior:

    - Load the cache payload. If absent or missing an ``access_token`` -> ``None``.
    - If ``expires_at`` is more than ``refresh_within`` in the future, return the
      cached access token.
    - Otherwise, if a ``refresh_token`` is present, call
      :meth:`ProcoreOAuthClient.refresh_access_token`, write the new token set
      back, and return the fresh access token. Any exception during refresh
      causes a silent ``None`` (fail closed) — never raises into the HTTP
      client which owns the explicit ``ProcoreAuthRequired`` failure.
    - If no ``refresh_token`` is present, returns the cached access token only
      while it is still valid; otherwise ``None``.
    """

    cache_path: Optional[Path] = None
    refresh_within_seconds: int = 60
    # ``None`` (the default) resolves at refresh time from the loaded
    # ``ProcoreAppProfile`` so the seed YAML stays the single source of truth
    # for environment selection. Explicit value overrides the profile.
    environment: Optional[str] = None
    kind: str = "oauth_refreshing"

    def _load(self) -> Optional[dict[str, Any]]:
        return read_token_cache_payload(self.cache_path)

    def _parse_expires_at(self, raw: Any) -> Optional[datetime]:
        if not isinstance(raw, str) or not raw:
            return None
        try:
            deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return deadline

    def get_access_token(self) -> Optional[str]:
        payload = self._load()
        if payload is None:
            return None
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return None
        refresh_token = payload.get("refresh_token")
        deadline = self._parse_expires_at(payload.get("expires_at"))
        now = datetime.now(timezone.utc)
        refresh_threshold = timedelta(seconds=self.refresh_within_seconds)

        if deadline is None:
            # No expiry assertion — return cached token; freshness is the operator's call.
            return access_token

        if deadline - now > refresh_threshold:
            return access_token

        if not isinstance(refresh_token, str) or not refresh_token:
            return access_token if deadline > now else None

        try:
            from hb_assistant.procore.config import load_procore_app_profile  # lazy
            from hb_assistant.procore.oauth import ProcoreOAuthClient  # lazy

            env = self.environment or load_procore_app_profile().environment
            client = ProcoreOAuthClient(environment=env)
            new_token = client.refresh_access_token(refresh_token)
        except Exception:  # noqa: BLE001 — fail closed
            return access_token if deadline > now else None
        with contextlib.suppress(Exception):  # best-effort cache write; still return the fresh token
            write_token_cache(new_token, self.cache_path)
        return new_token.access_token

    def __repr__(self) -> str:
        return f"<RefreshingOAuthTokenProvider kind={self.kind} env={self.environment}>"


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
    """Composed default: env/keychain → refreshing OAuth cache → missing.

    The middle slot is now :class:`RefreshingOAuthTokenProvider`, which reads
    the same cache file as :class:`LocalOAuthCacheTokenProvider` but also
    transparently refreshes near-expiry tokens via the OAuth client. The bare
    cache provider remains exported for diagnostics + isolated tests.
    """
    return _ChainedTokenProvider(
        providers=(
            EnvOrKeychainTokenProvider(),
            RefreshingOAuthTokenProvider(),
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
    "RefreshingOAuthTokenProvider",
    "StaticTokenProvider",
    "adapt_token_source",
    "clear_token_cache",
    "default_procore_token_provider",
    "read_token_cache_payload",
    "write_token_cache",
]
