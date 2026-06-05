"""Phase 09 Prompt 20 — hybrid retrieval broker (deterministic + advisory semantic, fail-closed).

Proves the five required paths: (1) normal — deterministic + advisory semantic results merge into one
source-linked envelope, persisting metadata-only guard-clean receipts; (2) missing-policy — fail-closed,
nothing persisted; (3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source — semantic nodes
that are excluded-family or fail the no-raw guard are dropped; (5) no-raw / no-writeback — persisted rows
carry no forbidden columns and all 23 guards stay 0, the raw query is never persisted (only its hash),
and the semantic path fails closed when the SDK is absent (deterministic still returned). Source-of-truth
discipline is asserted (`assembles_final_answer=false`, `semantic_retrieval_bypassed_policy=0`). The real
HuggingFace hybrid query is a separate `integration` smoke (excluded from the default-safe subset).
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import hybrid_broker
from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
    HybridRetrievalError,
    _mock_embed_model,
    build_hybrid_retrieval,
    build_hybrid_retrieval_proof,
    load_hybrid_retrieval_contract,
    persist_hybrid_query_record,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
)

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_RUNS = "second_brain_retrieval_hybrid_query_runs"
_RESULTS = "second_brain_retrieval_hybrid_query_results"


def _counts(db: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    try:
        runs = conn.execute(f"SELECT COUNT(*) FROM {_RUNS}").fetchone()[0]
        results = conn.execute(f"SELECT COUNT(*) FROM {_RESULTS}").fetchone()[0]
    finally:
        conn.close()
    return runs, results


def _applied_db(td: str) -> tuple[str, str]:
    """A proof DB with an applied vector index; returns (db_path, persist_root)."""
    db = _proof_db(td)
    persist_root = str(Path(td) / "vs")
    build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
    return db, persist_root


def test_normal_path_merges_deterministic_and_semantic() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_hybrid_retrieval(
            "project summary status",
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        assert result["status"] == "ok"
        assert result["deterministic_count"] >= 1
        assert result["semantic_count"] >= 1
        assert result["result_count"] == result["deterministic_count"] + result["semantic_count"]
        assert result["assembles_final_answer"] is False
        assert result["deterministic_authoritative"] is True
        # semantic results are advisory (never auto-tier-1) and source-linked
        assert "semantic_advisory_only" in result["coverage_warnings"]
        assert all(r["source_ref_hash"] for r in result["results"] if r["origin"] == "semantic")
        assert not _SECRET_OR_URL.search(json.dumps(result, default=str))

        run_id = persist_hybrid_query_record(
            db, result, policy_version=str(result["policy_version"])
        )
        runs, results = _counts(db)
        assert runs == 1
        assert results == result["result_count"]
        conn = sqlite3.connect(db)
        try:
            status = conn.execute(
                f"SELECT result_count, query_hash FROM {_RUNS} WHERE run_id = ?", (run_id,)
            ).fetchone()
        finally:
            conn.close()
        assert status[0] == result["result_count"]


def test_missing_policy_fail_closed_persists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise HybridRetrievalError("hybrid contract unavailable")

    monkeypatch.setattr(hybrid_broker, "load_hybrid_retrieval_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        with pytest.raises(HybridRetrievalError):
            build_hybrid_retrieval(
                "q", db_path=db, embed_model=_mock_embed_model(), persist_root=persist_root
            )
        assert _counts(db) == (0, 0)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(HybridRetrievalError):
            build_hybrid_retrieval("q", db_path=str(db), mode="deterministic_only")


def test_unsafe_source_semantic_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every semantic node resolves to an excluded (raw) family -> all dropped, none admitted.
    def _excluded_meta(db_path: str | None, item_id: str) -> dict:
        return {
            "source_family": "raw_email_body",
            "source_ref_hash": "h",
            "content_hash": "f" * 16,
            "confidence_class": "high",
            "freshness_label": "current",
        }

    monkeypatch.setattr(hybrid_broker, "_lookup_item_metadata", _excluded_meta)
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_hybrid_retrieval(
            "q",
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        assert result["semantic_count"] == 0
        assert result["deterministic_count"] >= 1
        assert all(r["source_family"] != "raw_email_body" for r in result["results"])


def test_no_raw_no_writeback_and_sdk_absent_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = load_hybrid_retrieval_contract()
    forbidden = set(contract["forbidden_persisted_fields"])
    raw_query = "what is the latest project status summary"
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_hybrid_retrieval(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        persist_hybrid_query_record(db, result, policy_version=str(result["policy_version"]))

        conn = sqlite3.connect(db)
        try:
            run_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RUNS})")}
            result_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RESULTS})")}
            guard_cols = [
                c
                for c in run_cols
                if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
            ]
            run_guard_sum = conn.execute(f"SELECT {'+'.join(guard_cols)} FROM {_RUNS}").fetchone()[
                0
            ]
            result_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_RESULTS}"
            ).fetchone()[0]
            bypass = conn.execute(
                f"SELECT semantic_retrieval_bypassed_policy FROM {_RUNS}"
            ).fetchone()[0]
            stored_query_hash = conn.execute(f"SELECT query_hash FROM {_RUNS}").fetchone()[0]
        finally:
            conn.close()

        assert not (forbidden & (run_cols | result_cols))
        assert run_guard_sum == 0
        assert result_guard_sum == 0
        assert bypass == 0
        assert raw_query not in stored_query_hash  # only the hash is persisted

    # SDK-absent: default writer + no SDK -> semantic skipped, deterministic still returned.
    monkeypatch.setattr(hybrid_broker, "_llama_index_core_available", lambda: False)
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_hybrid_retrieval(
            raw_query, db_path=db, mode="hybrid", persist_root=persist_root
        )
        assert result["semantic_count"] == 0
        assert result["semantic_skip_reason"] == "semantic_sdk_not_available"
        assert result["deterministic_count"] >= 1
        assert result["assembles_final_answer"] is False


def test_proof_passes_and_is_clean() -> None:
    proof = build_hybrid_retrieval_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["deterministic_count"] >= 1
    assert proof["semantic_count"] >= 1
    assert proof["assembles_final_answer"] is False
    assert proof["semantic_retrieval_bypassed_policy"] == 0
    assert proof["raw_query_not_persisted"] is True
    assert proof["run_record_guard_clean"] is True
    assert proof["result_records_guard_clean"] is True
    assert proof["no_applied_index_semantic_skipped"] is True
    assert proof["deterministic_only_mode_skips_semantic"] is True
    assert proof["unsafe_semantic_node_dropped"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_hybrid_retrieval_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "hybrid-retrieval-proof.json"
    pm = tmp_path / "hybrid-retrieval-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


@pytest.mark.integration
def test_hybrid_real_huggingface_query_smoke() -> None:
    """Real local hybrid query via the configured HuggingFace model (downloads weights; opt-in only)."""
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, persist_root=persist_root)  # real bge-small embed
        result = build_hybrid_retrieval(
            "project summary", db_path=db, mode="hybrid", persist_root=persist_root
        )
        assert result["status"] == "ok"
        assert result["semantic_count"] >= 1
        assert result["assembles_final_answer"] is False
