"""Local OAuth 2.1 / PKCE state for the UI-managed Obsidian MCP server.

Authorization-Code-with-PKCE support for the fixed local Grok public client.
Only hashed code/token digests and non-sensitive metadata are persisted; raw
authorization codes and access tokens are returned to the caller exactly once
and are never stored or logged. Storage mirrors ``config.py`` (atomic JSON
writes with ``0o600`` perms) and lives outside the repo under the macOS
Application Support root.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from hb_assistant.config.path_policy import PathPolicy

CLIENT_ID = "hb-obsidian-grok"
SUPPORTED_SCOPES = ("obsidian.read", "obsidian.write")
TOKEN_AUTH_METHOD = "none (PKCE)"
CODE_TTL_SECONDS = 600
TOKEN_TTL_SECONDS = 3600
_MAX_EVENTS = 50


class OAuthError(Exception):
    """RFC 6749 style error carrying a machine ``error`` code."""

    def __init__(self, error: str, description: str | None = None) -> None:
        super().__init__(description or error)
        self.error = error
        self.description = description


@dataclass(frozen=True)
class TokenInfo:
    scopes: tuple[str, ...]


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).replace(microsecond=0).isoformat()


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def oauth_dir() -> Path:
    root = PathPolicy().get_app_support() / "analytics" / "obsidian_mcp" / "oauth"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    with suppress(OSError):
        path.chmod(0o600)


def _codes_path() -> Path:
    return oauth_dir() / "codes.json"


def _tokens_path() -> Path:
    return oauth_dir() / "tokens.json"


def _events_path() -> Path:
    return oauth_dir() / "events.json"


# ---------------------------------------------------------------------------
# Request validation (shared by the authorize render + submit paths).
# ---------------------------------------------------------------------------
def normalize_scopes(scope: str | None) -> list[str]:
    requested = (scope or "").split()
    if not requested:
        raise OAuthError("invalid_scope", "no scope requested")
    normalized: list[str] = []
    for item in requested:
        if item not in SUPPORTED_SCOPES:
            raise OAuthError("invalid_scope", f"unsupported scope: {item}")
        if item not in normalized:
            normalized.append(item)
    return normalized


def _validate_redirect_uri(redirect_uri: str) -> None:
    if not redirect_uri:
        raise OAuthError("invalid_request", "redirect_uri is required")
    parsed = urlsplit(redirect_uri)
    if parsed.scheme == "https" and parsed.netloc:
        return
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return
    raise OAuthError("invalid_request", "redirect_uri must be https or a localhost http URL")


def validate_authorize_request(
    *,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
) -> list[str]:
    """Validate an /oauth/authorize request and return normalized scopes."""
    if response_type != "code":
        raise OAuthError("unsupported_response_type", "response_type must be 'code'")
    if client_id != CLIENT_ID:
        raise OAuthError("unauthorized_client", "unknown client_id")
    _validate_redirect_uri(redirect_uri)
    if code_challenge_method != "S256":
        raise OAuthError("invalid_request", "code_challenge_method must be S256")
    if not code_challenge:
        raise OAuthError("invalid_request", "code_challenge is required")
    return normalize_scopes(scope)


# ---------------------------------------------------------------------------
# Authorization codes.
# ---------------------------------------------------------------------------
def create_authorization_code(
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    scopes = validate_authorize_request(
        response_type="code",
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    raw = secrets.token_urlsafe(32)
    now = _now()
    path = _codes_path()
    data = _read(path)
    _prune(data, now)
    data[_sha256(raw)] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "issued_at": _iso(now),
        "expires_at": _iso(now + CODE_TTL_SECONDS),
        "expires_ts": now + CODE_TTL_SECONDS,
        "used": False,
    }
    _write(path, data)
    record_event("authorization_code_issued", scope=" ".join(scopes))
    return raw


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    if not code_verifier or not code_challenge:
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return secrets.compare_digest(computed, code_challenge)


def consume_authorization_code(
    *,
    raw_code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
) -> list[str]:
    path = _codes_path()
    data = _read(path)
    key = _sha256(raw_code or "")
    record = data.get(key)
    now = _now()
    if record is None:
        raise OAuthError("invalid_grant", "unknown authorization code")
    if record.get("used"):
        raise OAuthError("invalid_grant", "authorization code already used")
    if now > float(record.get("expires_ts", 0)):
        record["used"] = True
        _write(path, data)
        raise OAuthError("invalid_grant", "authorization code expired")
    if client_id != record.get("client_id"):
        raise OAuthError("invalid_grant", "client_id mismatch")
    if redirect_uri != record.get("redirect_uri"):
        raise OAuthError("invalid_grant", "redirect_uri mismatch")
    if not _verify_pkce(code_verifier, str(record.get("code_challenge", ""))):
        raise OAuthError("invalid_grant", "PKCE verification failed")
    record["used"] = True
    _write(path, data)
    record_event("authorization_code_redeemed", scope=str(record.get("scope", "")))
    return (record.get("scope") or "").split()


# ---------------------------------------------------------------------------
# Access tokens.
# ---------------------------------------------------------------------------
def issue_access_token(scopes: list[str]) -> dict:
    raw = secrets.token_urlsafe(32)
    now = _now()
    path = _tokens_path()
    data = _read(path)
    _prune(data, now)
    data[_sha256(raw)] = {
        "scope": " ".join(scopes),
        "issued_at": _iso(now),
        "expires_at": _iso(now + TOKEN_TTL_SECONDS),
        "expires_ts": now + TOKEN_TTL_SECONDS,
        "revoked": False,
    }
    _write(path, data)
    record_event("access_token_issued", scope=" ".join(scopes))
    return {
        "access_token": raw,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "scope": " ".join(scopes),
    }


def validate_access_token(raw_token: str) -> TokenInfo | None:
    if not raw_token:
        return None
    record = _read(_tokens_path()).get(_sha256(raw_token))
    if record is None or record.get("revoked"):
        return None
    if _now() > float(record.get("expires_ts", 0)):
        return None
    return TokenInfo(scopes=tuple((record.get("scope") or "").split()))


def _prune(data: dict, now: float) -> None:
    """Drop expired records in-place to keep the on-disk files bounded."""
    for key in [k for k, v in data.items() if isinstance(v, dict) and now > float(v.get("expires_ts", 0)) + CODE_TTL_SECONDS]:
        data.pop(key, None)


# ---------------------------------------------------------------------------
# Redacted audit events (never contain code/token values).
# ---------------------------------------------------------------------------
def record_event(kind: str, *, scope: str | None = None) -> None:
    path = _events_path()
    data = _read(path)
    events = data.get("events")
    if not isinstance(events, list):
        events = []
    entry = {"kind": kind, "at": _iso(_now())}
    if scope is not None:
        entry["scope"] = scope
    events.append(entry)
    data["events"] = events[-_MAX_EVENTS:]
    _write(path, data)


def recent_events(limit: int = 20) -> list[dict]:
    events = _read(_events_path()).get("events")
    if not isinstance(events, list):
        return []
    return list(reversed(events[-limit:]))


# ---------------------------------------------------------------------------
# Discovery metadata + Grok setup values (pure, FastAPI-agnostic).
# ---------------------------------------------------------------------------
def authorization_server_metadata(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": list(SUPPORTED_SCOPES),
    }


def protected_resource_metadata(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "scopes_supported": list(SUPPORTED_SCOPES),
        "bearer_methods_supported": ["header"],
    }


def grok_setup_values(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "mcp_url": f"{base}/mcp",
        "client_id": CLIENT_ID,
        "client_secret": "",
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "scopes": list(SUPPORTED_SCOPES),
        "token_auth_method": TOKEN_AUTH_METHOD,
    }


def redirect_with(redirect_uri: str, params: dict[str, str]) -> str:
    parts = urlsplit(redirect_uri)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
