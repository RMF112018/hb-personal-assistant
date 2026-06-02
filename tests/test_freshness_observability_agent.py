"""Phase 08B Prompt 07 — source / runtime / retrieval freshness observability."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.freshness import (
    build_freshness_observability_proof,
    evaluate_observability,
    evaluate_retrieval_freshness,
    evaluate_runtime_health,
    evaluate_source_freshness,
    run_observability,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection

_FORBIDDEN = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
)

_NOW = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    db = str(tmp_path / "obs.sqlite")
    ConstructionStore(db)  # migrate to LATEST
    return db


def _seed_drive(db_path: str, *, utc: str) -> None:
    conn = get_connection(Path(db_path))
    with conn:
        conn.execute(
            "INSERT INTO construction_source_locations "
            "(source_id, source_system, source_scope, source_name) "
            "VALUES ('s-drive','sharepoint','project','Drive X')"
        )
        conn.execute(
            "INSERT INTO construction_source_sync_state (source_id, last_successful_sync_utc, sync_status) "
            "VALUES ('s-drive', ?, 'ok')",
            (utc,),
        )


def _seed_index(db_path: str, *, manifest_utc: str, note_modified_utc: str) -> None:
    conn = get_connection(Path(db_path))
    with conn:
        conn.execute(
            "INSERT INTO obsidian_index_manifests "
            "(manifest_id, mode, approved_roots_json, policy_version, generated_utc) "
            "VALUES ('m1','apply','[]','v1', ?)",
            (manifest_utc,),
        )
        conn.execute(
            "INSERT INTO obsidian_index_entries "
            "(entry_id, manifest_id, note_path_redacted, note_path_hash, content_hash, modified_utc) "
            "VALUES ('e1','m1','~/n.md','h','c', ?)",
            (note_modified_utc,),
        )


# --- source freshness ----------------------------------------------------------------------
def test_source_unknown_on_empty_db(db_path: str) -> None:
    status = evaluate_source_freshness(db_path=db_path, now=_NOW)
    assert status.overall_status == "ok"  # unknown != stale
    assert status.reason_code == "SOURCE_FRESHNESS_UNKNOWN"
    assert status.unknown_count == 4


def test_source_fresh(db_path: str) -> None:
    _seed_drive(db_path, utc=(_NOW - timedelta(hours=1)).isoformat())
    status = evaluate_source_freshness(db_path=db_path, now=_NOW)
    by = {s.domain: s for s in status.signals}
    assert by["graph_drive"].reason_code == "SOURCE_FRESH"
    assert status.stale_count == 0


def test_source_stale(db_path: str) -> None:
    _seed_drive(db_path, utc=(_NOW - timedelta(hours=240)).isoformat())
    status = evaluate_source_freshness(db_path=db_path, now=_NOW)
    by = {s.domain: s for s in status.signals}
    assert by["graph_drive"].reason_code == "SOURCE_STALE"
    assert status.overall_status == "attention"
    assert status.stale_count == 1


# --- retrieval freshness -------------------------------------------------------------------
def test_retrieval_index_missing(db_path: str) -> None:
    status = evaluate_retrieval_freshness(db_path=db_path, now=_NOW)
    codes = {s.reason_code for s in status.signals}
    assert "RETRIEVAL_INDEX_MISSING" in codes


def test_retrieval_fresh(db_path: str) -> None:
    _seed_index(
        db_path,
        manifest_utc=(_NOW - timedelta(hours=1)).isoformat(),
        note_modified_utc=(_NOW - timedelta(hours=2)).isoformat(),
    )
    status = evaluate_retrieval_freshness(db_path=db_path, now=_NOW)
    idx = next(s for s in status.signals if s.name == "obsidian_index")
    assert idx.reason_code == "RETRIEVAL_FRESH"


def test_retrieval_stale_notes_modified_after_index(db_path: str) -> None:
    _seed_index(
        db_path,
        manifest_utc=(_NOW - timedelta(hours=10)).isoformat(),
        note_modified_utc=(_NOW - timedelta(hours=1)).isoformat(),  # newer than manifest
    )
    status = evaluate_retrieval_freshness(db_path=db_path, now=_NOW)
    idx = next(s for s in status.signals if s.name == "obsidian_index")
    assert idx.reason_code == "RETRIEVAL_STALE"
    assert idx.detail == "notes_modified_after_index"


# --- runtime health (composed) -------------------------------------------------------------
def test_runtime_health_ok_on_migrated_db(db_path: str) -> None:
    status = evaluate_runtime_health(db_path=db_path)
    assert status.overall_status == "ok"
    assert status.reason_code == "RUNTIME_HEALTH_OK"


# --- combined snapshot ---------------------------------------------------------------------
def test_observability_ok_when_nothing_stale(db_path: str) -> None:
    snap = evaluate_observability(db_path=db_path, now=_NOW)
    assert snap.overall_status == "ok"
    assert snap.reason_code == "OBSERVABILITY_OK"


def test_observability_degraded_on_stale_source(db_path: str) -> None:
    _seed_drive(db_path, utc=(_NOW - timedelta(hours=240)).isoformat())
    snap = evaluate_observability(db_path=db_path, now=_NOW)
    assert snap.overall_status == "attention"
    assert snap.reason_code == "OBSERVABILITY_DEGRADED"


# --- emit-gated receipt --------------------------------------------------------------------
def test_run_observability_read_only_by_default(db_path: str) -> None:
    _, agent_run_id = run_observability(db_path=db_path, now=_NOW)
    assert agent_run_id is None


def test_emit_persists_metadata_only_v28_receipt(db_path: str) -> None:
    _, agent_run_id = run_observability(db_path=db_path, now=_NOW, emit_receipt=True)
    assert agent_run_id is not None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(
        conn.execute(
            "SELECT * FROM second_brain_agent_run_receipts WHERE agent_id='freshness_observability_agent'"
        ).fetchone()
    )
    conn.close()
    assert row["run_kind"] == "freshness_observability"
    for col, value in row.items():
        if col.endswith("_persisted") or col == "external_writeback_performed":
            assert value == 0, f"guard {col} must be 0"


# --- proof ---------------------------------------------------------------------------------
def test_proof_passes() -> None:
    proof = build_freshness_observability_proof()
    assert proof["proof_passed"] is True
    assert proof["empty_reason_code"] == "OBSERVABILITY_OK"
    assert proof["degraded_reason_code"] == "OBSERVABILITY_DEGRADED"
    assert proof["no_raw_content"] is True


def test_proof_has_no_forbidden_tokens() -> None:
    import json

    blob = json.dumps(build_freshness_observability_proof(), default=str)
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob
