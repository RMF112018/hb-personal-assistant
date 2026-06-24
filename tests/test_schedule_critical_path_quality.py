"""Source-format-aware critical path quality tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.schedule_critical_path_analytics import (
    METRIC_STATUS_AVAILABLE_XER_DRIVING,
    METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
    SOURCE_CRITICAL_BASIS_XER_DRIVING,
    SOURCE_CRITICAL_BASIS_XER_TOTFLOAT,
)
from hb_assistant.construction.analytics.schedule_quality_engine import (
    METRIC_STATUS_NOT_MEASURABLE_RECALC,
    METRIC_STATUS_SOURCE_EXPORT_PROXY,
    ScheduleQualityAssessmentEngine,
    ScheduleQualityDataLoader,
)
from hb_assistant.construction.analytics.schedule_quality_profiles import DCMA_METRIC_SPECS
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

PGA_FIXTURE = Path(
    os.environ.get(
        "HB_SCHEDULE_FIXTURE_XER_PGA",
        "/Users/bobbyfetting/Downloads/PGA - The Modern.xer",
    )
)
TWNU_FIXTURE = Path(
    os.environ.get(
        "HB_SCHEDULE_FIXTURE_XER",
        "/Users/bobbyfetting/Downloads/TWNU18.xer",
    )
)


def _import_xer_and_evaluate(
    tmp_path: Path,
    *,
    fixture: Path,
    project_key: str,
    display_name: str,
    project_id: str = "9001",
) -> tuple[str, dict[str, dict]]:
    if not fixture.is_file():
        pytest.skip(f"missing XER fixture: {fixture}")
    try:
        data = fixture.read_bytes()
    except PermissionError:
        pytest.skip(f"XER fixture not readable: {fixture}")
    db = tmp_path / f"{project_key}.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(
        db,
        project_key=project_key,
        display_name=display_name,
        project_id=project_id,
    )
    from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService

    svc = ScheduleImportService(db_path=str(db))
    preview = svc.preview_bytes(
        filename=fixture.name,
        data=data,
        project_key=project_key,
    )
    commit = svc.commit(
        import_id=preview["import_id"],
        project_key=project_key,
        confirm=True,
        confirm_supersede=True,
    )
    svc_q = ScheduleQualityService(db_path=str(db))
    run = svc_q.request_rerun(schedule_version_key=commit["schedule_version_key"])
    svc_q.process_run(run["evaluation_run_id"])
    from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

    repo = ScheduleQualityRepository(db_path=str(db))
    metrics = {m["metric_code"]: m for m in repo.list_metrics(run["evaluation_run_id"])}
    return commit["schedule_version_key"], metrics


def _seed_xer_quality(tmp_path: Path) -> str:
    db = tmp_path / "q.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    xer = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"
    from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService

    svc = ScheduleImportService(db_path=str(db))
    preview = svc.preview_bytes(
        filename="minimal.xer",
        data=xer.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(
        import_id=preview["import_id"],
        project_key="tropical",
        confirm=True,
    )
    svc_q = ScheduleQualityService(db_path=str(db))
    run = svc_q.request_rerun(schedule_version_key=commit["schedule_version_key"])
    svc_q.process_run(run["evaluation_run_id"])
    return commit["schedule_version_key"]


def test_xer_dcma_critical_path_not_measurable_with_source_and_proxy(tmp_path: Path) -> None:
    svk = _seed_xer_quality(tmp_path)
    db = tmp_path / "q.db"
    loader = ScheduleQualityDataLoader(db_path=str(db))
    payload = loader.load(svk)
    from hb_assistant.construction.analytics.schedule_quality_engine import EvaluationContext
    from hb_assistant.construction.analytics.schedule_quality_profiles import get_profile

    ctx = EvaluationContext(
        project_key="tropical",
        schedule_version_key=svk,
        schedule_table_id=None,
        import_id=payload["import_meta"]["import_id"],
        evaluation_run_id="sq-test",
        assessment_profile=get_profile(),
        activities=payload["activities"],
        relationships=payload["relationships"],
        import_meta=payload["import_meta"],
        schedule_options=payload["schedule_options"],
    )
    engine = ScheduleQualityAssessmentEngine()
    metric, _ = engine._metric_critical_path_test(
        ctx, "dcma_critical_path_test", DCMA_METRIC_SPECS["dcma_critical_path_test"]
    )
    assert metric["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    assert "available separately" in str(metric.get("not_measurable_reason") or "")

    source_metrics = engine._evaluate_source_export_metrics(ctx)
    assert len(source_metrics) == 1
    source = source_metrics[0]
    assert source["metric_code"] == "source_critical_path_available"
    assert source["metric_family"] == "source_export"
    assert source["status"] == METRIC_STATUS_AVAILABLE_XER_DRIVING

    supplemental = engine._evaluate_supplemental_metrics(ctx)
    assert len(supplemental) == 1
    proxy = supplemental[0]
    assert proxy["status"] == METRIC_STATUS_SOURCE_EXPORT_PROXY
    evidence = json.loads(proxy["evidence_json"])
    assert evidence["driving_path_activity_count"] >= 1


def test_pga_xer_source_critical_path_drivpath(tmp_path: Path) -> None:
    _, metrics = _import_xer_and_evaluate(
        tmp_path,
        fixture=PGA_FIXTURE,
        project_key="pga-modern-garage",
        display_name="PGA The Modern Garage",
        project_id="61340",
    )
    dcma = metrics["dcma_critical_path_test"]
    assert dcma["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    source = metrics["source_critical_path_available"]
    assert source["status"] == METRIC_STATUS_AVAILABLE_XER_DRIVING
    evidence = json.loads(source["evidence_json"])
    assert evidence["source_critical_basis"] == SOURCE_CRITICAL_BASIS_XER_DRIVING
    assert evidence["source_critical_path_type"] == "CT_DrivPath"
    assert evidence["source_driving_path_count"] == 150
    assert evidence["explicit_float_activity_count"] == 1081
    assert evidence["driving_path_with_explicit_float_count"] == 150
    assert evidence["source_critical_activity_count"] == 150


def test_twnu_xer_source_critical_path_totfloat(tmp_path: Path) -> None:
    _, metrics = _import_xer_and_evaluate(
        tmp_path,
        fixture=TWNU_FIXTURE,
        project_key="tropical",
        display_name="Tropical Wind",
        project_id="1069",
    )
    dcma = metrics["dcma_critical_path_test"]
    assert dcma["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    source = metrics["source_critical_path_available"]
    assert source["status"] == METRIC_STATUS_AVAILABLE_XER_TOTFLOAT
    evidence = json.loads(source["evidence_json"])
    assert evidence["source_critical_basis"] == SOURCE_CRITICAL_BASIS_XER_TOTFLOAT
    assert evidence["source_critical_path_type"] == "CT_TotFloat"
    assert evidence["explicit_float_activity_count"] == 677
    assert evidence["total_float_le_zero_count"] == 664
    assert evidence["source_driving_path_count"] == 269
    assert evidence["driving_path_with_explicit_float_count"] == 32
    assert evidence["source_critical_activity_count"] == 664
    proxy = metrics.get("source_driving_path_integrity_proxy")
    assert proxy is not None
    assert proxy["metric_family"] == "supplemental"


def test_gma_p6_still_not_measurable_critical_path(tmp_path: Path) -> None:
    db_path = str(tmp_path / "q.db")
    SQLiteMigrator(db_path=db_path).apply()
    seed_procore_ep_project(db_path, project_key="tropical", display_name="Tropical Wind")
    gma = Path(__file__).parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"
    from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService

    svc = ScheduleImportService(db_path=db_path)
    preview = svc.preview_bytes(
        filename=gma.name, data=gma.read_bytes(), project_key="tropical"
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    svk = commit["schedule_version_key"]
    db = tmp_path / "q.db"
    loader = ScheduleQualityDataLoader(db_path=str(db))
    payload = loader.load(svk)
    from hb_assistant.construction.analytics.schedule_quality_engine import EvaluationContext
    from hb_assistant.construction.analytics.schedule_quality_profiles import get_profile

    ctx = EvaluationContext(
        project_key="tropical",
        schedule_version_key=svk,
        schedule_table_id=None,
        import_id=payload["import_meta"]["import_id"],
        evaluation_run_id="sq-test",
        assessment_profile=get_profile(),
        activities=payload["activities"],
        relationships=payload["relationships"],
        import_meta=payload["import_meta"],
        schedule_options=payload["schedule_options"],
    )
    engine = ScheduleQualityAssessmentEngine()
    metric, _ = engine._metric_critical_path_test(
        ctx, "dcma_critical_path_test", DCMA_METRIC_SPECS["dcma_critical_path_test"]
    )
    assert metric["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
    assert engine._evaluate_source_export_metrics(ctx) == []
