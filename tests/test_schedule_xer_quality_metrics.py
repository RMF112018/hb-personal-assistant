"""Focused XER parser + quality metric integration tests."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.construction.analytics.schedule_quality_engine import (
    METRIC_STATUS_XER_DRIVING_PATH,
    EvaluationContext,
    ScheduleQualityAssessmentEngine,
    ScheduleQualityDataLoader,
    run_evaluation_for_run,
)
from hb_assistant.construction.analytics.schedule_quality_normalization import normalize_duration_days
from hb_assistant.construction.analytics.schedule_quality_profiles import DCMA_METRIC_SPECS, get_profile
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _db(tmp_path: Path) -> str:
    db = tmp_path / "xer_quality.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return str(db)


def test_xer_parser_maps_actual_dates_and_duration_unit(tmp_path: Path) -> None:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename="minimal.xer",
        data=XER.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    conn = get_connection(db)
    rows = conn.execute(
        """
        SELECT activity_id, actual_start, actual_finish, duration_unit, duration_original
        FROM procore_ep_schedule_activities
        WHERE schedule_version_key=?
        ORDER BY activity_id
        """,
        (commit["schedule_version_key"],),
    ).fetchall()
    conn.close()
    assert rows
    driving = next(r for r in rows if r["activity_id"] == "A1000")
    assert driving["duration_unit"] == "hour"
    assert driving["actual_start"] is not None


def test_invalid_dates_numerator_never_exceeds_denominator(tmp_path: Path) -> None:
    engine = ScheduleQualityAssessmentEngine()
    ctx = EvaluationContext(
        project_key="tropical",
        schedule_version_key="tropical|1|2026-01-01",
        schedule_table_id=None,
        import_id="imp-test",
        evaluation_run_id="sq-xer-dates",
        assessment_profile=get_profile(),
        data_date="2026-05-26 08:00",
        activities=[
            {
                "activity_id": "C1",
                "activity_status": "TK_Complete",
                "percent_complete": 100,
            },
            {
                "activity_id": "C2",
                "activity_status": "TK_Complete",
                "percent_complete": 100,
                "finish_date": "2026-02-01 17:00",
            },
            {
                "activity_id": "S1",
                "activity_status": "TK_Active",
                "percent_complete": 50,
            },
        ],
    )
    metric, findings = engine._metric_invalid_dates(
        ctx, "dcma_invalid_dates", DCMA_METRIC_SPECS["dcma_invalid_dates"]
    )
    assert int(metric["numerator"]) <= int(metric["denominator"])
    evidence = json.loads(metric["evidence_json"])
    assert evidence["display_mode"] == "finding_count"
    assert evidence["subcategories"]["completed_missing_actual_finish"]["findings"] == 1
    assert evidence["subcategories"]["completed_missing_actual_finish"]["denominator"] == 2
    assert evidence["subcategories"]["started_missing_actual_start"]["findings"] == 3
    assert evidence["subcategories"]["started_missing_actual_start"]["denominator"] == 3
    assert len(findings) == 4


def test_high_duration_normalizes_xer_hours_to_days(tmp_path: Path) -> None:
    assert (
        normalize_duration_days(
            duration_value=80,
            duration_unit=None,
            source_format="primavera_xer",
        )
        == 10.0
    )
    engine = ScheduleQualityAssessmentEngine()
    ctx = EvaluationContext(
        project_key="tropical",
        schedule_version_key="tropical|1|2026-01-01",
        schedule_table_id=None,
        import_id="imp-test",
        evaluation_run_id="sq-xer-dur",
        assessment_profile=get_profile(),
        import_meta={"source_format": "primavera_xer"},
        activities=[
            {
                "activity_id": "D1",
                "duration_original": 80,
                "duration_unit": "hour",
                "calendar_id": "100",
            }
        ],
        calendars=[{"calendar_id": "100", "hours_per_day": 8}],
    )
    metric, _ = engine._metric_high_duration(
        ctx, "dcma_high_duration", DCMA_METRIC_SPECS["dcma_high_duration"]
    )
    assert metric["numerator"] == "0"
    evidence = json.loads(metric["evidence_json"])
    assert evidence["method"] == "normalized_working_days"


def test_xer_critical_path_evidence_explains_eligible_vs_export_flags(tmp_path: Path) -> None:
    svk = _seed_and_evaluate(tmp_path)
    db = str(tmp_path / "xer_quality.db")
    loader = ScheduleQualityDataLoader(db_path=db)
    payload = loader.load(svk)
    ctx = EvaluationContext(
        project_key="tropical",
        schedule_version_key=svk,
        schedule_table_id=None,
        import_id=payload["import_meta"]["import_id"],
        evaluation_run_id="sq-xer-cp",
        assessment_profile=get_profile(),
        activities=payload["activities"],
        relationships=payload["relationships"],
        import_meta=payload["import_meta"],
        schedule_options=payload["schedule_options"],
        code_assignments=payload["code_assignments"],
        udf_values=payload["udf_values"],
    )
    engine = ScheduleQualityAssessmentEngine()
    driving = [a for a in ctx.activities if a.get("source_driving_path_flag")]
    metric, _ = engine._metric_critical_path_xer_driving(
        ctx,
        "dcma_critical_path_test",
        DCMA_METRIC_SPECS["dcma_critical_path_test"],
        driving,
    )
    assert metric["status"] == METRIC_STATUS_XER_DRIVING_PATH
    evidence = json.loads(metric["evidence_json"])
    assert evidence["driving_path_activity_count"] == len(driving)
    assert evidence["eligible_driving_path_activity_count"] == int(metric["denominator"])
    assert evidence["critical_path_test_method"] == "source_export_driving_path_proxy"
    assert evidence["cpm_recalculation"] == "not_implemented"


def _seed_and_evaluate(tmp_path: Path) -> str:
    db = _db(tmp_path)
    svc = ScheduleImportService(db_path=db)
    preview = svc.preview_bytes(
        filename="minimal.xer",
        data=XER.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    run_evaluation_for_run(
        db_path=db,
        evaluation_run_id="sq-xer-full",
        project_key="tropical",
        schedule_version_key=commit["schedule_version_key"],
        schedule_table_id=None,
        import_id=preview["import_id"],
    )
    return commit["schedule_version_key"]