"""Phase 09 — approved-family retrieval coverage expansion.

Covers the new deterministic readers (generated_outputs / meeting_prep_brief_sections /
review_controlled_correspondence_context), the read-model → safe vector-node loader, the
``approved_read_models`` manifest category, the vector dry-run reaching >=5 indexed families when
eligible rows exist, and the coverage-layer distinction. All read-only / metadata-only; the eligibility
filter keeps review-required / tier-3 items out of the index.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.corpus_balance_mart import (
    build_coverage_parity_report,
)
from hb_assistant.construction.second_brain.retrieval.embedding_policy import (
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from hb_assistant.construction.second_brain.retrieval.read_model_loader import (
    iter_approved_read_model_items,
    load_approved_read_model_nodes,
    read_model_loader_families,
)
from hb_assistant.construction.second_brain.retrieval.readers import READER_REGISTRY
from hb_assistant.construction.second_brain.retrieval.source_manifest import (
    build_approved_source_manifest,
)
from hb_assistant.construction.second_brain.retrieval.vector_index import (
    build_vector_index_dry_run,
)
from hb_assistant.construction.store import ConstructionStore

_REF = json.dumps({"project_key": "P1"})

_THREE_NEW_FAMILIES = (
    "generated_outputs",
    "meeting_prep_brief_sections",
    "review_controlled_correspondence_context",
)


def _seed_five_eligible_families(db: str) -> ConstructionStore:
    """Seed 5 embeddable read-model families with eligible (non-review-required, tier<=2) rows."""
    store = ConstructionStore(db)
    # 1) cross-source relationship (deterministic -> tier 1)
    store.upsert_cross_source_relationship(
        relationship_id="rel-0",
        source_family="document",
        source_record_type="document",
        source_record_ref="doc-0",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-0",
        relationship_type="document_record_reference",
        confidence_class="deterministic",
        source_reference_json=_REF,
        project_key="P1",
    )
    # 2) source evidence trail (high -> tier 1)
    store.upsert_source_evidence_trail(
        evidence_trail_id="et-0",
        evidence_kind="document_relationship",
        source_refs_json=json.dumps(["r0"]),
        confidence_class="high",
        project_key="P1",
    )
    # 3) project issue history (high, not review-required -> tier 1)
    store.upsert_project_issue_history_item(
        issue_family_id="iss-0",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="high",
        issue_kind="rfi",
        age_days=10,
        review_required=False,
    )
    # 4) project risk digest (high -> tier 1)
    store.upsert_project_risk_digest_item(
        risk_digest_id="risk-0",
        project_key="P1",
        risk_indicator_type="schedule_slip",
        risk_source_class="source_stated",
        summary_redacted="schedule slip x2",
        confidence_class="high",
        review_required=False,
    )
    # 5) aging/exposure report (high -> tier 1)
    store.upsert_aging_exposure_report_item(
        aging_item_id="age-0",
        project_key="P1",
        record_family="procore",
        record_ref="rfi-0",
        status="open",
        threshold_band="aging_30_60",
        age_days=45,
        confidence_class="high",
        review_required=False,
    )
    return store


def test_three_families_registered() -> None:
    for fam in _THREE_NEW_FAMILIES:
        assert fam in READER_REGISTRY


def test_read_model_loader_families_excludes_dedicated_loaders() -> None:
    fams = set(read_model_loader_families())
    # the dedicated-loader families are NOT bridged here (they have their own node loaders)
    assert "approved_obsidian_generated_outputs" not in fams
    assert "accepted_long_term_memory" not in fams
    assert "generated_outputs" not in fams
    # the embeddable deterministic families are bridged
    assert {
        "phase_07d_source_evidence_trails",
        "project_issue_history_items",
        "project_risk_digest_items",
        "aging_exposure_report_items",
        "cross_source_relationships",
    } <= fams


def test_loader_nodes_cover_five_plus_families_and_validate(tmp_path: Path) -> None:
    db = str(tmp_path / "rm.sqlite3")
    _seed_five_eligible_families(db)
    nodes = load_approved_read_model_nodes(db)
    families = {n["source_family"] for n in nodes}
    assert len(families) >= 5
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    for node in nodes:
        # every bridged node is non-review-required, tier <= 2, and passes the no-raw embed guard
        assert node["review_required"] is False
        assert node["review_tier"] <= 2
        assert node["text_redacted"]
        assert validate_embedding_candidate(node, contract=contract, seed=seed) == []


def test_eligibility_excludes_review_required_and_tier3(tmp_path: Path) -> None:
    db = str(tmp_path / "rm2.sqlite3")
    store = _seed_five_eligible_families(db)
    # a review-required (tier-3) issue must never be bridged into the index
    store.upsert_project_issue_history_item(
        issue_family_id="iss-review",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="low",
        issue_kind="rfi",
        age_days=99,
        review_required=True,
    )
    items = iter_approved_read_model_items(db, None)
    assert all(it.review_required is False and it.review_tier <= 2 for it in items)
    assert not any(it.source_ref == "iss-review" for it in items)


def test_meeting_prep_reader_unscoped(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.retrieval.readers import (
        read_meeting_prep_brief_sections,
    )

    db = str(tmp_path / "mp.sqlite3")
    store = ConstructionStore(db)
    store.upsert_meeting_prep_brief_run(
        brief_run_id="mpr-1",
        project_key="P1",
        mode="apply",
        lookahead_days=7,
        status="assembled",
    )
    store.upsert_meeting_prep_brief_section(
        section_id="sec-1",
        brief_run_id="mpr-1",
        section_kind="open_items",
        section_redacted="3 open RFIs",
        confidence_class="high",
        review_required=False,
    )
    items = read_meeting_prep_brief_sections(store, db, None)
    assert any(it.source_ref == "sec-1" for it in items)
    assert all(it.source_family == "meeting_prep_brief_sections" for it in items)
    # project-scoped path returns nothing (table is not project-scoped)
    assert read_meeting_prep_brief_sections(store, db, "P1") == []


def test_approved_read_models_manifest_category(tmp_path: Path) -> None:
    db = str(tmp_path / "man.sqlite3")
    _seed_five_eligible_families(db)
    manifest = build_approved_source_manifest(db_path=db)
    assert "approved_read_models" in manifest["families"]
    assert manifest["families"]["approved_read_models"]["approved_count"] >= 5
    assert manifest["approved_ref_count"] >= 5
    assert manifest["status"] == "approved"


def test_vector_dry_run_reports_five_plus_families(tmp_path: Path) -> None:
    db = str(tmp_path / "vidx.sqlite3")
    _seed_five_eligible_families(db)
    plan = build_vector_index_dry_run(db)
    assert len(plan["per_family_node_count"]) >= 5
    assert plan["read_model_family_count"] >= 5
    assert plan["total_nodes"] >= 5
    assert plan["vectors_persisted_to_sqlite"] is False


def test_coverage_parity_report_exact_fields(tmp_path: Path) -> None:
    db = str(tmp_path / "cov.sqlite3")
    _seed_five_eligible_families(db)
    rep = build_coverage_parity_report(db)
    # exact objective field set is present
    for field in (
        "deterministic_allowlisted_family_count",
        "deterministic_reader_family_count",
        "missing_reader_families",
        "approved_manifest_family_count",
        "approved_manifest_families",
        "vector_indexed_family_count",
        "vector_indexed_families",
        "empty_approved_families",
        "deferred_families",
        "coverage_parity_ok",
    ):
        assert field in rep
    # all 10 allowlisted families are reader-backed -> parity holds
    assert rep["deterministic_allowlisted_family_count"] == 10
    assert rep["deterministic_reader_family_count"] == 10
    assert rep["missing_reader_families"] == []
    assert rep["coverage_parity_ok"] is True
    assert "approved_read_models" in rep["approved_manifest_categories"]
    # the read-model families are admitted by the manifest
    assert {"phase_07d_source_evidence_trails", "cross_source_relationships"} <= set(
        rep["approved_manifest_families"]
    )


def test_source_linked_proof_has_no_no_read_model_warnings(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.retrieval.source_linked_proof import (
        build_source_linked_retrieval_proof,
    )

    db = str(tmp_path / "slp.sqlite3")
    _seed_five_eligible_families(db)
    result = build_source_linked_retrieval_proof(db, mode="deterministic_only")
    for fam in _THREE_NEW_FAMILIES:
        assert not any(
            w.startswith(f"no_read_model:{fam}") for w in result["coverage_warnings"]
        )
    assert "coverage_parity" in result
    assert result["coverage_parity"]["coverage_parity_ok"] is True


# --- dedicated proof surfaces ------------------------------------------------------------------------

# Genuine raw-content / secret value shapes (NOT policy identifiers like the family name
# "raw_email_body", which legitimately appears in rejected-case reasons).
_RAW_TOKENS = ("Bearer ", "BEGIN ", "PRIVATE KEY", "access_token", "client_secret", "?sig=", "?token=")


def test_reader_registry_parity_proof_passes() -> None:
    from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
        build_reader_registry_parity_proof,
    )

    proof = build_reader_registry_parity_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["missing_reader_families"] == []
    assert proof["non_allowlisted_reader_families"] == []
    assert proof["deterministic_reader_family_count"] == proof["deterministic_allowlisted_family_count"]


def test_approved_read_model_manifest_proof_passes_and_rejects_unsafe(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.retrieval.source_manifest import (
        build_approved_read_model_manifest_proof,
    )

    proof = build_approved_read_model_manifest_proof(
        evidence_dir=str(tmp_path), write_evidence=True
    )
    assert proof["proof_passed"] is True
    assert proof["approved_read_models_category_present"] is True
    assert proof["approved_read_models_approved_count"] >= 5
    assert proof["manifest_row_metadata_only"] is True
    # every planted high-impact / review-required / excluded / raw-shape case is rejected
    by_name = {c["name"]: c for c in proof["cases"]}
    for name in ("review_required_unresolved", "tier_3_unaccepted", "excluded_family",
                 "forbidden_field", "raw_content_shape"):
        assert by_name[name]["passed"] is True
    # evidence artifacts are guard-clean
    text = (tmp_path / "approved-read-model-manifest-proof.json").read_text() + (
        tmp_path / "approved-read-model-manifest-proof.md"
    ).read_text()
    assert not any(t in text for t in _RAW_TOKENS)


def test_read_model_vector_loader_proof_passes(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.retrieval.read_model_loader import (
        build_read_model_vector_loader_proof,
    )

    proof = build_read_model_vector_loader_proof(evidence_dir=str(tmp_path), write_evidence=True)
    assert proof["proof_passed"] is True
    assert proof["indexed_family_count"] >= 5
    assert proof["review_required_high_impact_excluded"] is True
    assert proof["loader_persists_nothing_to_sqlite"] is True
    assert proof["rejects_raw_shape_candidate"] is True
    assert proof["rejects_excluded_family_candidate"] is True
    text = (tmp_path / "read-model-vector-loader-proof.json").read_text() + (
        tmp_path / "read-model-vector-loader-proof.md"
    ).read_text()
    assert not any(t in text for t in _RAW_TOKENS)


def test_coverage_parity_closeout_ok(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.retrieval.coverage_parity import (
        build_coverage_parity_closeout,
    )

    db = str(tmp_path / "closeout.sqlite3")
    _seed_five_eligible_families(db)
    closeout = build_coverage_parity_closeout(db, write_evidence=False)
    assert closeout["closeout_ok"] is True
    assert closeout["coverage_parity"]["coverage_parity_ok"] is True
    assert all(closeout["sub_proofs_passed"].values())
