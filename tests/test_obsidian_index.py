"""Phase 08A Synthesized Prompt 05 — approved Obsidian indexing (offline)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.obsidian_index import (
    build_approved_obsidian_index_proof,
    build_index,
    list_approved_obsidian_index_entries,
    load_obsidian_index_policy,
    scan_approved_notes,
)

_MANAGED = (
    "# Project Data Quality Summary\n"
    "project_key: P1\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:START -->\n"
    "bounded safe summary with [[ref1]] and [[ref2]]\n"
    "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:END -->\n"
)
_UNMANAGED = "# Private note\nno HB markers here — should not be indexed\n"

_GUARD_COLS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "retrieved_context_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "arbitrary_sql_allowed",
    "external_writeback_performed",
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault" / "Construction Intelligence" / "Phase 07A Data Quality"
    root.mkdir(parents=True)
    (root / "managed.md").write_text(_MANAGED, encoding="utf-8")
    (root / "unmanaged.md").write_text(_UNMANAGED, encoding="utf-8")
    return tmp_path / "vault"


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "idx.sqlite")


def test_scan_indexes_only_managed_notes(vault: Path) -> None:
    policy = load_obsidian_index_policy()
    entries, excluded = scan_approved_notes(vault, policy)
    assert len(entries) == 1
    assert excluded == 1  # the unmanaged note
    e = entries[0]
    assert e.section_marker == "HB-DATA-QUALITY-PROJECT-SUMMARY"
    assert e.project_key == "P1"
    assert e.source_ref_count == 2
    assert e.review_tier == 1
    assert e.source_type == "phase_07a_data_quality"
    assert len(e.content_hash) == 16 and len(e.note_path_hash) == 16


def test_entry_carries_no_raw_content(vault: Path) -> None:
    policy = load_obsidian_index_policy()
    entries, _ = scan_approved_notes(vault, policy)
    blob = entries[0].model_dump_json()
    assert "bounded safe summary" not in blob  # section text never stored
    for forbidden in ("raw_body", "signed_url", "download_url", "http://"):
        assert forbidden not in blob


def test_apply_persists_manifest_and_entries_guards_zero(vault: Path, db_path: str) -> None:
    manifest = build_index(mode="apply", vault_root=vault, db_path=db_path)
    assert manifest.mode == "apply"
    assert manifest.entry_count == 1
    assert manifest.excluded_count == 1
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    m = dict(conn.execute("SELECT * FROM obsidian_index_manifests").fetchone())
    assert m["mode"] == "apply"
    for col in _GUARD_COLS:
        assert m[col] == 0
    rows = conn.execute("SELECT * FROM obsidian_index_entries").fetchall()
    assert len(rows) == 1
    meta = json.loads(rows[0]["source_refs_json"])
    assert meta["review_tier"] == 1
    assert meta["source_ref_count"] == 2
    conn.close()


def test_dry_run_persists_dry_run_manifest(vault: Path, db_path: str) -> None:
    manifest = build_index(mode="dry_run", vault_root=vault, db_path=db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    m = conn.execute("SELECT mode FROM obsidian_index_manifests").fetchone()
    assert m["mode"] == "dry_run"
    assert manifest.entry_count == 1
    conn.close()


def test_source_notes_not_mutated(vault: Path, db_path: str) -> None:
    note = vault / "Construction Intelligence" / "Phase 07A Data Quality" / "managed.md"
    before = note.read_bytes()
    build_index(mode="apply", vault_root=vault, db_path=db_path)
    assert note.read_bytes() == before


def test_list_entries_reads_latest(vault: Path, db_path: str) -> None:
    build_index(mode="apply", vault_root=vault, db_path=db_path)
    rows = list_approved_obsidian_index_entries(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["meta"]["approved_root_label"].startswith("Construction Intelligence")


def test_missing_vault_degrades(tmp_path: Path, db_path: str) -> None:
    manifest = build_index(mode="dry_run", vault_root=tmp_path / "nope", db_path=db_path)
    assert manifest.entry_count == 0
    assert manifest.excluded_count == 0


def test_index_proof_passes() -> None:
    proof = build_approved_obsidian_index_proof()
    assert proof["proof"] == "phase_08a_approved_obsidian_index"
    assert proof["proof_passed"] is True
    assert proof["contract_required_fields_present"] is True
    assert proof["no_raw_content"] is True
    assert proof["source_notes_mutated"] is False
    assert proof["guardrails"]["raw_vault_browsing"] is False
    assert len(proof["approved_roots"]) == 4
