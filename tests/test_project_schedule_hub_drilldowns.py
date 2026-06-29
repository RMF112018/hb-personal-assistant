"""Drilldown endpoint tests for Project Schedule Hub Phase 2."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import (
    _seed_comparable_versions,
    _seed_non_authoritative_failed_cpm_run,
    _seed_twnu18_twnu19_canonical_metrics,
    _seed_xer_change_impact_comparison,
    _viewer,
)
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "drilldown.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def test_drilldown_count_reconciles_with_summary(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_xer_change_impact_comparison(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    summary = service.build_summary("tropical", as_of=date(2026, 7, 3))
    expected = summary["change_impact"]["direct_remaining_changes"]["summary"]["finish_moved_later_count"]
    drilldown = service.build_drilldown(
        "tropical",
        drilldown_type="remaining_later",
        limit=100,
        offset=0,
        as_of=date(2026, 7, 3),
    )
    assert drilldown["count"] == expected
    assert drilldown["count"] >= 2


def test_driver_drilldown_lists_candidates(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    page = service.build_driver_drilldown(
        "tropical",
        drilldown_type="drivers",
        limit=10,
        offset=0,
        as_of=date(2026, 7, 3),
    )
    assert page.get("available") is True
    assert page["drilldown_type"] == "drivers"


def test_drilldown_pagination_and_limit(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    page = service.build_drilldown("tropical", drilldown_type="finish_changed", limit=1, offset=0)
    assert page["limit"] == 1
    assert len(page["items"]) <= 1


def test_cpm_and_source_float_drilldowns_reconcile_with_canonical_metrics(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_twnu18_twnu19_canonical_metrics(db)
    _seed_non_authoritative_failed_cpm_run(db)
    service = ProjectScheduleSummaryService(db_path=str(db))

    summary = service.build_summary("tropical", as_of=date(2026, 6, 29))
    critical = service.build_drilldown(
        "tropical",
        drilldown_type="critical_remaining",
        limit=100,
        offset=0,
        as_of=date(2026, 6, 29),
    )
    near = service.build_drilldown(
        "tropical",
        drilldown_type="near_critical_remaining",
        limit=100,
        offset=0,
        as_of=date(2026, 6, 29),
    )
    negative = service.build_drilldown(
        "tropical",
        drilldown_type="negative_float",
        limit=100,
        offset=0,
        as_of=date(2026, 6, 29),
    )

    assert critical["count"] == summary["computed_cpm_summary"]["critical_remaining_count"] == 613
    assert near["count"] == summary["computed_cpm_summary"]["near_critical_remaining_count"] == 0
    assert negative["count"] == summary["source_float_summary"]["negative_float_remaining_count"] == 711


def test_update_to_update_drilldowns_reconcile_with_canonical_metrics(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_twnu18_twnu19_canonical_metrics(db)
    service = ProjectScheduleSummaryService(db_path=str(db))

    expected = {
        "remaining_later": 461,
        "remaining_earlier": 76,
        "finish_changed": 537,
        "new_remaining": 98,
        "worsened_float": 378,
        "improved_float": 122,
        "milestones_later": 6,
    }

    for drilldown_type, expected_count in expected.items():
        page = service.build_drilldown(
            "tropical",
            drilldown_type=drilldown_type,
            limit=100,
            offset=0,
            as_of=date(2026, 6, 29),
        )
        assert page["count"] == expected_count
        assert page["comparison_basis"] == "prior_update"
        assert page["finish_movement_basis"] == "resolved_finish_date"
        assert page["comparison_context"]["current_version_key"] == "tropical|S1|2026-06-29"
        assert page["comparison_context"]["previous_version_key"] == "tropical|S1|2026-06-28"


def test_project_schedule_drilldown_unsupported_type_returns_structured_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _fresh_db(tmp_path)
    _seed_twnu18_twnu19_canonical_metrics(db)
    monkeypatch.setenv("HB_ASSISTANT_DB_PATH", str(db))
    from fastapi.testclient import TestClient

    response = TestClient(create_app(db_path=str(db))).get(
        "/api/projects/tropical/schedule/drilldowns?type=relationship_changes&as_of=2026-06-29",
        headers=_viewer(),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "unsupported_drilldown_type"}


def test_logic_and_duration_changes_are_driver_drilldowns_not_project_drilldowns(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleSummaryService(db_path=str(db))

    with pytest.raises(ValueError, match="unsupported_drilldown_type"):
        service.build_drilldown(
            "tropical",
            drilldown_type="duration_changes",
            as_of=date(2026, 7, 3),
        )

    duration = service.build_driver_drilldown(
        "tropical",
        drilldown_type="duration_changes",
        as_of=date(2026, 7, 3),
    )
    logic = service.build_driver_drilldown(
        "tropical",
        drilldown_type="logic_changes",
        as_of=date(2026, 7, 3),
    )

    assert duration["drilldown_type"] == "duration_changes"
    assert duration["comparison_context"]["comparison_basis"] == "prior_update"
    assert duration["comparison_context"]["previous_version_key"] == "tropical|S1|2026-06-01"
    assert logic["drilldown_type"] == "logic_changes"
    assert logic["comparison_context"]["comparison_basis"] == "prior_update"
