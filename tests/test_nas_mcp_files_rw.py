"""Tests for NAS MCP filesystem RW (Phase N7-FS-RW)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.obsidian_adapter import NAS_OBSIDIAN_BLOCKED, list_nas_obsidian_tool_names

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_COMPOSE = REPO_ROOT / "deploy" / "nas" / "mcp" / "compose-mcp.yaml"
MCP_CONFIG_EX = REPO_ROOT / "deploy" / "nas" / "mcp" / "hb-pa-config.mcp.example.yml"


def _cfg(tmp_path: Path) -> NasMcpConfig:
    vault = tmp_path / "vault"
    home = tmp_path / "home"
    work = tmp_path / "work"
    outputs = tmp_path / "outputs"
    for p in (vault, home, work, outputs):
        p.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={
            "vault": RootSpec("vault", vault, "read_write"),
            "home": RootSpec("home", home, "read_only"),
            "work": RootSpec("work", work, "read_only"),
            "outputs": RootSpec("outputs", outputs, "read_write"),
        },
        obsidian=NasObsidianConfig(
            vault_root=vault,
            backup_dir=audit / "obsidian-backups",
            support_dir=audit / "obsidian-support",
        ),
    )


def test_mac_obsidian_tool_audit_registry_complete() -> None:
    names = list_nas_obsidian_tool_names()
    assert len(names) == 56
    assert "list_directory" in names
    assert "create_note" in names
    assert NAS_OBSIDIAN_BLOCKED["search_sources"].startswith("source-intelligence")


def test_obsidian_create_note_stays_in_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    broker = NasMcpBroker(cfg)
    ok = broker.dispatch(
        "create_note",
        {"path": "_nas-test/note.md", "content": "# test\n", "overwrite": True, "create_parent_dirs": True},
    )
    assert ok["ok"] is True
    assert (tmp_path / "vault" / "_nas-test" / "note.md").is_file()
    assert "/volume1/" not in json.dumps(ok["result"])


def test_obsidian_blocked_tool_denied(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    denied = broker.dispatch("search_sources", {"query": "x", "limit": 1})
    assert denied["ok"] is False
    assert "blocked" in denied["error"].lower() or "source-intelligence" in NAS_OBSIDIAN_BLOCKED["search_sources"]


def test_home_read_and_write_denied(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    cfg = _cfg(tmp_path)
    (cfg.roots["home"].mount / "doc.txt").write_text("hello home", encoding="utf-8")
    broker = NasMcpBroker(cfg)
    listing = broker.dispatch("hb_root_list", {"root_key": "home", "relative_path": "."})
    assert listing["ok"] is True
    write = broker.dispatch(
        "hb_output_write_file",
        {"relative_path": "../home/evil.txt", "content": "nope", "overwrite": True},
    )
    assert write["ok"] is False


def test_work_read_only(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    cfg = _cfg(tmp_path)
    (cfg.roots["work"].mount / "sheet.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    broker = NasMcpBroker(cfg)
    stat = broker.dispatch("hb_root_stat", {"root_key": "work", "relative_path": "sheet.csv"})
    assert stat["ok"] is True
    read = broker.dispatch("hb_root_read_file", {"root_key": "work", "relative_path": "sheet.csv"})
    assert read["ok"] is True
    assert "/volume1/" not in json.dumps(read["result"])


def test_output_sandbox_writes(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    txt = broker.dispatch("hb_output_write_file", {"relative_path": "probe.txt", "content": "hello"})
    assert txt["ok"] is True
    md = broker.dispatch("hb_output_write_file", {"relative_path": "probe.md", "content": "# hi"})
    assert md["ok"] is True
    csv = broker.dispatch("hb_output_write_file", {"relative_path": "probe.csv", "content": "a,b\n1,2"})
    assert csv["ok"] is True
    js = broker.dispatch("hb_output_write_file", {"relative_path": "probe.json", "content": '{"a":1}'})
    assert js["ok"] is True
    blocked = broker.dispatch("hb_output_write_file", {"relative_path": "bad.exe", "content": "x"})
    assert blocked["ok"] is False
    no_overwrite = broker.dispatch("hb_output_write_file", {"relative_path": "probe.txt", "content": "x"})
    assert no_overwrite["ok"] is False
    overwrite = broker.dispatch(
        "hb_output_write_file", {"relative_path": "probe.txt", "content": "updated", "overwrite": True}
    )
    assert overwrite["ok"] is True
    assert any((tmp_path / "audit").glob("mcp-audit-*.jsonl"))


def test_compose_four_root_mount_modes() -> None:
    text = MCP_COMPOSE.read_text(encoding="utf-8")
    assert "/mnt/vault:rw" in text
    assert "/mnt/roots/home:ro" in text
    assert "/mnt/roots/work:ro" in text
    assert "/mnt/outputs:rw" in text
    assert "syn-work" not in text


def test_config_backup_dir_is_container_path() -> None:
    import yaml

    data = yaml.safe_load(MCP_CONFIG_EX.read_text(encoding="utf-8"))
    assert data["mcp"]["obsidian"]["backup_dir"].startswith("/app-support/")
    assert not data["mcp"]["obsidian"]["backup_dir"].startswith("/volume1/")


def test_vault_write_outside_vault_denied(tmp_path: Path) -> None:
    from hb_assistant.nas_mcp.broker import NasMcpBroker

    broker = NasMcpBroker(_cfg(tmp_path))
    denied = broker.dispatch(
        "hb_output_write_file",
        {"relative_path": "../../vault/outside.txt", "content": "nope", "overwrite": True},
    )
    assert denied["ok"] is False
