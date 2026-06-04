"""Phase 09 Prompt 09 — approved Obsidian linkage proof tests (gap G-07).

Exercises ``build_obsidian_linkage_proof`` over controlled offline populations built by
the existing approved indexer against a throwaway fixture vault: a normal guard-clean
population with resolved + broken wikilinks, a fail-closed missing-policy path, a
stale-schema DB, an unapproved-note injection, a no-raw injection, and the broken-link
advisory classification. No live model call, no real-vault write, no external writeback.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from hb_assistant.construction.second_brain.obsidian_index import build_index
from hb_assistant.construction.second_brain.obsidian_index.policy import SEED_ENV_VAR
from hb_assistant.construction.second_brain.obsidian_linkage_proof import (
    build_obsidian_linkage_proof,
    write_linkage_fixture_vault,
)


def _populate(tmp_path: Path) -> str:
    """Build an apply index over the fixture vault into a fresh proof DB; return its path."""
    vault = tmp_path / "vault"
    write_linkage_fixture_vault(vault)
    db = str(tmp_path / "idx.sqlite")
    build_index(mode="apply", vault_root=vault, db_path=db)
    return db


def test_normal_population_resolves_links_and_is_guard_clean(tmp_path: Path) -> None:
    db = _populate(tmp_path)
    proof = build_obsidian_linkage_proof(db)

    assert proof["proof_passed"] is True
    assert proof["populated"] is True
    assert proof["entry_count"] == 2
    assert proof["guard_sum"] == 0
    assert proof["guard_clean"] is True
    assert proof["canonical_refs_preserved"] is True
    assert proof["approved_only"] is True
    assert proof["unapproved_indexed"] == 0
    assert proof["raw_content_findings"] == []
    links = proof["link_summary"]
    assert links["total_links"] == 3
    assert links["resolved_links"] == 2  # alpha<->beta resolve by filename
    assert links["broken_links"] == 1  # the dangling [[Missing Note]]
    assert proof["guardrails"]["no_external_writeback"] is True
    assert proof["guardrails"]["advisory_only_no_determination"] is True


def test_empty_operator_substrate_is_not_populated(tmp_path: Path) -> None:
    # An empty (migrated) DB mirrors the G-07 operator substrate: 0 entries, honest posture.
    db = str(tmp_path / "empty.sqlite")
    build_index(mode="apply", vault_root=tmp_path / "no-vault", db_path=db)  # 0 entries
    proof = build_obsidian_linkage_proof(db)

    assert proof["populated"] is False
    assert proof["entry_count"] == 0
    assert proof["guard_clean"] is True  # vacuously clean
    # proof_passed is permissive on an empty substrate (refs vacuously preserved).
    assert proof["proof_passed"] is True
    assert proof["link_summary"]["total_links"] == 0


def test_missing_policy_fails_closed(tmp_path: Path, monkeypatch) -> None:
    db = _populate(tmp_path)
    # Point the policy seed at a nonexistent path → load raises → fail-closed.
    monkeypatch.setenv(SEED_ENV_VAR, str(tmp_path / "nope" / "policy.yaml"))
    proof = build_obsidian_linkage_proof(db)

    assert proof["policy_loaded"] is False
    assert proof["proof_passed"] is False
    assert proof["policy_error"] == "ObsidianIndexPolicyError"


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    db = str(tmp_path / "stale.sqlite")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_obsidian_linkage_proof(db)
    assert proof["schema_version"] == 5
    assert proof["schema_ok"] is False
    assert proof["proof_passed"] is False
    assert proof["manifest_present"] is False  # V26 tables absent on a stale schema


def test_unapproved_note_indexed_is_hard_failure(tmp_path: Path) -> None:
    db = _populate(tmp_path)
    conn = sqlite3.connect(db)
    manifest_id = conn.execute("SELECT manifest_id FROM obsidian_index_manifests").fetchone()[0]
    conn.execute(
        """
        INSERT INTO obsidian_index_entries
            (entry_id, manifest_id, note_path_redacted, note_path_hash, section_marker,
             heading_redacted, content_hash, modified_utc, project_key, source_type,
             confidence_class, review_status, source_refs_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            manifest_id,
            "Unapproved/Private/leak.md",
            "deadbeefdeadbeef",
            "HB-DATA-QUALITY-PROJECT-SUMMARY",
            "Leaked note",
            "feedfacefeedface",
            None,
            "X",
            "unapproved",
            "high",
            "auto_advisory",
            json.dumps(
                {
                    "review_tier": 1,
                    "approved_root_label": "Unapproved/Private",
                    "source_ref_count": 0,
                    "note_name_hash": "0000000000000000",
                    "link_target_hashes": [],
                    "stale_unknown_flags": [],
                }
            ),
        ),
    )
    conn.commit()
    conn.close()

    proof = build_obsidian_linkage_proof(db)
    assert proof["unapproved_indexed"] == 1
    assert proof["approved_only"] is False
    assert proof["proof_passed"] is False


def test_raw_content_injection_fails_closed(tmp_path: Path) -> None:
    db = _populate(tmp_path)
    before = build_obsidian_linkage_proof(db)["entry_count"]
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE obsidian_index_entries SET heading_redacted = ? "
        "WHERE entry_id = (SELECT entry_id FROM obsidian_index_entries LIMIT 1)",
        ("https://example.com/file?sig=abcdef0123456789abcdef",),
    )
    conn.commit()
    conn.close()

    proof = build_obsidian_linkage_proof(db)
    assert proof["proof_passed"] is False
    assert "obsidian_index_entries.heading_redacted" in proof["raw_content_findings"]
    # The offending value is never echoed back — only the table.column location.
    assert "sig=abcdef" not in json.dumps(proof)
    # The read-only proof never mutates the DB (no-writeback): entry count is unchanged.
    after = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM obsidian_index_entries"
    ).fetchone()[0]
    assert after == before == 2


def test_broken_link_is_advisory_not_a_hard_failure(tmp_path: Path) -> None:
    db = _populate(tmp_path)
    proof = build_obsidian_linkage_proof(db)
    assert proof["link_summary"]["broken_links"] == 1
    assert any("broken_links" in w for w in proof["warnings"])
    # Broken links are advisory source-coverage warnings — they do not fail the proof.
    assert proof["proof_passed"] is True
