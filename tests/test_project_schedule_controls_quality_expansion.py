"""Phase 16 controls quality expansion integration tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.project_schedule_controls_service import (
    ProjectScheduleControlsService,
)
from hb_assistant.construction.analytics.project_schedule_memo_service import ProjectScheduleMemoService
from hb_assistant.construction.analytics.project_schedule_narrative_qa import (
    validate_controls_text,
    validate_rendered_text,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_controls_service import _fresh_db, _seed_cpm_obs, _seed_driver_chain
from tests.test_project_schedule_quality_controls import _seed_completed_quality


def test_controls_includes_quality_sections(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _seed_cpm_obs(db, schedule_version_key="tropical|S1|2026-07-01", import_id="imp-current")
    _seed_completed_quality(str(db), schedule_version_key="tropical|S1|2026-07-01")
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="prior_update",
    )
    assert payload["quality_controls"]["quality_run_status"] in {"complete", "unavailable", "degraded"}
    assert payload["sections"]["logic_integrity"]["available"] in {True, False}
    assert "capability_limitations" in payload["sections"]
    assert payload["controls_language_qa"]["passed"] is True


def test_pm_controls_redacts_schedule_version_key(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    assert "schedule_version_key" not in payload
    assert all("schedule_version_key" not in c for c in payload.get("top_controls") or [])
    operator = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        include_technical=True,
    )
    assert operator.get("schedule_version_key")


def test_export_includes_quality_controls_section(tmp_path: Path) -> None:
    summary = {
        "project_key": "tropical",
        "project_display_name": "Tropical Wind",
        "as_of_date": "2026-07-03",
        "quality_controls": {
            "quality_trust_status": "degraded",
            "quality_run_status": "complete",
            "scorecard": {"overall_score": "82.0", "quality_grade": "B"},
            "control_groups": [
                {
                    "group_key": "logic_integrity",
                    "label": "Logic integrity",
                    "status": "degraded",
                    "summary": "1 measured check(s) are in warning range for this group.",
                }
            ],
            "capability_limitations": [
                "Out-of-sequence progress analysis is not implemented in this release; do not treat schedule movement as entitlement or causation."
            ],
            "recommended_pm_actions": ["Review logic integrity counts and confirm whether open ends need cleanup."],
        },
        "analytics_trust": {"analytics_trust_status": "degraded", "identity_gate": "ready"},
    }
    body = ProjectScheduleMemoService()._markdown(summary, qa={"passed": True})
    qa = validate_rendered_text(body, surface="export")
    assert "## Schedule Quality Controls" in body
    assert "Out-of-sequence" in body
    assert qa["passed"] is True
    assert "schedule_version_key" not in body
