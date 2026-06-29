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
import ipaddress
import json
import logging
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
DCR_CLIENT_PREFIX = "chatgpt_"
_SUPPORTED_DCR_GRANTS = {"authorization_code", "refresh_token"}
_REJECTED_DCR_GRANTS = {
    "client_credentials",
    "password",
    "implicit",
    "jwt-bearer",
    "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "device_code",
    "urn:ietf:params:oauth:grant-type:device_code",
}
_SUPPORTED_DCR_RESPONSE_TYPES = {"code"}
_logger = logging.getLogger("hb_assistant.obsidian_mcp.oauth")


class OAuthError(Exception):
    """RFC 6749 style error carrying a machine ``error`` code."""

    def __init__(self, error: str, description: str | None = None) -> None:
        super().__init__(description or error)
        self.error = error
        self.description = description


@dataclass(frozen=True)
class TokenInfo:
    scopes: tuple[str, ...]
    client_id: str
    resource: str


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]
    scopes: tuple[str, ...]
    grant_types: tuple[str, ...] = ("authorization_code",)
    response_types: tuple[str, ...] = ("code",)
    token_endpoint_auth_method: str = "none"
    source: str = "dynamic"
    issued_at: int | None = None
    allow_any_https_redirect: bool = False
    allow_localhost_redirect: bool = False

    def public_dict(self) -> dict:
        payload = {
            "client_id": self.client_id,
            "redirect_uris": list(self.redirect_uris),
            "grant_types": list(self.grant_types),
            "response_types": list(self.response_types),
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
            "scope": " ".join(self.scopes),
            "client_name": self.client_name,
        }
        if self.issued_at is not None:
            payload["client_id_issued_at"] = self.issued_at
        return payload


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


def _clients_path() -> Path:
    return oauth_dir() / "clients.json"


def mcp_resource(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/mcp"


def fixed_grok_client() -> OAuthClient:
    return OAuthClient(
        client_id=CLIENT_ID,
        client_name="Grok",
        redirect_uris=(),
        scopes=SUPPORTED_SCOPES,
        source="fixed",
        allow_any_https_redirect=True,
        allow_localhost_redirect=True,
    )


def _client_from_record(record: dict) -> OAuthClient | None:
    try:
        scopes = tuple(str(record.get("scope", "")).split())
        return OAuthClient(
            client_id=str(record["client_id"]),
            client_name=str(record.get("client_name") or "Registered MCP client"),
            redirect_uris=tuple(str(item) for item in record.get("redirect_uris", [])),
            scopes=scopes,
            grant_types=tuple(str(item) for item in record.get("grant_types", ["authorization_code"])),
            response_types=tuple(str(item) for item in record.get("response_types", ["code"])),
            token_endpoint_auth_method=str(record.get("token_endpoint_auth_method", "none")),
            source=str(record.get("source", "dynamic")),
            issued_at=int(record["client_id_issued_at"]) if record.get("client_id_issued_at") is not None else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def registered_clients() -> dict[str, OAuthClient]:
    raw = _read(_clients_path()).get("clients", {})
    if not isinstance(raw, dict):
        return {}
    clients: dict[str, OAuthClient] = {}
    for client_id, record in raw.items():
        if isinstance(record, dict):
            client = _client_from_record(record | {"client_id": str(client_id)})
            if client is not None:
                clients[client.client_id] = client
    return clients


def get_client(client_id: str) -> OAuthClient | None:
    if client_id == CLIENT_ID:
        return fixed_grok_client()
    return registered_clients().get(client_id)


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


def _validate_https_redirect_uri(redirect_uri: str) -> None:
    if not redirect_uri:
        raise OAuthError("invalid_redirect_uri", "redirect_uris must not be empty")
    parsed = urlsplit(redirect_uri)
    if parsed.scheme != "https" or not parsed.netloc:
        raise OAuthError("invalid_redirect_uri", "redirect_uris must be absolute HTTPS URLs")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise OAuthError("invalid_redirect_uri", "localhost redirect URIs are not allowed for dynamic clients")
    with suppress(ValueError):
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise OAuthError("invalid_redirect_uri", "private IP redirect URIs are not allowed for dynamic clients")


def _validate_redirect_uri_for_client(client: OAuthClient, redirect_uri: str) -> None:
    if not redirect_uri:
        raise OAuthError("invalid_request", "redirect_uri is required")
    parsed = urlsplit(redirect_uri)
    if client.allow_any_https_redirect and parsed.scheme == "https" and parsed.netloc:
        return
    if client.allow_localhost_redirect and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return
    if redirect_uri in client.redirect_uris:
        return
    raise OAuthError("invalid_request", "redirect_uri is not registered for this client")


def _metadata_list(value: object, *, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise OAuthError("invalid_client_metadata", "metadata value must be a string or list")


def _normalize_grant_types(value: object) -> list[str]:
    requested = _metadata_list(value, default=["authorization_code"])
    if not requested:
        requested = ["authorization_code"]
    unknown = [item for item in requested if item not in _SUPPORTED_DCR_GRANTS]
    rejected = [item for item in requested if item in _REJECTED_DCR_GRANTS]
    if rejected or unknown or "authorization_code" not in requested:
        raise OAuthError("invalid_client_metadata", "grant_types must include authorization_code and no unsupported grants")
    return ["authorization_code"]


def _normalize_response_types(value: object) -> list[str]:
    requested = _metadata_list(value, default=["code"])
    if not requested:
        requested = ["code"]
    unsupported = [item for item in requested if item not in _SUPPORTED_DCR_RESPONSE_TYPES]
    if unsupported or "code" not in requested:
        raise OAuthError("invalid_client_metadata", "response_types must include code and no unsupported response types")
    return ["code"]


def registration_diagnostics(
    metadata: dict,
    *,
    grant_types: list[str] | None = None,
    response_types: list[str] | None = None,
    error: str | None = None,
) -> dict:
    def _safe_list(key: str, default: list[str]) -> list[str]:
        try:
            return _metadata_list(metadata.get(key), default=default)
        except OAuthError:
            return ["<invalid_type>"]

    payload = {
        "metadata_keys": sorted(str(key) for key in metadata.keys()),
        "grant_types": grant_types or _safe_list("grant_types", ["authorization_code"]),
        "response_types": response_types or _safe_list("response_types", ["code"]),
        "token_endpoint_auth_method": str(metadata.get("token_endpoint_auth_method", "none")),
    }
    if error:
        payload["error"] = error
    return payload


def _record_registration_rejection(metadata: dict, *, error: str) -> None:
    diagnostics = registration_diagnostics(metadata, error=error)
    _logger.warning("obsidian_mcp.oauth_register_rejected", extra={"obsidian_mcp_oauth": diagnostics})
    record_event("client_registration_rejected", registration_metadata=diagnostics)


def register_client(metadata: dict) -> dict:
    if metadata.get("client_secret") or metadata.get("client_secret_expires_at"):
        _record_registration_rejection(metadata, error="client_secret_present")
        raise OAuthError("invalid_client_metadata", "client secrets are not accepted for public clients")
    redirect_uris = metadata.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise OAuthError("invalid_redirect_uri", "redirect_uris is required")
    normalized_redirects: list[str] = []
    for item in redirect_uris:
        uri = str(item)
        _validate_https_redirect_uri(uri)
        if uri not in normalized_redirects:
            normalized_redirects.append(uri)
    try:
        grant_types = _normalize_grant_types(metadata.get("grant_types"))
        response_types = _normalize_response_types(metadata.get("response_types"))
    except OAuthError as exc:
        _record_registration_rejection(metadata, error=exc.description or exc.error)
        raise
    if metadata.get("token_endpoint_auth_method", "none") != "none":
        _record_registration_rejection(metadata, error="unsupported_token_endpoint_auth_method")
        raise OAuthError("invalid_client_metadata", "token_endpoint_auth_method must be none")
    scopes = normalize_scopes(str(metadata.get("scope") or "obsidian.read"))
    issued_at = int(_now())
    client_id = f"{DCR_CLIENT_PREFIX}{secrets.token_urlsafe(18)}"
    client = OAuthClient(
        client_id=client_id,
        client_name=str(metadata.get("client_name") or "ChatGPT"),
        redirect_uris=tuple(normalized_redirects),
        scopes=tuple(scopes),
        grant_types=tuple(grant_types),
        response_types=tuple(response_types),
        issued_at=issued_at,
        source="dynamic",
    )
    path = _clients_path()
    data = _read(path)
    records = data.get("clients")
    if not isinstance(records, dict):
        records = {}
    records[client_id] = client.public_dict() | {"source": "dynamic"}
    data["clients"] = records
    _write(path, data)
    record_event(
        "client_registered",
        scope=" ".join(scopes),
        client_id=client_id,
        registration_metadata=registration_diagnostics(metadata, grant_types=grant_types, response_types=response_types),
    )
    return client.public_dict()


def validate_authorize_request(
    *,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    code_challenge_method: str,
    resource: str | None = None,
    base_url: str | None = None,
) -> list[str]:
    """Validate an /oauth/authorize request and return normalized scopes."""
    if response_type != "code":
        raise OAuthError("unsupported_response_type", "response_type must be 'code'")
    client = get_client(client_id)
    if client is None:
        raise OAuthError("unauthorized_client", "unknown client_id")
    _validate_redirect_uri_for_client(client, redirect_uri)
    if code_challenge_method != "S256":
        raise OAuthError("invalid_request", "code_challenge_method must be S256")
    if not code_challenge:
        raise OAuthError("invalid_request", "code_challenge is required")
    scopes = normalize_scopes(scope)
    for item in scopes:
        if item not in client.scopes:
            raise OAuthError("invalid_scope", f"scope not registered for client: {item}")
    if base_url is not None:
        expected_resource = mcp_resource(base_url)
        if resource and resource != expected_resource:
            raise OAuthError("invalid_target", "resource does not match this MCP server")
    return scopes


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
    resource: str | None = None,
    base_url: str | None = None,
) -> str:
    if base_url is None:
        raise OAuthError("invalid_request", "base_url is required")
    resolved_resource = resource or mcp_resource(base_url)
    scopes = validate_authorize_request(
        response_type="code",
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        resource=resolved_resource,
        base_url=base_url,
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
        "resource": resolved_resource,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "issued_at": _iso(now),
        "expires_at": _iso(now + CODE_TTL_SECONDS),
        "expires_ts": now + CODE_TTL_SECONDS,
        "used": False,
    }
    _write(path, data)
    record_event("authorization_code_issued", scope=" ".join(scopes), client_id=client_id)
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
    resource: str | None = None,
    base_url: str | None = None,
) -> tuple[list[str], str, str]:
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
    expected_resource = mcp_resource(base_url) if base_url else str(record.get("resource") or "")
    stored_resource = str(record.get("resource") or "")
    requested_resource = resource or stored_resource
    if not stored_resource or requested_resource != stored_resource or (expected_resource and stored_resource != expected_resource):
        raise OAuthError("invalid_target", "resource mismatch")
    if not _verify_pkce(code_verifier, str(record.get("code_challenge", ""))):
        raise OAuthError("invalid_grant", "PKCE verification failed")
    record["used"] = True
    _write(path, data)
    record_event("authorization_code_redeemed", scope=str(record.get("scope", "")), client_id=client_id)
    return (record.get("scope") or "").split(), client_id, stored_resource


# ---------------------------------------------------------------------------
# Access tokens.
# ---------------------------------------------------------------------------
def issue_access_token(*, scopes: list[str], client_id: str, resource: str) -> dict:
    if not resource:
        raise OAuthError("invalid_target", "resource is required")
    raw = secrets.token_urlsafe(32)
    now = _now()
    path = _tokens_path()
    data = _read(path)
    _prune(data, now)
    data[_sha256(raw)] = {
        "scope": " ".join(scopes),
        "client_id": client_id,
        "resource": resource,
        "issued_at": _iso(now),
        "expires_at": _iso(now + TOKEN_TTL_SECONDS),
        "expires_ts": now + TOKEN_TTL_SECONDS,
        "revoked": False,
    }
    _write(path, data)
    record_event("access_token_issued", scope=" ".join(scopes), client_id=client_id)
    return {
        "access_token": raw,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "scope": " ".join(scopes),
    }


def validate_access_token(raw_token: str, *, resource: str | None = None) -> TokenInfo | None:
    if not raw_token:
        return None
    record = _read(_tokens_path()).get(_sha256(raw_token))
    if record is None or record.get("revoked"):
        return None
    if _now() > float(record.get("expires_ts", 0)):
        return None
    token_resource = str(record.get("resource") or "")
    if not token_resource or (resource is not None and token_resource != resource):
        return None
    return TokenInfo(
        scopes=tuple((record.get("scope") or "").split()),
        client_id=str(record.get("client_id") or ""),
        resource=token_resource,
    )


def _prune(data: dict, now: float) -> None:
    """Drop expired records in-place to keep the on-disk files bounded."""
    for key in [k for k, v in data.items() if isinstance(v, dict) and now > float(v.get("expires_ts", 0)) + CODE_TTL_SECONDS]:
        data.pop(key, None)


# ---------------------------------------------------------------------------
# Redacted audit events (never contain code/token values).
# ---------------------------------------------------------------------------
def record_event(
    kind: str,
    *,
    scope: str | None = None,
    client_id: str | None = None,
    registration_metadata: dict | None = None,
) -> None:
    path = _events_path()
    data = _read(path)
    events = data.get("events")
    if not isinstance(events, list):
        events = []
    entry = {"kind": kind, "at": _iso(_now())}
    if scope is not None:
        entry["scope"] = scope
    if client_id is not None:
        entry["client_id"] = client_id
    if registration_metadata is not None:
        entry["registration_metadata"] = registration_metadata
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
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": list(SUPPORTED_SCOPES),
    }


def protected_resource_metadata(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "resource": mcp_resource(base),
        "authorization_servers": [base],
        "scopes_supported": list(SUPPORTED_SCOPES),
        "bearer_methods_supported": ["header"],
    }


def resource_metadata_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/.well-known/oauth-protected-resource"


def www_authenticate_header(base_url: str, *, scope: str = "obsidian.read", error: str | None = None, error_description: str | None = None) -> str:
    parts = [
        f'resource_metadata="{resource_metadata_url(base_url)}"',
        f'scope="{scope}"',
    ]
    if error:
        parts.append(f'error="{error}"')
    if error_description:
        parts.append(f'error_description="{error_description}"')
    return "Bearer " + ", ".join(parts)


def grok_setup_values(base_url: str) -> dict:
    base = base_url.rstrip("/")
    client = fixed_grok_client()
    return {
        "mcp_url": mcp_resource(base),
        "client_id": client.client_id,
        "client_secret": "",
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "scopes": list(client.scopes),
        "token_auth_method": TOKEN_AUTH_METHOD,
    }


def chatgpt_setup_values(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "connector_url": mcp_resource(base),
        "mcp_url": mcp_resource(base),
        "protected_resource_metadata_url": resource_metadata_url(base),
        "authorization_server_metadata_url": f"{base}/.well-known/oauth-authorization-server",
        "openid_configuration_url": f"{base}/.well-known/openid-configuration",
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "registration_mode": "dynamic_client_registration",
        "client_id_metadata_document_supported": False,
        "initial_scope": "obsidian.read",
    }


def redirect_with(redirect_uri: str, params: dict[str, str]) -> str:
    parts = urlsplit(redirect_uri)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
