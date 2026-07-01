"""Phase 17 review action API and promotion tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _fresh_db, _operator, _seed_driver_chain, _viewer


def _client(db: Path) -> TestClient:
    app = create_app(db_path=str(db))
    return TestClient(app)


def test_operator_can_patch_disposition_with_legacy_alias(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    sync = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"as_of": "2026-07-03"},
    )
    assert sync.status_code == 200
    items = client.get(
        "/api/projects/tropical/schedule/review-items",
        headers=_viewer(),
        params={"as_of": "2026-07-03"},
    ).json()["items"]
    persisted = next(item for item in items if item.get("review_item_id"))
    patch = client.patch(
        f"/api/projects/tropical/schedule/review-items/{persisted['review_item_id']}",
        headers=_operator(),
        json={"disposition": "reviewed", "pm_notes": "follow up"},
    )
    assert patch.status_code == 200
    assert patch.json()["item"]["review_status"] == "accepted_for_follow_up"


def test_non_operator_patch_rejected(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    client.post("/api/projects/tropical/schedule/review-items", headers=_operator(), params={"as_of": "2026-07-03"})
    item_id = client.get(
        "/api/projects/tropical/schedule/review-items",
        params={"as_of": "2026-07-03"},
    ).json()["items"][0]["review_item_id"]
    response = client.patch(
        f"/api/projects/tropical/schedule/review-items/{item_id}",
        headers=_viewer(),
        json={"disposition": "dismissed_not_material", "disposition_reason": "not material"},
    )
    assert response.status_code == 403


def test_reason_required_for_dismiss_backend(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    client.post("/api/projects/tropical/schedule/review-items", headers=_operator(), params={"as_of": "2026-07-03"})
    item_id = next(
        row["review_item_id"]
        for row in client.get("/api/projects/tropical/schedule/review-items", params={"as_of": "2026-07-03"}).json()[
            "items"
        ]
        if row.get("review_item_id")
    )
    response = client.patch(
        f"/api/projects/tropical/schedule/review-items/{item_id}",
        headers=_operator(),
        json={"disposition": "dismissed_not_material"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "disposition_reason_required"


def test_promote_preview_cue_idempotent(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    preview = client.get(
        "/api/projects/tropical/schedule/review-items",
        params={"as_of": "2026-07-03"},
    ).json()
    preview_item = next(item for item in preview["items"] if not item.get("review_item_id"))
    stable_key = preview_item["stable_item_key"]
    body = {"stable_item_keys": [stable_key]}
    first = client.post(
        "/api/projects/tropical/schedule/review-items/promote",
        headers=_operator(),
        params={"as_of": "2026-07-03"},
        json=body,
    )
    assert first.status_code == 200
    assert first.json()["promoted_count"] == 1
    second = client.post(
        "/api/projects/tropical/schedule/review-items/promote",
        headers=_operator(),
        params={"as_of": "2026-07-03"},
        json=body,
    )
    assert second.status_code == 200
    assert second.json()["promoted_count"] == 0
    assert second.json()["skipped_duplicate_count"] == 1
    with sqlite3.connect(db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM project_schedule_review_items WHERE stable_item_key=?",
            (stable_key,),
        ).fetchone()[0]
        event_count = conn.execute(
            """
            SELECT COUNT(*) FROM project_schedule_review_item_events e
            JOIN project_schedule_review_items i ON i.review_item_id = e.review_item_id
            WHERE i.stable_item_key=?
            """,
            (stable_key,),
        ).fetchone()[0]
    assert count == 1
    assert event_count == 1


def test_project_mismatch_rejected(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    client.post("/api/projects/tropical/schedule/review-items", headers=_operator(), params={"as_of": "2026-07-03"})
    item_id = client.get("/api/projects/tropical/schedule/review-items", params={"as_of": "2026-07-03"}).json()[
        "items"
    ][0]["review_item_id"]
    response = client.patch(
        f"/api/projects/wrong/schedule/review-items/{item_id}",
        headers=_operator(),
        json={"disposition": "needs_review"},
    )
    assert response.status_code == 403
