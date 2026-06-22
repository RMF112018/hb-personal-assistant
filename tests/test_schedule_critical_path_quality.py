"""Source-format-aware critical path quality tests."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_xer_dcma_critical_path_not_measurable_with_supplemental_proxy(tmp_path: Path) -> None:
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

    supplemental = engine._evaluate_supplemental_metrics(ctx)
    assert len(supplemental) == 1
    proxy = supplemental[0]
    assert proxy["status"] == METRIC_STATUS_SOURCE_EXPORT_PROXY
    evidence = json.loads(proxy["evidence_json"])
    assert evidence["driving_path_activity_count"] >= 1
    assert evidence["eligible_driving_path_activity_count"] == int(proxy["denominator"])
    assert evidence["method"] == "source_export_proxy"


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