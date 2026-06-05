"""Phase 09 Prompt 31 — memory consolidation preview.

Proves the five required paths: (1) normal — exact-duplicate accepted memory items cluster into one
review-only proposal (canonical keep + supersede members), singletons are not proposed; (2) missing-policy
— fail-closed; (3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source — the clusterer emits
only hashed memory refs/statements (never raw), and a singleton is never proposed; (5) no-raw /
no-writeback / never-auto-supersede — the read-only default persists nothing, the persisted proposals are
metadata-only + guard-clean (advisory_only=1), and long_term_memory_items is left byte-for-byte unchanged.
Plus the proof. The surface makes no determination and never auto-deletes/supersedes/merges memory.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.memory import consolidation_preview as cp
from hb_assistant.construction.second_brain.memory.consolidation_preview import (
    MemoryConsolidationPreviewError,
    _memory_items_fingerprint,
    _seed_proof_db,
    build_memory_consolidation_preview,
    build_memory_consolidation_preview_proof,
    cluster_consolidation_candidates,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_CANDIDATES = "second_brain_memory_consolidation_candidates"
_REVIEW_ITEMS = "second_brain_memory_consolidation_review_items"


def _rows(db: str, table: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def _seeded_db(td: str) -> str:
    db = str(Path(td) / "mcons.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_proof_db(db)
    return db


def test_normal_clusters_duplicates_into_one_proposal() -> None:
    items = [
        {
            "memory_id": "a",
            "memory_type": "fact",
            "statement_redacted": "X",
            "project_key": "P",
            "confidence_class": "high",
            "created_utc": "2026-01-01",
        },
        {
            "memory_id": "b",
            "memory_type": "fact",
            "statement_redacted": "X",
            "project_key": "P",
            "confidence_class": "high",
            "created_utc": "2026-01-02",
        },
        {
            "memory_id": "c",
            "memory_type": "fact",
            "statement_redacted": "Y",
            "project_key": "P",
            "confidence_class": "high",
            "created_utc": "2026-01-03",
        },
    ]
    cl = cluster_consolidation_candidates(items, min_cluster_size=2)
    assert cl["cluster_count"] == 1  # X duplicated; Y singleton not proposed
    assert cl["total_member_count"] == 2
    prop = cl["proposals"][0]
    roles = [m["role"] for m in prop["members"]]
    assert roles.count("keep_canonical") == 1 and roles.count("supersede") == 1
    # canonical is the oldest (memory_id 'a', created 2026-01-01)
    blob = json.dumps(cl, default=str)
    assert "memory_id" not in blob.replace("memory_id_hash", "")  # only hashed
    assert "statement_redacted" not in blob


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise MemoryConsolidationPreviewError("contract unavailable")

    monkeypatch.setattr(cp, "load_memory_consolidation_preview_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        with pytest.raises(MemoryConsolidationPreviewError):
            build_memory_consolidation_preview(db)
        assert _rows(db, _CANDIDATES) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(MemoryConsolidationPreviewError):
            build_memory_consolidation_preview(str(db))


def test_unsafe_source_hashed_and_singleton_not_proposed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        result = build_memory_consolidation_preview(db)
        assert result["status"] == "built"
        assert result["cluster_count"] == 1  # the duplicate pair only
        assert result["total_member_count"] == 2  # the singleton is not proposed
        blob = json.dumps(result, default=str)
        assert "statement_redacted" not in blob
        assert "Project Alpha" not in blob and "Project Beta" not in blob
        assert not _SECRET_OR_URL.search(blob)


def test_no_raw_no_writeback_and_never_auto_supersede() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        before_fp = _memory_items_fingerprint(db)
        before_cand = _rows(db, _CANDIDATES)
        result = build_memory_consolidation_preview(db)
        assert _rows(db, _CANDIDATES) == before_cand  # read-only default persists nothing
        assert result["read_only"] is True
        assert result["makes_determination"] is False
        assert result["auto_deletes_or_supersedes"] is False

        result2 = build_memory_consolidation_preview(db, emit_receipt=True)
        assert result2["receipt_emitted"] is True
        # long_term_memory_items is byte-for-byte unchanged (never auto-delete/supersede)
        assert _memory_items_fingerprint(db) == before_fp
        # proposals persisted guard-clean + advisory_only=1
        conn = sqlite3.connect(db)
        try:
            assert conn.execute(f"SELECT COUNT(*) FROM {_CANDIDATES}").fetchone()[0] == 1
            assert conn.execute(f"SELECT COUNT(*) FROM {_REVIEW_ITEMS}").fetchone()[0] == 2
            assert (
                conn.execute(
                    f"SELECT COALESCE(SUM(advisory_only),0) FROM {_REVIEW_ITEMS}"
                ).fetchone()[0]
                == 2
            )
            for table in (_CANDIDATES, _REVIEW_ITEMS):
                cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")]
                guard_cols = [
                    g
                    for g in cols
                    if g.endswith(("_persisted", "_performed")) or g.endswith("_bypassed_policy")
                ]
                gsum = conn.execute(
                    f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {table}"
                ).fetchone()[0]
                assert gsum == 0
        finally:
            conn.close()


def test_proof_passes_and_is_clean() -> None:
    proof = build_memory_consolidation_preview_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["cluster_count"] == 1
    assert proof["total_member_count"] == 2
    assert proof["candidates_persisted"] is True
    assert proof["review_items_persisted"] is True
    assert proof["rows_guard_clean"] is True
    assert proof["advisory_only_flag_set"] is True
    assert proof["long_term_memory_items_unchanged"] is True
    assert proof["singleton_not_proposed"] is True
    assert proof["makes_determination"] is False
    assert proof["read_only_default_no_persist"] is True
    assert proof["no_raw_statement_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_memory_consolidation_preview_proof(
        evidence_dir=str(tmp_path), write_evidence=True
    )
    pj = tmp_path / "memory-consolidation-preview-proof.json"
    pm = tmp_path / "memory-consolidation-preview-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
