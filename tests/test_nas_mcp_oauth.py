"""OAuth 2.1 / PKCE surface for the NAS MCP server (N8B).

Ports the proven obsidian ``oauth_store`` authorization-server logic onto the ``nas_mcp``
surface with a NAS-branded scope vocabulary (``nas.read``/``nas.write``) and an isolated
token/code/client store. Proves the full DCR → authorize → token → validate dance at the
route layer; that OAuth is accepted as a SECOND credential by the origin-auth middleware
alongside the static bearer; that discovery endpoints are reachable pre-token while ``/mcp``
still 401s (now advertising the RFC 9728 resource-metadata pointer); and that OAuth scope
gates the single write tool — a ``nas.read``-only token is barred from the AI-Outputs writer
even though the profile permits it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from hb_assistant.nas_mcp import oauth, origin_auth, profile
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.origin_auth import OriginAuthTokenStore
from hb_assistant.obsidian_mcp import oauth_store

BASE = "https://nas-mcp.example.me"
REDIRECT = "https://chatgpt.example.com/callback"
RESOURCE = f"{BASE}/mcp"


@pytest.fixture(autouse=True)
def _oauth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Internet-facing profile (origin auth hard-on), OAuth enabled, isolated store + NAS
    # scope vocabulary. Setting HB_OAUTH_STORE_DIR up front means configure_process_oauth's
    # setdefault is a no-op, so both the app and direct oauth_store calls share this dir.
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    monkeypatch.setenv("HB_MCP_OAUTH_ENABLED", "1")
    monkeypatch.setenv("HB_MCP_PUBLIC_BASE_URL", BASE)
    monkeypatch.setenv("HB_OAUTH_STORE_DIR", str(tmp_path / "oauth-store"))
    monkeypatch.setenv("HB_OAUTH_SUPPORTED_SCOPES", "nas.read,nas.write")
    monkeypatch.delenv("HB_MCP_ORIGIN_AUTH_HEALTH_MODE", raising=False)


def _cfg(tmp_path: Path) -> NasMcpConfig:
    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={"vault": RootSpec("vault", root, "read_write")},
        origin_auth_store_path=tmp_path / "origin-auth" / "tokens.json",
        public_base_url=BASE,
        obsidian=NasObsidianConfig(
            vault_root=root,
            backup_dir=audit / "obsidian-backups",
            support_dir=audit / "obsidian-support",
        ),
    )


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _routes_app():
    from starlette.applications import Starlette

    return Starlette(routes=oauth.build_oauth_routes(BASE))


# --------------------------------------------------------------------- route-level dance


def test_full_oauth_dance_dcr_authorize_token(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    client = TestClient(_routes_app())

    # Discovery — NAS scope vocabulary, issuer, resource.
    asm = client.get("/.well-known/oauth-authorization-server").json()
    assert asm["issuer"] == BASE
    assert asm["scopes_supported"] == ["nas.read", "nas.write"]
    assert asm["code_challenge_methods_supported"] == ["S256"]
    prm = client.get("/.well-known/oauth-protected-resource").json()
    assert prm["resource"] == RESOURCE and prm["authorization_servers"] == [BASE]

    # Dynamic Client Registration (public client, no secret). Single-user policy: the NAS
    # registers every client for the FULL scope set regardless of what it asked for.
    reg = client.post("/oauth/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT"})
    assert reg.status_code == 201
    body = reg.json()
    client_id = body["client_id"]
    assert client_id.startswith("chatgpt_") and body["scope"] == "nas.read nas.write"

    # Authorize (consent render). Even though the client requests only nas.read, the NAS grants
    # the full set — consent shows both scopes.
    verifier, challenge = _pkce()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "scope": "nas.read",
        "state": "st-123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": RESOURCE,
    }
    consent = client.get("/oauth/authorize", params=params)
    assert consent.status_code == 200
    assert "Approve" in consent.text and "nas.read" in consent.text and "nas.write" in consent.text

    # Approve → 302 back to the client with the code.
    approved = client.post("/oauth/authorize", data={**params, "decision": "approve"}, follow_redirects=False)
    assert approved.status_code == 302
    loc = urlsplit(approved.headers["location"])
    q = parse_qs(loc.query)
    assert q["state"] == ["st-123"]
    code = q["code"][0]

    # Token exchange (PKCE verified).
    tok = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    assert tok.status_code == 200
    payload = tok.json()
    assert payload["token_type"] == "Bearer" and payload["scope"] == "nas.read nas.write"
    access = payload["access_token"]

    # The minted token is bound to this resource and carries BOTH NAS scopes (single-user policy).
    info = oauth_store.validate_access_token(access, resource=RESOURCE)
    assert info is not None and info.client_id == client_id
    assert "nas.read" in info.scopes and "nas.write" in info.scopes
    # ...and is rejected for a different resource audience.
    assert oauth_store.validate_access_token(access, resource="https://other.example/mcp") is None


def test_deny_paths_bad_grant_and_bad_pkce(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    client = TestClient(_routes_app())
    client_id = client.post("/oauth/register", json={"redirect_uris": [REDIRECT]}).json()["client_id"]
    _verifier, challenge = _pkce()
    params = {
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": "nas.read", "state": "s", "code_challenge": challenge,
        "code_challenge_method": "S256", "resource": RESOURCE,
    }
    code = parse_qs(
        urlsplit(
            client.post("/oauth/authorize", data={**params, "decision": "approve"}, follow_redirects=False)
            .headers["location"]
        ).query
    )["code"][0]

    # Wrong grant type.
    bad_grant = client.post("/oauth/token", data={"grant_type": "client_credentials"})
    assert bad_grant.status_code == 400 and bad_grant.json()["error"] == "unsupported_grant_type"

    # Wrong PKCE verifier → invalid_grant.
    bad_pkce = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": client_id, "code_verifier": "not-the-verifier", "resource": RESOURCE,
        },
    )
    assert bad_pkce.status_code == 400 and bad_pkce.json()["error"] == "invalid_grant"


def test_authorize_deny_redirects_access_denied(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    client = TestClient(_routes_app())
    client_id = client.post("/oauth/register", json={"redirect_uris": [REDIRECT]}).json()["client_id"]
    _v, challenge = _pkce()
    params = {
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
        "scope": "nas.read", "state": "keep", "code_challenge": challenge,
        "code_challenge_method": "S256", "resource": RESOURCE,
    }
    denied = client.post("/oauth/authorize", data={**params, "decision": "deny"}, follow_redirects=False)
    assert denied.status_code == 302
    q = parse_qs(urlsplit(denied.headers["location"]).query)
    assert q["error"] == ["access_denied"] and q["state"] == ["keep"]


# ------------------------------------------------------------- middleware: 2nd credential


def _oauth_token(scopes: list[str], client_id: str = "chatgpt_probe") -> str:
    return oauth_store.issue_access_token(scopes=scopes, client_id=client_id, resource=RESOURCE)["access_token"]


def test_well_known_reachable_but_mcp_still_401(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    app = build_nas_mcp_asgi_app(_cfg(tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        # Discovery is reachable pre-token through the real app (routed before Mount("/")).
        prm = client.get("/.well-known/oauth-protected-resource")
        assert prm.status_code == 200 and prm.json()["resource"] == RESOURCE
        # /mcp still requires a credential, now pointing clients at the resource metadata.
        unauth = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"accept": "application/json, text/event-stream", "content-type": "application/json"},
        )
        assert unauth.status_code == 401
        assert "oauth-protected-resource" in unauth.headers.get("www-authenticate", "")


def test_oauth_token_accepted_as_second_credential(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    cfg = _cfg(tmp_path)
    app = build_nas_mcp_asgi_app(cfg)  # calls configure_process_oauth → store dir set
    raw = _oauth_token(["nas.read"])
    h = {
        "authorization": f"Bearer {raw}",
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        init = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26", "capabilities": {},
                    "clientInfo": {"name": "probe", "version": "1"},
                },
            },
            headers=h,
        )
        assert init.status_code == 200
        call = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "hb_mcp_status", "arguments": {}}},
            headers=h,
        )
        assert call.status_code == 200

    lines = (cfg.audit_dir / f"mcp-audit-{datetime.now(UTC):%Y%m%d}.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    assert all(raw not in line for line in lines)  # OAuth token never in audit
    allow = next(e for e in events if e.get("tool_name") == "hb_mcp_status")
    assert allow["auth_method"] == "oauth"
    assert allow["client"] == "oauth"
    assert allow["client_label"] == "chatgpt_probe"


# ------------------------------------------------------------- scope gates the one write


def _run_authed(broker, ctx, tool: str, args: dict) -> dict:
    token = origin_auth._auth_context_var.set(ctx)
    try:
        return broker.dispatch(tool, args)
    finally:
        origin_auth._auth_context_var.reset(token)


def test_read_scope_oauth_barred_from_write_tool(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    # Mirror what the middleware builds for a nas.read-only OAuth token.
    ctx = origin_auth.AuthContext(
        client="oauth", client_label="chatgpt_probe", actor="oauth:chatgpt_probe",
        token_id="chatgpt_probe", tier="oauth",
        denied_tools=(profile.AI_OUTPUTS_WRITE_TOOL,), auth_method="oauth",
    )
    denied = _run_authed(
        broker, ctx, "ai_outputs_card_upsert",
        {"title": "N", "body_markdown": "# x", "source_client": "chatgpt", "mode": "create"},
    )
    assert denied["ok"] is False and "tool_denied_by_token_scope" in denied["error"]
    # A read tool is unaffected by the denylist.
    assert _run_authed(broker, ctx, "hb_mcp_status", {})["ok"] is True


def test_write_scope_oauth_allowed_through_denylist_gate(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    cfg = _cfg(tmp_path)
    broker = NasMcpBroker(cfg)
    # nas.write present → denied_tools empty → the write tool passes the scope gate and,
    # under the remote profile, the folder-locked AI-Outputs write succeeds.
    ctx = origin_auth.AuthContext(
        client="oauth", client_label="chatgpt_probe", actor="oauth:chatgpt_probe",
        token_id="chatgpt_probe", tier="oauth", denied_tools=(), auth_method="oauth",
    )
    ok = _run_authed(
        broker, ctx, "ai_outputs_card_upsert",
        {"title": "Note One", "body_markdown": "# hi", "source_client": "chatgpt", "mode": "create"},
    )
    assert ok["ok"] is True


def test_oauth_context_builder_maps_scope_to_denied_tools(tmp_path: Path) -> None:
    # Directly exercise the middleware's OAuth-context builder for both scope postures.
    read_raw = _oauth_token(["nas.read"], client_id="chatgpt_read")
    write_raw = _oauth_token(["nas.read", "nas.write"], client_id="chatgpt_write")
    read_ctx = origin_auth._oauth_auth_context(read_raw, resource=RESOURCE)
    write_ctx = origin_auth._oauth_auth_context(write_raw, resource=RESOURCE)
    assert read_ctx is not None and read_ctx.denied_tools == (profile.AI_OUTPUTS_WRITE_TOOL,)
    assert read_ctx.auth_method == "oauth" and read_ctx.client_label == "chatgpt_read"
    assert write_ctx is not None and write_ctx.denied_tools == ()
    # Wrong audience → no context (returns None, never raises).
    assert origin_auth._oauth_auth_context(read_raw, resource="https://other/mcp") is None


def test_gate_status_surfaces_oauth_enabled() -> None:
    assert profile.gate_status()["oauth_enabled"] is True


def test_oauth_disabled_leaves_bearer_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With OAuth off, discovery/flow paths are NOT bypassed and a valid OAuth token is not
    accepted — the surface falls back to origin bearer only."""
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    monkeypatch.setenv("HB_MCP_OAUTH_ENABLED", "0")
    cfg = _cfg(tmp_path)
    # Mint a token in the store (valid material) — must still be rejected when OAuth is off.
    OriginAuthTokenStore(cfg.origin_auth_store_path)  # ensure dir exists
    raw = _oauth_token(["nas.read"])
    app = build_nas_mcp_asgi_app(cfg)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        # Discovery path is now gated by origin auth (no OAuth bypass) → 401.
        assert client.get("/.well-known/oauth-protected-resource").status_code == 401
        rej = client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "authorization": f"Bearer {raw}",
                "accept": "application/json, text/event-stream",
                "content-type": "application/json",
            },
        )
        assert rej.status_code == 401  # OAuth token not honored when the feature is off
