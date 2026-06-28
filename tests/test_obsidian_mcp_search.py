"""Semantic/hybrid search tool for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import load_config
from hb_assistant.obsidian_mcp.search import semantic_search
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError


def _write_config(tmp_path: Path, vault: Path) -> Path:
    app_support = tmp_path / "app-support"
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                f"  application_support_root: {app_support.as_posix()!r}",
                f"  obsidian_vault: {vault.as_posix()!r}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _setup(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    work = vault / "Work"
    work.mkdir(parents=True)
    (work / "Schedule.md").write_text("# Schedule\n\nSmartPM competitor schedule health implementation.\n", encoding="utf-8")
    (work / "Other.md").write_text("# Other\n\nUnrelated content.\n", encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "schedule.md").write_text("# hidden schedule\n", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    return load_config(), vault


def test_lexical_mode_no_warning(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = semantic_search(config, query="schedule health", path_scope="Work", mode="lexical")
    assert result["mode"] == "lexical"
    assert "warning" not in result
    assert {r["path"] for r in result["results"]} == {"Work/Schedule.md"}


def test_semantic_mode_falls_back_to_lexical(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = semantic_search(config, query="schedule health", path_scope="Work", mode="semantic")
    assert result["mode"] == "lexical_fallback"
    assert result["requested_mode"] == "semantic"
    assert result["warning"] == "semantic index not configured"
    assert {r["path"] for r in result["results"]} == {"Work/Schedule.md"}


def test_hybrid_mode_falls_back(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = semantic_search(config, query="schedule", path_scope="Work", mode="hybrid")
    assert result["mode"] == "lexical_fallback"


def test_invalid_mode_rejected(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        semantic_search(config, query="schedule", mode="vector")
    assert exc.value.code == "unsupported_search_mode"


def test_search_excludes_hidden_paths(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = semantic_search(config, query="schedule", mode="semantic", operator_mode=False)
    paths = {r["path"] for r in result["results"]}
    assert "Work/Schedule.md" in paths
    assert not any(p.startswith(".obsidian") for p in paths)
