"""Phase 09 Prompt 33 — daily brief reproducibility proof tests.

Covers the normal path, missing-policy fail-closed, stale-schema fail-closed, unsafe-source / no-raw
emission, no-raw/no-writeback proof, and guard-clean artifact writing.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from hb_assistant.construction.second_brain import daily_brief_reproducibility as dbr
from hb_assistant.store.migrator import SQLiteMigrator


def _migrated_db(tmp_path) -> str:
    db = str(tmp_path / "operator.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def test_normal_reproducible_output_and_source_refs(tmp_path):
    result = dbr.build_daily_brief_reproducibility(_migrated_db(tmp_path))

    assert result["status"] == "built"
    assert result["reproducible"] is True
    assert result["output_hash_match"] is True
    assert result["output_hash"] and result["output_hash"] == result["output_hash_b"]
    assert result["source_refs_match"] is True
    assert result["source_ref_count"] >= 1
    assert result["evaluation_receipt_present"] is True
    assert result["makes_determination"] is False
    assert result["read_only"] is True
    # source_refs are metadata-only family counts (no raw record refs)
    assert all(set(ref) == {"source_family", "count"} for ref in result["source_refs"])
    assert result["guard_attestation"] == {"all_false": True, "column_count": 23}


def test_missing_policy_fail_closed(tmp_path, monkeypatch):
    def _boom() -> dict:
        raise dbr.DailyBriefReproducibilityError("contract missing")

    monkeypatch.setattr(dbr, "load_daily_brief_reproducibility_contract", _boom)
    with pytest.raises(dbr.DailyBriefReproducibilityError):
        dbr.build_daily_brief_reproducibility(_migrated_db(tmp_path))


def test_stale_schema_fail_closed(tmp_path):
    empty = str(tmp_path / "empty.sqlite")
    sqlite3.connect(empty).close()  # no schema_migrations
    with pytest.raises(dbr.DailyBriefReproducibilityError):
        dbr.build_daily_brief_reproducibility(empty)


def test_unsafe_source_no_raw_emitted(tmp_path):
    result = dbr.build_daily_brief_reproducibility(_migrated_db(tmp_path))
    serialized = json.dumps(result, default=str)
    assert "reason" not in serialized
    for token in (
        "raw_body",
        "raw_document_text",
        "raw_calendar_payload",
        "raw_prompt",
        "raw_response",
        "signed_url",
        "download_url",
        "secret",
    ):
        assert token not in serialized


def test_no_raw_no_writeback_proof_clean(tmp_path):
    db = _migrated_db(tmp_path)
    proof = dbr.build_daily_brief_reproducibility_proof(db_path=db, write_evidence=False)

    assert proof["proof_passed"] is True
    assert proof["guards_zero"] is True
    assert proof["output_hash_match"] is True
    assert proof["source_refs_preserved"] is True
    assert proof["no_raw_emitted"] is True
    # The operator DB is never written to (experiment runs in throwaway temp DBs).
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0] == 0
    finally:
        conn.close()


def test_proof_writes_guard_clean_artifacts(tmp_path):
    out_dir = tmp_path / "evidence"
    proof = dbr.build_daily_brief_reproducibility_proof(
        evidence_dir=str(out_dir), write_evidence=True
    )

    json_path = out_dir / "daily-brief-reproducibility-proof.json"
    md_path = out_dir / "daily-brief-reproducibility-proof.md"
    assert json_path.exists() and md_path.exists()
    assert proof["proof_passed"] is True

    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    for token in ("BEGIN", "PRIVATE KEY", "signed_url", "download_url", "secret", "reason"):
        assert token not in text
