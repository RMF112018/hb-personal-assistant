"""Phase 09 Prompt 25 — deterministic vs semantic benchmark.

Proves the five required paths: (1) normal — all three retrieval modes (deterministic, semantic,
hybrid) are compared over the approved corpus + applied index, emitting bucketed comparative metrics;
(2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source —
nodes without a source ref / redacted excerpt / an excluded family are excluded from the probe set
(all-unsafe → empty); (5) no-raw / no-writeback — the summary carries no raw probe/query/content/source
ref and persists nothing by default; the persisted `benchmark_runs` rows are metadata-only + guard-clean.
Plus the proof (incl. the fail-closed blocked-semantic path).
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import benchmark as bm
from hb_assistant.construction.second_brain.retrieval.benchmark import (
    RetrievalBenchmarkError,
    _build_probes,
    build_retrieval_benchmark,
    build_retrieval_benchmark_proof,
)
from hb_assistant.construction.second_brain.retrieval.hybrid_broker import _mock_embed_model
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
    """A proof DB with an applied vector index — semantic retrieval is available."""
    db = _proof_db(td)
    persist_root = str(Path(td) / "vector_store")
    build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
    return db, persist_root


def test_normal_compares_three_modes() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_retrieval_benchmark(
            db, name="t", embed_model=_mock_embed_model(), persist_root=persist_root
        )
        assert result["status"] == "built"
        assert result["assembles_final_answer"] is False
        mm = result["mode_metrics"]
        assert set(mm) == {"deterministic", "semantic", "hybrid"}
        assert result["metric_row_count"] == 7
        assert mm["semantic"]["status"] == "available"
        assert mm["semantic"]["min_review_tier"] == 2
        # read-only default persists nothing
        assert _rows(db) == 0
        blob = json.dumps(result, default=str)
        assert "probe_text" not in blob and "text_redacted" not in blob
        assert not _SECRET_OR_URL.search(blob)


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise RetrievalBenchmarkError("contract unavailable")

    monkeypatch.setattr(bm, "load_retrieval_benchmark_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(RetrievalBenchmarkError):
            build_retrieval_benchmark(db, name="t")
        assert _rows(db) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(RetrievalBenchmarkError):
            build_retrieval_benchmark(str(db), name="t")


def test_unsafe_source_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    # _build_probes skips a missing source ref, a missing excerpt, and an excluded family.
    synthetic = [
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "ok",
            "text_redacted": "Project Alpha summary",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "",
            "text_redacted": "no ref",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "noexcerpt",
            "text_redacted": "",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "raw_email_body",
            "source_ref": "x",
            "text_redacted": "excluded family",
            "confidence_class": "high",
            "review_tier": 1,
        },
    ]
    assert len(_build_probes(synthetic)) == 1

    # All-unsafe approved corpus -> empty benchmark, nothing persisted.
    def _gather(db_path: str | None, project_key: str | None) -> tuple[list[dict], dict]:
        return ([synthetic[3]], {"manifest_id": "asm_stub"})

    monkeypatch.setattr(bm, "_gather_approved_nodes", _gather)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        result = build_retrieval_benchmark(db, name="t")
        assert result["status"] == "empty"
        assert result["probe_count"] == 0
        assert result["mode_metrics"] is None
        assert "no_approved_outputs" in result["warnings"]
        assert _rows(db) == 0


def test_no_raw_no_writeback_and_receipts_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        embed = _mock_embed_model()
        # default build persists nothing; no raw probe/source ref in the summary
        result = build_retrieval_benchmark(
            db, name="approved_retrieval_benchmark", embed_model=embed, persist_root=persist_root
        )
        blob = json.dumps(result, default=str)
        assert "probe_text" not in blob and "text_redacted" not in blob
        assert "source_ref" not in blob.replace("source_ref_hash", "")
        assert not _SECRET_OR_URL.search(blob)
        assert _rows(db) == 0

        # emit_receipt: benchmark_runs rows persisted, metadata-only + guard-clean
        result2 = build_retrieval_benchmark(
            db,
            name="approved_retrieval_benchmark",
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
        assert n == result2["metric_row_count"] == 7


def test_proof_passes_and_is_clean() -> None:
    proof = build_retrieval_benchmark_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["all_three_modes_compared"] is True
    assert proof["semantic_available"] is True
    assert proof["semantic_floored_tier_2"] is True
    assert proof["assembles_final_answer"] is False
    assert proof["rows_persisted_guard_clean"] is True
    assert proof["semantic_retrieval_bypassed_policy"] == 0
    assert proof["no_raw_emitted"] is True
    assert proof["semantic_blocked_path_status"] == "blocked"
    assert proof["unsafe_node_excluded"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_retrieval_benchmark_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "retrieval-benchmark-proof.json"
    pm = tmp_path / "retrieval-benchmark-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
