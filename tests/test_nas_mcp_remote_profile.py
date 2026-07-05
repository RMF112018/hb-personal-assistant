"""N8B foundation: remote_cloudflare exposure profile + capability-split write gates + AI Outputs tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec

BROAD_WRITE_TOOLS = [
    "create_note",
    "patch_note",
    "vault_update_frontmatter",
    "vault_create_note_from_template",
    "vault_append_to_daily_note",
    "hb_output_write_file",
    "hb_output_create_dir",
]


def _cfg(tmp_path: Path) -> NasMcpConfig:
    vault = tmp_path / "vault"
    outputs = tmp_path / "outputs"
    for p in (vault, outputs):
        p.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={
            "vault": RootSpec("vault", vault, "read_write"),
            "outputs": RootSpec("outputs", outputs, "read_write"),
        },
        obsidian=NasObsidianConfig(
            vault_root=vault,
            backup_dir=audit / "obsidian-backups",
            support_dir=audit / "obsidian-support",
        ),
    )


def _remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_PROFILE", "remote_cloudflare")


def test_remote_profile_blocks_all_broad_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remote(monkeypatch)
    broker = NasMcpBroker(_cfg(tmp_path))
    for tool in BROAD_WRITE_TOOLS:
        denied = broker.dispatch(tool, {"path": "x.md", "content": "y", "relative_path": "x.md", "expected_sha256": "z"})
        assert denied["ok"] is False, tool
        assert "write_tool_blocked_by_profile" in denied["error"], tool
    assert any((tmp_path / "audit").glob("mcp-audit-*.jsonl"))  # denials are audited


def test_remote_profile_ignores_write_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remote(monkeypatch)
    monkeypatch.setenv("HB_MCP_ALLOW_LEGACY_VAULT_WRITE", "1")
    monkeypatch.setenv("HB_MCP_ALLOW_SCRATCH_OUTPUT_WRITE", "1")
    broker = NasMcpBroker(_cfg(tmp_path))
    assert broker.dispatch("create_note", {"path": "x.md", "content": "y"})["ok"] is False
    assert broker.dispatch("hb_output_write_file", {"relative_path": "x.md", "content": "y"})["ok"] is False


def test_ai_outputs_create_update_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remote(monkeypatch)
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    broker = NasMcpBroker(cfg)

    created = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Test Card", "body_markdown": "hello", "tags": ["a"], "source_client": "claude", "mode": "create"},
    )
    assert created["ok"] is True
    assert created["result"]["relative_path"] == "AI Outputs/Test Card.md"
    card = tmp_path / "vault" / "AI Outputs" / "Test Card.md"
    assert card.is_file()
    sha = created["result"]["sha256"]

    # update requires the current sha
    assert broker.dispatch(
        "ai_outputs_card_upsert", {"title": "Test Card", "body_markdown": "v2", "source_client": "claude", "mode": "update"}
    )["ok"] is False
    assert broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Test Card", "body_markdown": "v2", "source_client": "claude", "mode": "update", "expected_sha": "deadbeef"},
    )["ok"] is False
    updated = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Test Card", "body_markdown": "v2", "source_client": "claude", "mode": "update", "expected_sha": sha},
    )
    assert updated["ok"] is True

    appended = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "Test Card", "body_markdown": "more", "source_client": "grok", "mode": "append"},
    )
    assert appended["ok"] is True
    assert "more" in card.read_text(encoding="utf-8")
    # a mutation receipt was written
    assert any((cfg.obsidian.support_dir).glob("mutations.jsonl")) or (cfg.obsidian.support_dir / "mutations.jsonl").exists()


def test_ai_outputs_is_folder_locked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remote(monkeypatch)
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    broker = NasMcpBroker(cfg)
    # A traversal-y title is slugified — it can NEVER escape the AI Outputs folder.
    res = broker.dispatch(
        "ai_outputs_card_upsert",
        {"title": "../../etc/passwd", "body_markdown": "x", "source_client": "claude", "mode": "create"},
    )
    if res["ok"]:
        assert res["result"]["relative_path"].startswith("AI Outputs/")
        assert not (tmp_path / "etc" / "passwd").exists()
    # A title that slugs to empty is refused.
    empty = broker.dispatch(
        "ai_outputs_card_upsert", {"title": "///", "body_markdown": "x", "source_client": "claude", "mode": "create"}
    )
    assert empty["ok"] is False


def test_status_reports_profile_and_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _remote(monkeypatch)
    broker = NasMcpBroker(_cfg(tmp_path))
    result = broker.dispatch("hb_mcp_status", {})["result"]
    prof = result["exposure_profile"]
    assert prof["profile"] == "remote_cloudflare"
    assert prof["legacy_broad_vault_write_enabled"] is False
    assert prof["local_scratch_output_write_enabled"] is False
    assert prof["ai_outputs_write_enabled"] is True
    assert "create_note" in result["blocked_write_tools"]
    assert "create_note" in result["obsidian_tools_blocked"]
    assert "create_note" not in result["obsidian_tools_enabled"]


def test_local_trusted_profile_reenables_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_MCP_PROFILE", "local_trusted")
    cfg = _cfg(tmp_path)
    monkeypatch.setenv("HB_OBSIDIAN_MCP_SUPPORT_DIR", str(cfg.obsidian.support_dir))
    broker = NasMcpBroker(cfg)
    created = broker.dispatch(
        "create_note", {"path": "_t/note.md", "content": "# x\n", "overwrite": True, "create_parent_dirs": True}
    )
    assert created["ok"] is True
    assert broker.dispatch("hb_output_write_file", {"relative_path": "probe.txt", "content": "hi"})["ok"] is True
