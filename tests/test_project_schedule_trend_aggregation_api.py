"""Phase 6 Project Schedule Hub trend aggregation API tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
    ProjectScheduleTrendAggregationService,
)
from tests.test_project_schedule_hub_api import (
    _fresh_db,
    _seed_twnu18_twnu19_canonical_metrics,
    _viewer,
)


def _seed_phase6_supporting_facts(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_quality_evaluation_runs (
              evaluation_run_id, project_key, schedule_version_key, import_id,
              assessment_profile, assessment_profile_version, method_source,
              trigger_source, idempotency_key, status, is_latest,
              completed_at, engine_version, checker_version
            ) VALUES (
              'quality-twnu19', 'tropical', 'tropical|S1|2026-06-29', 'imp-twnu19',
              'default', '1', 'test', 'manual_rerun', 'phase6-quality',
              'completed', 1, '2026-06-29T13:00:00Z', 'test', 'test'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_scorecards (
              evaluation_run_id, project_key, schedule_version_key,
              assessment_profile, quality_score, quality_grade,
              dcma_measured_count, dcma_pass_count, gao_category_summary_json,
              finding_counts_json, downstream_readiness_json
            ) VALUES (
              'quality-twnu19', 'tropical', 'tropical|S1|2026-06-29',
              'default', '82.5', 'B', 1, 1, '{}', '{}', '{}'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_cpm_paths (
              path_id, cpm_run_id, schedule_version_key, project_key,
              path_type, path_rank, start_activity_id, end_activity_id,
              activity_count, relationship_count, path_duration,
              path_finish_offset_days, path_total_float, path_basis, path_status
            ) VALUES (
              'path-twnu19', 'cpm-twnu19-criticality',
              'tropical|S1|2026-06-29', 'tropical',
              'longest_path', 1, 'LATER-000', 'LATER-460',
              613, 612, 155.0, 155.0, 0.0, 'computed_cpm', 'complete'
            )
            """
        )
        conn.commit()


def _phase6_db(tmp_path: Path) -> Path:
    db = _fresh_db(tmp_path)
    _seed_twnu18_twnu19_canonical_metrics(db)
    _seed_phase6_supporting_facts(db)
    return db


def test_supported_trend_service_payloads_include_contract_metadata(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    body = service.build_trend(
        "tropical",
        "planned_vs_actual_percent_complete",
    )

    assert body["available"] is True
    assert body["metric_key"] == "planned_vs_actual_percent_complete"
    assert body["weighting_basis"] == "duration_weighted"
    assert "source_export" in body["basis_labels"]
    assert body["formula_summary"]
    assert body["caveats"]
    assert len(body["points"]) == 2
    assert body["unavailable_variants"] == [{"variant": "cost_weighted", "reason": "cost_weighted_unavailable"}]


def test_progress_and_schedule_performance_default_and_activity_count_alternate(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    progress = service.build_trend("tropical", "planned_vs_actual_percent_complete")
    activity_count = service.build_trend(
        "tropical",
        "planned_vs_actual_percent_complete",
        weighting_basis="activity_count",
    )
    ratio = service.build_trend("tropical", "schedule_performance_ratio")

    assert progress["weighting_basis"] == "duration_weighted"
    assert activity_count["weighting_basis"] == "activity_count"
    assert ratio["weighting_basis"] == "duration_weighted"
    assert ratio["summary"]["earned_value_spi"] is False
    assert "not certified earned-value SPI" in " ".join(ratio["data_quality_notes"])
    assert ratio["points"][-1]["schedule_performance_ratio"] is not None


def test_cost_weighted_progress_and_unsupported_weighting_are_structured_errors(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    with pytest.raises(ValueError, match="cost_weighted_unavailable"):
        service.build_trend(
            "tropical",
            "planned_vs_actual_percent_complete",
            weighting_basis="cost_weighted",
        )
    with pytest.raises(ValueError, match="unsupported_weighting_basis"):
        service.build_trend(
            "tropical",
            "schedule_delay_over_time",
            weighting_basis="duration_weighted",
        )


def test_delay_changes_and_float_trends_expose_required_bases(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    delay = service.build_trend("tropical", "schedule_delay_over_time")
    changes = service.build_trend("tropical", "schedule_changes_over_time")
    float_trend = service.build_trend("tropical", "total_float_consumption_index")

    assert delay["points"][-1]["delay_days"] == 19
    assert delay["points"][-1]["gain_days"] == 0
    assert delay["points"][-1]["planned_variance_days"] is None
    assert delay["points"][-1]["net_movement_days"] == 19
    assert delay["summary"]["baseline_variance_separate"] is True

    categories = changes["points"][-1]["categories"]
    assert {
        "total_activities",
        "activity_changes",
        "logic_changes",
        "duration_changes",
        "critical_changes",
        "near_critical_changes",
        "lag_changes",
        "calendar_changes",
        "deleted_activity_changes",
        "added_activity_changes",
    } <= set(categories)
    assert categories["activity_changes"] == 537

    series = float_trend["points"][-1]["series"]
    assert {row["float_basis"] for row in series} == {"source_export", "computed_cpm"}
    assert float_trend["summary"]["float_bases_separate"] is True


def test_quality_cpm_and_dependency_supported_metrics_are_caveated(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    health = service.build_trend("tropical", "project_schedule_health_index")
    feasibility = service.build_trend("tropical", "schedule_feasibility_score")
    recovery = service.build_trend("tropical", "required_recovery_days")
    critical_path = service.build_trend("tropical", "critical_path_length_index")

    assert health["points"][-1]["health_index"] == 82.5
    assert feasibility["available"] is False
    assert feasibility["reason"] == "dependency_inputs_unavailable"
    assert recovery["available"] is True
    assert recovery["points"][-1]["required_recovery_days"] is not None
    assert any("causation" in caveat for caveat in recovery["caveats"])
    assert critical_path["available"] is True
    assert critical_path["points"][-1]["criticality_basis"] == "computed_cpm_path"


def test_single_trend_api_and_machine_errors(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))

    ok = client.get(
        "/api/projects/tropical/schedule/metrics/schedule_changes_over_time/trend",
        headers=_viewer(),
    )
    assert ok.status_code == 200
    assert ok.json()["points"][-1]["categories"]["activity_changes"] == 537

    invalid_as_of = client.get(
        "/api/projects/tropical/schedule/metrics/schedule_changes_over_time/trend?as_of=not-a-date",
        headers=_viewer(),
    )
    assert invalid_as_of.status_code == 400
    assert invalid_as_of.json() == {"detail": "invalid_as_of_date"}

    unsupported = client.get(
        "/api/projects/tropical/schedule/metrics/nope/trend",
        headers=_viewer(),
    )
    assert unsupported.status_code == 400
    assert unsupported.json() == {"detail": "unsupported_metric_key"}

    udf_metric = client.get(
        "/api/projects/tropical/schedule/metrics/delay_analysis/trend",
        headers=_viewer(),
    )
    assert udf_metric.status_code == 200
    assert udf_metric.json()["metric_key"] == "delay_analysis"
    assert "available" in udf_metric.json()

    cost = client.get(
        "/api/projects/tropical/schedule/metrics/schedule_performance_ratio/trend?weighting_basis=cost_weighted",
        headers=_viewer(),
    )
    assert cost.status_code == 422
    assert cost.json() == {"detail": "cost_weighted_unavailable"}


def test_batch_trends_api_returns_mixed_supported_and_blocked_results(tmp_path: Path) -> None:
    db = _phase6_db(tmp_path)
    client = TestClient(create_app(db_path=str(db)))

    response = client.get(
        "/api/projects/tropical/schedule/metrics/trends?metrics=planned_vs_actual_percent_complete,delay_analysis,nope",
        headers=_viewer(),
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["metric_key"] for item in body["metrics"]] == [
        "planned_vs_actual_percent_complete",
        "delay_analysis",
    ]
    assert body["errors"] == [
        {"metric_key": "nope", "detail": "unsupported_metric_key"},
    ]
