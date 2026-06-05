"""Phase 09 Prompt 26 — project-specific retrieval benchmarks + coverage reports.

Proves the five required paths: (1) normal — projects are enumerated from the approved corpus and each
carries a per-project benchmark (3 modes) + a coverage report; (2) missing-policy — fail-closed;
(3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source — excluded raw families never appear
in a project's coverage; (5) no-raw / no-writeback — the summary carries no raw probe/source ref and
persists nothing by default; per-project benchmark_runs rows are metadata-only + guard-clean. Plus the
proof. The `_proof_db` fixture vault carries project_key ALPHA/BETA, so projects enumerate.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import project_benchmark as pb
from hb_assistant.construction.second_brain.retrieval.hybrid_broker import _mock_embed_model
from hb_assistant.construction.second_brain.retrieval.policy import EXCLUDED_FAMILIES
from hb_assistant.construction.second_brain.retrieval.project_benchmark import (
    ProjectRetrievalBenchmarkError,
    build_project_retrieval_benchmarks,
    build_project_retrieval_benchmarks_proof,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
)

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_BENCH = "second_brain_retrieval_benchmark_runs"


def _rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_BENCH}").fetchone()[0])
    finally:
        conn.close()


def _applied_db(td: str) -> tuple[str, str]:
    db = _proof_db(td)
    persist_root = str(Path(td) / "vector_store")
    build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
    return db, persist_root


def test_normal_per_project_benchmark_and_coverage() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_project_retrieval_benchmarks(
            db, name="t", embed_model=_mock_embed_model(), persist_root=persist_root
        )
        assert result["status"] == "built"
        assert result["assembles_final_answer"] is False
        assert result["projects_count"] >= 1
        for entry in result["per_project"]:
            assert entry["project_key"]
            assert entry["benchmark"]["metric_row_count"] == 7
            cov = entry["coverage"]
            assert "covered_family_count" in cov and "coverage_complete" in cov
        # read-only default persists nothing
        assert _rows(db) == 0
        blob = json.dumps(result, default=str)
        assert "probe_text" not in blob and "text_redacted" not in blob
        assert not _SECRET_OR_URL.search(blob)


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise ProjectRetrievalBenchmarkError("contract unavailable")

    monkeypatch.setattr(pb, "load_project_retrieval_benchmark_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(ProjectRetrievalBenchmarkError):
            build_project_retrieval_benchmarks(db, name="t")
        assert _rows(db) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(ProjectRetrievalBenchmarkError):
            build_project_retrieval_benchmarks(str(db), name="t")


def test_unsafe_source_excluded_from_coverage() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_project_retrieval_benchmarks(
            db, name="t", embed_model=_mock_embed_model(), persist_root=persist_root
        )
        for entry in result["per_project"]:
            cov = entry["coverage"]
            listed = set(cov["covered_families"] + cov["empty_families"] + cov["deferred_families"])
            assert not (EXCLUDED_FAMILIES & listed)  # no raw family ever appears in coverage


def test_no_raw_no_writeback_and_receipts_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        embed = _mock_embed_model()
        # default build persists nothing; no raw probe/source ref in summary
        result = build_project_retrieval_benchmarks(
            db,
            name="approved_project_retrieval_benchmark",
            embed_model=embed,
            persist_root=persist_root,
        )
        blob = json.dumps(result, default=str)
        assert "probe_text" not in blob and "text_redacted" not in blob
        assert "source_ref" not in blob.replace("source_ref_hash", "")
        assert not _SECRET_OR_URL.search(blob)
        assert _rows(db) == 0

        # emit_receipt: per-project benchmark_runs rows persisted, metadata-only + guard-clean
        result2 = build_project_retrieval_benchmarks(
            db,
            name="approved_project_retrieval_benchmark",
            embed_model=embed,
            persist_root=persist_root,
            emit_receipt=True,
        )
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {_BENCH}").fetchone()[0]
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_BENCH})")]
            guard_cols = [
                g
                for g in cols
                if g.endswith(("_persisted", "_performed")) or g.endswith("_bypassed_policy")
            ]
            gsum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_BENCH}"
            ).fetchone()[0]
            assert gsum == 0
        finally:
            conn.close()
        # 7 metric rows per project
        assert n == result2["projects_count"] * 7 and n >= 7


def test_proof_passes_and_is_clean() -> None:
    proof = build_project_retrieval_benchmarks_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["projects_count"] >= 1
    assert proof["per_project_benchmarks_persisted"] is True
    assert proof["per_project_coverage_present"] is True
    assert proof["rows_persisted_guard_clean"] is True
    assert proof["semantic_retrieval_bypassed_policy"] == 0
    assert proof["assembles_final_answer"] is False
    assert proof["read_only_default_no_persist"] is True
    assert proof["no_raw_emitted"] is True
    assert proof["coverage_excludes_raw_families"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_project_retrieval_benchmarks_proof(
        evidence_dir=str(tmp_path), write_evidence=True
    )
    pj = tmp_path / "project-retrieval-benchmark-proof.json"
    pm = tmp_path / "project-retrieval-benchmark-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
