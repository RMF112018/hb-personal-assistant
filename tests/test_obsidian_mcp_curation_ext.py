"""Curation expansion + email-to-note tools for the Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import plan_store
from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.curation import (
    apply_curation_plan,
    apply_email_to_note_plan,
    build_auto_link_plan,
    build_bulk_tagging_plan,
    build_email_to_note_plan,
    build_moc_plan,
)


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
    msg["Subject"] = "Tropical RFI 142"
    msg["From"] = "Jane <jane@example.com>"
    msg["Date"] = "Mon, 15 Jun 2026 09:00:00 -0400"
    msg.set_content("Please confirm the crane delivery. We decided to resequence pours.\n")
    path.write_bytes(bytes(msg))


def _setup(tmp_path, monkeypatch, *, enable_writes=True):
    vault = tmp_path / "vault"
    work = vault / "Work"
    work.mkdir(parents=True)
    (work / "Alpha.md").write_text("# Alpha\n\nMentions Beta in prose. #project\n", encoding="utf-8")
    (work / "Beta.md").write_text("# Beta\n\nReferences Alpha here.\n", encoding="utf-8")
    (work / "Gamma.md").write_text("# Gamma\n\nStandalone. #idea\n", encoding="utf-8")
    (vault / "Email").mkdir()
    _make_eml(vault / "Email" / "msg.eml")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    if enable_writes:
        apply_patch(ObsidianMcpConfigPatch(writes_enabled=True, vault_markdown_write_enabled=True))
    return load_config(), vault


# ---------------------------------------------------------------------------
# MOC plan
# ---------------------------------------------------------------------------
def test_create_moc_plan_and_apply(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = build_moc_plan(config, root_path="Work", moc_title="Work", include_sections=["overview", "notes"])
    assert plan["allowed_actions"] == ["create_moc_notes"]
    assert plan["actions"][0]["target_path"] == "Work/Work MOC.md"
    assert "payload" not in plan["actions"][0]  # redacted
    result = apply_curation_plan(config, plan_id=plan["plan_id"], approved_actions=["create_moc_notes"])
    assert (vault / "Work" / "Work MOC.md").exists()
    assert len(result["applied"]) == 1


# ---------------------------------------------------------------------------
# auto-link + bulk tagging plans
# ---------------------------------------------------------------------------
def test_auto_link_plan_suggests_links(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = build_auto_link_plan(config, root_path="Work", min_confidence=0.5)
    assert plan["allowed_actions"] == ["suggest_links"]
    targets = {a["target_path"] for a in plan["actions"]}
    assert "Work/Alpha.md" in targets or "Work/Beta.md" in targets


def test_bulk_tagging_plan_and_apply(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = build_bulk_tagging_plan(config, root_path="Work", tag_namespace="work")
    assert plan["allowed_actions"] == ["suggest_tags"]
    result = apply_curation_plan(config, plan_id=plan["plan_id"], approved_actions=["suggest_tags"])
    assert result["counts"]["applied"] >= 1
    alpha = (vault / "Work" / "Alpha.md").read_text(encoding="utf-8")
    assert "tags:" in alpha and "work" in alpha


# ---------------------------------------------------------------------------
# email-to-note plan + apply
# ---------------------------------------------------------------------------
def test_email_to_note_plan_and_apply(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = build_email_to_note_plan(config, email_path="Email/msg.eml", target_folder="Work/Processed")
    assert plan["allowed_actions"] == ["email_to_note"]
    assert plan["target_path"] == "Work/Processed/msg.md"
    assert plan["source_email"] == "Email/msg.eml"

    result = apply_email_to_note_plan(config, plan_id=plan["plan_id"])
    assert len(result["applied"]) == 1
    note = vault / "Work" / "Processed" / "msg.md"
    assert note.exists()
    text = note.read_text(encoding="utf-8")
    assert "# Tropical RFI 142" in text
    assert "source_email: Email/msg.eml" in text
    assert "## Action Items" in text
    assert "Source email: Email/msg.eml" in text


def test_email_to_note_apply_refuses_unknown_plan(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

    with pytest.raises(ObsidianMcpToolError) as exc:
        apply_email_to_note_plan(config, plan_id="curation_20200101T000000Z_aaaaaaaaaaaa")
    assert exc.value.code == "unknown_plan"


def test_focused_plans_persist(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = build_moc_plan(config, root_path="Work")
    assert plan_store.load_plan(plan["plan_id"]) is not None
