"""Phase 16 schedule quality controls read model tests."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_quality_controls_service import (
    ProjectScheduleQualityControlsService,
    pm_quality_controls_payload,
)
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project


def _seed_completed_quality(db_path: str, schedule_version_key: str = "tropical|S1|2026-07-01") -> None:
    svc = ScheduleQualityService(db_path=db_path)
    queued = svc.queue_evaluation(
        project_key="tropical",
        schedule_version_key=schedule_version_key,
        schedule_table_id=None,
        import_id="imp-quality",
        trigger_source="import_commit",
    )
    svc.process_run(queued["evaluation_run_id"])


def _db(tmp_path: Path) -> str:
    db = tmp_path / "quality-controls.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return str(db)


def test_quality_controls_unavailable_without_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    payload = ProjectScheduleQualityControlsService(db_path=db).build_quality_controls(
        "tropical|missing|2026-01-01"
    )
    assert payload["quality_run_status"] == "unavailable"
    assert payload["quality_trust_status"] == "unavailable"


def test_quality_controls_complete_run_maps_groups(tmp_path: Path) -> None:
    db = _db(tmp_path)
    from tests.test_project_schedule_review_workbench import _seed_driver_chain

    _seed_driver_chain(Path(db))
    svk = "tropical|S1|2026-07-01"
    _seed_completed_quality(db, schedule_version_key=svk)
    payload = ProjectScheduleQualityControlsService(db_path=db).build_quality_controls(svk)
    assert payload["quality_run_status"] == "complete"
    group_keys = {g["group_key"] for g in payload["control_groups"]}
    assert "logic_integrity" in group_keys
    assert "capability_limitations" in group_keys
    assert any("Out-of-sequence" in item for item in payload["capability_limitations"])


def test_identity_blocked_caps_quality_trust(tmp_path: Path) -> None:
    db = _db(tmp_path)
    from tests.test_project_schedule_review_workbench import _seed_driver_chain

    _seed_driver_chain(Path(db))
    svk = "tropical|S1|2026-07-01"
    _seed_completed_quality(db, schedule_version_key=svk)
    payload = ProjectScheduleQualityControlsService(db_path=db).build_quality_controls(
        svk,
        analytics_trust={"analytics_trust_status": "blocked", "identity_gate": "blocked"},
        identity_trust={"identity_gate": "blocked", "identity_trust_status": "mismatch"},
    )
    assert payload["quality_trust_status"] == "blocked"


def test_pm_payload_strips_technical_ids(tmp_path: Path) -> None:
    db = _db(tmp_path)
    from tests.test_project_schedule_review_workbench import _seed_driver_chain

    _seed_driver_chain(Path(db))
    svk = "tropical|S1|2026-07-01"
    _seed_completed_quality(db, schedule_version_key=svk)
    raw = ProjectScheduleQualityControlsService(db_path=db).build_quality_controls(svk)
    pm = pm_quality_controls_payload(raw)
    blob = json.dumps(pm)
    assert "schedule_version_key" not in blob
    assert "evaluation_run_id" not in blob
