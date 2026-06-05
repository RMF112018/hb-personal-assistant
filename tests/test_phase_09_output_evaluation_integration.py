"""Phase 09 Prompt 23 — output evaluation integration (semantic outputs → evaluation + checks).

Proves the five required paths: (1) normal — semantic outputs route through the A05 evaluation +
unsupported-claim check + source-linked proof, overall passing without synthesizing an answer;
(2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source —
an item lacking a source ref / an excluded family is detected as an unsupported/unlinked claim (and an
excluded-family filter fails closed); (5) no-raw / no-writeback — the summary carries no raw query/answer/
excerpt and persists nothing by default; the persisted receipts are metadata-only + guard-clean. Plus the
proof. The real-HF smoke is an `integration` test.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval.hybrid_broker import _mock_embed_model
from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
    MetadataFilter,
    MetadataFilterError,
)
from hb_assistant.construction.second_brain.retrieval.models import RetrievalItem
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
)
from hb_assistant.construction.second_brain.synthesis import semantic_output_evaluation as soe
from hb_assistant.construction.second_brain.synthesis.semantic_output_evaluation import (
    SemanticOutputEvaluationError,
    _source_linked_proof,
    _unsupported_claim_check,
    build_semantic_output_evaluation,
    build_semantic_output_evaluation_proof,
)

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_SL = "second_brain_retrieval_source_linked_proof_runs"
_CC = "second_brain_retrieval_unsupported_claim_checks"


def _applied_db(td: str) -> tuple[str, str]:
    db = _proof_db(td)
    persist_root = str(Path(td) / "vs")
    build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
    return db, persist_root


def _counts(db: str) -> tuple[int, int]:
    conn = sqlite3.connect(db)
    try:
        sl = conn.execute(f"SELECT COUNT(*) FROM {_SL}").fetchone()[0]
        cc = conn.execute(f"SELECT COUNT(*) FROM {_CC}").fetchone()[0]
    finally:
        conn.close()
    return sl, cc


def test_normal_routes_through_evaluation() -> None:
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        result = build_semantic_output_evaluation(
            "project summary status",
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        assert result["status"] == "ok"
        assert result["route"] == "evaluation_only"
        assert result["synthesis_performed"] is False
        assert result["assembles_final_answer"] is False
        assert result["evaluation"]["passed"] is True
        assert result["unsupported_claim_check"]["unsupported_count"] == 0
        assert result["source_linked_proof"]["unlinked_count"] == 0
        assert result["overall_passed"] is True
        assert "answer" not in result and "answer_redacted" not in result
        assert _counts(db) == (0, 0)  # read-only default persists nothing


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise SemanticOutputEvaluationError("contract unavailable")

    monkeypatch.setattr(soe, "load_output_evaluation_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        with pytest.raises(SemanticOutputEvaluationError):
            build_semantic_output_evaluation(
                "q", db_path=db, embed_model=_mock_embed_model(), persist_root=persist_root
            )
        assert _counts(db) == (0, 0)


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(SemanticOutputEvaluationError):
            build_semantic_output_evaluation("q", db_path=str(db), mode="deterministic_only")


def test_unsafe_source_detected_and_excluded_family_fail_closed() -> None:
    # Unsupported/unlinked detection over synthetic items.
    items = [
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="ok",
            record_type="issue",
            record_ref="ok",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="",  # missing source ref -> unsupported / unlinked
            record_type="issue",
            record_ref="x",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
        ),
    ]
    assert _unsupported_claim_check(items)["unsupported_count"] == 1
    assert _source_linked_proof(items)["unlinked_count"] == 1

    # An excluded-family filter fails closed (excluded families never queried).
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        with pytest.raises(MetadataFilterError):
            build_semantic_output_evaluation(
                "q",
                db_path=db,
                mode="hybrid",
                embed_model=_mock_embed_model(),
                persist_root=persist_root,
                metadata_filter=MetadataFilter(source_families=("raw_email_body",)),
            )


def test_no_raw_no_writeback_and_receipts_guard_clean() -> None:
    raw_query = "what is the latest status of the active project summary"
    with tempfile.TemporaryDirectory() as td:
        db, persist_root = _applied_db(td)
        # default run: no raw query / answer emitted; persists nothing
        result = build_semantic_output_evaluation(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
        )
        blob = json.dumps(result, default=str)
        assert raw_query not in blob
        assert "answer" not in result
        assert not _SECRET_OR_URL.search(blob)
        assert _counts(db) == (0, 0)

        # emit_receipt: both receipts persisted, metadata-only + guard-clean
        result2 = build_semantic_output_evaluation(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            emit_receipt=True,
        )
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            sl, cc = (
                conn.execute(f"SELECT COUNT(*) FROM {_SL}").fetchone()[0],
                conn.execute(f"SELECT COUNT(*) FROM {_CC}").fetchone()[0],
            )
            for table in (_SL, _CC):
                cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")]
                guard_cols = [
                    c
                    for c in cols
                    if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
                ]
                gsum = conn.execute(
                    f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {table}"
                ).fetchone()[0]
                assert gsum == 0
        finally:
            conn.close()
        assert sl >= 1 and cc >= 1


def test_proof_passes_and_is_clean() -> None:
    proof = build_semantic_output_evaluation_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["evaluation_passed"] is True
    assert proof["unsupported_count"] == 0
    assert proof["unlinked_count"] == 0
    assert proof["overall_passed"] is True
    assert proof["receipts_persisted_guard_clean"] is True
    assert proof["unsupported_claim_detected_and_blocked"] is True
    assert proof["no_answer_emitted"] is True
    assert proof["raw_query_not_emitted"] is True
    assert proof["excluded_family_fail_closed"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_semantic_output_evaluation_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "output-evaluation-integration-proof.json"
    pm = tmp_path / "output-evaluation-integration-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


@pytest.mark.integration
def test_output_eval_real_huggingface_smoke() -> None:
    """Real local semantic output evaluation via the configured HuggingFace model (downloads weights)."""
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, persist_root=persist_root)
        result = build_semantic_output_evaluation(
            "project summary", db_path=db, mode="hybrid", persist_root=persist_root
        )
        assert result["status"] == "ok"
        assert result["route"] == "evaluation_only"
        assert result["synthesis_performed"] is False
        assert result["overall_passed"] is True
