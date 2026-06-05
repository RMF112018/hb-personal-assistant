"""Phase 09 Prompt 35 — no raw vector index proof tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source scanner
detection (value never echoed), the no-raw/no-writeback proof + guard-clean persisted row, and
guard-clean artifact writing.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from hb_assistant.construction.second_brain.retrieval import no_raw_vector_index_proof as nrv
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normal_clean_proof_over_migrated_db(tmp_path):
    out_dir = tmp_path / "ev"
    out_dir.mkdir()
    result = nrv.build_no_raw_vector_index_proof(
        _migrated_db(tmp_path), evidence_dir=str(out_dir), write_evidence=False
    )

    assert result["proof_passed"] is True
    assert result["gates"]["db_guard_clean"] is True
    assert result["gates"]["no_vector_blob_columns"] is True
    assert result["gates"]["vectors_outside_sqlite"] is True
    assert result["gates"]["evidence_no_forbidden"] is True
    assert result["gates"]["scanner_detects_planted"] is True
    assert result["forbidden_findings"] == 0
    assert result["guard_violations"] == 0
    assert result["makes_determination"] is False


def test_missing_policy_fail_closed(tmp_path, monkeypatch):
    def _boom() -> dict:
        raise nrv.NoRawVectorIndexProofError("contract missing")

    monkeypatch.setattr(nrv, "load_no_raw_vector_index_proof_contract", _boom)
    with pytest.raises(nrv.NoRawVectorIndexProofError):
        nrv.build_no_raw_vector_index_proof(_migrated_db(tmp_path))


def test_stale_schema_fail_closed(tmp_path):
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations
    with pytest.raises(nrv.NoRawVectorIndexProofError):
        nrv.build_no_raw_vector_index_proof(empty)


def test_unsafe_source_flagged_value_not_echoed(tmp_path):
    # plant a synthetic signed-url in a vector-index-items text column + an evidence file
    db = _migrated_db(tmp_path)
    synthetic = "https://x.example/a" + "?sig=" + "Q" * 24
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            f"INSERT INTO {nrv._VECTOR_TABLES[1]} "
            "(item_id, run_id, policy_version, schema_version, source_family, source_ref_hash, "
            "content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("p-1", "r-1", "v", 39, "accepted_long_term_memory", synthetic, "h"),
        )
        conn.commit()
        db_scan = nrv.scan_db(
            conn, scanned_tables=nrv._VECTOR_TABLES, blob_cols=nrv._VECTOR_BLOB_COLS
        )
    finally:
        conn.close()
    assert len(db_scan["findings"]) >= 1
    # findings carry table.column + a pattern label, never the offending value
    serialized = json.dumps(db_scan["findings"])
    assert synthetic not in serialized
    assert all(set(f) == {"location", "pattern"} for f in db_scan["findings"])

    ev = tmp_path / "ev"
    ev.mkdir()
    (ev / "dirty.json").write_text('{"x": "' + synthetic + '"}', encoding="utf-8")
    ev_scan = nrv.scan_evidence(str(ev), extensions=(".json", ".md"))
    assert len(ev_scan["findings"]) >= 1
    assert synthetic not in json.dumps(ev_scan["findings"])


def test_no_raw_no_writeback_proof_and_guard_clean_row(tmp_path):
    db = _migrated_db(tmp_path)
    out_dir = tmp_path / "ev"
    out_dir.mkdir()

    before = (
        sqlite3.connect(db).execute(f"SELECT COUNT(*) FROM {nrv._VALIDATION_TABLE}").fetchone()[0]
    )
    result = nrv.build_no_raw_vector_index_proof(
        db, evidence_dir=str(out_dir), write_evidence=False
    )
    assert before == 0 and result["receipt_emitted"] is False

    result2 = nrv.build_no_raw_vector_index_proof(
        db, evidence_dir=str(out_dir), write_evidence=False, emit_receipt=True
    )
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            f"SELECT gate_count, pass_count, fail_count, overall_status FROM {nrv._VALIDATION_TABLE} "
            "WHERE run_id = ?",
            (result2["run_id"],),
        ).fetchone()
        guard_cols = nrv._guard_columns_for(
            [str(r[1]) for r in conn.execute(f"PRAGMA table_info({nrv._VALIDATION_TABLE})")]
        )
        guard_sum = conn.execute(
            f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {nrv._VALIDATION_TABLE} "
            "WHERE run_id = ?",
            (result2["run_id"],),
        ).fetchone()[0]
    finally:
        conn.close()
    assert row is not None and row[3] == "clean"
    assert int(guard_sum or 0) == 0


def test_proof_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    result = nrv.build_no_raw_vector_index_proof(
        _migrated_db(tmp_path), evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "no-raw-vector-index-proof.json"
    md_path = out_dir / "no-raw-vector-index-proof.md"
    assert json_path.exists() and md_path.exists()
    assert result["proof_passed"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "access_token", "client_secret", "?sig="):
        assert token not in text
