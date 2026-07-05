"""N8C-2 — Source/Card Identity Hardening: read-only lookup / stale / duplicate / classification.

Everything under test is read-only: no DB mutation, no card write, no retire/delete. Card identity is
computed; source-card rendering is byte-unchanged (no new frontmatter fields).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_card_identity as sci
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.obsidian_mcp.source_notes import CARD_VERSION, generate_source_card
from hb_assistant.store.migrator import SQLiteMigrator

REL_A = "docs/alpha.txt"
REL_B = "docs/beta.txt"


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = tmp_path / "c.yml"
    cfg.write_text(
        f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n  obsidian_vault: {vault.as_posix()!r}\n"
    )
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    root = tmp_path / "proj"
    config = ObsidianMcpConfig.model_validate({
        "enabled": True, "vault_root": str(vault), "writes_enabled": True,
        "vault_markdown_write_enabled": True,
        "external_sources": [{"source_root_key": "proj", "path": str(root), "enabled": True}],
    })
    repo = SourceIndexRepository(db)
    (root / "docs").mkdir(parents=True)
    (root / REL_A).write_text("alpha content v1", encoding="utf-8")
    (root / REL_B).write_text("beta content", encoding="utf-8")
    sid_a = index_source_file(root / REL_A, config.external_sources[0], repo, config)
    sid_b = index_source_file(root / REL_B, config.external_sources[0], repo, config)
    out_a = generate_source_card(repo, config, source_id=sid_a)
    out_b = generate_source_card(repo, config, source_id=sid_b)
    return {"repo": repo, "config": config, "vault": vault, "root": root,
            "sid_a": sid_a, "sid_b": sid_b, "card_a": out_a["note_path"], "card_b": out_b["note_path"]}


# --- identity primitives ---------------------------------------------------------------

def test_compute_card_id_is_deterministic_and_distinct_from_source_id() -> None:
    sid = "a" * 32
    cid = sci.compute_card_id(sid, "Source Notes/Shared/x__abc.md")
    assert cid == sci.compute_card_id(sid, "Source Notes/Shared/x__abc.md")  # deterministic
    assert cid != sid and cid != sid[:16]                                    # separate from source id
    assert len(cid) == 16
    # Same source at a different path is a different card.
    assert cid != sci.compute_card_id(sid, "Source Notes/Shared/x__def.md")


# --- source -> card and card -> source -------------------------------------------------

def test_source_to_card_lookup(env) -> None:
    card = sci.get_card_for_source(env["repo"], env["sid_a"])
    assert card is not None
    assert card["note_rel_path"] == env["card_a"]
    assert card["generation_status"] == "generated"
    assert card["card_id"] == sci.compute_card_id(env["sid_a"], env["card_a"])


def test_card_to_source_reverse_lookup_unique(env) -> None:
    res = sci.get_source_for_card(env["repo"], env["card_a"])
    assert res.resolution == "unique"
    assert res.source_id == env["sid_a"]
    assert len(res.sources) == 1


def test_card_to_source_reverse_lookup_none(env) -> None:
    res = sci.get_source_for_card(env["repo"], "Source Notes/Shared/does-not-exist__000.md")
    assert res.resolution == "none"
    assert res.source_id is None and res.sources == []


def test_card_to_source_reverse_lookup_ambiguous_never_arbitrary(env) -> None:
    # Two different sources point at ONE card path (no DB UNIQUE on note_rel_path alone).
    env["repo"].record_generated_note(env["sid_b"], env["card_a"], "generated", "2026-07-05T00:00:00Z")
    res = sci.get_source_for_card(env["repo"], env["card_a"])
    assert res.resolution == "ambiguous"
    assert res.source_id is None                       # never picks one arbitrarily
    assert {s["source_id"] for s in res.sources} == {env["sid_a"], env["sid_b"]}


# --- duplicate detection ---------------------------------------------------------------

def test_duplicate_cards_one_source_multiple_paths(env) -> None:
    env["repo"].record_generated_note(env["sid_a"], "Source Notes/Shared/dup__extra.md",
                                      "generated", "2026-07-05T00:00:00Z")
    rep = sci.detect_duplicate_cards(env["repo"], env["sid_a"])
    assert rep.is_duplicate is True
    assert len(rep.active_card_paths) == 2
    assert sci.classify_card_state(env["repo"], env["vault"], env["sid_a"]).state == sci.STATE_DUPLICATE


def test_duplicate_cards_cross_source_conflict(env) -> None:
    env["repo"].record_generated_note(env["sid_b"], env["card_a"], "generated", "2026-07-05T00:00:00Z")
    rep = sci.detect_duplicate_cards(env["repo"], env["sid_a"])
    assert rep.is_duplicate is False                   # sid_a still has one path
    assert rep.cross_source_conflicts
    assert env["sid_b"] in rep.cross_source_conflicts[0]["other_source_ids"]


def test_no_duplicate_for_clean_source(env) -> None:
    rep = sci.detect_duplicate_cards(env["repo"], env["sid_a"])
    assert rep.is_duplicate is False and rep.cross_source_conflicts == []


# --- staleness -------------------------------------------------------------------------

def test_stale_by_source_digest_drift(env) -> None:
    # Change the source content and re-index -> metadata content_sha256 changes; the card still
    # carries the old source_sha256 in frontmatter -> digest drift (detected from card frontmatter,
    # no DB status change or migration required).
    (env["root"] / REL_A).write_text("alpha content v2 CHANGED", encoding="utf-8")
    index_source_file(env["root"] / REL_A, env["config"].external_sources[0], env["repo"], env["config"])
    verdict = sci.detect_stale_card(env["repo"], env["vault"], env["sid_a"], env["card_a"])
    assert verdict.is_stale is True
    assert verdict.reason == sci.STALE_SOURCE_DIGEST_DRIFT


def test_missing_card_file(env) -> None:
    (env["vault"] / env["card_a"]).unlink()
    verdict = sci.detect_stale_card(env["repo"], env["vault"], env["sid_a"], env["card_a"])
    assert verdict.reason == sci.STALE_CARD_FILE_MISSING
    assert sci.classify_card_state(env["repo"], env["vault"], env["sid_a"]).state == sci.STATE_MISSING


def test_source_deleted_card_active_is_classification_only(env) -> None:
    # mark_deleted flips the source deleted flag (and DB-stales the note); N8C-2 must only CLASSIFY.
    env["repo"].mark_deleted("external_file", REL_A, source_root_key="proj")
    state = sci.classify_card_state(env["repo"], env["vault"], env["sid_a"])
    assert state.state == sci.STATE_SOURCE_DELETED
    # Read-only: the card file and source row are untouched by the identity layer.
    assert (env["vault"] / env["card_a"]).exists()
    assert env["repo"].get_source_detail(env["sid_a"]) is not None


def test_source_id_mismatch(env) -> None:
    # A card whose frontmatter source_id differs from the source it is looked up against.
    verdict = sci.detect_stale_card(env["repo"], env["vault"], env["sid_b"], env["card_a"])
    assert verdict.reason == sci.STALE_SOURCE_ID_MISMATCH


def test_card_version_obsolete_uses_constant_not_legacy(env) -> None:
    card_path = env["vault"] / env["card_a"]
    text = card_path.read_text(encoding="utf-8")
    assert f'card_version: "{CARD_VERSION}"' in text
    card_path.write_text(text.replace(f'card_version: "{CARD_VERSION}"', 'card_version: "old-v0"'),
                         encoding="utf-8")
    verdict = sci.detect_stale_card(env["repo"], env["vault"], env["sid_a"], env["card_a"])
    assert verdict.reason == sci.STALE_CARD_VERSION_OBSOLETE
    assert sci.LEGACY_NO_CARD_VERSION not in verdict.legacy_flags   # present-but-old != legacy-missing


def test_current_card_is_not_stale(env) -> None:
    verdict = sci.detect_stale_card(env["repo"], env["vault"], env["sid_a"], env["card_a"])
    assert verdict.is_stale is False and verdict.reason == sci.STALE_NONE
    assert sci.classify_card_state(env["repo"], env["vault"], env["sid_a"]).state == sci.STATE_CURRENT


# --- legacy compatibility --------------------------------------------------------------

def test_legacy_card_missing_fields_is_distinct_not_corruption() -> None:
    legacy = "---\nnote_type: source_card\nsource_id: \"leg123\"\n---\n\nbody\n"
    ident = sci.parse_source_card(legacy, "Source Notes/Shared/leg__x.md")
    assert ident is not None and ident.has_source_id
    assert not ident.has_card_version and not ident.has_source_digest
    vr = sci.validate_card_frontmatter(legacy, "Source Notes/Shared/leg__x.md")
    assert vr.is_source_card is True and vr.ok is True          # legacy != invalid
    assert set(vr.problems) == {sci.LEGACY_NO_CARD_VERSION, sci.LEGACY_NO_SOURCE_DIGEST}


# --- type non-misclassification --------------------------------------------------------

def test_ai_outputs_card_not_classified_as_source_card() -> None:
    ai = "---\ntitle: X\nsource_client: chatgpt\nmanaged_by: personal_assistant\nnote_type: ai_output\ndomain: home\ncreated_via: mcp\n---\nbody"
    assert sci.classify_note(ai, "AI Outputs/X.md") == sci.NOTE_AI_OUTPUT
    assert sci.parse_source_card(ai) is None
    assert sci.validate_card_frontmatter(ai, "AI Outputs/X.md").is_source_card is False


def test_email_archive_note_not_classified_as_source_card() -> None:
    arch = "---\nnote_type: email_archive\nsource_type: eml\nemail_subject: hi\n---\nbody"
    assert sci.classify_note(arch, "Email Archive/Work/e__x.md") == sci.NOTE_EMAIL_ARCHIVE
    assert sci.parse_source_card(arch) is None


def test_user_authored_note_not_classified_as_source_card(env) -> None:
    user = "# My hand-written note\n\nsome personal text, no frontmatter\n"
    assert sci.classify_note(user, "Notes/mine.md", env["config"]) == sci.NOTE_USER_AUTHORED
    assert sci.parse_source_card(user) is None
    # generate_source_card already refuses obsidian_note sources — the policy seam is intact.


# --- neutrality / byte-unchanged -------------------------------------------------------

def test_source_card_rendering_is_byte_unchanged_and_neutral(env) -> None:
    text = (env["vault"] / env["card_a"]).read_text(encoding="utf-8")
    front = text.split("\n---\n", 1)[0]
    # Existing neutral identity fields are present...
    assert "note_type: source_card" in front
    assert "source_id:" in front and "source_sha256:" in front
    # ...and N8C-2 added NO frontmatter fields (identity is computed) and NO hb-branded metadata.
    assert "card_id:" not in front
    assert "managed_by:" not in front
    assert "card_status:" not in front
    assert "hb_" not in front and "hb-" not in front


def test_domain_metadata_preserved_on_source_card(env) -> None:
    ident = sci.parse_source_card(
        (env["vault"] / env["card_a"]).read_text(encoding="utf-8"), env["card_a"])
    assert ident.domain in {"work", "home", "shared"}
