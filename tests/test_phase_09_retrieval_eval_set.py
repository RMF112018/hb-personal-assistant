"""Phase 09 Prompt 24 — retrieval quality eval set (source-linked cases from approved outputs).

Proves the five required paths: (1) normal — source-linked eval cases are built from the approved
Obsidian + reviewed-memory corpus; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a
pre-V38 store; (4) unsafe-source — nodes without a source ref / an excluded family are excluded from the
cases (all-unsafe → empty set); (5) no-raw / no-writeback — the summary carries no raw source ref (only
hashes) and persists nothing by default; the persisted `eval_sets` + `eval_cases` rows are metadata-only +
guard-clean. Plus the proof. (No embeddings involved — the eval set is pure metadata enumeration.)
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import eval_set as es
from hb_assistant.construction.second_brain.retrieval.eval_set import (
    RetrievalEvalSetError,
    _build_cases,
    build_retrieval_eval_set,
    build_retrieval_eval_set_proof,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import _proof_db

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_SETS = "second_brain_retrieval_eval_sets"
_CASES = "second_brain_retrieval_eval_cases"


def _counts(db: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    try:
        s = conn.execute(f"SELECT COUNT(*) FROM {_SETS}").fetchone()[0]
        c = conn.execute(f"SELECT COUNT(*) FROM {_CASES}").fetchone()[0]
    finally:
        conn.close()
    return s, c


def test_normal_builds_source_linked_cases() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        result = build_retrieval_eval_set(db, name="t")
        assert result["status"] == "built"
        assert result["case_count"] >= 1
        for c in result["cases"]:
            assert c["expected_source_ref_hash"] and len(c["expected_source_ref_hash"]) == 48
            assert "source_ref" not in c  # hashed only, never the raw ref
        assert _counts(db) == (0, 0)  # read-only default persists nothing
        assert not _SECRET_OR_URL.search(json.dumps(result, default=str))


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise RetrievalEvalSetError("contract unavailable")

    monkeypatch.setattr(es, "load_retrieval_eval_set_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(RetrievalEvalSetError):
            build_retrieval_eval_set(db, name="t")
        assert _counts(db) == (0, 0)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(RetrievalEvalSetError):
            build_retrieval_eval_set(str(db), name="t")


def test_unsafe_source_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    # _build_cases skips a missing source ref and an excluded family.
    synthetic = [
        {
            "source_family": "accepted_long_term_memory",
            "source_ref": "m1",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "accepted_long_term_memory",
            "source_ref": "",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "raw_email_body",
            "source_ref": "x",
            "confidence_class": "high",
            "review_tier": 1,
        },
    ]
    assert len(_build_cases(synthetic, set_id="s")) == 1

    # All-unsafe approved corpus -> empty set, nothing persisted.
    def _gather(db_path: str | None, project_key: str | None) -> tuple[list[dict], dict]:
        return ([synthetic[2]], {"manifest_id": "asm_stub"})

    monkeypatch.setattr(es, "_gather_approved_nodes", _gather)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        result = build_retrieval_eval_set(db, name="t")
        assert result["status"] == "empty"
        assert result["case_count"] == 0
        assert _counts(db) == (0, 0)


def test_no_raw_no_writeback_and_receipts_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        # default build persists nothing; no raw source ref in summary
        result = build_retrieval_eval_set(db, name="approved_retrieval_eval")
        blob = json.dumps(result, default=str)
        assert "source_ref" not in blob.replace("source_ref_hash", "")  # only the hashed field
        assert not _SECRET_OR_URL.search(blob)
        assert _counts(db) == (0, 0)

        # emit_receipt: eval_sets + eval_cases persisted, metadata-only + guard-clean
        result2 = build_retrieval_eval_set(db, name="approved_retrieval_eval", emit_receipt=True)
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            s, c = (
                conn.execute(f"SELECT COUNT(*) FROM {_SETS}").fetchone()[0],
                conn.execute(f"SELECT COUNT(*) FROM {_CASES}").fetchone()[0],
            )
            for table in (_SETS, _CASES):
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
        assert s == 1 and c == result2["case_count"]


def test_proof_passes_and_is_clean() -> None:
    proof = build_retrieval_eval_set_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["case_count"] >= 1
    assert proof["cases_source_linked"] is True
    assert proof["set_persisted_guard_clean"] is True
    assert proof["cases_persisted_guard_clean"] is True
    assert proof["unsafe_node_excluded"] is True
    assert proof["no_raw_source_ref_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_retrieval_eval_set_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "retrieval-eval-set-proof.json"
    pm = tmp_path / "retrieval-eval-set-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
