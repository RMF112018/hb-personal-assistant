"""Origin-side bearer auth for the NAS MCP surface (nas_mcp:8765).

Defense-in-depth: the origin rejects unauthenticated MCP even if Cloudflare Access is
bypassed. Proves missing/malformed/unknown/revoked/expired are denied, valid is allowed,
audit carries the authenticated actor/client label, no token ever leaks into audit, the
capability profile still blocks tier-4/5 + broad writes even with a valid token, and the
health endpoint does not leak sensitive detail unauthenticated.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hb_assistant.nas_mcp import origin_auth, profile
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.origin_auth import (
    OriginAuthError,
    OriginAuthTokenStore,
    get_auth_context,
)


@pytest.fixture(autouse=True)
def _remote_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default all tests to the internet-facing profile (origin auth hard-on).
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    monkeypatch.delenv("HB_MCP_ORIGIN_AUTH_HEALTH_MODE", raising=False)


def _store(tmp_path: Path) -> OriginAuthTokenStore:
    return OriginAuthTokenStore(tmp_path / "origin-auth" / "tokens.json")


def _cfg(tmp_path: Path) -> NasMcpConfig:
    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={"vault": RootSpec("vault", root, "read_write")},
        origin_auth_store_path=tmp_path / "origin-auth" / "tokens.json",
        obsidian=NasObsidianConfig(
            vault_root=root,
            backup_dir=audit / "obsidian-backups",
            support_dir=audit / "obsidian-support",
        ),
    )


def _mint(store: OriginAuthTokenStore, **kw: object) -> tuple[str, dict]:
    defaults = {
        "client": "claude", "client_label": "Claude Desktop",
        "actor": "bfetting", "expires_days": 30,
    }
    defaults.update(kw)
    return store.create_token(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- store


def test_token_hashed_never_persisted_and_0600(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw, rec = _mint(store)
    path = tmp_path / "origin-auth" / "tokens.json"
    contents = path.read_text(encoding="utf-8")
    assert raw not in contents  # raw token never persisted
    assert rec["fingerprint"] in contents  # only the hash prefix fingerprint
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_validate_roundtrip_and_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw, _ = _mint(store)
    ctx, reason = store.validate(raw)
    assert reason == "ok" and ctx is not None
    assert ctx.client == "claude" and ctx.actor == "bfetting"
    assert store.validate("not-a-real-token")[1] == "unknown_token"


def test_expired_token_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path)
    raw, _ = _mint(store, expires_days=1)
    monkeypatch.setattr(origin_auth, "_now", lambda: datetime.now(UTC) + timedelta(days=2))
    assert store.validate(raw)[1] == "expired"


def test_revoked_token_denied(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw, rec = _mint(store)
    assert store.revoke(rec["token_id"]) is True
    assert store.validate(raw)[1] == "revoked"
    assert store.revoke(rec["token_id"]) is False  # already revoked / idempotent-false


def test_rotate_revokes_old_mints_new(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw_old, rec = _mint(store)
    raw_new, rec_new = store.rotate(rec["token_id"])
    assert store.validate(raw_old)[1] == "revoked"
    ctx, reason = store.validate(raw_new)
    assert reason == "ok" and ctx is not None
    assert ctx.client_label == "Claude Desktop"  # attributes carried forward
    assert rec_new["token_id"] != rec["token_id"]


def test_list_tokens_has_no_secrets(tmp_path: Path) -> None:
    store = _store(tmp_path)
    raw, _ = _mint(store)
    listed = store.list_tokens()
    blob = json.dumps(listed)
    assert raw not in blob
    assert origin_auth._sha256(raw) not in blob  # not even the hash key
    assert set(listed[0]) == {
        "token_id", "client", "client_label", "actor", "issued_at",
        "expires_at", "revoked", "tier", "allowed_tools", "fingerprint",
    }


def test_create_rejects_unknown_client(tmp_path: Path) -> None:
    with pytest.raises(OriginAuthError):
        _mint(_store(tmp_path), client="rogue")


# ------------------------------------------------------------------- middleware/app


def _post_mcp(client, headers: dict[str, str] | None = None):
    base = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    base.update(headers or {})
    return client.post(
        "/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=base
    )


@pytest.fixture()
def app_and_token(tmp_path: Path):
    """Returns (build_app, raw_token, record, cfg). ``build_app()`` yields a FRESH ASGI
    app each call — the MCP session manager can only .run() once per instance, so any
    test opening multiple TestClient sessions must build a new app per session."""
    pytest.importorskip("mcp")
    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    cfg = _cfg(tmp_path)
    store = OriginAuthTokenStore(cfg.origin_auth_store_path)  # type: ignore[arg-type]
    raw, rec = _mint(store)
    return (lambda: build_nas_mcp_asgi_app(cfg)), raw, rec, cfg


def test_mcp_denied_without_auth(app_and_token) -> None:
    from starlette.testclient import TestClient

    build_app, _raw, _rec, _cfg = app_and_token
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        resp = _post_mcp(client)
        assert resp.status_code == 401
        assert resp.json() == {"detail": "unauthorized"}  # uniform, no existence leak


def test_mcp_denied_bad_and_malformed_bearer(app_and_token) -> None:
    from starlette.testclient import TestClient

    build_app, _raw, _rec, _cfg = app_and_token
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        assert _post_mcp(client, {"authorization": "Bearer wrong-token"}).status_code == 401
        assert _post_mcp(client, {"authorization": "Basic abc"}).status_code == 401
        assert _post_mcp(client, {"authorization": "Bearer "}).status_code == 401


def test_mcp_denied_revoked_and_expired(app_and_token, monkeypatch: pytest.MonkeyPatch) -> None:
    from starlette.testclient import TestClient

    build_app, raw, rec, cfg = app_and_token
    store = OriginAuthTokenStore(cfg.origin_auth_store_path)
    store.revoke(rec["token_id"])
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        assert _post_mcp(client, {"authorization": f"Bearer {raw}"}).status_code == 401
    # a fresh valid token, then jump past expiry
    raw2, _ = _mint(store, expires_days=1)
    monkeypatch.setattr(origin_auth, "_now", lambda: datetime.now(UTC) + timedelta(days=3))
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        assert _post_mcp(client, {"authorization": f"Bearer {raw2}"}).status_code == 401


def test_valid_token_allowed_and_audit_attribution(app_and_token) -> None:
    """End-to-end: valid bearer runs a tool call; audit carries actor/client, no leak."""
    from starlette.testclient import TestClient

    build_app, raw, _rec, cfg = app_and_token
    h = {
        "authorization": f"Bearer {raw}",
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
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
            json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hb_mcp_status", "arguments": {}},
            },
            headers=h,
        )
        assert call.status_code == 200

    lines = (cfg.audit_dir / f"mcp-audit-{datetime.now(UTC):%Y%m%d}.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    assert all(raw not in line for line in lines)  # no token value in audit
    allow = next(e for e in events if e.get("tool_name") == "hb_mcp_status")
    assert allow["authenticated"] is True
    assert allow["client_label"] == "Claude Desktop"
    assert allow["actor"] == "bfetting"
    assert allow["client"] == "claude"
    # a middleware denial (if any) records a reason class, never a token
    denies = [e for e in events if e.get("decision") == "deny"]
    for d in denies:
        assert d["deny_reason"].startswith("origin_auth:") or "blocked" in d["deny_reason"]


# ------------------------------------------------------ profile/capability under auth


def _authed(ctx: origin_auth.AuthContext):
    """Context manager-ish helper to run with an auth context set."""
    return origin_auth._auth_context_var, ctx


def test_valid_token_cannot_call_blocked_or_scratch_writes(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    ctx = origin_auth.AuthContext(
        client="claude", client_label="Claude Desktop", actor="bfetting", token_id="t1"
    )
    token = origin_auth._auth_context_var.set(ctx)
    try:
        assert get_auth_context() is ctx
        broad = broker.dispatch("create_note", {"path": "x.md", "content": "y"})
        assert broad["ok"] is False and "blocked_by_profile" in broad["error"]
        scratch = broker.dispatch("hb_output_write_file", {"relative_path": "a.txt", "content": "z"})
        assert scratch["ok"] is False and "blocked_by_profile" in scratch["error"]
    finally:
        origin_auth._auth_context_var.reset(token)


def test_valid_token_can_call_ai_outputs_but_not_outside_folder(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    cfg = _cfg(tmp_path)
    broker = NasMcpBroker(cfg)
    ctx = origin_auth.AuthContext(
        client="claude", client_label="Claude Desktop", actor="bfetting", token_id="t1"
    )
    token = origin_auth._auth_context_var.set(ctx)
    try:
        ok = broker.dispatch(
            "ai_outputs_card_upsert",
            {"title": "Note One", "body_markdown": "# hi", "source_client": "claude", "mode": "create"},
        )
        assert ok["ok"] is True
        # A traversal-y title must never write outside the AI Outputs folder, even with a
        # valid token — the folder-lock slugs traversal chars away.
        broker.dispatch(
            "ai_outputs_card_upsert",
            {"title": "../../escape", "body_markdown": "x", "source_client": "claude", "mode": "create"},
        )
        vault = cfg.roots["vault"].mount
        stray = [p for p in vault.parent.rglob("*.md") if "AI Outputs" not in str(p)]
        assert not stray  # every card lives under AI Outputs; nothing escaped
    finally:
        origin_auth._auth_context_var.reset(token)


def test_allowed_tools_narrowing(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    ctx = origin_auth.AuthContext(
        client="claude", client_label="Scoped", actor="bfetting", token_id="t2",
        allowed_tools=("hb_mcp_status",),
    )
    token = origin_auth._auth_context_var.set(ctx)
    try:
        assert broker.dispatch("hb_mcp_status", {})["ok"] is True
        denied = broker.dispatch("hb_root_list", {"root_key": "vault"})
        assert denied["ok"] is False and "tool_not_in_token_scope" in denied["error"]
    finally:
        origin_auth._auth_context_var.reset(token)


# ------------------------------------------------------------------------- health


def test_health_minimal_public_hides_detail(app_and_token) -> None:
    from starlette.testclient import TestClient

    build_app, _raw, _rec, _cfg = app_and_token
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        resp = client.get("/health")
        assert resp.status_code == 200  # liveness reachable unauthenticated
        body = resp.json()
        assert body["status"] == "ok"
        assert body["origin_auth_required"] is True
        # no sensitive detail
        assert "configured_roots" not in body
        assert "allowlisted_table_keys" not in body
        assert "guardrails" not in body


def test_health_protected_requires_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    monkeypatch.setenv("HB_MCP_ORIGIN_AUTH_HEALTH_MODE", "protected")
    cfg = _cfg(tmp_path)
    store = OriginAuthTokenStore(cfg.origin_auth_store_path)  # type: ignore[arg-type]
    raw, _ = _mint(store)
    app = build_nas_mcp_asgi_app(cfg)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/health").status_code == 401  # gated
        ok = client.get("/health", headers={"authorization": f"Bearer {raw}"})
        assert ok.status_code == 200
        assert "configured_roots" in ok.json()  # detailed once authenticated


# --------------------------------------------------------------- signals + hard-on


def test_gate_status_surfaces_origin_auth_signals() -> None:
    status = profile.gate_status()
    assert status["origin_auth_required"] is True
    assert status["health_mode"] == "minimal_public"


def test_remote_profile_origin_auth_is_hard_on(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even an explicit disable env cannot turn off origin auth in the remote profile.
    monkeypatch.setenv("HB_MCP_ORIGIN_AUTH_REQUIRED", "0")
    assert profile.origin_auth_required() is True
    monkeypatch.setenv("HB_MCP_PROFILE", "local_trusted")
    assert profile.origin_auth_required() is False  # trusted profile honors the override


# ------------------------------------------------------------------------- CLI


def test_cli_create_lists_and_revokes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hb_assistant.nas_mcp import origin_auth_cli

    store_path = str(tmp_path / "tokens.json")
    rc = origin_auth_cli.main(
        ["--store", store_path, "create-token", "--client", "grok",
         "--label", "Grok", "--actor", "bfetting", "--expires-days", "7"]
    )
    assert rc == 0
    out = capsys.readouterr()
    raw = out.out.strip()  # raw token printed to stdout (once)
    assert raw and raw not in out.err  # secret only on stdout, not the notice on stderr

    rc = origin_auth_cli.main(["--store", store_path, "list-tokens"])
    assert rc == 0
    listing = capsys.readouterr().out
    assert raw not in listing  # never re-shown
    token_id = json.loads(listing)[0]["token_id"]

    rc = origin_auth_cli.main(["--store", store_path, "revoke-token", "--token-id", token_id])
    assert rc == 0
    assert '"revoked": true' in capsys.readouterr().out
