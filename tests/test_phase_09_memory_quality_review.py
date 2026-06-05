"""Phase 09 Prompt 30 — memory quality review.

Proves the five required paths: (1) normal — proposed candidates are evaluated and duplicate/stale/
conflicting are detected and flagged for review; (2) missing-policy — fail-closed; (3) stale-schema —
fail-closed on a pre-V38 store; (4) unsafe-source — only hashed statements are emitted (never raw), and a
candidate restating a superseded item is flagged stale (not silently accepted); (5) no-raw / no-writeback
— the read-only default persists nothing and the persisted run row is metadata-only + guard-clean. Plus
the proof. The surface makes no determination and never merges/deletes/accepts memory.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.memory import quality_review as qr
from hb_assistant.construction.second_brain.memory.quality_review import (
    MemoryQualityReviewError,
    _seed_proof_db,
    build_memory_quality_review,
    build_memory_quality_review_proof,
    evaluate_memory_candidates,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_TABLE = "second_brain_memory_quality_review_runs"


def _run_rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0])
    finally:
        conn.close()


def _seeded_db(td: str) -> str:
    db = str(Path(td) / "mqr.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_proof_db(db)
    return db


def test_normal_detects_all_categories() -> None:
    candidates = [
        {
            "candidate_id": "c1",
            "statement_redacted": "A",
            "review_tier": 1,
            "review_tier_reason_code": "T1_DETERMINISTIC_SOURCE_BACKED",
        },
        {
            "candidate_id": "c2",
            "statement_redacted": "B",
            "review_tier": 1,
            "review_tier_reason_code": "T1_DETERMINISTIC_SOURCE_BACKED",
        },
        {
            "candidate_id": "c3",
            "statement_redacted": "Z",
            "review_tier": 3,
            "review_tier_reason_code": "T3_CONFLICT_DETECTED",
        },
        {
            "candidate_id": "c4",
            "statement_redacted": "Q",
            "review_tier": 1,
            "review_tier_reason_code": "T1_DETERMINISTIC_SOURCE_BACKED",
        },
    ]
    accepted = [{"statement_redacted": "A"}]
    superseded = [{"statement_redacted": "B"}]
    ev = evaluate_memory_candidates(candidates, accepted, superseded)
    assert ev["reviewed_count"] == 4
    assert ev["flagged_count"] == 3  # A=dup, B=stale, Z=conflict; Q clean
    assert ev["per_category"] == {"duplicate": 1, "stale": 1, "conflicting": 1}
    assert ev["status"] == "flagged"
    for rec in ev["flag_records"]:
        assert "statement_redacted" not in rec  # only hashed
        assert len(rec["statement_hash"]) == 48


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise MemoryQualityReviewError("contract unavailable")

    monkeypatch.setattr(qr, "load_memory_quality_review_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        with pytest.raises(MemoryQualityReviewError):
            build_memory_quality_review(db)
        assert _run_rows(db) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(MemoryQualityReviewError):
            build_memory_quality_review(str(db))


def test_unsafe_source_hashed_and_stale_flagged() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        result = build_memory_quality_review(db)
        assert result["status"] == "flagged"
        assert (
            result["per_category"]["stale"] >= 1
        )  # the superseded-restating candidate is flagged stale
        blob = json.dumps(result, default=str)
        assert "statement_redacted" not in blob
        assert "Project Alpha" not in blob and "Project Beta" not in blob
        assert not _SECRET_OR_URL.search(blob)


def test_no_raw_no_writeback_and_run_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        before = _run_rows(db)
        result = build_memory_quality_review(db)
        assert _run_rows(db) == before  # read-only default persists nothing
        assert result["read_only"] is True
        assert result["makes_determination"] is False
        assert result["merges_or_deletes_or_accepts"] is False

        result2 = build_memory_quality_review(db, emit_receipt=True)
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_TABLE})")]
            guard_cols = [
                g
                for g in cols
                if g.endswith(("_persisted", "_performed")) or g.endswith("_bypassed_policy")
            ]
            gsum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_TABLE}"
            ).fetchone()[0]
            assert gsum == 0
        finally:
            conn.close()
        assert n == 1


def test_proof_passes_and_is_clean() -> None:
    proof = build_memory_quality_review_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["flagged_count"] == 3
    assert proof["duplicate_detected"] is True
    assert proof["stale_detected"] is True
    assert proof["conflicting_detected"] is True
    assert proof["makes_determination"] is False
    assert proof["run_row_guard_clean"] is True
    assert proof["read_only_default_no_persist"] is True
    assert proof["no_raw_statement_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_memory_quality_review_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "memory-quality-review-proof.json"
    pm = tmp_path / "memory-quality-review-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
