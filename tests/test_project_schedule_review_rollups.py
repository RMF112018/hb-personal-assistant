"""Phase 17 review rollup read model tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_review_rollup_service import build_review_status_rollup
from tests.test_project_schedule_review_workbench import _fresh_db, _operator, _seed_driver_chain, _viewer


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def test_rollup_counts_preview_and_persisted_separately() -> None:
    rollup = build_review_status_rollup(
        items=[{"review_item_id": "psri-1", "review_status": "needs_review"}],
        preview_items=[{"review_item_id": None, "review_status": "needs_review", "stable_item_key": "cue-1"}],
    )
    assert rollup["persisted_item_count"] == 1
    assert rollup["preview_cue_count"] == 1
    assert rollup["needs_review"] == 1
    assert rollup["pm_summary"]


def test_hub_includes_review_rollup(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    hub = client.get("/api/projects/tropical/schedule", params={"as_of": "2026-07-03"}).json()
    review = hub.get("review_workbench") or {}
    status = review.get("review_status") or review.get("summary") or {}
    assert "preview_cue_count" in status
    assert "recommended_next_action" in status


def test_workbench_includes_review_rollup(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    body = client.get(
        "/api/projects/tropical/schedule/review-items",
        params={"as_of": "2026-07-03"},
    ).json()
    workbench = body.get("workbench") or {}
    status = workbench.get("review_status") or workbench.get("summary") or {}
    assert "persisted_item_count" in status
    assert "preview_cue_count" in status


def test_controls_includes_review_rollup(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    controls = client.get("/api/projects/tropical/schedule/controls", params={"as_of": "2026-07-03"}).json()
    review = (controls.get("sections") or {}).get("review_workbench") or {}
    assert review.get("review_status")
