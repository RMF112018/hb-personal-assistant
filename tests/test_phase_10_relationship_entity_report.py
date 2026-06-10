"""Phase 10 — relationship/entity normalization report (read-only, deterministic, review-safe).

Proves the consolidated report groups V25 cross-source candidates into the right operator categories
(alias/project, relationships, likely-duplicate, needs-review, rejected) by stable enums, keeps
unreviewed inferences out of an accepted state, stays raw-free + source-linked, and that the
`relationship-candidates report` CLI verb works.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.relationship_entity_report import (
    build_relationship_entity_report,
    classify_relationship_candidate,
    render_relationship_entity_report_markdown,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


def _seed(store: ConstructionStore, cid: str, **kw) -> None:
    base = dict(
        candidate_id=cid, source_family="person", source_record_type="contact",
        source_record_ref=f"ent:{cid}:a", target_family="company", target_record_type="org",
        target_record_ref=f"ent:{cid}:b", relationship_type="related_to",
        confidence_score=0.8, confidence_class="strong_heuristic",
        source_reference_json=json.dumps(["srh-1", "srh-2"]), review_required=False,
        promotion_status="candidate", deterministic=True,
    )
    base.update(kw)
    store.upsert_cross_source_relationship_candidate(**base)


def test_classification_logic() -> None:
    assert classify_relationship_candidate(
        {"promotion_status": "rejected"}) == "rejected_not_actionable"
    assert classify_relationship_candidate(
        {"review_required": True}) == "low_confidence_needs_review"
    assert classify_relationship_candidate(
        {"confidence_class": "weak_heuristic"}) == "low_confidence_needs_review"
    assert classify_relationship_candidate(
        {"relationship_type": "email_project_match", "target_family": "project"}
    ) == "alias_project_matches"
    assert classify_relationship_candidate(
        {"relationship_type": "same_entity", "source_family": "person",
         "target_family": "person", "source_record_type": "contact",
         "target_record_type": "contact"}) == "likely_duplicate_entities"
    assert classify_relationship_candidate(
        {"relationship_type": "related_to", "source_family": "person",
         "target_family": "company"}) == "entity_relationships"


def test_report_groups_and_is_raw_free(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "r.db"))
    _seed(store, "rel1")  # entity relationship
    _seed(store, "proj1", target_family="project", target_record_type="project",
          target_record_ref="ent:proj1:b", relationship_type="email_project_match")
    _seed(store, "dup1", source_family="person", target_family="person",
          source_record_type="contact", target_record_type="contact",
          relationship_type="same_entity")
    _seed(store, "nr1", review_required=True, confidence_class="weak_heuristic",
          confidence_score=0.3, promotion_status="needs_review")
    _seed(store, "rej1", promotion_status="rejected")

    report = build_relationship_entity_report(store=store)
    g = report["groups"]
    assert report["counts"]["total"] == 5
    assert any(i["candidate_id"] == "proj1" for i in g["alias_project_matches"])
    assert any(i["candidate_id"] == "dup1" for i in g["likely_duplicate_entities"])
    assert any(i["candidate_id"] == "nr1" for i in g["low_confidence_needs_review"])
    assert any(i["candidate_id"] == "rej1" for i in g["rejected_not_actionable"])
    assert any(i["candidate_id"] == "rel1" for i in g["entity_relationships"])
    assert report["promotion_safety"]["ok"] is True

    md = render_relationship_entity_report_markdown(report)
    blob = json.dumps(report) + md
    for bad in ("Bearer ", "https://", "-----BEGIN", '"raw_body"', '"prompt"', "@"):
        assert bad not in blob
    assert report["guardrails"]["no_writeback"] is True
    assert report["guardrails"]["no_promotion"] is True


def test_empty_db_is_clean(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "r.db"))
    report = build_relationship_entity_report(store=store)
    assert report["ok"] is True
    assert report["counts"]["total"] == 0
    assert "_None._" in render_relationship_entity_report_markdown(report)


def test_cli_report_emits_json(tmp_path: Path) -> None:
    db = str(tmp_path / "r.db")
    store = ConstructionStore(db_path=db)
    _seed(store, "rel1")
    res = runner.invoke(app, ["second-brain", "relationship-candidates", "report", "--db", db,
                              "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["command"] == "second-brain relationship-candidates report"
    assert payload["counts"]["total"] == 1
    assert payload["guardrails"]["read_only"] is True
