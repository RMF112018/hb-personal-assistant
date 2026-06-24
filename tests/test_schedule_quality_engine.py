"""Schedule quality assessment engine tests."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.construction.analytics.schedule_quality_engine import (
    METRIC_STATUS_DERIVED_FINISH_FLOAT,
    METRIC_STATUS_NOT_MEASURABLE_RECALC,
    EvaluationContext,
    ScheduleQualityAssessmentEngine,
    run_evaluation_for_run,
)
from hb_assistant.construction.analytics.schedule_quality_profiles import (
    DCMA_METRIC_SPECS,
    get_profile,
)
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
GMA = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"


def _db(tmp_path: Path) -> str:
    db = tmp_path / "q.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return str(db)


def _lag_context(relationships: list[dict[str, object]]) -> EvaluationContext:
    return EvaluationContext(
        project_key="tropical",
        schedule_version_key="tropical|1|2026-01-01",
        schedule_table_id=None,
        import_id="imp-test",
        evaluation_run_id="sq-lag-units",
        assessment_profile=get_profile(),
        relationships=relationships,
    )


def _msp_context(activities: list[dict[str, object]]) -> EvaluationContext:
    return EvaluationContext(
        project_key="tropical",
        schedule_version_key="tropical|1|2026-01-01",
        schedule_table_id=None,
        import_id="imp-msp",
        evaluation_run_id="sq-msp-source",
        assessment_profile=get_profile(),
        activities=activities,
        import_meta={"source_format": "ms_project_xml"},
    )


def _baseline_context(
    activities: list[dict[str, object]],
    *,
    data_date: str | None = "2026-01-10",
    schedule_version_key: str = "tropical|1|2026-01-10",
) -> EvaluationContext:
    return EvaluationContext(
        project_key="tropical",
        schedule_version_key=schedule_version_key,
        schedule_table_id=None,
        import_id="imp-baseline",
        evaluation_run_id="sq-baseline",
        assessment_profile=get_profile(),
        data_date=data_date,
        activities=activities,
        import_meta={"source_format": "ms_project_xml", "baseline_source": "msp_baseline"},
    )


def test_dcma_lag_metric_normalizes_source_units_before_thresholding() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _lag_context(
        [
            {
                "relationship_id": "r-48h",
                "predecessor_activity_id": "A1",
                "successor_activity_id": "A2",
                "lag_value": "48",
                "lag_unit": "hour",
            },
            {
                "relationship_id": "r-360h",
                "predecessor_activity_id": "A2",
                "successor_activity_id": "A3",
                "lag_value": "360",
                "lag_unit": "hour",
            },
            {
                "relationship_id": "r-msp",
                "predecessor_activity_id": "A3",
                "successor_activity_id": "A4",
                "lag_value": "4800",
                "lag_unit": "minute_tenth",
            },
            {
                "relationship_id": "r-missing",
                "predecessor_activity_id": "A4",
                "successor_activity_id": "A5",
                "lag_value": "12",
                "lag_unit": None,
            },
            {
                "relationship_id": "r-unknown",
                "predecessor_activity_id": "A5",
                "successor_activity_id": "A6",
                "lag_value": "7",
                "lag_unit": "fortnight",
            },
            {
                "relationship_id": "r-blank",
                "predecessor_activity_id": "A6",
                "successor_activity_id": "A7",
                "lag_value": "",
                "lag_unit": "hour",
            },
            {
                "relationship_id": "r-bad",
                "predecessor_activity_id": "A7",
                "successor_activity_id": "A8",
                "lag_value": "not-a-number",
                "lag_unit": "hour",
            },
        ]
    )

    metric, findings = engine._metric_lags(
        ctx, "dcma_lags", DCMA_METRIC_SPECS["dcma_lags"]
    )
    evidence = json.loads(metric["evidence_json"])

    assert metric["numerator"] == "1"
    assert metric["denominator"] == "7"
    assert len(findings) == 1
    assert findings[0]["relationship_id"] == "r-360h"
    finding_evidence = json.loads(findings[0]["evidence_json"])
    assert finding_evidence == {
        "relationship_id": "r-360h",
        "predecessor_activity_id": "A2",
        "successor_activity_id": "A3",
        "raw_lag_value": "360",
        "raw_lag_unit": "hour",
        "normalized_lag_days": "45",
        "conversion_status": "known_unit",
    }
    assert evidence["total_relationships_assessed"] == 7
    assert evidence["lag_values_normalized_count"] == 3
    assert evidence["assumed_day_count"] == 2
    assert evidence["skipped_unparseable_count"] == 2
    assert evidence["unit_distribution"]["hour"] == 4
    assert evidence["unit_distribution"]["minute_tenth"] == 1
    assert evidence["unit_distribution"]["(missing)"] == 1
    assert evidence["unit_distribution"]["fortnight"] == 1
    assert evidence["max_positive_lag_days"] == "45"
    assert evidence["excessive_lag_threshold_days"] == "44"
    assert evidence["finding_samples"][0]["normalized_lag_days"] == "45"


def test_dcma_lead_metric_counts_negative_normalized_lags_only() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _lag_context(
        [
            {
                "relationship_id": "r-lead",
                "predecessor_activity_id": "A1",
                "successor_activity_id": "A2",
                "lag_value": "-16",
                "lag_unit": "hour",
            },
            {
                "relationship_id": "r-blank",
                "predecessor_activity_id": "A2",
                "successor_activity_id": "A3",
                "lag_value": "",
                "lag_unit": "hour",
            },
            {
                "relationship_id": "r-positive",
                "predecessor_activity_id": "A3",
                "successor_activity_id": "A4",
                "lag_value": "48",
                "lag_unit": "hour",
            },
        ]
    )

    metric, findings = engine._metric_leads(
        ctx, "dcma_leads", DCMA_METRIC_SPECS["dcma_leads"]
    )
    evidence = json.loads(metric["evidence_json"])

    assert metric["numerator"] == "1"
    assert metric["denominator"] == "3"
    assert len(findings) == 1
    assert findings[0]["relationship_id"] == "r-lead"
    finding_evidence = json.loads(findings[0]["evidence_json"])
    assert finding_evidence["normalized_lag_days"] == "-2"
    assert finding_evidence["raw_lag_value"] == "-16"
    assert finding_evidence["raw_lag_unit"] == "hour"
    assert evidence["min_negative_lag_days"] == "-2"
    assert evidence["max_positive_lag_days"] == "6"
    assert evidence["skipped_unparseable_count"] == 1


def test_msp_source_export_metric_and_dcma_separation() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _msp_context(
        [
            {
                "activity_id": "C0",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "0.0",
            },
            {
                "activity_id": "CP",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "2.0",
            },
            {
                "activity_id": "FP",
                "source_critical_flag": 0,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "1.0",
            },
        ]
    )

    dcma, _ = engine._metric_critical_path_test(
        ctx, "dcma_critical_path_test", DCMA_METRIC_SPECS["dcma_critical_path_test"]
    )
    assert dcma["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC

    metrics = engine._evaluate_source_export_metrics(ctx)
    assert len(metrics) == 1
    metric = metrics[0]
    evidence = json.loads(metric["evidence_json"])
    assert metric["metric_code"] == "source_msp_critical_slack_available"
    assert metric["metric_family"] == "source_export"
    assert metric["status"] == "measured_from_msp_critical_flag"
    assert metric["numerator"] == "2"
    assert metric["denominator"] == "3"
    assert metric["value"] == "0.6667"
    assert evidence["consistent_critical_slack_count"] == 2
    assert evidence["inconsistent_critical_slack_count"] == 1
    assert evidence["not_a_dcma_critical_path_test"] is True
    assert evidence["cpm_recalculation_performed"] is False


def test_dcma_baseline_metrics_not_measurable(tmp_path: Path) -> None:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename=FIXTURE.name,
        data=FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    version_key = commit["schedule_version_key"]

    result = run_evaluation_for_run(
        db_path=db,
        evaluation_run_id="sq-test000001",
        project_key="tropical",
        schedule_version_key=version_key,
        schedule_table_id=None,
        import_id=preview["import_id"],
    )
    codes = {m["metric_code"]: m for m in result.metrics}
    assert codes["dcma_cpli"]["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    assert codes["dcma_bei"]["status"] == "not_measurable_missing_data"
    assert codes["dcma_missed_tasks"]["status"] == "not_measurable_missing_data"
    assert result.scorecard["quality_grade"] in {"A", "B", "C", "D", "F", "insufficient_data"}


def test_dcma_missed_tasks_measures_true_baseline_due_population() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _baseline_context(
        [
            {
                "activity_id": "DONE",
                "activity_name": "Completed due",
                "baseline_finish": "2026-01-05",
                "activity_status": "TK_Complete",
                "actual_finish": "2026-01-04",
            },
            {
                "activity_id": "MISS",
                "activity_name": "Incomplete due",
                "baseline_finish": "2026-01-06",
                "activity_status": "TK_Active",
            },
            {
                "activity_id": "LATE",
                "activity_name": "Finished after status date",
                "baseline_finish": "2026-01-07",
                "activity_status": "TK_Complete",
                "actual_finish": "2026-01-12",
            },
            {
                "activity_id": "FUTURE",
                "activity_name": "Not due yet",
                "baseline_finish": "2026-01-20",
                "activity_status": "TK_NotStart",
            },
        ]
    )

    metric, findings = engine._metric_missed_tasks(
        ctx, "dcma_missed_tasks", DCMA_METRIC_SPECS["dcma_missed_tasks"]
    )
    evidence = json.loads(metric["evidence_json"])

    assert findings == []
    assert metric["status"] == "measured"
    assert metric["numerator"] == "2"
    assert metric["denominator"] == "3"
    assert metric["value"] == "0.6667"
    assert evidence["profile_thresholds_defined"] is False
    assert evidence["threshold_status_available"] is False
    assert evidence["metric_interpretation"] == "reported_indicator_no_profile_threshold"
    assert evidence["status_date"] == "2026-01-10"
    assert evidence["status_date_source"] == "ctx.data_date"
    assert evidence["denominator_definition"] == (
        "eligible activities with true baseline_finish on or before status_date"
    )
    assert [sample["activity_id"] for sample in evidence["missed_activity_samples"]] == [
        "MISS",
        "LATE",
    ]
    assert evidence["missed_activity_samples"][1]["reason"] == "actual_finish_after_status_date"
    assert [sample["activity_id"] for sample in evidence["completed_due_activity_samples"]] == [
        "DONE"
    ]


def test_dcma_missed_tasks_not_measurable_prerequisites() -> None:
    engine = ScheduleQualityAssessmentEngine()
    cases = [
        (
            _baseline_context(
                [{"activity_id": "A1", "planned_finish": "2026-01-05"}],
                data_date="2026-01-10",
            ),
            "missing baseline finish dates",
        ),
        (
            _baseline_context(
                [{"activity_id": "A1", "baseline_finish": "2026-01-05"}],
                data_date=None,
                schedule_version_key="tropical|1|not-a-date",
            ),
            "invalid_status_date",
        ),
        (
            _baseline_context(
                [{"activity_id": "A1", "baseline_finish": "2026-01-20"}],
                data_date="2026-01-10",
            ),
            "baseline due denominator is zero",
        ),
    ]

    for ctx, expected_reason in cases:
        metric, _ = engine._metric_missed_tasks(
            ctx, "dcma_missed_tasks", DCMA_METRIC_SPECS["dcma_missed_tasks"]
        )
        evidence = json.loads(metric["evidence_json"])
        assert metric["status"] == "not_measurable_missing_data"
        assert expected_reason in metric["not_measurable_reason"]
        assert expected_reason in evidence["missing_prerequisites"]


def test_dcma_bei_measures_completed_due_ratio() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _baseline_context(
        [
            {
                "activity_id": "DONE",
                "baseline_finish": "2026-01-05",
                "activity_status": "TK_Complete",
                "actual_finish": "2026-01-04",
            },
            {
                "activity_id": "LATE",
                "baseline_finish": "2026-01-06",
                "activity_status": "TK_Complete",
                "actual_finish": "2026-01-12",
            },
            {
                "activity_id": "OPEN",
                "baseline_finish": "2026-01-07",
                "activity_status": "TK_Active",
            },
        ]
    )

    metric, findings = engine._metric_bei(ctx, "dcma_bei", DCMA_METRIC_SPECS["dcma_bei"])
    evidence = json.loads(metric["evidence_json"])

    assert findings == []
    assert metric["status"] == "measured"
    assert metric["numerator"] == "1"
    assert metric["denominator"] == "3"
    assert metric["value"] == "0.3333"
    assert evidence["profile_thresholds_defined"] is False
    assert evidence["threshold_status_available"] is False
    assert evidence["metric_interpretation"] == "reported_indicator_no_profile_threshold"
    assert [sample["activity_id"] for sample in evidence["completed_due_activity_samples"]] == [
        "DONE"
    ]
    assert [sample["activity_id"] for sample in evidence["missed_activity_samples"]] == [
        "LATE",
        "OPEN",
    ]


def test_dcma_bei_not_measurable_prerequisites() -> None:
    engine = ScheduleQualityAssessmentEngine()
    cases = [
        (
            _baseline_context(
                [{"activity_id": "A1", "target_finish": "2026-01-05"}],
                data_date="2026-01-10",
            ),
            "missing baseline finish dates",
        ),
        (
            _baseline_context(
                [{"activity_id": "A1", "baseline_finish": "2026-01-05"}],
                data_date=None,
                schedule_version_key="tropical|1|not-a-date",
            ),
            "invalid_status_date",
        ),
        (
            _baseline_context(
                [{"activity_id": "A1", "baseline_finish": "2026-01-20"}],
                data_date="2026-01-10",
            ),
            "baseline due denominator is zero",
        ),
    ]

    for ctx, expected_reason in cases:
        metric, _ = engine._metric_bei(ctx, "dcma_bei", DCMA_METRIC_SPECS["dcma_bei"])
        evidence = json.loads(metric["evidence_json"])
        assert metric["status"] == "not_measurable_missing_data"
        assert expected_reason in metric["not_measurable_reason"]
        assert expected_reason in evidence["missing_prerequisites"]


def test_dcma_cpli_remains_recalculation_gated_with_source_export_evidence() -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = _baseline_context(
        [
            {
                "activity_id": "C0",
                "baseline_finish": "2026-01-05",
                "source_critical_flag": 1,
                "source_critical_flag_present": True,
                "explicit_total_float_days": "0.0",
                "critical_path_source": "msp_critical_flag",
                "derived_total_float_days": "0.0",
                "derived_float_basis": "remaining_late_finish_minus_remaining_early_finish",
            }
        ]
    )

    metric, findings = engine._metric_cpli(ctx, "dcma_cpli", DCMA_METRIC_SPECS["dcma_cpli"])
    evidence = json.loads(metric["evidence_json"])

    assert findings == []
    assert metric["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    assert metric["not_measurable_reason"] == (
        "critical path length unavailable without CPM recalculation"
    )
    assert evidence["critical_path_length_prerequisites_available"] is False
    assert evidence["source_export_critical_flags_sufficient"] is False
    assert evidence["msp_slack_sufficient"] is False
    assert evidence["derived_float_sufficient"] is False
    assert "critical path length unavailable without CPM recalculation" in evidence[
        "missing_recalculation_prerequisites"
    ]


def test_queue_and_process_completes_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    imp = ScheduleImportService(db_path=db)
    preview = imp.preview_bytes(
        filename=FIXTURE.name,
        data=FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = imp.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    qsvc = ScheduleQualityService(db_path=db)
    summary = qsvc.get_quality_summary(commit["schedule_version_key"])
    assert summary["status"] in {"completed", "pending", "running", "failed"}
    if summary["status"] != "completed":
        out = qsvc.process_next_pending()
        assert out is not None
        summary = qsvc.get_quality_summary(commit["schedule_version_key"])
    assert summary["status"] == "completed"
    assert summary.get("metrics")


def test_gma_derived_float_metrics_measured(tmp_path: Path) -> None:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename=GMA.name,
        data=GMA.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    result = run_evaluation_for_run(
        db_path=db,
        evaluation_run_id="sq-testgma001",
        project_key="tropical",
        schedule_version_key=commit["schedule_version_key"],
        schedule_table_id=None,
        import_id=preview["import_id"],
    )
    codes = {m["metric_code"]: m for m in result.metrics}
    assert codes["dcma_high_float"]["status"] == METRIC_STATUS_DERIVED_FINISH_FLOAT
    assert codes["dcma_negative_float"]["status"] == METRIC_STATUS_DERIVED_FINISH_FLOAT
    assert codes["dcma_critical_path_test"]["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    import json

    gao = json.loads(result.scorecard.get("gao_category_summary_json") or "{}")
    assert (
        gao.get("critical_path_validity", {}).get("posture")
        == "partially_measurable_critical_float_available"
    )


def test_relationship_types_normalize_finish_to_start_labels(tmp_path: Path) -> None:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename=FIXTURE.name,
        data=FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    from hb_assistant.store.connection import get_connection

    conn = get_connection(db)
    conn.execute(
        """
        UPDATE procore_ep_schedule_relationships
        SET relationship_type='Finish to Start'
        WHERE schedule_version_key=?
        """,
        (commit["schedule_version_key"],),
    )
    conn.commit()
    conn.close()

    result = run_evaluation_for_run(
        db_path=db,
        evaluation_run_id="sq-testrel001",
        project_key="tropical",
        schedule_version_key=commit["schedule_version_key"],
        schedule_table_id=None,
        import_id=preview["import_id"],
    )
    metric = next(m for m in result.metrics if m["metric_code"] == "dcma_relationship_types")
    import json

    evidence = json.loads(metric.get("evidence_json") or "{}")
    assert metric["numerator"] != "0"
    assert evidence["distribution"]["FS"] >= 1


def test_cost_loading_not_applicable_for_not_cost_loaded_import(tmp_path: Path) -> None:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename=FIXTURE.name,
        data=FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    assert commit["cost_loaded_status"] == "not_cost_loaded"
    result = run_evaluation_for_run(
        db_path=db,
        evaluation_run_id="sq-testcost001",
        project_key="tropical",
        schedule_version_key=commit["schedule_version_key"],
        schedule_table_id=None,
        import_id=preview["import_id"],
    )
    metric = next(m for m in result.metrics if m["metric_code"] == "dcma_resources_cost_loading")
    assert metric["status"] == "not_applicable"
