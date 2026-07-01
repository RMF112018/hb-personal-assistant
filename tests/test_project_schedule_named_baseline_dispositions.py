"""Phase 13 named-baseline review disposition persistence tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from hb_assistant.store.project_schedule_named_baseline_review_repository import (
    NAMED_REVIEW_ITEM_ID_PREFIX,
    ProjectScheduleNamedBaselineReviewRepository,
)
from tests.test_project_schedule_baseline_selection import _operator
from tests.test_project_schedule_named_baseline_workbench import (
    _client,
    _fresh_db,
    _select_named_contract_baseline,
)
from tests.test_project_schedule_review_workbench import _seed_driver_chain, _viewer


def _select_named_progress_baseline(db: Path, version_key: str = "tropical|S1|2026-05-01") -> None:
    from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
        ProjectScheduleNamedBaselineService,
    )
    from tests.test_project_schedule_named_baseline_workbench import _seed_extra_baseline_version

    if version_key == "tropical|S1|2026-05-01":
        _seed_extra_baseline_version(db)
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, wbs_code, duration_remaining, is_milestone
                ) VALUES ('tropical', 'S1', 'tropical|S1|2026-05-01', 'imp-early', 'xer', 'primavera_xer',
                  'DRV-A', 'Driver Activity', '2026-06-20', '2026-06-30', 'WBS-A', '10', 0)
                """
            )
            conn.commit()
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"previous_progress_update_baseline": {"schedule_version_key": version_key}},
        selected_by="operator",
    )


def test_named_post_sync_materializes_items(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["workbench"]["review_scope"] == "named_baseline"
    assert body["workbench"]["synced"] is True
    assert body["workbench"]["sync"]["synced_count"] >= 1
    persisted = [
        item for item in body["workbench"]["items"] if str(item.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    ]
    assert persisted


def test_named_get_returns_persisted_after_sync(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    body = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    assert body["available"] is True
    assert any(str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX) for i in body["items"])


def test_named_patch_updates_status_and_notes(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    synced = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    item = next(
        i for i in synced["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    review_item_id = str(item["review_item_id"])
    patched = client.patch(
        f"/api/projects/tropical/schedule/review-items/{review_item_id}",
        headers=_operator(),
        json={"review_status": "watching", "pm_notes": "named follow-up"},
    ).json()
    assert patched["item"]["review_status"] == "needs_review"
    assert patched["item"]["pm_notes"] == "named follow-up"


def test_named_patch_records_event(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    synced = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    review_item_id = next(
        str(i["review_item_id"])
        for i in synced["workbench"]["items"]
        if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{review_item_id}",
        headers=_operator(),
        json={"review_status": "dismissed", "disposition_reason": "not material"},
    )
    events = client.get(
        f"/api/projects/tropical/schedule/review-items/{review_item_id}/events",
        headers=_viewer(),
    ).json()
    assert any(e.get("event_type") == "status_changed" for e in events["events"])


def test_named_rehydrates_disposition_same_scope(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    synced = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    item = next(
        i for i in synced["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    review_item_id = str(item["review_item_id"])
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{review_item_id}",
        headers=_operator(),
        json={"review_status": "reviewed", "pm_notes": "kept"},
    )
    reloaded = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    match = next(i for i in reloaded["items"] if str(i.get("review_item_id")) == review_item_id)
    assert match["review_status"] == "accepted_for_follow_up"
    assert match["pm_notes"] == "kept"


def test_different_named_slot_does_not_inherit_disposition(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    _select_named_progress_baseline(db)
    client = _client(db)
    contract_sync = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    contract_item = next(
        i for i in contract_sync["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    stable = str(contract_item["stable_item_key"])
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{contract_item['review_item_id']}",
        headers=_operator(),
        json={"review_status": "watching"},
    )
    client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "previous_progress_update_baseline", "as_of": "2026-07-03"},
    )
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT comparison_basis, review_status, source_stable_key
            FROM project_schedule_named_baseline_review_items
            WHERE source_stable_key=?
            """,
            (stable,),
        ).fetchall()
    assert rows
    contract_rows = [r for r in rows if r["comparison_basis"] == "current_contract_baseline"]
    progress_rows = [r for r in rows if r["comparison_basis"] == "previous_progress_update_baseline"]
    assert contract_rows and progress_rows
    assert all(r["review_status"] == "needs_review" for r in contract_rows)
    assert all(r["review_status"] == "needs_review" for r in progress_rows)


def test_different_baseline_version_does_not_inherit_disposition(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-may', 'tropical', 'xer', 'primavera_xer', 'committed',
              4, 3, 'not_cost_loaded', 'tropical|S1|2026-05-01', 'TWNU05.xer', '2026-05-01')
            """,
        )
        for row in (
            ("tropical|S1|2026-05-01", "imp-may", "DRV-A", "Driver Activity", "2026-06-20", "2026-06-30"),
            ("tropical|S1|2026-05-01", "imp-may", "SUCC-B", "Successor B", "2026-07-01", "2026-07-10"),
        ):
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, wbs_code, duration_remaining, is_milestone
                ) VALUES ('tropical', 'S1', ?, ?, 'xer', 'primavera_xer', ?, ?, ?, ?, 'WBS-A', '5', 0)
                """,
                row,
            )
        conn.commit()
    _select_named_contract_baseline(db, version_key="tropical|S1|2026-06-01")
    client = _client(db)
    synced = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    item = next(
        i for i in synced["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{item['review_item_id']}",
        headers=_operator(),
        json={"review_status": "dismissed", "disposition_reason": "not material", "pm_notes": "v1"},
    )
    from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
        ProjectScheduleNamedBaselineService,
    )

    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-05-01"}},
        selected_by="operator",
    )
    client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT review_status, baseline_schedule_version_key
            FROM project_schedule_named_baseline_review_items
            WHERE source_stable_key=?
            ORDER BY baseline_schedule_version_key
            """,
            (str(item["stable_item_key"]),),
        ).fetchall()
    assert len(rows) >= 2
    june = [r for r in rows if r["baseline_schedule_version_key"] == "tropical|S1|2026-06-01"]
    may = [r for r in rows if r["baseline_schedule_version_key"] == "tropical|S1|2026-05-01"]
    assert june and may
    assert june[0]["review_status"] == "dismissed_not_material"
    assert may[0]["review_status"] == "needs_review"


def test_prior_update_unaffected_by_named_sync(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    prior = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    ).json()
    prior_item = next(i for i in prior["workbench"]["items"] if i.get("review_item_id"))
    prior_id = str(prior_item["review_item_id"])
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{prior_id}",
        headers=_operator(),
        json={"review_status": "watching", "pm_notes": "prior only"},
    )
    client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    prior_reload = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    ).json()
    match = next(i for i in prior_reload["items"] if str(i.get("review_item_id")) == prior_id)
    assert match["review_status"] == "needs_review"
    assert match["pm_notes"] == "prior only"
    assert not str(prior_id).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)


def test_patch_isolation_named_does_not_mutate_prior_update(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    prior = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    ).json()
    prior_id = str(next(i for i in prior["workbench"]["items"] if i.get("review_item_id"))["review_item_id"])
    named = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    named_id = str(
        next(
            i for i in named["workbench"]["items"]
            if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
        )["review_item_id"]
    )
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{named_id}",
        headers=_operator(),
        json={"review_status": "dismissed", "disposition_reason": "not material", "pm_notes": "named only"},
    )
    repo = ProjectScheduleHubRepository(db_path=str(db))
    prior_row = repo.get_review_item(review_item_id=prior_id)
    assert prior_row is not None
    assert prior_row["review_status"] == "needs_review"
    assert prior_row.get("pm_notes") in (None, "")


def test_patch_isolation_named_slot_separate_rows(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    _select_named_progress_baseline(db)
    client = _client(db)
    contract = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    contract_id = str(
        next(
            i for i in contract["workbench"]["items"]
            if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
        )["review_item_id"]
    )
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{contract_id}",
        headers=_operator(),
        json={"review_status": "reviewed"},
    )
    progress = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "previous_progress_update_baseline", "as_of": "2026-07-03"},
    ).json()
    progress_ids = [
        str(i["review_item_id"])
        for i in progress["workbench"]["items"]
        if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    ]
    assert progress_ids
    named_repo = ProjectScheduleNamedBaselineReviewRepository(db_path=str(db))
    contract_row = named_repo.get_review_item(review_item_id=contract_id)
    assert contract_row is not None
    assert contract_row["review_status"] == "accepted_for_follow_up"
    for pid in progress_ids:
        row = named_repo.get_review_item(review_item_id=pid)
        assert row is not None
        assert row["comparison_basis"] == "previous_progress_update_baseline"
        assert row["review_status"] == "needs_review"


def test_legacy_baseline_preview_unchanged(tmp_path: Path) -> None:
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
    assert body["workbench"]["sync"]["synced_count"] == 0


def test_missing_named_baseline_cannot_sync(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "baseline_not_selected"


def test_invalid_named_baseline_cannot_sync(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO project_schedule_named_baseline_slots (
              selection_id, project_key, slot_key, schedule_version_key,
              display_name, selected_by, selected_at, is_active
            ) VALUES ('sel-bad', 'tropical', 'current_contract_baseline', 'tropical|S1|2099-01-01',
              'Bad baseline', 'operator', '2026-07-01', 1)
            """
        )
        conn.commit()
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "baseline_invalid"


def test_unknown_comparison_basis_rejects(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    response = _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "mystery_basis"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_comparison_basis"


def test_named_items_use_scoped_identity_columns(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    _client(db).post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM project_schedule_named_baseline_review_items LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row["review_scope"] == "named_baseline"
    assert row["comparison_basis"] == "current_contract_baseline"
    assert row["source_metric_key"]
    assert row["source_signal_type"]
    assert row["source_stable_key"]


def test_named_skips_prior_update_carry_forward(tmp_path: Path) -> None:
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
    assert all(item.get("review_status") == "needs_review" for item in driver_items if not item.get("review_item_id"))


def _driver_detail(client: TestClient, activity_id: str, basis: str) -> dict:
    response = client.get(
        "/api/projects/tropical/schedule/drivers/detail",
        params={"activity_id": activity_id, "comparison_basis": basis, "as_of": "2026-07-03"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_driver_detail_prior_update_disposition(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
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
    row = repo.get_review_item_for_version_scope(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        stable_item_key="driver:DRV-A",
        source_activity_id="DRV-A",
    )
    repo.update_review_item(
        review_item_id=str(row["review_item_id"]),
        review_status="watching",
        pm_notes="prior",
        reviewed_by_operator="operator",
    )
    detail = _driver_detail(_client(db), "DRV-A", "prior_update")
    assert detail["review_status"] == "needs_review"
    assert str(detail["review_item_id"]).startswith("psri-")
    assert detail["disposition_source"] == "prior_update_review"


def test_driver_detail_named_disposition_after_sync(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    client = _client(db)
    synced = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    item = next(
        i for i in synced["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{item['review_item_id']}",
        headers=_operator(),
        json={"review_status": "watching"},
    )
    detail = _driver_detail(client, str(item.get("source_activity_id") or "DRV-A"), "current_contract_baseline")
    assert detail["review_status"] == "needs_review"
    assert str(detail["review_item_id"]).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    assert detail["disposition_source"] == "named_baseline_review"


def test_driver_detail_named_open_when_not_persisted(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    detail = _driver_detail(_client(db), "DRV-A", "current_contract_baseline")
    assert detail["review_status"] == "needs_review"
    assert detail["review_item_id"] is None
    assert detail["disposition_source"] == "preview"


def test_driver_detail_named_does_not_bleed_prior_update_disposition(tmp_path: Path) -> None:
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
        evidence={},
        source_activity_id="DRV-A",
    )
    row = repo.get_review_item_for_version_scope(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        stable_item_key="driver:DRV-A",
        source_activity_id="DRV-A",
    )
    repo.update_review_item(
        review_item_id=str(row["review_item_id"]),
        review_status="reviewed",
        reviewed_by_operator="operator",
    )
    detail = _driver_detail(_client(db), "DRV-A", "current_contract_baseline")
    assert detail["review_status"] == "needs_review"
    assert detail["disposition_source"] == "preview"


def test_driver_detail_slot_isolation_for_disposition(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _select_named_contract_baseline(db)
    _select_named_progress_baseline(db)
    client = _client(db)
    contract_sync = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    ).json()
    contract_item = next(
        i for i in contract_sync["workbench"]["items"] if str(i.get("review_item_id", "")).startswith(NAMED_REVIEW_ITEM_ID_PREFIX)
    )
    activity_id = str(contract_item.get("source_activity_id") or "DRV-A")
    client.patch(
        f"/api/projects/tropical/schedule/review-items/{contract_item['review_item_id']}",
        headers=_operator(),
        json={"review_status": "watching"},
    )
    contract_detail = _driver_detail(client, activity_id, "current_contract_baseline")
    progress_detail = _driver_detail(client, activity_id, "previous_progress_update_baseline")
    assert contract_detail["review_status"] == "needs_review"
    assert progress_detail["review_status"] == "needs_review"
