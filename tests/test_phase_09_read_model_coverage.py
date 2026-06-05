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
    build_retrieval_coverage_layers,
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


def test_coverage_layers_distinguish_layers(tmp_path: Path) -> None:
    db = str(tmp_path / "cov.sqlite3")
    _seed_five_eligible_families(db)
    layers = build_retrieval_coverage_layers(db)
    # all 10 allowlisted families are now reader-backed; none deferred for lack of a reader
    assert len(layers["deterministic_reader_families"]) == 10
    assert layers["deferred_families_no_reader"] == []
    assert "approved_read_models" in layers["approved_manifest_categories"]
    assert layers["deferred_memory_substrate"] is True


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
    assert "coverage_layers" in result
