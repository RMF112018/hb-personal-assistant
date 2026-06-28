"""Graph/linking tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import load_config
from hb_assistant.obsidian_mcp.graph import (
    get_backlinks,
    get_note_graph,
    get_unlinked_mentions,
)
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
    # Hub is linked by Alpha (wikilink) and Beta (markdown link); Gamma mentions it unlinked.
    (work / "Hub.md").write_text("# Hub\n\nCentral note.\n", encoding="utf-8")
    (work / "Alpha.md").write_text("# Alpha\n\nSee [[Hub]] for context.\n", encoding="utf-8")
    (work / "Beta.md").write_text("# Beta\n\nReference [Hub](Hub.md) here. Also [[Alpha]].\n", encoding="utf-8")
    (work / "Gamma.md").write_text("# Gamma\n\nThe Hub is important but not linked.\n", encoding="utf-8")
    (work / "Lonely.md").write_text("# Lonely\n\nNo links at all.\n", encoding="utf-8")
    (vault / ".obsidian").mkdir()
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    return load_config(), vault


# ---------------------------------------------------------------------------
# backlinks
# ---------------------------------------------------------------------------
def test_get_backlinks_wikilinks_and_markdown(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = get_backlinks(config, target_path="Work/Hub.md", root_path="Work")
    paths = {b["path"] for b in result["backlinks"]}
    assert paths == {"Work/Alpha.md", "Work/Beta.md"}  # both link styles found
    assert "Work/Gamma.md" not in paths  # mention only, not a link


def test_get_backlinks_requires_markdown_target(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    (vault / "Work" / "data.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ObsidianMcpToolError) as exc:
        get_backlinks(config, target_path="Work/data.txt")
    assert exc.value.code == "markdown_only"


# ---------------------------------------------------------------------------
# unlinked mentions
# ---------------------------------------------------------------------------
def test_get_unlinked_mentions(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = get_unlinked_mentions(config, target_title="Hub", root_path="Work")
    paths = {m["path"] for m in result["mentions"]}
    assert "Work/Gamma.md" in paths  # mentions "Hub" without linking
    assert "Work/Alpha.md" not in paths  # already links to Hub
    assert "Work/Hub.md" not in paths  # the entity note itself
    assert result["mentions"][0].get("snippet")


def test_get_unlinked_mentions_rejects_short_title(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        get_unlinked_mentions(config, target_title="ab", root_path="Work")
    assert exc.value.code == "target_title_too_short"


# ---------------------------------------------------------------------------
# note graph
# ---------------------------------------------------------------------------
def test_get_note_graph_nodes_edges_orphans(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = get_note_graph(config, root_path="Work")
    node_paths = {n["path"] for n in result["nodes"]}
    assert {"Work/Hub.md", "Work/Alpha.md", "Work/Beta.md", "Work/Lonely.md"} <= node_paths
    assert {"source": "Work/Alpha.md", "target": "Work/Hub.md"} in result["edges"]
    assert "Work/Lonely.md" in result["orphans"]
    assert "Work/Hub.md" in result["high_degree_notes"]  # most-linked


def test_get_note_graph_depth_from_target(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = get_note_graph(config, root_path="Work", target_path="Work/Hub.md", depth=1)
    node_paths = {n["path"] for n in result["nodes"]}
    # Depth-1 neighborhood of Hub: Hub + its direct linkers (Alpha, Beta).
    assert "Work/Hub.md" in node_paths
    assert "Work/Alpha.md" in node_paths
    assert "Work/Lonely.md" not in node_paths  # unconnected, excluded at depth 1
