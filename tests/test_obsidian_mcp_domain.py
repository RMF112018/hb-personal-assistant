"""Construction/PM domain tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import load_config
from hb_assistant.obsidian_mcp.domain import (
    extract_action_items,
    extract_project_mentions,
    project_status_summary,
)
from hb_assistant.obsidian_mcp.mutations import recent_read_receipts
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

_NOTE = """---
status: active
project: Tropical
---
# Tropical Update

Please submit RFI 142 by Friday. We decided to resequence the slab pours.
There is a $25,000 cost exposure and a schedule delay risk on switchgear.
When will the crane arrive?
Project 25-123-01 is referenced here.
"""


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


def _make_eml(path: Path) -> None:
    msg = EmailMessage()
    msg["Subject"] = "RFI 142 schedule impact"
    msg["From"] = "Jane <jane@example.com>"
    msg["To"] = "Bobby <bobby@example.com>"
    msg.set_content("Please confirm the change order. Owner approved. Risk of delay on Tropical.\n")
    path.write_bytes(bytes(msg))


def _setup(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    proj = vault / "Projects" / "Tropical"
    proj.mkdir(parents=True)
    (proj / "Update.md").write_text(_NOTE, encoding="utf-8")
    _make_eml(proj / "mail.eml")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    return load_config(), vault


# ---------------------------------------------------------------------------
# extract_action_items
# ---------------------------------------------------------------------------
def test_extract_action_items_from_note(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = extract_action_items(config, path="Projects/Tropical/Update.md", source_type="note")
    assert result["source_type"] == "note"
    assert any("rfi" in a.lower() or "submit" in a.lower() for a in result["action_items"])
    assert any("resequence" in d.lower() or "decided" in d.lower() for d in result["decisions"])
    assert any("exposure" in r.lower() or "risk" in r.lower() or "delay" in r.lower() for r in result["risks"])
    assert "Friday" in str(result["action_items"]) or result["dates"] is not None


def test_extract_action_items_from_email(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = extract_action_items(config, path="Projects/Tropical/mail.eml", source_type="email")
    assert result["source_type"] == "email"
    assert any("confirm" in a.lower() for a in result["action_items"])
    assert result["owners"]  # people from the email


def test_extract_action_items_from_folder(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = extract_action_items(config, path="Projects/Tropical", source_type="folder")
    assert result["source_type"] == "folder"
    assert result["files"] == 2  # note + email
    assert result["action_items"]
    assert any(r["tool_name"] == "vault_extract_action_items" for r in recent_read_receipts(5))


# ---------------------------------------------------------------------------
# project_status_summary
# ---------------------------------------------------------------------------
def test_project_status_summary(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = project_status_summary(config, root_path="Projects/Tropical")
    assert result["files_considered"] == 2
    assert result["executive_summary"]
    assert result["risks"]
    assert result["cost_mentions"]
    assert result["schedule_mentions"]
    assert any(s["status"] == "active" for s in result["current_status"])
    assert "When will the crane arrive?" in result["open_questions"]


# ---------------------------------------------------------------------------
# extract_project_mentions
# ---------------------------------------------------------------------------
def test_extract_project_mentions(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = extract_project_mentions(
        config, root_path="Projects", project_aliases=["Tropical", "TWN"]
    )
    by_path = {m["path"]: m["projects"] for m in result["mentions"]}
    assert "Projects/Tropical/Update.md" in by_path
    proj = by_path["Projects/Tropical/Update.md"]
    assert "25-123-01" in proj  # HB project number
    assert "Tropical" in proj  # alias


def test_extract_project_mentions_rejects_protected(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    (vault / ".obsidian").mkdir()
    with pytest.raises(ObsidianMcpToolError) as exc:
        extract_project_mentions(config, root_path=".obsidian")
    assert exc.value.code == "protected_path_blocked"
