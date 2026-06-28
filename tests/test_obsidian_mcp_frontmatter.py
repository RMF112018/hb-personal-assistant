"""Frontmatter / properties / structured-query tools for the Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.frontmatter import (
    dataview_query,
    read_frontmatter,
    search_by_properties,
    update_frontmatter,
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


def _setup(tmp_path, monkeypatch, *, enable_writes=False):
    vault = tmp_path / "vault"
    work = vault / "Work"
    work.mkdir(parents=True)
    (work / "Active.md").write_text(
        "---\nstatus: active\nproject: Tropical\ntags: [project, obsidian-mcp]\n---\n# Active\n\nBody text.\n",
        encoding="utf-8",
    )
    (work / "Closed.md").write_text(
        "---\nstatus: closed\nproject: Other\ntags: [project]\n---\n# Closed\n\nDone.\n",
        encoding="utf-8",
    )
    (work / "Bare.md").write_text("# Bare\n\nNo frontmatter here.\n", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    if enable_writes:
        apply_patch(ObsidianMcpConfigPatch(writes_enabled=True, vault_markdown_write_enabled=True))
    return load_config(), vault


# ---------------------------------------------------------------------------
# read_frontmatter
# ---------------------------------------------------------------------------
def test_read_frontmatter(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = read_frontmatter(config, path="Work/Active.md")
    assert result["has_frontmatter"] is True
    assert result["frontmatter"]["status"] == "active"
    assert len(result["file_sha256"]) == 64
    bare = read_frontmatter(config, path="Work/Bare.md")
    assert bare["has_frontmatter"] is False
    assert bare["frontmatter"] == {}


# ---------------------------------------------------------------------------
# update_frontmatter
# ---------------------------------------------------------------------------
def test_update_frontmatter_merges_tags_and_preserves_body(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    before = read_frontmatter(config, path="Work/Active.md")
    result = update_frontmatter(
        config,
        path="Work/Active.md",
        updates={"status": "review", "tags": ["new-tag"]},
        expected_sha256=before["file_sha256"],
    )
    assert result["frontmatter"]["status"] == "review"
    assert "new-tag" in result["frontmatter"]["tags"]
    assert "project" in result["frontmatter"]["tags"]  # merged, not replaced
    assert result["frontmatter"]["project"] == "Tropical"  # unrelated key preserved
    text = (vault / "Work" / "Active.md").read_text(encoding="utf-8")
    assert "# Active" in text and "Body text." in text  # body preserved
    assert result.get("backup_path")


def test_update_frontmatter_requires_matching_sha(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    with pytest.raises(ObsidianMcpToolError) as exc:
        update_frontmatter(
            config,
            path="Work/Active.md",
            updates={"status": "review"},
            expected_sha256="deadbeef",
        )
    assert exc.value.code == "sha256_mismatch"


# ---------------------------------------------------------------------------
# search_by_properties
# ---------------------------------------------------------------------------
def test_search_by_properties_filters_and_tags(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    by_status = search_by_properties(config, root_path="Work", filters={"status": "active"})
    assert {r["path"] for r in by_status["results"]} == {"Work/Active.md"}
    by_tag = search_by_properties(config, root_path="Work", tags_all=["project", "obsidian-mcp"])
    assert {r["path"] for r in by_tag["results"]} == {"Work/Active.md"}


# ---------------------------------------------------------------------------
# dataview_query
# ---------------------------------------------------------------------------
def test_dataview_query_structured(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = dataview_query(
        config,
        root_path="Work",
        where=[
            {"field": "status", "op": "eq", "value": "active"},
            {"field": "project", "op": "exists"},
        ],
        select=["path", "status", "project"],
    )
    assert result["count"] == 1
    row = result["rows"][0]
    assert row["path"] == "Work/Active.md"
    assert row["status"] == "active"
    assert row["project"] == "Tropical"


def test_dataview_query_rejects_unknown_op(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        dataview_query(config, root_path="Work", where=[{"field": "status", "op": "regex", "value": "x"}])
    assert exc.value.code == "unsupported_query_op"
