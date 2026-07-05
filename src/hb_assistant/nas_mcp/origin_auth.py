"""Origin-side bearer-token authentication for the NAS MCP surface (nas_mcp:8765).

Defense-in-depth: this authenticates the MCP *client* at the NAS origin so the surface
rejects unauthenticated requests even if Cloudflare Access at the edge is misconfigured,
bypassed, or disabled. Cloudflare Access remains required at the edge later; origin auth
is an additional layer, never a replacement (see ``10-cloudflare-access-integration``).

Security design is adapted from ``obsidian_mcp/oauth_store.py`` — same primitives (SHA-256
hex hashing, ``secrets.token_urlsafe`` generation, one-time raw return, 0600 atomic JSON,
expiry + revoked enforcement) — but this is a *dedicated NAS store* because the obsidian
store has no revoke/list/rotate and no client-label/actor/tier fields, is bound to the
obsidian ``/mcp`` resource, and the FastAPI backend it belongs to is a forbidden import in
the NAS process. Raw tokens are NEVER persisted, logged, or returned except once at mint.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .audit import NasMcpAuditWriter
from .profile import (
    AI_OUTPUTS_WRITE_TOOL,
    active_profile,
    health_mode,
    oauth_enabled,
    origin_auth_required,
)

ALLOWED_TOKEN_CLIENTS = frozenset({"claude", "chatgpt", "grok", "admin", "local"})
STORE_VERSION = 1
DEFAULT_EXPIRES_DAYS = 30
AUTH_METHOD_BEARER = "bearer"
AUTH_METHOD_OAUTH = "oauth"
# OAuth scope that unlocks the single sanctioned remote write. A token without it is barred
# from AI_OUTPUTS_WRITE_TOOL via AuthContext.denied_tools even though the profile permits it.
OAUTH_WRITE_SCOPE = "nas.write"

# Internal deny reason classes (recorded in the 0600 audit only — NEVER returned to the
# client, which always sees a uniform 401 so token existence is not leaked).
REASON_OK = "ok"
REASON_MISSING = "missing_authorization"
REASON_MALFORMED = "malformed_authorization"
REASON_UNKNOWN = "unknown_token"
REASON_REVOKED = "revoked"
REASON_EXPIRED = "expired"


class OriginAuthError(RuntimeError):
    """Origin-auth store operation failed."""


def _now() -> datetime:
    """Indirection so tests can freeze time (mirrors oauth_store._now)."""
    return datetime.now(UTC)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthContext:
    """Authenticated client identity attached to a request for audit attribution."""

    client: str
    client_label: str
    actor: str
    token_id: str
    tier: str | None = None
    allowed_tools: tuple[str, ...] = ()
    # Denylist that only ever RESTRICTS (never broadens). Used to bar a read-scoped OAuth
    # token from the single write tool; the broker checks it alongside allowed_tools.
    denied_tools: tuple[str, ...] = ()
    auth_method: str = AUTH_METHOD_BEARER


# Request-scoped authenticated identity. Set by the middleware on the request coroutine's
# context; read by the broker to attribute audit events. None when unauthenticated.
_auth_context_var: contextvars.ContextVar[AuthContext | None] = contextvars.ContextVar(
    "nas_mcp_auth_context", default=None
)


def get_auth_context() -> AuthContext | None:
    return _auth_context_var.get()


def resolve_token_store_path(config: Any = None) -> Path:
    """Env override wins, then config field, then the NAS app-support default."""
    env = os.environ.get("HB_MCP_ORIGIN_AUTH_TOKEN_STORE")
    if env:
        return Path(env)
    store_path = getattr(config, "origin_auth_store_path", None)
    if store_path:
        return Path(store_path)
    raise OriginAuthError(
        "origin-auth token store path unresolved: set HB_MCP_ORIGIN_AUTH_TOKEN_STORE "
        "or configure mcp.origin_auth_store_path"
    )


@dataclass
class OriginAuthTokenStore:
    """SHA-256-hashed bearer-token store (JSON, 0600). Raw tokens are never persisted."""

    path: Path

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": STORE_VERSION, "tokens": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OriginAuthError(f"origin-auth store unreadable: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("tokens"), dict):
            raise OriginAuthError("origin-auth store malformed")
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.chmod(0o600)
        tmp.replace(self.path)
        with contextlib.suppress(OSError):
            self.path.chmod(0o600)

    def create_token(
        self,
        *,
        client: str,
        client_label: str,
        actor: str,
        expires_days: int = DEFAULT_EXPIRES_DAYS,
        tier: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Mint a token. Returns (raw_token, public_record). Raw is returned ONCE."""
        if client not in ALLOWED_TOKEN_CLIENTS:
            raise OriginAuthError(
                f"unknown client '{client}'; allowed: {sorted(ALLOWED_TOKEN_CLIENTS)}"
            )
        if expires_days <= 0:
            raise OriginAuthError("expires_days must be positive")
        raw = secrets.token_urlsafe(32)
        digest = _sha256(raw)
        now = _now()
        expires = now + timedelta(days=expires_days)
        token_id = secrets.token_hex(8)
        record = {
            "token_id": token_id,
            "client": client,
            "client_label": client_label,
            "actor": actor,
            "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "expires_ts": expires.timestamp(),
            "revoked": False,
            "tier": tier,
            "allowed_tools": sorted(set(allowed_tools)) if allowed_tools else [],
            "fingerprint": digest[:8],
        }
        data = self._load()
        data["tokens"][digest] = record
        self._save(data)
        return raw, self._public(record)

    def validate(self, raw_token: str) -> tuple[AuthContext | None, str]:
        """Return (AuthContext, 'ok') or (None, reason_class). Does not leak existence."""
        digest = _sha256(raw_token)
        record = self._load()["tokens"].get(digest)
        if record is None:
            return None, REASON_UNKNOWN
        if record.get("revoked"):
            return None, REASON_REVOKED
        if _now().timestamp() > float(record.get("expires_ts", 0.0)):
            return None, REASON_EXPIRED
        ctx = AuthContext(
            client=str(record.get("client", "unknown")),
            client_label=str(record.get("client_label", "")),
            actor=str(record.get("actor", "")),
            token_id=str(record.get("token_id", "")),
            tier=record.get("tier"),
            allowed_tools=tuple(record.get("allowed_tools") or ()),
            auth_method=AUTH_METHOD_BEARER,
        )
        return ctx, REASON_OK

    def revoke(self, token_id: str) -> bool:
        data = self._load()
        for record in data["tokens"].values():
            if record.get("token_id") == token_id and not record.get("revoked"):
                record["revoked"] = True
                record["revoked_at"] = _now().isoformat()
                self._save(data)
                return True
        return False

    def rotate(self, token_id: str, *, expires_days: int = DEFAULT_EXPIRES_DAYS) -> tuple[str, dict[str, Any]]:
        """Revoke the old token and mint a fresh one with the same attributes."""
        data = self._load()
        old = next((r for r in data["tokens"].values() if r.get("token_id") == token_id), None)
        if old is None:
            raise OriginAuthError(f"unknown token_id '{token_id}'")
        if not self.revoke(token_id):
            raise OriginAuthError(f"token_id '{token_id}' already revoked; rotate refused")
        return self.create_token(
            client=str(old.get("client", "unknown")),
            client_label=str(old.get("client_label", "")),
            actor=str(old.get("actor", "")),
            expires_days=expires_days,
            tier=old.get("tier"),
            allowed_tools=list(old.get("allowed_tools") or []),
        )

    def list_tokens(self) -> list[dict[str, Any]]:
        """Public records only — never the SHA key or any raw token material."""
        records = self._load()["tokens"].values()
        return sorted((self._public(r) for r in records), key=lambda r: r["issued_at"])

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "token_id": record.get("token_id"),
            "client": record.get("client"),
            "client_label": record.get("client_label"),
            "actor": record.get("actor"),
            "issued_at": record.get("issued_at"),
            "expires_at": record.get("expires_at"),
            "revoked": bool(record.get("revoked")),
            "tier": record.get("tier"),
            "allowed_tools": list(record.get("allowed_tools") or []),
            "fingerprint": record.get("fingerprint"),
        }


def _extract_bearer(authorization: str | None) -> tuple[str | None, str]:
    if not authorization:
        return None, REASON_MISSING
    if not authorization.startswith("Bearer "):
        return None, REASON_MALFORMED
    raw = authorization[len("Bearer ") :].strip()
    if not raw:
        return None, REASON_MALFORMED
    return raw, REASON_OK


def _oauth_auth_context(raw_token: str, *, resource: str) -> AuthContext | None:
    """Validate ``raw_token`` as an OAuth 2.1 access token bound to ``resource`` and, on
    success, build an audit-attributed :class:`AuthContext`. Returns None (never raises) so
    the middleware can fall through to a uniform 401. Scope gates the single write tool:
    a token lacking ``nas.write`` is barred from ``ai_outputs_card_upsert`` via denied_tools.

    Imported lazily: ``oauth_store`` pulls in ``PathPolicy`` which is import-safe in the NAS
    process, but keeping it lazy avoids any cost when OAuth is disabled.
    """
    from hb_assistant.obsidian_mcp import oauth_store  # noqa: PLC0415

    info = oauth_store.validate_access_token(raw_token, resource=resource)
    if info is None:
        return None
    denied = () if OAUTH_WRITE_SCOPE in info.scopes else (AI_OUTPUTS_WRITE_TOOL,)
    return AuthContext(
        client="oauth",
        client_label=info.client_id,
        actor=f"oauth:{info.client_id}",
        token_id=info.client_id,
        tier="oauth",
        denied_tools=denied,
        auth_method=AUTH_METHOD_OAUTH,
    )


class OriginAuthMiddleware:
    """Pure-ASGI bearer-auth wrapper for the NAS MCP app (adapted from the obsidian
    ``BearerTokenMiddleware`` pattern). Gates protected routes, sets the request auth
    context for audit attribution, and audits denials with a reason class but no token.

    The client always receives a uniform ``401 {"detail":"unauthorized"}`` so token
    existence is never revealed; the precise reason is recorded only in the 0600 audit.
    """

    def __init__(
        self,
        app: Any,
        *,
        config: Any,
        store: OriginAuthTokenStore | None = None,
        audit_writer: NasMcpAuditWriter | None = None,
    ) -> None:
        self.app = app
        self._config = config
        self._store = store
        self._audit = audit_writer
        # Fixed public HTTPS origin used to bind/verify OAuth token audience + build the
        # RFC 9728 WWW-Authenticate pointer. None when OAuth is not configured.
        self._public_base_url = (getattr(config, "public_base_url", None) or "").rstrip("/") or None

    @property
    def store(self) -> OriginAuthTokenStore:
        if self._store is None:
            self._store = OriginAuthTokenStore(resolve_token_store_path(self._config))
        return self._store

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/health" and health_mode() != "protected":
            await self.app(scope, receive, send)
            return
        # OAuth flow + discovery endpoints run PRE-token and must be reachable unauthenticated
        # (resource-owner auth for /oauth/authorize is supplied at the edge by CF Access SSO).
        if oauth_enabled() and (path.startswith("/oauth/") or path.startswith("/.well-known/")):
            await self.app(scope, receive, send)
            return
        if not origin_auth_required():
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])
        }
        raw, reason = _extract_bearer(headers.get("authorization"))
        ctx: AuthContext | None = None
        if raw is not None:
            ctx, reason = self.store.validate(raw)
            # Fall back to an OAuth 2.1 access token (additive second credential). The static
            # origin bearer store is tried first; unknown-there tokens may still be valid OAuth.
            if ctx is None and oauth_enabled() and self._public_base_url:
                from hb_assistant.obsidian_mcp.oauth_store import mcp_resource  # noqa: PLC0415

                ctx = _oauth_auth_context(raw, resource=mcp_resource(self._public_base_url))
                if ctx is not None:
                    reason = REASON_OK
        if ctx is None:
            self._audit_denial(path, reason)
            await self._deny(send)
            return

        token = _auth_context_var.set(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            _auth_context_var.reset(token)

    def _audit_denial(self, path: str, reason: str) -> None:
        writer = self._audit or NasMcpAuditWriter(self._config.audit_dir)
        writer.write(
            {
                "surface": "origin_auth_middleware",
                "decision": "deny",
                "deny_reason": f"origin_auth:{reason}",
                "auth_method": AUTH_METHOD_BEARER,
                "profile": active_profile(),
                "path_class": "health" if path == "/health" else "mcp",
                "write_attempted": False,
            }
        )

    def _www_authenticate(self) -> bytes:
        """When OAuth is on, point unauthenticated clients at the Protected Resource Metadata
        (RFC 9728) so they can discover the authorization server and start the flow; otherwise
        the plain bearer realm challenge."""
        if oauth_enabled() and self._public_base_url:
            from hb_assistant.obsidian_mcp import oauth_store  # noqa: PLC0415

            return oauth_store.www_authenticate_header(self._public_base_url).encode("latin1")
        return b'Bearer realm="hb-nas-mcp"'

    async def _deny(self, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", self._www_authenticate()),
                ],
            }
        )
        await send(
            {"type": "http.response.body", "body": b'{"detail":"unauthorized"}'}
        )
