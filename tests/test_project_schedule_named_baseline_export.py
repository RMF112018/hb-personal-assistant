"""Phase 13C named-baseline export production-readiness tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_memo_service import ProjectScheduleMemoService
from hb_assistant.construction.analytics.project_schedule_named_baseline_service import (
    ProjectScheduleNamedBaselineService,
)
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_named_baseline_comparison_accuracy import (
    _client,
    _fresh_db,
    _seed_differential_baseline_versions,
    _select_all_named_baselines,
)
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _seed_named_export_fixture(db: Path) -> None:
    _seed_comparable_versions(db)
    _seed_differential_baseline_versions(db)
    _select_all_named_baselines(db)


def _export_body(client: TestClient, basis: str, *, fmt: str = "markdown") -> str:
    response = client.get(
        "/api/projects/tropical/schedule/export",
        params={"format": fmt, "comparison_basis": basis, "as_of": "2026-07-03"},
    )
    assert response.status_code == 200, response.text
    return response.text


@pytest.mark.parametrize(
    ("basis", "version_key", "slot_label", "expected_later"),
    [
        ("current_contract_baseline", "tropical|S1|2026-06-01", "Current Contract Baseline", 2),
        ("previous_progress_update_baseline", "tropical|S1|2026-06-15", "Previous Progress Update Baseline", 1),
        ("secondary_progress_update_baseline", "tropical|S1|2026-05-01", "Secondary Progress Update Baseline", 2),
    ],
)
def test_named_markdown_export_includes_slot_context_and_movement(
    tmp_path: Path,
    basis: str,
    version_key: str,
    slot_label: str,
    expected_later: int,
) -> None:
    db = _fresh_db(tmp_path)
    _seed_named_export_fixture(db)
    body = _export_body(_client(db), basis)
    assert slot_label in body
    assert version_key in body
    assert f"{expected_later} remaining activities moved later" in body
    assert "compared against prior update" not in body.lower()


def test_named_html_export_succeeds(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_named_export_fixture(db)
    body = _export_body(_client(db), "current_contract_baseline", fmt="html")
    assert "Comparison Context" in body
    assert "tropical|S1|2026-06-01" in body


def test_named_export_uses_deterministic_fallback_when_narrative_qa_fails(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_named_export_fixture(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    with patch(
        "hb_assistant.construction.analytics.project_schedule_memo_service.validate_summary",
        return_value={"passed": False, "violations": [{"code": "test"}], "advisory_posture": "sequence_cues_not_causation"},
    ):
        payload = service.build_export(
            "tropical",
            export_format="markdown",
            as_of=date(2026, 7, 3),
            comparison_basis="current_contract_baseline",
        )
    assert payload.get("available") is True
    assert payload.get("export_mode") == "deterministic_fallback"
    assert "Narrative QA unavailable" in (payload.get("body") or "")
    assert "tropical|S1|2026-06-01" in (payload.get("body") or "")


def test_named_export_does_not_fallback_to_prior_update_counts(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_named_export_fixture(db)
    client = _client(db)
    prior = _export_body(client, "prior_update")
    contract = _export_body(client, "current_contract_baseline")
    secondary = _export_body(client, "secondary_progress_update_baseline")
    assert prior != contract
    assert contract != secondary


def test_named_export_unavailable_when_slot_missing(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_differential_baseline_versions(db)
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    response = _client(db).get(
        "/api/projects/tropical/schedule/export",
        params={
            "format": "markdown",
            "comparison_basis": "secondary_progress_update_baseline",
            "as_of": "2026-07-03",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] in {"baseline_not_selected", "comparison_context_incomplete", "export_unavailable"}


def test_memo_export_comparison_context_complete_guard() -> None:
    from hb_assistant.construction.analytics.project_schedule_memo_service import (
        _export_comparison_context_complete,
    )

    assert _export_comparison_context_complete(
        {
            "project_key": "tropical",
            "as_of": "2026-07-03",
            "comparison_basis": "current_contract_baseline",
            "comparison_label": "Compared against Current Contract Baseline",
            "source_model": "named_slot",
            "slot_key": "current_contract_baseline",
            "slot_label": "Current Contract Baseline",
            "current_schedule_version_key": "tropical|A",
            "comparison_schedule_version_key": "tropical|B",
            "baseline_schedule_version_key": "tropical|B",
        }
    )
    assert not _export_comparison_context_complete({"comparison_basis": "current_contract_baseline"})
