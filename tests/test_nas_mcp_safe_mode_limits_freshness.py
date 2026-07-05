"""N8B safe mode + rate limits + operator overrides + read-only freshness/status.

Proves the remotely reachable NAS MCP survives real LLM/agent behavior before live
Cloudflare: safe mode blocks mutations while keeping reads/status; rate limits (rows,
search, card size, write-window, concurrency) fail closed and audit; operator overrides are
local-only, narrow, expiring, revocable, raise-only, and cannot be created remotely; and
freshness/queue/failure/capability tools return redacted aggregates requiring origin auth.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hb_assistant.nas_mcp import limits, overrides
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec


@pytest.fixture(autouse=True)
def _remote_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    for var in (
        "HB_MCP_SAFE_MODE", "HB_MCP_MAX_ROWS", "HB_MCP_MAX_SEARCH_RESULTS", "HB_MCP_MAX_CARD_BYTES",
        "HB_MCP_MAX_AI_OUTPUTS_WRITES_PER_WINDOW", "HB_MCP_WRITE_WINDOW_SECONDS",
        "HB_MCP_MAX_CONCURRENT_CALLS", "HB_OBSIDIAN_MCP_SUPPORT_DIR",
    ):
        monkeypatch.delenv(var, raising=False)


def _cfg(tmp_path: Path) -> NasMcpConfig:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        origin_auth_store_path=tmp_path / "tokens.json",
        override_store_path=tmp_path / "overrides.json",
        obsidian=NasObsidianConfig(
            vault_root=vault,
            backup_dir=audit / "obsidian-backups",
            support_dir=tmp_path / "support",
        ),
    )


def _seed_db(cfg: NasMcpConfig) -> None:
    conn = sqlite3.connect(cfg.db_path)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)")
    conn.execute("INSERT INTO schema_migrations VALUES (99,'v99','2026-07-05 10:00:00')")
    conn.execute(
        "CREATE TABLE source_intelligence_events (event_id TEXT, status TEXT, error_code TEXT, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO source_intelligence_events VALUES (?,?,?,?)",
        [("e1", "queued", None, "2026-07-05 09:00:00"), ("e2", "error", "boom", "2026-07-05 09:05:00")],
    )
    conn.commit()
    conn.close()


def _audit_events(cfg: NasMcpConfig) -> list[dict]:
    day = datetime.now(UTC).strftime("%Y%m%d")
    path = cfg.audit_dir / f"mcp-audit-{day}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ------------------------------------------------------------------------ safe mode


def test_safe_mode_allows_status_and_freshness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    broker = NasMcpBroker(cfg)
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    assert broker.dispatch("hb_mcp_status", {})["ok"] is True
    assert broker.dispatch("hb_data_freshness", {})["ok"] is True
    assert broker.dispatch("hb_capability_mode", {})["result"]["exposure_profile"]["safe_mode"] is True


def test_safe_mode_denies_ai_outputs_and_mutations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broker = NasMcpBroker(_cfg(tmp_path))
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    w = broker.dispatch(
        "ai_outputs_card_upsert", {"title": "X", "body_markdown": "y", "source_client": "claude", "mode": "create"}
    )
    assert w["ok"] is False and w["error"] == "safe_mode_active:ai_outputs_card_upsert"
    # a broad vault write is also denied by safe mode (before the profile gate)
    v = broker.dispatch("create_note", {"path": "x.md", "content": "y"})
    assert v["ok"] is False and v["error"].startswith("safe_mode_active:")


def test_safe_mode_denial_is_audited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    broker = NasMcpBroker(cfg)
    monkeypatch.setenv("HB_MCP_SAFE_MODE", "1")
    broker.dispatch("ai_outputs_card_upsert", {"title": "X", "body_markdown": "y", "source_client": "claude"})
    denies = [e for e in _audit_events(cfg) if e.get("decision") == "deny"]
    assert any(e["deny_reason"].startswith("safe_mode_active:") and e["safe_mode"] is True for e in denies)


# ------------------------------------------------------------------------ rate limits


def test_rows_capped_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    conn = sqlite3.connect(cfg.db_path)
    conn.execute("CREATE TABLE nas_mcp_test_items (id INTEGER, label TEXT, category TEXT)")
    conn.executemany("INSERT INTO nas_mcp_test_items VALUES (?,?,?)", [(i, f"l{i}", "c") for i in range(5)])
    conn.commit()
    conn.close()
    from hb_assistant.nas_mcp.db_allowlist import clear_test_allowlist, register_test_allowlist

    register_test_allowlist()
    try:
        monkeypatch.setenv("HB_MCP_MAX_ROWS", "2")
        broker = NasMcpBroker(cfg)
        r = broker.dispatch("hb_db_select", {"table_key": "nas_mcp_test_items", "columns": ["id"], "limit": 100})
        assert r["ok"] is True
        assert len(r["result"]["rows"]) <= 2  # env cap wins
    finally:
        clear_test_allowlist()


def test_search_results_capped_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    for i in range(5):
        (cfg.roots["vault"].mount / f"match{i}.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("HB_MCP_MAX_SEARCH_RESULTS", "2")
    broker = NasMcpBroker(cfg)
    r = broker.dispatch("hb_vault_search", {"query": "match", "limit": 100})
    assert r["ok"] is True and r["result"]["match_count"] <= 2


def test_oversized_card_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_MAX_CARD_BYTES", "16")
    broker = NasMcpBroker(_cfg(tmp_path))
    r = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Big", "body_markdown": "x" * 500, "source_client": "claude", "mode": "create"},
    )
    assert r["ok"] is False and "body_too_large" in r["error"]


def test_write_window_blocks_repeated_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    monkeypatch.setenv("HB_MCP_MAX_AI_OUTPUTS_WRITES_PER_WINDOW", "1")
    monkeypatch.setenv("HB_MCP_WRITE_WINDOW_SECONDS", "3600")
    broker = NasMcpBroker(cfg)
    first = broker.dispatch(
        "ai_outputs_card_upsert", {"title": "One", "body_markdown": "a", "source_client": "claude", "mode": "create"}
    )
    assert first["ok"] is True
    second = broker.dispatch(
        "ai_outputs_card_upsert", {"title": "Two", "body_markdown": "b", "source_client": "claude", "mode": "create"}
    )
    assert second["ok"] is False and second["error"] == limits.DENY_WRITE_RATE
    assert any(e.get("rate_limit_result") == limits.DENY_WRITE_RATE for e in _audit_events(cfg))


def test_write_window_fails_closed_on_unreadable_or_corrupt_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _cfg(tmp_path)
    support = cfg.obsidian.support_dir
    support.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(support))
    args = {"title": "One", "body_markdown": "a", "source_client": "claude", "mode": "create"}

    # Corrupt/unparseable receipt line → deny (never fail open to 0).
    (support / "mutations.jsonl").write_text("{not valid json\n", encoding="utf-8")
    broker = NasMcpBroker(cfg)
    r = broker.dispatch("ai_outputs_card_upsert", args)
    assert r["ok"] is False and r["error"] == limits.DENY_WRITE_STATE
    assert any(e.get("rate_limit_result") == limits.DENY_WRITE_STATE for e in _audit_events(cfg))

    # Existing-but-unreadable receipt path (a directory where the file is expected) → deny.
    (support / "mutations.jsonl").unlink()
    (support / "mutations.jsonl").mkdir()
    r2 = NasMcpBroker(cfg).dispatch("ai_outputs_card_upsert", args)
    assert r2["ok"] is False and r2["error"] == limits.DENY_WRITE_STATE


def test_write_window_state_error_missing_file_is_zero(tmp_path: Path) -> None:
    # A missing receipt file on a clean first run is NOT a state error — counts as 0.
    cfg = _cfg(tmp_path)
    cfg.obsidian.support_dir.mkdir(parents=True, exist_ok=True)
    assert limits.recent_ai_outputs_write_count(cfg, 3600) == 0


def test_binary_and_broad_scan_denied(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    (cfg.roots["vault"].mount / "b.bin").write_bytes(b"\x00\x01\x02\x03binary")
    broker = NasMcpBroker(cfg)
    binr = broker.dispatch("hb_vault_read_excerpt", {"relative_path": "b.bin"})
    assert binr["ok"] is False and "binary" in binr["error"].lower()
    # traversal / denied path
    trav = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "../../etc/passwd"})
    assert trav["ok"] is False


def test_concurrency_limiter_unit() -> None:
    lim = limits.ConcurrencyLimiter(2)
    assert lim.try_acquire() and lim.try_acquire()
    assert lim.try_acquire() is False  # over cap
    lim.release()
    assert lim.try_acquire() is True


# ------------------------------------------------------------------------ overrides


def test_no_mcp_tool_can_create_override(tmp_path: Path) -> None:
    """Remote self-approval is structurally impossible — no dispatch path mints an override."""
    broker = NasMcpBroker(_cfg(tmp_path))
    for name in ("override_create", "create_override", "hb_override_create"):
        r = broker.dispatch(name, {"scope": "rows", "max_value": 9999})
        assert r["ok"] is False  # tool_not_registered


def test_operator_cli_creates_and_revokes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hb_assistant.nas_mcp import override_cli

    store = str(tmp_path / "ovr.json")
    rc = override_cli.main(
        ["--store", store, "create", "--scope", "rows", "--max-value", "500",
         "--client", "claude", "--expires-minutes", "30", "--reason", "triage"]
    )
    assert rc == 0
    rec = json.loads(capsys.readouterr().out)
    assert rec["scope"] == "rows" and rec["reason"] == "triage" and rec["revoked"] is False
    rc = override_cli.main(["--store", store, "revoke", "--override-id", rec["override_id"]])
    assert rc == 0 and '"revoked": true' in capsys.readouterr().out


def test_override_requires_reason_and_expiry(tmp_path: Path) -> None:
    store = overrides.OverrideStore(tmp_path / "o.json")
    with pytest.raises(overrides.OverrideError):
        store.create(scope="rows", max_value=5, client_label="any", expires_minutes=30, reason="  ", created_by="op")
    with pytest.raises(overrides.OverrideError):
        store.create(scope="rows", max_value=5, client_label="any", expires_minutes=0, reason="x", created_by="op")


def test_override_extends_only_its_scope(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = overrides.OverrideStore(tmp_path / "overrides.json")
    store.create(scope="search_results", max_value=999, client_label="any", expires_minutes=30, reason="r", created_by="op")
    val, oid = limits.effective_limit("search_results", cfg, "claude", store)
    assert val == 999 and oid is not None
    other, oid2 = limits.effective_limit("rows", cfg, "claude", store)
    assert other == cfg.max_db_rows and oid2 is None


def test_expired_and_revoked_override_no_longer_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path)
    store = overrides.OverrideStore(tmp_path / "overrides.json")
    rec = store.create(scope="rows", max_value=999, client_label="any", expires_minutes=1, reason="r", created_by="op")
    assert limits.effective_limit("rows", cfg, "claude", store)[0] == 999
    # expire
    monkeypatch.setattr(overrides, "_now", lambda: datetime.now(UTC) + timedelta(minutes=5))
    assert limits.effective_limit("rows", cfg, "claude", store)[0] == cfg.max_db_rows
    monkeypatch.undo()
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")
    # revoke
    assert store.revoke(rec["override_id"]) is True
    assert limits.effective_limit("rows", cfg, "claude", store)[0] == cfg.max_db_rows


def test_raise_only_override_never_lowers(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    store = overrides.OverrideStore(tmp_path / "overrides.json")
    store.create(scope="rows", max_value=1, client_label="any", expires_minutes=30, reason="r", created_by="op")
    # override value (1) is below the base (100) → base wins; override never lowers a limit
    assert limits.effective_limit("rows", cfg, "claude", store)[0] == cfg.max_db_rows


def test_active_override_in_capability_mode(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    overrides.OverrideStore(cfg.override_store_path).create(
        scope="rows", max_value=999, client_label="any", expires_minutes=30, reason="r", created_by="op"
    )
    broker = NasMcpBroker(cfg)
    result = broker.dispatch("hb_capability_mode", {})["result"]
    assert result["active_override_count"] == 1
    assert result["active_overrides"][0]["scope"] == "rows"


# ------------------------------------------------------------------------ freshness


def test_freshness_reports_present_and_missing_explicitly(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    broker = NasMcpBroker(cfg)
    fr = broker.dispatch("hb_data_freshness", {})["result"]
    assert fr["schema_version"] == {"status": "ok", "version": 99, "applied_at": "2026-07-05 10:00:00"}
    assert fr["daily_brief"]["status"] == "not_configured"  # absent table, explicit
    assert fr["watcher"]["status"] == "unknown"  # in-memory only on NAS
    assert fr["source_intelligence"]["error_count"] == 1  # from seeded events


def test_queue_status_returns_counts(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    q = NasMcpBroker(cfg).dispatch("hb_queue_status", {})["result"]
    assert q["status"] == "ok" and q["queued_count"] == 1 and q["error_count"] == 1


def test_recent_failures_redacted_no_payload(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    conn = sqlite3.connect(cfg.db_path)
    conn.execute("CREATE TABLE assistant_runs (run_type TEXT, status TEXT, started_at TEXT)")
    conn.execute("INSERT INTO assistant_runs VALUES ('brief','error','2026-07-05 09:00:00')")
    conn.commit()
    conn.close()
    rf = NasMcpBroker(cfg).dispatch("hb_recent_failures", {})["result"]
    assert rf["subsystems"]["assistant_runs"]["failed_count"] == 1


def test_freshness_output_has_no_local_paths(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    fr = NasMcpBroker(cfg).dispatch("hb_data_freshness", {})["result"]
    blob = json.dumps(fr)
    assert str(cfg.db_path) not in blob
    assert str(cfg.roots["vault"].mount) not in blob  # no vault path leaked


def test_freshness_tier0_in_audit(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    NasMcpBroker(cfg).dispatch("hb_data_freshness", {})
    ev = next(e for e in _audit_events(cfg) if e.get("tool_name") == "hb_data_freshness")
    assert ev["capability_tier"] == 0 and ev["decision"] == "allow"


# ------------------------------------------------- origin-auth interaction (app-level)


@pytest.fixture()
def app_and_token(tmp_path: Path):
    pytest.importorskip("mcp")
    from hb_assistant.nas_mcp.origin_auth import OriginAuthTokenStore
    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    raw, _ = OriginAuthTokenStore(cfg.origin_auth_store_path).create_token(
        client="claude", client_label="Claude Desktop", actor="bfetting", expires_days=30
    )
    return (lambda: build_nas_mcp_asgi_app(cfg)), raw


def test_freshness_requires_origin_auth(app_and_token) -> None:
    from starlette.testclient import TestClient

    build_app, raw = app_and_token
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        # no bearer → 401 before the tool runs
        unauth = client.post(
            "/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "hb_data_freshness", "arguments": {}}}, headers=headers,
        )
        assert unauth.status_code == 401
    with TestClient(build_app(), base_url="http://127.0.0.1:8765") as client:
        h = {**headers, "authorization": f"Bearer {raw}"}
        client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "p", "version": "1"}}}, headers=h)
        ok = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                         "params": {"name": "hb_data_freshness", "arguments": {}}}, headers=h)
        assert ok.status_code == 200


def test_per_token_allowed_tools_cannot_reach_freshness(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp import origin_auth

    cfg = _cfg(tmp_path)
    _seed_db(cfg)
    broker = NasMcpBroker(cfg)
    ctx = origin_auth.AuthContext(
        client="claude", client_label="Scoped", actor="bfetting", token_id="t", allowed_tools=("hb_mcp_status",)
    )
    token = origin_auth._auth_context_var.set(ctx)
    try:
        denied = broker.dispatch("hb_data_freshness", {})
        assert denied["ok"] is False and "tool_not_in_token_scope" in denied["error"]
    finally:
        origin_auth._auth_context_var.reset(token)
