"""Schedule quality assessment engine tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.construction.analytics.schedule_quality_engine import (
    METRIC_STATUS_DERIVED_FINISH_FLOAT,
    METRIC_STATUS_NOT_MEASURABLE_RECALC,
    run_evaluation_for_run,
)
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
GMA = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"


def _db(tmp_path: Path) -> str:
    db = tmp_path / "q.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


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
    assert codes["dcma_cpli"]["status"] == "not_measurable_missing_data"
    assert codes["dcma_bei"]["status"] == "not_measurable_missing_data"
    assert codes["dcma_missed_tasks"]["status"] == "not_measurable_missing_data"
    assert result.scorecard["quality_grade"] in {"A", "B", "C", "D", "F", "insufficient_data"}


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