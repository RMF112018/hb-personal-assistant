"""Phase 09 Prompt 21 — metadata filter enforcement (before + after retrieval, fail-closed).

Proves the five required paths: (1) normal — pre-filter constrains families/project and post-filter keeps
only items inside the project/family/date/tier/confidence envelope, with drop reasons + coverage warnings,
integrated into the hybrid broker; (2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a
pre-V38 store; (4) unsafe-source — an explicitly requested excluded family is rejected pre-filter;
(5) no-raw / no-writeback — the filtered summary carries no raw query/excerpt and persists nothing, with
review tier / confidence / source refs / freshness preserved. Plus date-window correctness (incl.
date-incapable families) and the proof. The real-HF filtered smoke is an `integration` test.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import metadata_filter as mf
from hb_assistant.construction.second_brain.retrieval.hybrid_broker import (
    HybridRetrievalError,
    _mock_embed_model,
    build_hybrid_retrieval,
)
from hb_assistant.construction.second_brain.retrieval.metadata_filter import (
    MetadataFilter,
    MetadataFilterError,
    apply_metadata_filter,
    build_metadata_filter_proof,
    load_metadata_filter_contract,
    normalize_filter,
)
from hb_assistant.construction.second_brain.retrieval.models import RetrievalItem
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    _mock_vector_writer,
    _proof_db,
    build_vector_index_apply,
)

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_HYBRID_RUNS = "second_brain_retrieval_hybrid_query_runs"


def _item(
    ref: str, family: str, *, project: str, tier: int, conf: str, recency: str
) -> RetrievalItem:
    return RetrievalItem(
        source_family=family,
        source_ref=ref,
        record_type="x",
        record_ref=ref,
        project_key=project,
        confidence_class=conf,
        review_tier=tier,
        review_status="auto_advisory" if tier == 1 else "review_required",
        review_required=tier == 3,
        recency=recency,
    )


def test_normal_pre_and_post_filter() -> None:
    contract = load_metadata_filter_contract()
    items = [
        _item(
            "a",
            "project_issue_history_items",
            project="P1",
            tier=1,
            conf="high",
            recency="2026-05-15T00:00:00Z",
        ),
        _item(
            "b",
            "project_issue_history_items",
            project="P1",
            tier=1,
            conf="high",
            recency="2024-01-01T00:00:00Z",
        ),  # out of window
        _item(
            "c",
            "project_risk_digest_items",
            project="P1",
            tier=3,
            conf="low",
            recency="2026-05-10T00:00:00Z",
        ),  # tier above max
        _item(
            "d",
            "project_issue_history_items",
            project="P2",
            tier=1,
            conf="high",
            recency="2026-05-15T00:00:00Z",
        ),  # project mismatch
    ]
    spec = MetadataFilter(
        project_key="P1",
        source_families=("project_issue_history_items", "project_risk_digest_items"),
        date_from="2026-01-01T00:00:00Z",
        date_to="2026-12-31T00:00:00Z",
        max_review_tier=2,
        min_confidence="high",
    )
    _proj, selected, notes = normalize_filter(spec, contract=contract)
    assert selected == ("project_issue_history_items", "project_risk_digest_items")
    kept, dropped, coverage = apply_metadata_filter(
        items, spec, contract=contract, selected_families=selected
    )
    assert {it.source_ref for it in kept} == {"a"}
    assert dropped.get("out_of_date_window") == 1
    assert dropped.get("review_tier_above_max") == 1
    assert dropped.get("project_mismatch") == 1
    # kept item preserves review tier + confidence + source ref + freshness
    k = kept[0]
    assert k.review_tier == 1 and k.confidence_class == "high" and k.source_ref == "a" and k.recency
    # the risk family yielded nothing -> source-coverage warning
    assert any(c == "no_results_for_family:project_risk_digest_items" for c in coverage)


def test_normal_integration_with_hybrid_broker() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
        result = build_hybrid_retrieval(
            "project summary status",
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            metadata_filter=MetadataFilter(max_review_tier=2),
        )
        assert result["status"] == "ok"
        assert result["filter_applied"] is True
        assert result["filter_summary"] is not None
        assert result["assembles_final_answer"] is False
        # every kept item respects the tier ceiling
        assert all(int(t) <= 2 for t, n in result["tier_distribution"].items() if n)


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise MetadataFilterError("metadata-filter contract unavailable")

    monkeypatch.setattr(mf, "load_metadata_filter_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        with pytest.raises(MetadataFilterError):
            build_hybrid_retrieval(
                "q", db_path=db, mode="hybrid", metadata_filter=MetadataFilter(max_review_tier=2)
            )


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(HybridRetrievalError):
            build_hybrid_retrieval(
                "q", db_path=str(db), mode="deterministic_only", metadata_filter=MetadataFilter()
            )


def test_unsafe_source_excluded_family_rejected() -> None:
    contract = load_metadata_filter_contract()
    with pytest.raises(MetadataFilterError):
        normalize_filter(MetadataFilter(source_families=("raw_email_body",)), contract=contract)
    # an unknown (non-allowlisted, non-excluded) family is dropped with a coverage note, not raised
    _p, eff, notes = normalize_filter(
        MetadataFilter(source_families=("project_issue_history_items", "not_a_family")),
        contract=contract,
    )
    assert eff == ("project_issue_history_items",)
    assert any(n.startswith("requested_family_not_allowlisted:") for n in notes)


def test_no_raw_no_writeback() -> None:
    raw_query = "what is the latest status of the active project summary"
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
        result = build_hybrid_retrieval(
            raw_query,
            db_path=db,
            mode="hybrid",
            embed_model=_mock_embed_model(),
            persist_root=persist_root,
            metadata_filter=MetadataFilter(project_key="P1", min_confidence="medium"),
        )
        blob = json.dumps(result, default=str)
        assert raw_query not in blob  # only query_hash is emitted
        assert not _SECRET_OR_URL.search(blob)
        # build_hybrid_retrieval persists nothing
        conn = sqlite3.connect(db)
        try:
            runs = conn.execute(f"SELECT COUNT(*) FROM {_HYBRID_RUNS}").fetchone()[0]
        finally:
            conn.close()
        assert runs == 0


def test_date_window_and_date_incapable_family() -> None:
    contract = load_metadata_filter_contract()
    items = [
        _item(
            "recent",
            "accepted_long_term_memory",
            project="P1",
            tier=1,
            conf="high",
            recency="2026-06-01T00:00:00Z",
        ),
        _item(
            "old",
            "accepted_long_term_memory",
            project="P1",
            tier=1,
            conf="high",
            recency="2020-01-01T00:00:00Z",
        ),
        _item(
            "rel",
            "cross_source_relationships",
            project="P1",
            tier=1,
            conf="deterministic",
            recency="rel-id-not-a-date",
        ),
    ]
    spec = MetadataFilter(date_from="2026-01-01T00:00:00Z")
    kept, dropped, coverage = apply_metadata_filter(
        items, spec, contract=contract, selected_families=None
    )
    refs = {it.source_ref for it in kept}
    assert "recent" in refs  # in window
    assert "old" not in refs  # out of window
    assert dropped.get("out_of_date_window") == 1
    # the date-incapable relationship family is kept, not silently dropped
    assert "rel" in refs
    assert any(c == "date_filter_not_applicable:cross_source_relationships" for c in coverage)


def test_min_confidence_floor() -> None:
    contract = load_metadata_filter_contract()
    items = [
        _item("hi", "project_issue_history_items", project="P1", tier=1, conf="high", recency=""),
        _item("lo", "project_issue_history_items", project="P1", tier=1, conf="low", recency=""),
        _item(
            "unk", "project_issue_history_items", project="P1", tier=1, conf="unknown", recency=""
        ),
    ]
    kept, dropped, _cov = apply_metadata_filter(
        items, MetadataFilter(min_confidence="medium"), contract=contract, selected_families=None
    )
    assert {it.source_ref for it in kept} == {"hi"}
    assert dropped.get("confidence_below_min") == 2


def test_proof_passes_and_is_clean() -> None:
    proof = build_metadata_filter_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["excluded_family_rejected_pre_filter"] is True
    assert proof["post_filter_drop_matrix_ok"] is True
    assert proof["date_incapable_family_noted"] is True
    assert proof["hybrid_integration_ok"] is True
    assert proof["raw_query_not_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_metadata_filter_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "metadata-filter-proof.json"
    pm = tmp_path / "metadata-filter-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())


@pytest.mark.integration
def test_filtered_hybrid_real_huggingface_smoke() -> None:
    """Real local filtered hybrid query via the configured HuggingFace model (downloads weights)."""
    with tempfile.TemporaryDirectory() as td:
        db = _proof_db(td)
        persist_root = str(Path(td) / "vs")
        build_vector_index_apply(db, persist_root=persist_root)
        result = build_hybrid_retrieval(
            "project summary",
            db_path=db,
            mode="hybrid",
            persist_root=persist_root,
            metadata_filter=MetadataFilter(max_review_tier=2),
        )
        assert result["status"] == "ok"
        assert result["filter_applied"] is True
        assert result["assembles_final_answer"] is False
