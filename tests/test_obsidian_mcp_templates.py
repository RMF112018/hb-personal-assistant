"""Template + daily-note tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.templates import (
    append_to_daily_note,
    create_note_from_template,
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
    (vault / "Templates").mkdir(parents=True)
    (vault / "Templates" / "Project Note.md").write_text(
        "# {{project_name}}\n\nStatus: {{status}}\nOwner: {{owner}}\n", encoding="utf-8"
    )
    (vault / "Templates" / "Daily.md").write_text("# {{date}}\n\n## Actions\n", encoding="utf-8")
    (vault / "Projects").mkdir()
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    apply_patch(ObsidianMcpConfigPatch(writes_enabled=True, vault_markdown_write_enabled=True))
    return load_config(), vault


# ---------------------------------------------------------------------------
# create_note_from_template
# ---------------------------------------------------------------------------
def test_create_note_from_template_renders_and_writes(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    result = create_note_from_template(
        config,
        template_path="Templates/Project Note.md",
        target_path="Projects/New.md",
        variables={"project_name": "Tropical", "status": "active"},
        frontmatter={"tags": ["project"], "status": "active"},
    )
    assert result["created"] is True
    text = (vault / "Projects" / "New.md").read_text(encoding="utf-8")
    assert "# Tropical" in text
    assert "Status: active" in text
    assert "{{owner}}" in text  # unfilled variable left intact
    assert text.startswith("---")  # frontmatter injected
    assert "tags:" in text


def test_create_note_from_template_no_overwrite(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    (vault / "Projects" / "Exists.md").write_text("# Exists\n", encoding="utf-8")
    with pytest.raises(ObsidianMcpToolError) as exc:
        create_note_from_template(
            config,
            template_path="Templates/Project Note.md",
            target_path="Projects/Exists.md",
            variables={"project_name": "X"},
        )
    assert exc.value.code == "note_already_exists"


# ---------------------------------------------------------------------------
# append_to_daily_note
# ---------------------------------------------------------------------------
def test_append_to_daily_note_creates_and_appends_section(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    result = append_to_daily_note(
        config,
        date="2026-06-28",
        section="Actions",
        content="- Follow up on Grok runtime validation.",
        template_path="Templates/Daily.md",
    )
    assert result["created"] is True
    daily = vault / "Daily Notes" / "2026-06-28.md"
    assert daily.exists()
    text = daily.read_text(encoding="utf-8")
    assert "## Actions" in text
    assert "Follow up on Grok" in text

    # Second append to the same note + section preserves prior content and backs up.
    second = append_to_daily_note(
        config,
        date="2026-06-28",
        section="Actions",
        content="- Second item.",
    )
    assert second.get("backup_path")
    text2 = daily.read_text(encoding="utf-8")
    assert "Follow up on Grok" in text2 and "Second item." in text2


def test_append_to_daily_note_missing_without_create(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        append_to_daily_note(
            config,
            date="2026-01-01",
            content="- x",
            create_if_missing=False,
        )
    assert exc.value.code == "daily_note_missing"


def test_append_to_daily_note_rejects_bad_date(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        append_to_daily_note(config, date="June 1", content="- x")
    assert exc.value.code == "invalid_date"
