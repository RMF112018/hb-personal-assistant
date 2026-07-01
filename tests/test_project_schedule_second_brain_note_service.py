"""Tests for ProjectScheduleSecondBrainNoteService."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.project_schedule_second_brain_note_service import (
    ProjectScheduleSecondBrainNoteService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "note-source.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(db)
    return db


def test_note_source_contains_required_fields(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    svc = ProjectScheduleSecondBrainNoteService(db_path=str(db))
    payload = svc.build_note_source(
        "schedule_update",
        project_key="tropical",
        as_of=date(2026, 7, 3),
    )
    for key in (
        "note_type",
        "project_key",
        "project_label",
        "comparison_basis",
        "analytics_trust_status",
        "review_status",
        "safe_links",
        "capability_limitations",
        "body_markdown",
    ):
        assert key in payload


def test_note_source_has_no_redaction_leaks(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    svc = ProjectScheduleSecondBrainNoteService(db_path=str(db))
    payload = svc.build_note_source(
        "controls_snapshot",
        project_key="tropical",
        as_of=date(2026, 7, 3),
    )
    assert not find_redaction_leaks(payload)


def test_portfolio_snapshot_source(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    svc = ProjectScheduleSecondBrainNoteService(db_path=str(db))
    payload = svc.build_note_source("portfolio_snapshot", as_of=date(2026, 7, 3))
    assert payload["note_type"] == "portfolio_snapshot"
    assert payload.get("portfolio_summary") is not None


def test_idempotency_key_stable(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    svc = ProjectScheduleSecondBrainNoteService(db_path=str(db))
    payload = svc.build_note_source(
        "baseline_comparison",
        project_key="tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert svc.idempotency_key(payload) == svc.idempotency_key(payload)
