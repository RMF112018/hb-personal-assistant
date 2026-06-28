"""Second-brain curation tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

import json
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
    build_curation_plan,
    vault_map,
)
from hb_assistant.obsidian_mcp.mutations import recent_mutations, sha256_file
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

_AREA_NOTES = {
    "Alpha.md": "# Alpha\n\nSECRETBODYMARKER See [[Beta]] for gamma context. #project\n",
    "Beta.md": "# Beta\n\nProcurement notes. #area-x\n",
    "Gamma.md": "# Gamma\n\nAlpha is referenced here in prose.\n",
    "Delta.md": "# Delta\n\nStandalone note.\n",
    "Epsilon.md": "# Epsilon\n\nAnother note.\n",
}


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


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enable_writes: bool = False):
    vault = tmp_path / "vault"
    # Hidden / system / protected paths that must never surface to OAuth clients.
    for hidden in (".obsidian", ".git", ".venv", ".smart-env"):
        (vault / hidden).mkdir(parents=True)
        (vault / hidden / "data.txt").write_text("hidden", encoding="utf-8")
    (vault / ".hidden-note.md").parent.mkdir(parents=True, exist_ok=True)
    (vault / ".hidden-note.md").write_text("# Hidden\n", encoding="utf-8")
    # A dense folder (>= threshold notes, no index/MOC).
    area = vault / "Area"
    area.mkdir()
    for name, body in _AREA_NOTES.items():
        (area / name).write_text(body, encoding="utf-8")
    # A sparse folder.
    solo = vault / "Solo"
    solo.mkdir()
    (solo / "One.md").write_text("# One\n\nLonely note.\n", encoding="utf-8")

    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    if enable_writes:
        apply_patch(ObsidianMcpConfigPatch(writes_enabled=True, vault_markdown_write_enabled=True))
    return load_config(), vault


def _note_shas(vault: Path) -> dict[str, str]:
    return {p.as_posix(): sha256_file(p) for p in vault.rglob("*.md")}


# ---------------------------------------------------------------------------
# vault_map
# ---------------------------------------------------------------------------
def test_vault_map_skips_hidden_and_protected_paths(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = vault_map(config, root_path="", recursive=True, include_hidden=True)

    file_paths = {f["path"] for f in result["files"]}
    folder_paths = {f["path"] for f in result["folders"]}
    blocked = {".git", ".obsidian", ".trash", ".venv", ".smart-env", ".hb-assistant"}
    for path in file_paths | folder_paths:
        segments = path.split("/")
        assert not any(seg in blocked for seg in segments), path
        assert not any(seg.startswith(".") for seg in segments), path
    assert ".hidden-note.md" not in file_paths


def test_vault_map_returns_inventory(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    result = vault_map(config, root_path="Area", recursive=True)

    names = {f["name"] for f in result["files"]}
    assert set(_AREA_NOTES) <= names
    alpha = next(f for f in result["files"] if f["name"] == "Alpha.md")
    assert alpha["has_frontmatter"] is False
    assert "Beta" in alpha["links"]
    assert "project" in alpha["tags"]


# ---------------------------------------------------------------------------
# vault_curation_plan
# ---------------------------------------------------------------------------
def test_plan_is_durable_and_read_only(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch)
    before = _note_shas(vault)
    plan = build_curation_plan(config, root_path="")

    assert plan["plan_id"].startswith("curation_")
    assert plan_store.load_plan(plan["plan_id"]) is not None
    assert _note_shas(vault) == before  # no vault mutation during planning


def test_plan_proposes_moc_and_index_for_dense_folder(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = build_curation_plan(
        config,
        root_path="",
        allowed_actions=["create_moc_notes", "create_index_notes"],
    )
    actions = plan["actions"]
    assert any(a["action"] == "create_moc_notes" and a["target_path"] == "Area/Area MOC.md" for a in actions)
    assert any(a["action"] == "create_index_notes" and a["target_path"] == "Area/_index.md" for a in actions)
    # The sparse Solo folder must not get an index.
    assert not any("Solo" in a["target_path"] for a in actions)


def test_plan_suggests_tags_and_related_links(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = build_curation_plan(config, root_path="Area")
    actions = plan["actions"]
    assert any(a["action"] == "suggest_tags" for a in actions)
    assert any(a["action"] in {"append_related_links", "suggest_links"} for a in actions)


def test_plan_record_omits_full_note_bodies(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch)
    plan = build_curation_plan(config, root_path="Area")

    assert all("payload" not in a for a in plan["actions"])  # returned actions are redacted
    record = plan_store.load_plan(plan["plan_id"])
    assert "SECRETBODYMARKER" not in json.dumps(record)  # stored plan keeps deltas, not bodies


# ---------------------------------------------------------------------------
# vault_curation_apply
# ---------------------------------------------------------------------------
def test_apply_refuses_unknown_plan(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    with pytest.raises(ObsidianMcpToolError) as exc:
        apply_curation_plan(
            config,
            plan_id="curation_20200101T000000Z_aaaaaaaaaaaa",
            approved_actions=["create_moc_notes"],
        )
    assert exc.value.code == "unknown_plan"


def test_apply_refuses_action_not_in_plan(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    plan = build_curation_plan(config, root_path="Area", allowed_actions=["create_moc_notes"])
    with pytest.raises(ObsidianMcpToolError) as exc:
        apply_curation_plan(
            config,
            plan_id=plan["plan_id"],
            approved_actions=["add_frontmatter"],
        )
    assert exc.value.code == "action_not_in_plan"


def test_apply_respects_max_updates(tmp_path, monkeypatch):
    config, _vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    plan = build_curation_plan(config, root_path="Area", allowed_actions=["add_frontmatter"])
    result = apply_curation_plan(
        config,
        plan_id=plan["plan_id"],
        approved_actions=["add_frontmatter"],
        max_updates=2,
    )
    assert len(result["applied"]) == 2
    assert any(s["reason"] == "max_updates" for s in result["skipped"])


def test_apply_requires_expected_sha_for_edits(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    plan = build_curation_plan(config, root_path="Area", allowed_actions=["add_frontmatter"])
    # Drift the file after planning so its live sha no longer matches the baseline.
    (vault / "Area" / "Alpha.md").write_text("changed after planning\n", encoding="utf-8")

    result = apply_curation_plan(
        config,
        plan_id=plan["plan_id"],
        approved_actions=["add_frontmatter"],
        max_updates=25,
    )
    assert any(
        f["target_path"] == "Area/Alpha.md" and f["reason"] == "sha256_mismatch" for f in result["failed"]
    )
    # The drifted file was not silently overwritten.
    assert (vault / "Area" / "Alpha.md").read_text(encoding="utf-8") == "changed after planning\n"


def test_apply_creates_backup_and_receipt(tmp_path, monkeypatch):
    config, vault = _setup(tmp_path, monkeypatch, enable_writes=True)
    plan = build_curation_plan(
        config,
        root_path="Area",
        allowed_actions=["create_moc_notes", "append_related_links"],
    )
    result = apply_curation_plan(
        config,
        plan_id=plan["plan_id"],
        approved_actions=["create_moc_notes", "append_related_links"],
        max_updates=25,
    )

    # One MOC note created.
    assert (vault / "Area" / "Area MOC.md").exists()
    # The related-links edit produced a backup.
    edits = [a for a in result["applied"] if a["op"] == "edit"]
    assert edits and any(a.get("backup_path") for a in edits)
    # Receipt persisted next to the plan.
    receipt = plan_store.load_receipt(plan["plan_id"])
    assert receipt is not None
    assert receipt["counts"]["applied"] == len(result["applied"])
    # Mutations are visible in the existing mutation/events surface.
    assert any(m.get("caller_surface") == "mcp_curation" for m in recent_mutations(20))
    assert {"applied", "skipped", "failed"} <= set(result)
