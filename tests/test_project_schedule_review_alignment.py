"""Phase 5 review workbench alignment tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_memo_service import ProjectScheduleMemoService
from hb_assistant.construction.analytics.project_schedule_narrative_qa import (
    validate_review_cue_text,
)
from hb_assistant.construction.analytics.project_schedule_review_cue_service import (
    NON_CAUSATION_CUE,
    ProjectScheduleReviewCueService,
)
from hb_assistant.construction.analytics.project_schedule_summary_service import ProjectScheduleSummaryService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)
from tests.schedule_project_test_helpers import (
    seed_named_schedule_udfs,
    seed_procore_ep_project,
    seed_schedule_quality_findings,
)
from tests.test_project_schedule_hub_api import _seed_comparable_versions
from tests.test_project_schedule_review_workbench import _operator, _seed_driver_chain, _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "review-alignment.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _seed_alignment_fixture(db: Path) -> None:
    _seed_comparable_versions(db)
    seed_named_schedule_udfs(
        db,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
    )
    seed_schedule_quality_findings(
        db,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
    )
    lineage_payload = {
        "merged_from_files_json": json.dumps(
            [
                {"filename": "primary.xer", "source_format": "primavera_xer"},
                {"filename": "companion.xml", "source_format": "primavera_pmxml"},
            ]
        ),
        "source_object_ids_json": json.dumps(
            [
                {"source_format": "primavera_xer", "source_object_id": "XER-1"},
                {"source_format": "primavera_pmxml", "source_object_id": "XML-1"},
            ]
        ),
        "field_lineage_json": json.dumps(
            [
                {
                    "field_name": "activity_name",
                    "source_format": "primavera_xer",
                    "canonical_value": "Driver Activity",
                }
            ]
        ),
    }
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET planned_finish='2026-06-28', finish_date='2026-06-28',
                actual_finish=NULL, total_float='2',
                raw_source_fields_json=?
            WHERE schedule_version_key='tropical|S1|2026-07-01' AND activity_id='A100'
            """,
            (json.dumps(lineage_payload),),
        )
        conn.execute(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key, to_schedule_version_key,
              activity_id, change_domain, change_type, field_name, day_delta, wbs_code
            ) VALUES (
              'diff-detail-align', 1, 'tropical', 'tropical|S1|2026-06-01', 'tropical|S1|2026-07-01',
              'A100', 'activity', 'changed', 'finish_date', 5, 'WBS-A'
            )
            """
        )
        conn.commit()

    ScheduleCpmImportObservabilityRepository(db_path=str(db)).upsert(
        import_id="imp-current",
        schedule_version_key="tropical|S1|2026-07-01",
        package_id="pkg-align",
        trigger_source="import_commit",
        canonical_input_activity_count=10,
        canonical_input_relationship_count=8,
        graph_node_count=10,
        graph_edge_count=8,
        status="success",
        started_at="2026-07-01T10:00:00Z",
        finished_at="2026-07-01T10:00:05Z",
        duration_ms=5000,
        cpm_run_id="cpm-align-1",
    )


def test_post_review_sync_accepts_comparison_basis(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    client = TestClient(create_app(db_path=str(db)))

    prior = client.post(
        "/api/projects/tropical/schedule/review-items?comparison_basis=prior_update",
        headers=_operator(),
    )
    baseline = client.post(
        "/api/projects/tropical/schedule/review-items?comparison_basis=baseline&as_of=2026-07-03",
        headers=_operator(),
    )

    assert prior.status_code == 200
    assert baseline.status_code == 200
    assert prior.json()["workbench"]["comparison_basis"] == "prior_update"
    assert baseline.json()["workbench"]["comparison_basis"] == "baseline"


def test_sync_and_list_respects_comparison_basis(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    prior = service.sync_review_workbench("tropical", as_of=date(2026, 7, 3), comparison_basis="prior_update")
    baseline = service.sync_review_workbench("tropical", as_of=date(2026, 7, 3), comparison_basis="baseline")
    assert prior["comparison_basis"] == "prior_update"
    assert prior.get("persisted") is True
    assert baseline["comparison_basis"] == "baseline"
    if baseline.get("available"):
        assert baseline.get("persisted") is False


def test_as_of_historical_review_context_uses_distinct_dates(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    historical = service.sync_review_workbench("tropical", as_of=date(2026, 6, 28))
    current = service.sync_review_workbench("tropical", as_of=date(2026, 7, 3))
    historical_evidence = (historical["items"][0]["evidence"] if historical.get("items") else {})
    current_evidence = (current["items"][0]["evidence"] if current.get("items") else {})
    if historical_evidence and current_evidence:
        assert historical_evidence["as_of"] == "2026-06-28"
        assert current_evidence["as_of"] == "2026-07-03"
        assert historical_evidence["schedule_data_date"] != current_evidence["as_of"]


def test_cue_evidence_includes_lineage_and_cpm_observability(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    context = ProjectScheduleSummaryService(db_path=str(db))._review_workbench_context(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert context is not None
    cues = ProjectScheduleReviewCueService(db_path=str(db)).collect_materializable_cues(
        project_key="tropical",
        schedule_version_key=context["schedule_version_key"],
        as_of_date=date(2026, 7, 3),
        driver_analysis=context["driver_analysis"],
        milestones=context["milestones"],
        remaining_health=context["remaining_health"],
        cpm_summary=context["cpm_summary"],
        change_impact=context["change_impact"],
        remaining_activities=context["remaining_activities"],
        baseline_summary=context["baseline_summary"],
    )
    activity_cues = [cue for cue in cues if cue.get("source_activity_id") == "A100"]
    assert activity_cues
    evidence = activity_cues[0]["evidence"]
    assert evidence["as_of"] == "2026-07-03"
    assert evidence["schedule_data_date"] == "2026-07-01"
    assert evidence["data_date"] == "2026-07-01"
    assert set(evidence.get("source_file_names") or []) == {"primary.xer", "companion.xml"}
    assert set(evidence.get("source_formats") or []) == {"primavera_xer", "primavera_pmxml"}
    assert evidence.get("technical_evidence_available") is True
    technical = evidence.get("technical_evidence") or {}
    assert technical.get("cpm_status") == "success"
    assert technical.get("import_id") == "imp-current"


def test_canonical_package_lineage_batch_matches_import_health_fixture(tmp_path: Path) -> None:
    from tests.test_schedule_import_health_foundation import _unified_zip_payload

    db = _fresh_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("unified-package.zip", _unified_zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={
            "import_id": preview.json()["import_id"],
            "project_key": "tropical",
            "confirm": True,
        },
    )
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]
    repo = ScheduleActivityRepository(db_path=str(db))
    sample = repo.list_activities(svk, limit=1)[0]["activity_id"]
    lineage = repo.get_activity_merge_lineage(schedule_version_key=svk, activity_id=sample)
    assert lineage is not None
    assert {row["filename"] for row in lineage["merged_from_files"]} == {"primary.xer", "companion.xml"}
    assert {row["source_format"] for row in lineage["source_object_ids"]} == {
        "primavera_xer",
        "primavera_pmxml",
    }


def test_validate_review_cue_text_flags_unsafe_wording() -> None:
    safe = validate_review_cue_text(
        {
            "item_title": "Review driver sequence",
            "cue_summary": "This is not a compensable delay determination.",
            "caveats": [NON_CAUSATION_CUE],
        }
    )
    unsafe = validate_review_cue_text(
        {
            "item_title": "Compensable delay confirmed",
            "cue_summary": "Owner-caused delay proved delay responsibility.",
            "recommended_review_action": "Claim impact accepted.",
        }
    )
    assert safe["passed"] is True
    assert unsafe["passed"] is False
    assert any(v["code"] == "forbidden_term" for v in unsafe["violations"])


def test_non_causation_cue_present_on_milestone_and_quality_cues(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    context = ProjectScheduleSummaryService(db_path=str(db))._review_workbench_context(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert context is not None
    cues = ProjectScheduleReviewCueService(db_path=str(db)).collect_materializable_cues(
        project_key="tropical",
        schedule_version_key=context["schedule_version_key"],
        as_of_date=date(2026, 7, 3),
        driver_analysis=context["driver_analysis"],
        milestones=context["milestones"],
        remaining_health=context["remaining_health"],
        cpm_summary=context["cpm_summary"],
        change_impact=context["change_impact"],
        remaining_activities=context["remaining_activities"],
        baseline_summary=context["baseline_summary"],
    )
    milestone = next((cue for cue in cues if cue["item_type"] == "milestone"), None)
    quality = next((cue for cue in cues if cue["item_type"] == "metric_quality_finding"), None)
    if milestone:
        assert NON_CAUSATION_CUE in milestone["evidence"].get("caveats", [])
    if quality:
        assert NON_CAUSATION_CUE in quality["evidence"].get("caveats", [])


def test_export_advisory_language_blocks_unsafe_memo() -> None:
    summary = {
        "project_key": "tropical",
        "project_display_name": "Tropical",
        "as_of_date": "2026-07-03",
        "schedule_story": {
            "headline": "Compensable delay confirmed.",
            "synopsis": "Bad wording.",
            "what_changed": "Changed.",
            "why_it_matters": "Matters.",
            "primary_change_driver": "Driver.",
        },
        "command_summary": {},
        "change_impact": {"available": False},
        "change_driver_analysis": {"available": False},
        "review_workbench": {"available": False},
    }
    export = ProjectScheduleMemoService().build_export(summary, export_format="markdown")
    assert export["available"] is False
    assert export["reason"] == "narrative_qa_failed"
    assert export["advisory_posture"] == "sequence_cues_not_causation"


def test_upstream_cues_include_as_of_and_provenance(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_alignment_fixture(db)
    workbench = ProjectScheduleSummaryService(db_path=str(db)).sync_review_workbench(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert workbench.get("items")
    for item in workbench.get("items") or []:
        evidence = item.get("evidence") or {}
        assert evidence.get("as_of") == "2026-07-03"
        assert "schedule_data_date" in evidence
        assert evidence.get("cue_category")
        assert evidence.get("recommended_review_action")
