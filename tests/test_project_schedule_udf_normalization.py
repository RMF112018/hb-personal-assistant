"""Phase 8B UDF normalization and schedule-dimension tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
    ProjectScheduleTrendAggregationService,
)
from hb_assistant.construction.analytics.project_schedule_udf_normalization_service import (
    ALIAS_TO_INTERNAL,
    UDF_FIELD_ALIASES,
    ProjectScheduleUdfNormalizationService,
)
from hb_assistant.construction.analytics.project_schedule_visualization_metric_contract import (
    NON_CAUSATION_CAVEAT,
    ProjectScheduleVisualizationMetricContractService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_named_schedule_udfs, seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "udf-normalization.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _seed_udf_phase8b(db: Path) -> None:
    _seed_comparable_versions(db)
    seed_named_schedule_udfs(
        db,
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
    )
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET planned_start='2026-06-28', planned_finish='2026-06-30',
                start_date='2026-06-28', finish_date='2026-06-30',
                actual_start='2026-06-28', actual_finish=NULL
            WHERE schedule_version_key='tropical|S1|2026-07-01' AND activity_id='A100'
            """
        )
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET planned_start='2026-06-29', planned_finish='2026-07-02',
                start_date='2026-06-29', finish_date='2026-07-02',
                actual_start=NULL, actual_finish=NULL
            WHERE schedule_version_key='tropical|S1|2026-07-01' AND activity_id='A200'
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key, to_schedule_version_key,
              activity_id, change_domain, change_type, field_name, day_delta, wbs_code
            ) VALUES (
              'diff-detail-1', 1, 'tropical', 'tropical|S1|2026-06-01', 'tropical|S1|2026-07-01',
              'A100', 'activity', 'changed', 'finish_date', 5, 'WBS-A'
            )
            """
        )
        conn.commit()


def test_generic_udf_source_table_is_discovered(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "procore_ep_schedule_udf_values" in tables


def test_required_udf_names_are_inventoried(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    service = ProjectScheduleUdfNormalizationService(db_path=str(db))
    inventory = service.get_udf_name_inventory(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
    )
    names = {row["udf_type_name"] for row in inventory["udf_names"]}
    assert "PHASE" in names
    assert "Filter Out" in names
    assert inventory["total_rows"] > 0


def test_raw_udf_names_map_to_internal_keys() -> None:
    assert ALIAS_TO_INTERNAL["PHASE"] == "phase"
    assert ALIAS_TO_INTERNAL["Start (Previous Status)"] == "start_previous_status"
    assert ALIAS_TO_INTERNAL["Update Notes - 1"] == "update_notes_1"


def test_alias_behavior_is_deterministic(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    service = ProjectScheduleUdfNormalizationService(db_path=str(db))
    first = service.get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        activity_ids=["A100"],
    )
    second = service.get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        activity_ids=["A100"],
    )
    assert first["records"] == second["records"]
    assert first["records"][0]["phase"] == "Phase 1"
    assert first["records"][0]["start_previous_status"] == "Planned"


def test_udf_values_join_deterministically_to_activities(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    proof = ProjectScheduleUdfNormalizationService(db_path=str(db)).get_udf_join_proof(
        "tropical",
        "tropical|S1|2026-07-01",
    )
    assert proof["join_success_rate"] == 1.0
    assert proof["join_failure_count"] == 0
    assert proof["deterministic_join_proven"] is True


def test_join_failures_are_reported_not_hidden(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_udf_values (
              project_key, schedule_table_id, schedule_id, schedule_version_key,
              import_id, activity_id, udf_type_name, udf_data_type, udf_value
            ) VALUES (
              'tropical', 'S1', 'S1', 'tropical|S1|2026-07-01', 'imp-current',
              'MISSING-ACT', 'PHASE', 'Text', 'Orphan'
            )
            """
        )
        conn.commit()
    proof = ProjectScheduleUdfNormalizationService(db_path=str(db)).get_udf_join_proof(
        "tropical",
        "tropical|S1|2026-07-01",
    )
    assert proof["join_failure_count"] == 1
    assert proof["deterministic_join_proven"] is False
    assert proof["orphan_udf_examples"]


def test_null_sparsity_profile_is_reported(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    sparsity = ProjectScheduleUdfNormalizationService(db_path=str(db)).get_udf_sparsity_summary(
        "tropical",
        "tropical|S1|2026-07-01",
    )
    assert sparsity["activity_count"] == 3
    assert "phase" in sparsity["field_stats"]
    assert sparsity["field_stats"]["phase"]["non_null_count"] >= 1


def test_raw_udf_values_are_preserved(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    with sqlite3.connect(db) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
            ("tropical|S1|2026-07-01",),
        ).fetchone()[0]
    service = ProjectScheduleUdfNormalizationService(db_path=str(db))
    _ = service.get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
    )
    with sqlite3.connect(db) as conn:
        after = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
            ("tropical|S1|2026-07-01",),
        ).fetchone()[0]
    assert before == after
    record = service.get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        activity_ids=["A100"],
    )["records"][0]
    assert any(src["udf_type_name"] == "PHASE" for src in record["raw_udf_sources"])


def test_filter_out_parsed_safely_and_not_assumed_if_ambiguous(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    service = ProjectScheduleUdfNormalizationService(db_path=str(db))
    records = service.get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
    )["records"]
    by_id = {rec["activity_id"]: rec for rec in records}
    assert by_id["A100"]["filter_out_parsed"] is False
    assert by_id["A300"]["filter_out_parsed"] is None
    assert any("filter_out value not safely parsed" in note for note in by_id["A300"]["alias_notes"])


def test_old_id_supports_cross_version_matching_only_when_stable(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    records = ProjectScheduleUdfNormalizationService(db_path=str(db)).get_normalized_activity_dimensions(
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
    )["records"]
    assert all(rec["old_id"] == "OLD-100" for rec in records if rec["activity_id"] in {"A100", "A200", "A300"})


def test_udf_dependent_metrics_do_not_become_available_without_support(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleUdfNormalizationService(db_path=str(db))
    payload = service.build_metric_payload(
        metric_key="delay_analysis",
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        as_of_date=date(2026, 7, 3),
    )
    assert payload["available"] is False
    assert payload["reason"] == "prior_update_diff_unavailable"


def test_window_start_accuracy_payload_when_support_exists(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    payload = ProjectScheduleTrendAggregationService(db_path=str(db)).build_trend(
        "tropical",
        "window_start_accuracy",
        as_of=date(2026, 7, 3),
    )
    assert "available" in payload
    if payload["available"]:
        point = payload["points"][0]
        assert {"on_time_count", "late_count", "did_not_start_count"} <= set(point)


def test_window_finish_accuracy_readiness(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    payload = ProjectScheduleUdfNormalizationService(db_path=str(db)).build_metric_payload(
        metric_key="window_finish_accuracy",
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        as_of_date=date(2026, 7, 3),
    )
    assert "available" in payload
    assert "partial_dimension_support" in payload


def test_should_have_finished_status_returns_backend_categories(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    payload = ProjectScheduleUdfNormalizationService(db_path=str(db)).build_metric_payload(
        metric_key="should_have_finished_status",
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        as_of_date=date(2026, 7, 10),
    )
    if payload["available"]:
        statuses = {point["status"] for point in payload["points"]}
        assert statuses <= {"on_track", "at_risk", "delayed"}


def test_delay_analysis_remains_caveated_without_causation(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    payload = ProjectScheduleUdfNormalizationService(db_path=str(db)).build_metric_payload(
        metric_key="delay_analysis",
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        as_of_date=date(2026, 7, 3),
    )
    assert NON_CAUSATION_CAVEAT in payload.get("caveats", [])
    assert payload.get("summary", {}).get("review_cue_only") is True
    assert "candidate_driver" in str(payload["points"][0] if payload.get("points") else {})


def test_critical_issues_category_model_does_not_infer_responsibility(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    payload = ProjectScheduleUdfNormalizationService(db_path=str(db)).build_metric_payload(
        metric_key="critical_issues_category_model",
        project_key="tropical",
        version_key="tropical|S1|2026-07-01",
        as_of_date=date(2026, 7, 3),
    )
    assert NON_CAUSATION_CAVEAT in payload.get("caveats", [])
    assert payload["summary"]["review_item_eligible"] is False
    assert len(payload["points"]) == 5


def test_contract_reports_stable_named_udf_normalization_proven(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    summary = ProjectScheduleVisualizationMetricContractService(db_path=str(db)).udf_availability_summary()
    assert summary["stable_named_udf_normalization_proven"] is True
    assert summary["normalization_approach"] == "read_through_service"
    assert "internal_field_aliases" in summary


def test_trend_api_returns_structured_udf_metric_payload(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_udf_phase8b(db)
    client = TestClient(create_app(db_path=str(db)))
    response = client.get(
        "/api/projects/tropical/schedule/metrics/window_start_accuracy/trend?as_of=2026-07-03",
        headers={"X-HB-UI-Role": "viewer"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metric_key"] == "window_start_accuracy"
    assert "available" in body


def test_internal_field_alias_registry_matches_spec() -> None:
    assert set(UDF_FIELD_ALIASES) == {
        "old_id",
        "phase",
        "floor",
        "sector_area",
        "subcontractor",
        "cost_code",
        "filter_out",
        "start_previous_status",
        "finish_previous_status",
        "update_notes_1",
        "update_notes_2",
        "update_notes",
        "schedule_review_comments",
    }
