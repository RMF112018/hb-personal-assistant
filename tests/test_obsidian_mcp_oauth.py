"""Phase 3A — OAuth 2.1 / PKCE adapter for Grok Remote MCP.

Proves the Authorization-Code-with-PKCE flow added to the UI-managed Obsidian
MCP server: discovery metadata, authorize validation, single-use + expiring
codes, PKCE verification, token issuance/expiry, per-tool scope enforcement,
static-bearer coexistence, ``/mcp`` authentication, and no token/code leakage.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import api as api_module
from hb_assistant.construction.analytics.api import create_app
from hb_assistant.obsidian_mcp import config as config_module
from hb_assistant.obsidian_mcp import mcp_app, oauth_store
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfigPatch, apply_patch
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

REDIRECT_URI = "https://grok.example.com/connector/callback"
BASE_URL = "https://seafood-gene-relief-league.trycloudflare.com"

# Raw token/code shapes that must never leak in advisory responses.
_FORBIDDEN_MARKERS = ("BEGIN RSA", "BEGIN PRIVATE", "?sig=", "AKIA", "sk-")


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _enable_oauth(*, public_base_url: str | None = BASE_URL) -> None:
    apply_patch(ObsidianMcpConfigPatch(oauth_enabled=True, public_base_url=public_base_url))


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(db_path=str(tmp_path / "config.sqlite")))


def _authorize(client: TestClient, *, scope: str, challenge: str) -> str:
    response = client.post(
        "/oauth/authorize",
        data={
            "response_type": "code",
            "client_id": oauth_store.CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": scope,
            "state": "xyz-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "decision": "approve",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    query = parse_qs(urlsplit(location).query)
    assert query["state"] == ["xyz-state"]
    return query["code"][0]


def _token(client: TestClient, *, code: str, verifier: str) -> dict:
    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": oauth_store.CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    return {"status": response.status_code, "body": response.json()}


def test_authorization_server_metadata(tmp_path: Path) -> None:
    _enable_oauth()
    body = _client(tmp_path).get("/.well-known/oauth-authorization-server").json()
    assert body["issuer"] == BASE_URL
    assert body["authorization_endpoint"] == f"{BASE_URL}/oauth/authorize"
    assert body["token_endpoint"] == f"{BASE_URL}/oauth/token"
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert body["token_endpoint_auth_methods_supported"] == ["none"]
    assert body["scopes_supported"] == ["obsidian.read", "obsidian.write"]


def test_protected_resource_metadata(tmp_path: Path) -> None:
    _enable_oauth()
    body = _client(tmp_path).get("/.well-known/oauth-protected-resource").json()
    assert body["resource"] == f"{BASE_URL}/mcp"
    assert body["authorization_servers"] == [BASE_URL]


def test_authorize_renders_consent_with_scopes_and_vault(tmp_path: Path) -> None:
    _enable_oauth()
    _, challenge = _pkce()
    response = _client(tmp_path).get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_store.CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "obsidian.read obsidian.write",
            "state": "s",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 200
    assert "obsidian.read" in response.text and "obsidian.write" in response.text
    assert "Vault root" in response.text


def test_authorize_rejects_missing_pkce_and_bad_client(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    base = {
        "response_type": "code",
        "client_id": oauth_store.CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "obsidian.read",
        "code_challenge_method": "S256",
    }
    assert client.get("/oauth/authorize", params=base).status_code == 400  # no code_challenge
    _, challenge = _pkce()
    bad_client = {**base, "client_id": "someone-else", "code_challenge": challenge}
    assert client.get("/oauth/authorize", params=bad_client).status_code == 400


def test_authorize_disabled_returns_403(tmp_path: Path) -> None:
    _, challenge = _pkce()
    response = _client(tmp_path).get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_store.CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "obsidian.read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 403


def test_token_exchange_success(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read obsidian.write", challenge=challenge)
    result = _token(client, code=code, verifier=verifier)
    assert result["status"] == 200
    body = result["body"]
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["scope"] == "obsidian.read obsidian.write"
    assert oauth_store.validate_access_token(body["access_token"]) is not None


def test_pkce_mismatch_rejected(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    _, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read", challenge=challenge)
    result = _token(client, code=code, verifier="not-the-verifier")
    assert result["status"] == 400
    assert result["body"]["error"] == "invalid_grant"


def test_code_is_single_use(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read", challenge=challenge)
    assert _token(client, code=code, verifier=verifier)["status"] == 200
    reuse = _token(client, code=code, verifier=verifier)
    assert reuse["status"] == 400
    assert reuse["body"]["error"] == "invalid_grant"


def test_expired_code_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read", challenge=challenge)
    real_now = oauth_store._now()
    monkeypatch.setattr(oauth_store, "_now", lambda: real_now + oauth_store.CODE_TTL_SECONDS + 5)
    result = _token(client, code=code, verifier=verifier)
    assert result["status"] == 400
    assert result["body"]["error"] == "invalid_grant"


def test_expired_token_not_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read", challenge=challenge)
    token = _token(client, code=code, verifier=verifier)["body"]["access_token"]
    assert oauth_store.validate_access_token(token) is not None
    real_now = oauth_store._now()
    monkeypatch.setattr(oauth_store, "_now", lambda: real_now + oauth_store.TOKEN_TTL_SECONDS + 5)
    assert oauth_store.validate_access_token(token) is None


def test_scope_enforcement_read_token_cannot_write(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read", challenge=challenge)
    token = _token(client, code=code, verifier=verifier)["body"]["access_token"]
    config = config_module.load_config()
    header = f"Bearer {token}"
    # Read tools allowed (including the read-only curation tools).
    mcp_app.enforce_tool_scope("read_file", header, config)
    mcp_app.enforce_tool_scope("list_directory", header, config)
    mcp_app.enforce_tool_scope("vault_map", header, config)
    mcp_app.enforce_tool_scope("vault_summarize_note", header, config)
    mcp_app.enforce_tool_scope("vault_summarize_folder", header, config)
    mcp_app.enforce_tool_scope("vault_read_eml", header, config)
    mcp_app.enforce_tool_scope("vault_email_inventory", header, config)
    mcp_app.enforce_tool_scope("vault_parse_email", header, config)
    mcp_app.enforce_tool_scope("vault_read_frontmatter", header, config)
    mcp_app.enforce_tool_scope("vault_search_by_properties", header, config)
    mcp_app.enforce_tool_scope("vault_dataview_query", header, config)
    mcp_app.enforce_tool_scope("vault_get_backlinks", header, config)
    mcp_app.enforce_tool_scope("vault_get_unlinked_mentions", header, config)
    mcp_app.enforce_tool_scope("vault_get_note_graph", header, config)
    mcp_app.enforce_tool_scope("vault_curation_plan", header, config)
    # Write tools blocked (including curation apply + frontmatter update + template writes).
    with pytest.raises(ObsidianMcpToolError) as exc:
        mcp_app.enforce_tool_scope("create_note", header, config)
    assert exc.value.code == "insufficient_scope"
    with pytest.raises(ObsidianMcpToolError) as exc_tpl:
        mcp_app.enforce_tool_scope("vault_create_note_from_template", header, config)
    assert exc_tpl.value.code == "insufficient_scope"
    with pytest.raises(ObsidianMcpToolError) as exc_daily:
        mcp_app.enforce_tool_scope("vault_append_to_daily_note", header, config)
    assert exc_daily.value.code == "insufficient_scope"
    with pytest.raises(ObsidianMcpToolError) as exc_apply:
        mcp_app.enforce_tool_scope("vault_curation_apply", header, config)
    assert exc_apply.value.code == "insufficient_scope"
    with pytest.raises(ObsidianMcpToolError) as exc_fm:
        mcp_app.enforce_tool_scope("vault_update_frontmatter", header, config)
    assert exc_fm.value.code == "insufficient_scope"


def test_scope_enforcement_write_token_allows_write(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read obsidian.write", challenge=challenge)
    token = _token(client, code=code, verifier=verifier)["body"]["access_token"]
    config = config_module.load_config()
    header = f"Bearer {token}"
    mcp_app.enforce_tool_scope("create_note", header, config)  # no raise
    mcp_app.enforce_tool_scope("patch_note", header, config)
    mcp_app.enforce_tool_scope("vault_curation_apply", header, config)
    mcp_app.enforce_tool_scope("vault_update_frontmatter", header, config)
    mcp_app.enforce_tool_scope("vault_create_note_from_template", header, config)
    mcp_app.enforce_tool_scope("vault_append_to_daily_note", header, config)


def test_static_bearer_is_unrestricted(tmp_path: Path) -> None:
    apply_patch(ObsidianMcpConfigPatch(bearer_token="static-local-token", oauth_enabled=True))
    config = config_module.load_config()
    header = "Bearer static-local-token"
    assert mcp_app.is_authorized(header, config) is True
    assert mcp_app.resolve_granted_scopes(header, config) is None
    mcp_app.enforce_tool_scope("create_note", header, config)  # static token = full access


def test_no_auth_configured_is_unrestricted(tmp_path: Path) -> None:
    config = config_module.load_config()  # defaults: no token, oauth disabled
    mcp_app.enforce_tool_scope("create_note", None, config)
    assert mcp_app.resolve_granted_scopes(None, config) is None


@pytest.mark.parametrize("authorization", [None, "Bearer bogus-token"])
def test_mcp_rejects_missing_or_bad_token(tmp_path: Path, authorization: str | None) -> None:
    pytest.importorskip("mcp")
    _enable_oauth()
    client = _client(tmp_path)
    headers = {"authorization": authorization} if authorization else {}
    response = client.post("/mcp", headers=headers, content=b"{}")
    assert response.status_code == 401


def _middleware_client() -> TestClient:
    """Wrap the auth middleware around a trivial inner app to test the allow-path.

    Driving the live MCP session manager under TestClient needs its ASGI lifespan;
    here we only exercise the middleware's authentication decision.
    """
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route

    async def _ok(_request: object) -> PlainTextResponse:
        return PlainTextResponse("ok")

    inner = Starlette(routes=[Route("/mcp", _ok, methods=["GET", "POST"])])
    return TestClient(mcp_app.BearerTokenMiddleware(inner))


def test_middleware_accepts_valid_oauth_token(tmp_path: Path) -> None:
    _enable_oauth()
    token = oauth_store.issue_access_token(["obsidian.read"])["access_token"]
    client = _middleware_client()
    assert client.post("/mcp", headers={"authorization": f"Bearer {token}"}).status_code == 200
    assert client.post("/mcp", headers={"authorization": "Bearer bogus"}).status_code == 401
    assert client.post("/mcp").status_code == 401


def test_middleware_static_bearer_still_works(tmp_path: Path) -> None:
    apply_patch(ObsidianMcpConfigPatch(bearer_token="static-local-token"))
    client = _middleware_client()
    assert client.post("/mcp", headers={"authorization": "Bearer static-local-token"}).status_code == 200
    assert client.post("/mcp", headers={"authorization": "Bearer wrong"}).status_code == 401


def test_ui_oauth_status_has_no_token_leak(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    verifier, challenge = _pkce()
    code = _authorize(client, scope="obsidian.read obsidian.write", challenge=challenge)
    token = _token(client, code=code, verifier=verifier)["body"]["access_token"]

    response = client.get("/api/settings/obsidian-mcp/oauth")
    assert response.status_code == 200
    body = response.json()
    assert body["oauth_enabled"] is True
    assert body["client_id"] == oauth_store.CLIENT_ID
    assert body["token_auth_method"] == "none (PKCE)"
    assert body["grok_setup"]["mcp_url"] == f"{BASE_URL}/mcp"
    assert body["grok_setup"]["authorization_endpoint"] == f"{BASE_URL}/oauth/authorize"
    # Recorded events exist but never carry the raw token or code.
    kinds = {event["kind"] for event in body["recent_events"]}
    assert "access_token_issued" in kinds
    text = response.text
    assert token not in text
    assert code not in text
    for marker in _FORBIDDEN_MARKERS:
        assert marker not in text, marker


def test_deny_redirects_with_access_denied(tmp_path: Path) -> None:
    _enable_oauth()
    client = _client(tmp_path)
    _, challenge = _pkce()
    response = client.post(
        "/oauth/authorize",
        data={
            "response_type": "code",
            "client_id": oauth_store.CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "obsidian.read",
            "state": "s",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "decision": "deny",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["error"] == ["access_denied"]


def test_unused_import_guard() -> None:
    # api_module is imported to assert the OAuth helpers are module-level (importable).
    assert callable(api_module._oauth_consent_html)
    assert callable(api_module._oauth_error_html)
