"""Phase 8C review cue workflow and workbench expansion tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_review_cue_service import (
    NON_CAUSATION_CUE,
    ProjectScheduleReviewCueService,
)
from hb_assistant.construction.analytics.project_schedule_review_service import ProjectScheduleReviewService
from hb_assistant.construction.analytics.project_schedule_summary_service import ProjectScheduleSummaryService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import REVIEW_WATCHING
from tests.schedule_project_test_helpers import (
    seed_named_schedule_udfs,
    seed_procore_ep_project,
    seed_schedule_quality_findings,
)
from tests.test_project_schedule_hub_api import _seed_comparable_versions
from tests.test_project_schedule_review_workbench import _operator, _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "phase8c.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _seed_phase8c_fixture(db: Path) -> None:
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
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET planned_finish='2026-06-28', finish_date='2026-06-28',
                actual_finish=NULL, total_float='2'
            WHERE schedule_version_key='tropical|S1|2026-07-01' AND activity_id='A100'
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key, to_schedule_version_key,
              activity_id, change_domain, change_type, field_name, day_delta, wbs_code
            ) VALUES (
              'diff-detail-8c', 1, 'tropical', 'tropical|S1|2026-06-01', 'tropical|S1|2026-07-01',
              'A100', 'activity', 'changed', 'finish_date', 5, 'WBS-A'
            )
            """
        )
        conn.commit()


def test_cue_service_lists_hub_and_metric_cues(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    summary = ProjectScheduleSummaryService(db_path=str(db)).build_summary("tropical", as_of=date(2026, 7, 3))
    context = ProjectScheduleSummaryService(db_path=str(db))._review_workbench_context(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert context is not None
    cues = ProjectScheduleReviewCueService(db_path=str(db)).collect_materializable_cues(
        project_key="tropical",
        schedule_version_key=context["schedule_version_key"],
        as_of_date=date(2026, 7, 3),
        driver_analysis=summary["change_driver_analysis"],
        milestones=summary["milestones"],
        remaining_health=summary["remaining_health"],
        cpm_summary=summary["computed_cpm"],
        change_impact=summary["change_impact"],
        remaining_activities=context["remaining_activities"],
        baseline_summary=context["baseline_summary"],
    )
    keys = {cue["stable_item_key"] for cue in cues}
    assert any(key.startswith("metric:quality_finding:") for key in keys)
    assert any(key.startswith("metric:should_have_finished:") for key in keys) or any(
        key.startswith("metric:delay_analysis:") for key in keys
    )


def test_cue_evidence_includes_non_causation_and_dimensions(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
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
    metric_cues = [cue for cue in cues if str(cue.get("source_metric_key", "")).startswith("should_have_finished")]
    if metric_cues:
        evidence = metric_cues[0]["evidence"]
        assert NON_CAUSATION_CUE in evidence.get("caveats", [])
        assert evidence.get("phase") == "Phase 1"
    quality = next(cue for cue in cues if cue["stable_item_key"].startswith("metric:quality_finding:"))
    assert quality["evidence"]["source_metric_key"] == "schedule_quality_findings"


def test_sync_materializes_metric_cues_without_duplicates(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    first = service.sync_review_workbench("tropical", as_of=date(2026, 7, 3))
    assert first["available"] is True
    first_count = first["summary"]["total_count"]
    first_keys = {item["stable_item_key"] for item in first["items"]}
    second = service.sync_review_workbench("tropical", as_of=date(2026, 7, 3))
    second_keys = {item["stable_item_key"] for item in second["items"]}
    assert len(second_keys) == len(first_keys)
    assert second["summary"]["total_count"] == first_count
    assert any(key.startswith("metric:") for key in second_keys)


def test_review_items_filters_and_detail_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    monkeypatch.setenv("HB_ASSISTANT_DB_PATH", str(db))
    app = create_app(db_path=str(db))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    sync = client.post("/api/projects/tropical/schedule/review-items?as_of=2026-07-03", headers=_operator())
    assert sync.status_code == 200

    all_items = client.get("/api/projects/tropical/schedule/review-items?as_of=2026-07-03", headers=_viewer())
    assert all_items.status_code == 200
    payload = all_items.json()
    assert payload["available"] is True
    assert payload["count"] >= 1

    driver_items = client.get(
        "/api/projects/tropical/schedule/review-items?as_of=2026-07-03&source_metric=schedule_quality_findings",
        headers=_viewer(),
    )
    assert driver_items.status_code == 200
    for item in driver_items.json()["items"]:
        assert item.get("source_metric_key") == "schedule_quality_findings"

    persisted = next(item for item in payload["items"] if item.get("review_item_id"))
    detail = client.get(
        f"/api/projects/tropical/schedule/review-items/{persisted['review_item_id']}",
        headers=_viewer(),
    )
    assert detail.status_code == 200
    assert detail.json()["item"]["review_item_id"] == persisted["review_item_id"]
    assert "events" in detail.json()

    events = client.get(
        f"/api/projects/tropical/schedule/review-items/{persisted['review_item_id']}/events",
        headers=_viewer(),
    )
    assert events.status_code == 200
    assert events.json()["count"] >= 1


def test_viewer_cannot_sync_or_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    monkeypatch.setenv("HB_ASSISTANT_DB_PATH", str(db))
    app = create_app(db_path=str(db))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    sync = client.post("/api/projects/tropical/schedule/review-items", headers=_viewer())
    assert sync.status_code == 403

    operator_sync = client.post("/api/projects/tropical/schedule/review-items", headers=_operator())
    assert operator_sync.status_code == 200
    item_id = operator_sync.json()["workbench"]["items"][0]["review_item_id"]
    patch = client.patch(
        f"/api/projects/tropical/schedule/review-items/{item_id}",
        headers=_viewer(),
        json={"review_status": "reviewed"},
    )
    assert patch.status_code == 403


def test_patch_and_missing_item_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    monkeypatch.setenv("HB_ASSISTANT_DB_PATH", str(db))
    app = create_app(db_path=str(db))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    missing = client.get("/api/projects/tropical/schedule/review-items/missing-id", headers=_viewer())
    assert missing.status_code == 404

    bad_patch = client.patch(
        "/api/projects/tropical/schedule/review-items/missing-id",
        headers=_operator(),
        json={"review_status": "reviewed"},
    )
    assert bad_patch.status_code == 404


def test_public_item_surfaces_cue_fields_and_lineage(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_phase8c_fixture(db)
    review = ProjectScheduleReviewService(db_path=str(db))
    context = ProjectScheduleSummaryService(db_path=str(db))._review_workbench_context(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert context is not None
    envelope = review.sync_and_list(**context)
    item = next(i for i in envelope["items"] if i.get("review_item_id"))
    assert item.get("source_metric_key")
    assert item.get("confidence")
    assert item.get("new_since_last_review") is True
    review.update_item(
        review_item_id=str(item["review_item_id"]),
        review_status=REVIEW_WATCHING,
        pm_notes="watching",
        reviewed_by_operator="operator",
    )
    events = review.list_item_events(review_item_id=str(item["review_item_id"]))
    assert events["count"] >= 2
