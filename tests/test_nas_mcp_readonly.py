"""Tests for NAS MCP readonly mode (Phase N7)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_COMPOSE = REPO_ROOT / "deploy" / "nas" / "mcp" / "compose-mcp.yaml"
MCP_CHECK = REPO_ROOT / "deploy" / "nas" / "mcp" / "check-mcp-compose.sh"
LAUNCHER = REPO_ROOT / "deploy" / "nas" / "mcp" / "hb-mcp-launcher"
RUNNER = REPO_ROOT / "deploy" / "nas" / "mcp" / "hb-mcp-runner"
MCP_CONFIG_EX = REPO_ROOT / "deploy" / "nas" / "mcp" / "hb-pa-config.mcp.example.yml"
SUDOERS_EX = REPO_ROOT / "deploy" / "nas" / "mcp" / "sudoers.hb-pa-mcp.example"
CLIENT_EX = REPO_ROOT / "deploy" / "nas" / "mcp" / "claude-desktop-config.example.json"
NAS_VAULT_HOST = "/volume1/personal-assistant/vault/obsidian"
NAS_VAULT_CONTAINER = "/mnt/vault"
MAC_VAULT_FRAGMENT = "Documents/Obsidian Vault"


def _strip_comments(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


@pytest.fixture(autouse=True)
def _nas_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_NAS_READONLY", "1")
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    monkeypatch.setenv("HB_ASSISTANT_DB_READONLY", "1")
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)


def test_compose_static_guard_script_passes() -> None:
    import subprocess

    proc = subprocess.run(["sh", str(MCP_CHECK)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_compose_rejects_network_mode_none_with_ports() -> None:
    text = _strip_comments(MCP_COMPOSE.read_text(encoding="utf-8"))
    if "network_mode: none" in text and "ports:" in text:
        pytest.fail("network_mode:none must not be paired with ports in MCP compose")
    assert "127.0.0.1:8765:8765" in text
    assert "0.0.0.0:8765:8765" not in text
    assert "8000" not in text
    assert "hb-personal-assistant-backend" not in text


def test_compose_vault_mount_uses_nas_obsidian_path() -> None:
    text = _strip_comments(MCP_COMPOSE.read_text(encoding="utf-8"))
    assert NAS_VAULT_HOST in text
    assert f":{NAS_VAULT_CONTAINER}:ro" in text
    assert MAC_VAULT_FRAGMENT not in text


def test_mcp_config_vault_root_is_container_mount() -> None:
    import yaml

    data = yaml.safe_load(MCP_CONFIG_EX.read_text(encoding="utf-8"))
    vault = data["mcp"]["roots"]["vault"]
    assert vault["mount"] == NAS_VAULT_CONTAINER
    assert vault["mode"] == "read_only"
    blob = MCP_CONFIG_EX.read_text(encoding="utf-8")
    assert MAC_VAULT_FRAGMENT not in blob


def test_nas_mcp_sources_exclude_mac_vault_path() -> None:
    nas_mcp = REPO_ROOT / "src" / "hb_assistant" / "nas_mcp"
    deploy_mcp = REPO_ROOT / "deploy" / "nas" / "mcp"
    for path in (*nas_mcp.rglob("*.py"), *deploy_mcp.rglob("*")):
        if path.is_dir() or path.suffix not in ("", ".py", ".yaml", ".yml", ".sh"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert MAC_VAULT_FRAGMENT not in text, f"Mac vault path in {path}"


def test_launcher_status_uses_runner_not_docker() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'sudo -n "$RUNNER" status' in text
    assert "docker ps" not in text
    assert "DOCKER=" not in text


def test_launcher_start_uses_runner_not_docker() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'sudo -n "$RUNNER" start' in text
    assert "docker ps" not in text


def test_runner_fixed_verbs_only() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    for verb in ("start", "stop", "status", "health"):
        assert f"  {verb})" in text
    assert "usage: hb-mcp-runner {start|stop|status|health}" in text
    assert '"$2"' not in text
    assert "shift" not in text
    assert " compose " in text
    assert "hb-personal-assistant-mcp" in text
    assert "NOPASSWD: /bin/sh" not in text
    assert " exec /bin/sh" not in text
    assert " exec bash" not in text


def test_runner_status_inspection_is_bounded() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert 'ps --filter "name=^/${CONTAINER}$"' in text
    assert '"$DOCKER" port "$CONTAINER" 8765/tcp' in text
    assert "127\\.0\\.0\\.1\\.8765" in text
    assert "port_8000" in text


def test_runner_fixed_commands_only() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "compose -f" in text
    assert "hb-personal-assistant-mcp" in text
    assert " compose " in text
    assert "NOPASSWD: /bin/sh" not in text
    assert " exec /bin/sh" not in text
    assert " exec bash" not in text


def test_sudoers_example_is_single_command() -> None:
    text = SUDOERS_EX.read_text(encoding="utf-8")
    assert "NOPASSWD: /volume1/personal-assistant/bin/hb-mcp-runner" in text
    assert "NOPASSWD: /usr/local/bin/docker" not in text
    assert "NOPASSWD: /bin/sh" not in text
    assert "/bin/sh" not in text
    assert "/bin/bash" not in text
    assert "ALL=(ALL)" not in text
    assert text.strip().count("NOPASSWD:") == 1


def test_client_example_uses_mac_tunnel_endpoint() -> None:
    payload = json.loads(CLIENT_EX.read_text(encoding="utf-8"))
    url = payload["mcpServers"]["hb-nas-readonly"]["url"]
    assert url == "http://127.0.0.1:18765/mcp"
    assert "100." not in json.dumps(payload)


def test_nas_mcp_does_not_import_create_app_on_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    audit = tmp_path / "audit" / "mcp"
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(
        f"""
mcp:
  audit_dir: {audit}
  db_path: {tmp_path / 'test.sqlite'}
  roots:
    vault: {{ mount: {vault}, mode: read_only }}
    syn-work: {{ mount: {work}, mode: read_only }}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    for mod in list(sys.modules):
        if mod.startswith("hb_assistant.construction.analytics.api"):
            del sys.modules[mod]
    from hb_assistant.nas_mcp.server import serve_nas_readonly_streamable_http

    status = serve_nas_readonly_streamable_http(host="127.0.0.1", port=8765, dry_run=True)
    assert status.get("ready") is True
    assert "hb_assistant.construction.analytics.api" not in sys.modules


def test_db_select_allowlist_and_denials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.nas_mcp.db_allowlist import register_test_allowlist

    register_test_allowlist()
    db = tmp_path / "items.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nas_mcp_test_items (id INTEGER, label TEXT, category TEXT)")
    conn.executemany(
        "INSERT INTO nas_mcp_test_items VALUES (?, ?, ?)",
        [(1, "alpha", "a"), (2, "beta", "b")],
    )
    conn.commit()
    conn.close()

    audit = tmp_path / "audit"
    cfg = NasMcpConfig(
        db_path=db,
        audit_dir=audit,
        roots={},
    )
    broker = NasMcpBroker(cfg)

    ok = broker.dispatch(
        "hb_db_select",
        {"table_key": "nas_mcp_test_items", "columns": ["id", "label"], "limit": 1},
    )
    assert ok["ok"] is True
    assert ok["result"]["row_count"] == 1

    denied_table = broker.dispatch("hb_db_select", {"table_key": "secrets", "columns": ["id"]})
    assert denied_table["ok"] is False

    denied_star = broker.dispatch(
        "hb_db_select",
        {"table_key": "nas_mcp_test_items", "columns": ["*"]},
    )
    assert denied_star["ok"] is False

    injection = broker.dispatch(
        "hb_db_select",
        {"table_key": "nas_mcp_test_items", "columns": ["id;DROP"], "limit": 1},
    )
    assert injection["ok"] is False

    assert any(audit.glob("mcp-audit-*.jsonl"))


def test_db_select_limit_clamped(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig
    from hb_assistant.nas_mcp.db_allowlist import register_test_allowlist

    register_test_allowlist()
    db = tmp_path / "items.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE nas_mcp_test_items (id INTEGER, label TEXT, category TEXT)")
    for i in range(30):
        conn.execute("INSERT INTO nas_mcp_test_items VALUES (?, ?, ?)", (i, f"l{i}", "c"))
    conn.commit()
    conn.close()
    cfg = NasMcpConfig(db_path=db, audit_dir=tmp_path / "audit", roots={}, max_db_rows=10)
    broker = NasMcpBroker(cfg)
    ok = broker.dispatch(
        "hb_db_select",
        {"table_key": "nas_mcp_test_items", "columns": ["id"], "limit": 999},
    )
    assert ok["ok"] is True
    assert ok["result"]["limit_applied"] == 10
    assert ok["result"]["row_count"] == 10


def test_filesystem_traversal_and_enc_denied(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig, RootSpec

    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    (root / "ok.md").write_text("hello", encoding="utf-8")
    (root / "secret.enc").write_bytes(b"blob")
    cfg = NasMcpConfig(
        db_path=tmp_path / "x.sqlite",
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", root)},
    )
    broker = NasMcpBroker(cfg)

    ok = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "ok.md"})
    assert ok["ok"] is True
    assert ok["result"]["path_display"] == "vault/ok.md"
    assert "/volume1/" not in json.dumps(ok["result"])

    traversal = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "../etc/passwd"})
    assert traversal["ok"] is False

    enc = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "secret.enc"})
    assert enc["ok"] is False

    absolute = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "/etc/passwd"})
    assert absolute["ok"] is False

    token = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "msal-token-cache.json"})
    assert token["ok"] is False

    assert any((tmp_path / "audit").glob("mcp-audit-*.jsonl"))


def test_vault_tools_use_vault_root_key_only(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig, RootSpec

    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    (root / "note.md").write_text("vault note", encoding="utf-8")
    cfg = NasMcpConfig(
        db_path=tmp_path / "x.sqlite",
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", root)},
    )
    broker = NasMcpBroker(cfg)

    listing = broker.dispatch("hb_secure_list", {"root_key": "vault", "relative_path": "."})
    assert listing["ok"] is True
    assert listing["result"]["root_key"] == "vault"
    assert listing["result"]["path_display"] == "vault"
    assert "/volume1/" not in json.dumps(listing["result"])

    stat = broker.dispatch("hb_secure_stat", {"root_key": "vault", "relative_path": "note.md"})
    assert stat["ok"] is True
    assert stat["result"]["path_display"] == "vault/note.md"

    search = broker.dispatch("hb_vault_search", {"query": "note", "relative_path": "."})
    assert search["ok"] is True
    assert search["result"]["root_key"] == "vault"

    excerpt = broker.dispatch("hb_vault_read_excerpt", {"relative_path": "note.md"})
    assert excerpt["ok"] is True
    assert excerpt["result"]["path_display"] == "vault/note.md"
    assert "/volume1/" not in json.dumps(excerpt["result"])


def test_symlink_escape_denied(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker
    from hb_assistant.nas_mcp.config import NasMcpConfig, RootSpec

    root = tmp_path / "vault"
    outside = tmp_path / "outside"
    root.mkdir(exist_ok=True)
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    (root / "link.md").symlink_to(outside / "secret.txt")
    cfg = NasMcpConfig(
        db_path=tmp_path / "x.sqlite",
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", root)},
    )
    broker = NasMcpBroker(cfg)
    denied = broker.dispatch("hb_secure_read_excerpt", {"root_key": "vault", "relative_path": "link.md"})
    assert denied["ok"] is False


def test_build_asgi_health_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from starlette.testclient import TestClient

    from hb_assistant.nas_mcp.config import NasMcpConfig, RootSpec
    from hb_assistant.nas_mcp.server import build_nas_mcp_asgi_app

    root = tmp_path / "vault"
    root.mkdir(exist_ok=True)
    cfg = NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", root)},
    )
    app = build_nas_mcp_asgi_app(cfg)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nas_readonly"] is True
        assert "hb_assistant.construction.analytics.api" not in sys.modules
