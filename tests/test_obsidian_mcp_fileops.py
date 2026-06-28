"""Safe file-operation tools (move/rename/archive) for the Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import plan_store
from hb_assistant.obsidian_mcp.config import (
    ObsidianMcpConfigPatch,
    apply_patch,
    load_config,
)
from hb_assistant.obsidian_mcp.fileops import (
    archive_note_apply,
    archive_note_plan,
    delete_note_plan,
    move_note_apply,
    move_note_plan,
    rename_note_apply,
    rename_note_plan,
)
from hb_assistant.obsidian_mcp.mutations import recent_mutations
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


def _setup(tmp_path, monkeypatch, *, enable_writes=True):
    vault = tmp_path / "vault"
    inbox = vault / "Inbox"
    work = vault / "Work"
    inbox.mkdir(parents=True)
    work.mkdir(parents=True)
    (inbox / "Note.md").write_text("# Note\n\nMoved content.\n", encoding="utf-8")
    (work / "Alpha.md").write_text("# Alpha\n\nSee [[Note]] for details.\n", encoding="utf-8")
    (work / "Beta.md").write_text("# Beta\n\nRef [Note](../Inbox/Note.md) and prose.\n", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    if enable_writes:
        apply_patch(ObsidianMcpConfigPatch(writes_enabled=True, vault_markdown_write_enabled=True))
    return load_config(), vault


# ---------------------------------------------------------------------------
# plan is read-only
# ---------------------------------------------------------------------------
def test_move_plan_is_read_only_and_previews_backlinks(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = move_note_plan(config, source_path="Inbox/Note.md", target_path="Work/Note.md")
    assert plan["plan_id"].startswith("fileop_")
    assert plan["backlinks_to_update"] >= 1
    assert "Work/Alpha.md" in plan["affected_notes"]
    # Nothing moved during planning.
    assert (vault / "Inbox" / "Note.md").exists()
    assert not (vault / "Work" / "Note.md").exists()
    assert plan_store.load_plan(plan["plan_id"]) is not None


# ---------------------------------------------------------------------------
# apply requires a stored plan_id
# ---------------------------------------------------------------------------
def test_move_apply_refuses_unknown_plan(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    with pytest.raises(ObsidianMcpToolError) as exc:
        move_note_apply(config, plan_id="fileop_20200101T000000Z_aaaaaaaaaaaa")
    assert exc.value.code == "unknown_plan"


def test_apply_refuses_op_mismatch(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = move_note_plan(config, source_path="Inbox/Note.md", target_path="Work/Note.md")
    with pytest.raises(ObsidianMcpToolError) as exc:
        archive_note_apply(config, plan_id=plan["plan_id"])  # plan op is "move"
    assert exc.value.code == "plan_op_mismatch"


# ---------------------------------------------------------------------------
# move apply: moves file, backs up source, rewrites backlinks
# ---------------------------------------------------------------------------
def test_move_apply_moves_and_rewrites_links(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = move_note_plan(config, source_path="Inbox/Note.md", target_path="Work/Moved.md")
    result = move_note_apply(config, plan_id=plan["plan_id"])

    assert (vault / "Work" / "Moved.md").exists()
    assert not (vault / "Inbox" / "Note.md").exists()  # source vacated
    # Source content preserved at the new path.
    assert "Moved content." in (vault / "Work" / "Moved.md").read_text(encoding="utf-8")
    # Wikilink + markdown link both rewritten to the new stem.
    alpha = (vault / "Work" / "Alpha.md").read_text(encoding="utf-8")
    assert "[[Moved]]" in alpha
    beta = (vault / "Work" / "Beta.md").read_text(encoding="utf-8")
    assert "(Moved.md)" in beta
    assert {e["path"] for e in result["links_updated"]} == {"Work/Alpha.md", "Work/Beta.md"}
    # A backup of the source exists, and a move receipt was recorded.
    assert any(m.get("action") == "note_moved_out" for m in recent_mutations(20))
    receipt = plan_store.load_receipt(plan["plan_id"])
    assert receipt and receipt["counts"]["links_updated"] == 2


def test_move_apply_respects_max_updates(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = move_note_plan(config, source_path="Inbox/Note.md", target_path="Work/Moved.md")
    result = move_note_apply(config, plan_id=plan["plan_id"], max_updates=1)
    assert result["counts"]["links_updated"] == 1
    assert any(s["reason"] == "max_updates" for s in result["skipped"])


def test_move_apply_drift_on_source_refused(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = move_note_plan(config, source_path="Inbox/Note.md", target_path="Work/Moved.md")
    (vault / "Inbox" / "Note.md").write_text("# Note\n\nChanged.\n", encoding="utf-8")
    with pytest.raises(ObsidianMcpToolError) as exc:
        move_note_apply(config, plan_id=plan["plan_id"])
    assert exc.value.code == "sha256_mismatch"
    assert (vault / "Inbox" / "Note.md").exists()  # not moved


# ---------------------------------------------------------------------------
# rename + archive + delete-substitution
# ---------------------------------------------------------------------------
def test_rename_apply(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = rename_note_plan(config, source_path="Inbox/Note.md", new_name="Renamed")
    assert plan["target_path"] == "Inbox/Renamed.md"
    rename_note_apply(config, plan_id=plan["plan_id"])
    assert (vault / "Inbox" / "Renamed.md").exists()
    assert not (vault / "Inbox" / "Note.md").exists()


def test_archive_apply_moves_to_archive(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    plan = archive_note_plan(config, source_path="Inbox/Note.md")
    assert plan["target_path"] == "Archive/Inbox/Note.md"
    archive_note_apply(config, plan_id=plan["plan_id"])
    assert (vault / "Archive" / "Inbox" / "Note.md").exists()
    assert not (vault / "Inbox" / "Note.md").exists()


def test_delete_plan_substitutes_archive(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = delete_note_plan(config, source_path="Inbox/Note.md")
    assert plan["requested_operation"] == "delete"
    assert plan["substituted_with"] == "archive"
    # The returned plan is an applyable archive plan; there is no delete-apply tool.
    stored = plan_store.load_plan(plan["plan_id"])
    assert stored["op"] == "archive"
