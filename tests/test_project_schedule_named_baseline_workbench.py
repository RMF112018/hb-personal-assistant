"""Phase 8 named baseline workbench parity tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_comparison_basis_resolver import (
    resolve_workbench_comparison_basis,
)
from hb_assistant.construction.analytics.project_schedule_controls_service import (
    ProjectScheduleControlsService,
)
from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
    ProjectScheduleNamedBaselineService,
)
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_baseline_selection import _operator
from tests.test_project_schedule_hub_api import _seed_comparable_versions
from tests.test_project_schedule_multi_baseline_controls import _seed_third_version
from tests.test_project_schedule_review_workbench import _seed_driver_chain, _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "named-workbench.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _seed_extra_baseline_version(db: Path) -> str:
    version_key = "tropical|S1|2026-05-01"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-early', 'tropical', 'xer', 'primavera_xer', 'committed',
              1, 0, 'not_cost_loaded', ?, 'TWNU17.xer', '2026-05-01')
            """,
            (version_key,),
        )
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_activities (
              project_key, schedule_id, schedule_version_key, import_id,
              source_type, source_format, activity_id, activity_name,
              start_date, finish_date, wbs_code, duration_remaining, is_milestone
            ) VALUES ('tropical', 'S1', ?, 'imp-early', 'xer', 'primavera_xer',
              'EARLY-A', 'Early baseline activity', '2026-05-01', '2026-05-10', 'WBS-E', '5', 0)
            """,
            (version_key,),
        )
        conn.commit()
    return version_key


def _select_named_contract_baseline(db: Path, version_key: str = "tropical|S1|2026-06-01") -> None:
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": version_key}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )


def test_resolver_rejects_unknown_basis() -> None:
    with pytest.raises(ValueError, match="invalid_comparison_basis"):
        resolve_workbench_comparison_basis("not_a_real_basis")


def test_resolver_named_slot_source_model() -> None:
    resolved = resolve_workbench_comparison_basis("current_contract_baseline")
    assert resolved.source_model == "named_slot"
    assert resolved.preview_basis == "baseline"
    assert resolved.comparison_basis == "current_contract_baseline"


def test_review_items_unknown_basis_returns_400(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    response = _client(db).get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "mystery_basis", "as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_comparison_basis"


def test_review_items_unknown_basis_does_not_coerce_to_prior_update(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    bad = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "mystery_basis"},
    )
    assert bad.status_code == 400
    good = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    )
    assert good.status_code == 200
    assert good.json()["available"] is True


def test_review_items_named_missing_returns_baseline_not_selected(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    body = _client(db).get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is False
    assert body["reason"] == "baseline_not_selected"
    assert body["comparison_basis"] == "current_contract_baseline"


def test_review_items_named_selected_live_preview(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    body = _client(db).get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert body["comparison_basis"] == "current_contract_baseline"
    workbench = body["workbench"]
    assert workbench["comparison_basis"] == "current_contract_baseline"
    assert workbench.get("synced") is False
    assert workbench.get("read_only_baseline_preview") is True
    assert workbench["baseline_context"]["schedule_version_key"] == "tropical|S1|2026-06-01"


def test_review_items_named_skips_disposition_carry_forward(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    repo.upsert_review_item(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        stable_item_key="driver:DRV-A",
        item_type="driver",
        item_title="Persisted driver",
        priority=90,
        evidence={"cue_summary": "persisted"},
        source_activity_id="DRV-A",
    )
    repo.update_review_item(
        review_item_id=str(
            repo.get_latest_review_item_by_stable_key(
                project_key="tropical", stable_item_key="driver:DRV-A"
            )["review_item_id"]
        ),
        review_status="watching",
        pm_notes="carried",
        reviewed_by_operator="operator",
    )
    items = _client(db).get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()["items"]
    driver_items = [item for item in items if item.get("source_activity_id") == "DRV-A"]
    assert driver_items
    assert all(item.get("review_item_id") is None for item in driver_items)
    assert all(item.get("review_status") == "open" for item in driver_items)


def test_post_named_baseline_sync_not_supported(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "named_baseline_sync_not_supported"


def test_post_unknown_basis_returns_400(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "mystery_basis"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_comparison_basis"


def test_post_legacy_baseline_preserves_preview_only_behavior(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    ProjectScheduleHubRepository(db_path=str(db)).set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key="tropical|S1|2026-06-01",
        selected_by_operator="operator",
    )
    body = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert body["workbench"]["sync"]["synced_count"] == 0


def test_driver_detail_named_basis_and_baseline_context(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    body = _client(db).get(
        "/api/projects/tropical/schedule/drivers/DRV-A/detail",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert body["comparison_basis"] == "current_contract_baseline"
    assert body["baseline_context"]["schedule_version_key"] == "tropical|S1|2026-06-01"


def test_driver_detail_accepts_basis_alias(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    body = _client(db).get(
        "/api/projects/tropical/schedule/drivers/DRV-A/detail",
        headers=_viewer(),
        params={"basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert body["comparison_basis"] == "current_contract_baseline"


def test_driver_detail_conflicting_params_returns_400(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    response = _client(db).get(
        "/api/projects/tropical/schedule/drivers/DRV-A/detail",
        headers=_viewer(),
        params={
            "basis": "prior_update",
            "comparison_basis": "current_contract_baseline",
            "as_of": "2026-07-03",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "conflicting_comparison_params"


def test_named_driver_detail_uses_named_slot_not_legacy_v90(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    early_key = _seed_extra_baseline_version(db)
    ProjectScheduleHubRepository(db_path=str(db)).set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key=early_key,
        selected_by_operator="operator",
    )
    _select_named_contract_baseline(db, version_key="tropical|S1|2026-06-01")
    body = ProjectScheduleSummaryService(db_path=str(db)).build_driver_detail(
        "tropical",
        "DRV-A",
        comparison_basis="current_contract_baseline",
        as_of=date(2026, 7, 3),
    )
    assert body["baseline_context"]["schedule_version_key"] == "tropical|S1|2026-06-01"
    assert body["baseline_context"]["schedule_version_key"] != early_key


def test_legacy_baseline_does_not_read_named_slots(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    early_key = _seed_extra_baseline_version(db)
    ProjectScheduleHubRepository(db_path=str(db)).set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key=early_key,
        selected_by_operator="operator",
    )
    _select_named_contract_baseline(db, version_key="tropical|S1|2026-06-01")
    with patch.object(
        ProjectScheduleNamedBaselineService,
        "resolve_slot_for_controls",
        side_effect=AssertionError("legacy_v90 must not read named slots"),
    ):
        body = ProjectScheduleSummaryService(db_path=str(db)).build_driver_detail(
            "tropical",
            "DRV-A",
            comparison_basis="baseline",
            as_of=date(2026, 7, 3),
        )
    assert body["available"] is True
    assert body["comparison_basis"] == "baseline"


def test_controls_reinstates_named_workbench_and_driver_links(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert "review_workbench" in payload["links"]
    assert "comparison_basis=current_contract_baseline" in payload["links"]["review_workbench"]
    assert "as_of=2026-07-03" in payload["links"]["review_workbench"]
    control = next(c for c in payload["top_controls"] if c.get("activity_id"))
    assert control["links"]["review_item"]
    assert "comparison_basis=current_contract_baseline" in control["links"]["review_item"]
    assert control["links"]["driver_detail"]
    assert "basis=current_contract_baseline" in control["links"]["driver_detail"]


def test_controls_and_routes_resolve_same_named_slot(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    controls = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    control = next(c for c in controls["top_controls"] if c.get("activity_id"))
    activity_id = str(control["activity_id"])
    workbench = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    driver = client.get(
        f"/api/projects/tropical/schedule/drivers/{activity_id}/detail",
        headers=_viewer(),
        params={"basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    slot_key = workbench["workbench"]["baseline_context"]["schedule_version_key"]
    assert driver["baseline_context"]["schedule_version_key"] == slot_key
    assert controls["baseline_context"]["baseline_schedule_version_key"] == slot_key


def test_all_three_named_slots_supported_on_workbench(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_third_version(db)
    svc = ProjectScheduleNamedBaselineService(db_path=str(db))
    svc.update_baselines(
        "tropical",
        selections={
            "current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"},
            "previous_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-06-15"},
            "secondary_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-05-01"},
        },
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    client = _client(db)
    for basis in (
        "current_contract_baseline",
        "previous_progress_update_baseline",
        "secondary_progress_update_baseline",
    ):
        body = client.get(
            "/api/projects/tropical/schedule/review-items",
            headers=_viewer(),
            params={"comparison_basis": basis, "as_of": "2026-07-03"},
        ).json()
        assert body["available"] is True
        assert body["comparison_basis"] == basis


def test_prior_update_sync_still_runs(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    body = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert body["workbench"]["sync"]["synced_count"] >= 1
