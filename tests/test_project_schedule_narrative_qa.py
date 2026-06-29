"""Tests for deterministic schedule narrative QA gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.construction.analytics.project_schedule_memo_service import ProjectScheduleMemoService
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_summary
from hb_assistant.construction.analytics.project_schedule_summary_service import ProjectScheduleSummaryService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "narrative-qa.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def test_validate_summary_passes_for_driver_fixture(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    summary = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical",
        as_of=__import__("datetime").date(2026, 7, 3),
    )
    qa = summary["narrative_qa"]
    assert qa["passed"] is True
    assert qa["advisory_posture"] == "sequence_cues_not_causation"
    assert "forecast_finish" in qa["source_basis"]


def test_validate_summary_flags_forbidden_terms() -> None:
    summary = {
        "schedule_story": {
            "headline": "Owner-caused delay moved the finish.",
            "synopsis": "Review needed.",
            "what_changed": "Movement detected.",
            "why_it_matters": "Pressure remains.",
            "primary_change_driver": "Driver review.",
        },
        "command_summary": {},
        "change_impact": {"available": False},
        "change_driver_analysis": {"available": False},
        "review_workbench": {"available": False},
    }
    qa = validate_summary(summary)
    assert qa["passed"] is False
    assert any(v["code"] == "forbidden_term" for v in qa["violations"])


def test_memo_export_blocked_on_narrative_qa_failure() -> None:
    summary = {
        "project_key": "tropical",
        "project_display_name": "Tropical",
        "as_of_date": "2026-07-03",
        "schedule_story": {
            "headline": "Claim impact confirmed.",
            "synopsis": "Bad wording.",
            "what_changed": "Changed.",
            "why_it_matters": "Matters.",
            "primary_change_driver": "Driver.",
        },
        "command_summary": {},
        "change_impact": {"available": False},
        "change_driver_analysis": {"available": False},
        "review_workbench": {"available": False},
    }
    export = ProjectScheduleMemoService().build_export(summary, export_format="markdown")
    assert export["available"] is False
    assert export["reason"] == "narrative_qa_failed"


def test_memo_export_includes_source_basis_footnotes(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    summary = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical",
        as_of=__import__("datetime").date(2026, 7, 3),
    )
    export = ProjectScheduleMemoService().build_export(summary, export_format="markdown")
    assert export["available"] is True
    assert "Source Basis" in export["body"]
    assert "command_summary.forecast_finish" in export["body"]