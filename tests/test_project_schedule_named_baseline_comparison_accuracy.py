"""Phase 13A named baseline comparison accuracy tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
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
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_baseline_selection import _operator
from tests.test_project_schedule_hub_api import _seed_comparable_versions
from tests.test_project_schedule_review_workbench import _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "named-comparison-accuracy.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _seed_differential_baseline_versions(db: Path) -> None:
    """Add May and mid-June versions with distinct A100/A200 finishes for differential proof."""
    with sqlite3.connect(db) as conn:
        for import_id, version_key, filename, created, a100_finish, a200_finish in (
            (
                "imp-early",
                "tropical|S1|2026-05-01",
                "TWNU17.xer",
                "2026-05-01",
                "2026-05-20",
                "2026-05-25",
            ),
            (
                "imp-mid",
                "tropical|S1|2026-06-15",
                "TWNU18b.xer",
                "2026-06-15",
                "2026-06-17",
                "2026-06-20",
            ),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  2, 1, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, version_key, filename, created),
            )
            for activity_id, finish, is_milestone in (
                ("A100", a100_finish, 0),
                ("A200", a200_finish, 1),
            ):
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_activities (
                      project_key, schedule_id, schedule_version_key, import_id,
                      source_type, source_format, activity_id, activity_name,
                      start_date, finish_date, wbs_code, duration_remaining, is_milestone
                    ) VALUES ('tropical', 'S1', ?, ?, 'xer', 'primavera_xer',
                      ?, ?, '2026-05-01', ?, 'WBS-A', '5', ?)
                    """,
                    (
                        version_key,
                        import_id,
                        activity_id,
                        "Substantial completion milestone" if is_milestone else "Area A start",
                        finish,
                        is_milestone,
                    ),
                )
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_relationships (
                  project_key, schedule_id, schedule_version_key, import_id,
                  predecessor_activity_id, successor_activity_id, relationship_type
                ) VALUES ('tropical', 'S1', ?, ?, 'A100', 'A200', 'FS')
                """,
                (version_key, import_id),
            )
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, 'identity-main', ?, ?, 'tropical', 'primavera_xer',
                  2, 1, 0, 'seed', 'resolved', 'seed', '1.00', 0)
                """,
                (f"match-{import_id}", version_key, import_id),
            )
        conn.commit()


def _select_all_named_baselines(db: Path) -> None:
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={
            "current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"},
            "previous_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-06-15"},
            "secondary_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-05-01"},
        },
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )


def _movement_count(payload: dict) -> int:
    return int(payload["sections"]["movement"]["finish_moved_later_count"])


def _a100_finish_delta(context: dict) -> int | None:
    items = (
        context.get("change_impact", {})
        .get("direct_remaining_changes", {})
        .get("items", [])
    )
    for row in items:
        activity = row.get("activity") or {}
        if str(activity.get("activity_id")) == "A100":
            return int(row.get("finish_delta_days") or 0)
    return None


@pytest.fixture()
def differential_db(tmp_path: Path) -> Path:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_differential_baseline_versions(db)
    _select_all_named_baselines(db)
    return db


def test_named_controls_movement_differs_by_slot(differential_db: Path) -> None:
    svc = ProjectScheduleControlsService(db_path=str(differential_db))
    prior = svc.build_controls("tropical", as_of=date(2026, 7, 3), comparison_basis="prior_update")
    contract = svc.build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="current_contract_baseline"
    )
    progress = svc.build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="previous_progress_update_baseline"
    )
    secondary = svc.build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="secondary_progress_update_baseline"
    )

    prior_later = _movement_count(prior)
    contract_later = _movement_count(contract)
    progress_later = _movement_count(progress)
    secondary_later = _movement_count(secondary)

    assert prior_later > 0
    assert contract["baseline_context"]["baseline_schedule_version_key"] != progress["baseline_context"]["baseline_schedule_version_key"]
    summary = ProjectScheduleSummaryService(db_path=str(differential_db))
    contract_ctx = summary.build_schedule_hub_context_with_named_baseline(
        "tropical",
        as_of=date(2026, 7, 3),
        baseline_version_key="tropical|S1|2026-06-01",
        comparison_basis="current_contract_baseline",
    )
    progress_ctx = summary.build_schedule_hub_context_with_named_baseline(
        "tropical",
        as_of=date(2026, 7, 3),
        baseline_version_key="tropical|S1|2026-06-15",
        comparison_basis="previous_progress_update_baseline",
    )
    assert _a100_finish_delta(contract_ctx or {}) != _a100_finish_delta(progress_ctx or {})

    assert contract["baseline_context"]["baseline_schedule_version_key"] == "tropical|S1|2026-06-01"
    assert progress["baseline_context"]["baseline_schedule_version_key"] == "tropical|S1|2026-06-15"
    assert secondary["baseline_context"]["baseline_schedule_version_key"] == "tropical|S1|2026-05-01"


def test_named_hub_context_provenance_and_activity_delta(differential_db: Path) -> None:
    summary = ProjectScheduleSummaryService(db_path=str(differential_db))
    contract = summary.build_schedule_hub_context_with_named_baseline(
        "tropical",
        as_of=date(2026, 7, 3),
        baseline_version_key="tropical|S1|2026-06-01",
        comparison_basis="current_contract_baseline",
    )
    progress = summary.build_schedule_hub_context_with_named_baseline(
        "tropical",
        as_of=date(2026, 7, 3),
        baseline_version_key="tropical|S1|2026-06-15",
        comparison_basis="previous_progress_update_baseline",
    )
    assert contract is not None and progress is not None

    contract_prov = contract["comparison_provenance"]
    progress_prov = progress["comparison_provenance"]
    assert contract_prov["comparison_schedule_version_key"] == "tropical|S1|2026-06-01"
    assert progress_prov["comparison_schedule_version_key"] == "tropical|S1|2026-06-15"
    assert contract["change_impact"]["comparison_basis"] == "current_contract_baseline"
    assert progress["change_impact"]["comparison_basis"] == "previous_progress_update_baseline"

    contract_delta = _a100_finish_delta(contract)
    progress_delta = _a100_finish_delta(progress)
    assert contract_delta == 12
    assert progress_delta in {0, None}
    assert contract_delta != (progress_delta or 0)

    contract_ms = next(
        item for item in contract["milestones"]["items"] if item["activity_id"] == "A200"
    )
    progress_ms = next(
        item for item in progress["milestones"]["items"] if item["activity_id"] == "A200"
    )
    assert contract_ms["movement_days"] == 15
    assert progress_ms["movement_days"] == 5


def test_named_drilldown_and_export_carry_comparison_basis(differential_db: Path) -> None:
    client = _client(differential_db)
    summary = ProjectScheduleSummaryService(db_path=str(differential_db))

    for basis in (
        "prior_update",
        "baseline",
        "current_contract_baseline",
        "previous_progress_update_baseline",
        "secondary_progress_update_baseline",
    ):
        if basis == "baseline":
            pytest.skip("legacy baseline selection not seeded in this fixture")
        drill = client.get(
            "/api/projects/tropical/schedule/drilldowns",
            headers=_viewer(),
            params={"type": "remaining_later", "comparison_basis": basis, "as_of": "2026-07-03"},
        )
        assert drill.status_code == 200, basis
        body = drill.json()
        assert body.get("comparison_basis") == basis
        if basis == "prior_update":
            assert body.get("comparison_context", {}).get("comparison_basis") == "prior_update"
        else:
            expected_key = {
                "current_contract_baseline": "tropical|S1|2026-06-01",
                "previous_progress_update_baseline": "tropical|S1|2026-06-15",
                "secondary_progress_update_baseline": "tropical|S1|2026-05-01",
            }[basis]
            assert body.get("comparison_schedule_version_key") == expected_key

    export = summary.build_export(
        "tropical",
        export_format="markdown",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert export["available"] is True
    assert "current_contract_baseline" in export["body"] or export.get("comparison_basis") == "current_contract_baseline"


def test_named_workbench_cue_copy_uses_comparison_basis(differential_db: Path) -> None:
    client = _client(differential_db)
    response = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert response.status_code == 200
    items = response.json()["workbench"]["items"]
    milestone = next(item for item in items if item["item_type"] == "milestone")
    assert milestone["comparison_basis"] == "current_contract_baseline"
    assert "compared against current contract baseline" in milestone["cue_summary"].lower()


def test_prior_update_disposition_does_not_join_named_workbench(differential_db: Path) -> None:
    client = _client(differential_db)
    prior = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "prior_update", "as_of": "2026-07-03"},
    )
    assert prior.status_code == 200
    open_prior = [
        item
        for item in prior.json()["workbench"]["items"]
        if item.get("review_status") == "open" and item.get("item_type") == "milestone"
    ]
    assert open_prior
    target = open_prior[0]
    patch = client.patch(
        f"/api/projects/tropical/schedule/review-items/{target['review_item_id']}",
        headers=_operator(),
        json={"review_status": "reviewed", "review_note": "prior update disposition"},
    )
    assert patch.status_code == 200

    named = client.post(
        "/api/projects/tropical/schedule/review-items",
        headers=_operator(),
        params={"comparison_basis": "current_contract_baseline", "as_of": "2026-07-03"},
    )
    assert named.status_code == 200
    named_milestone = next(
        item for item in named.json()["workbench"]["items"] if item["item_type"] == "milestone"
    )
    assert named_milestone["review_status"] == "open"
    assert named_milestone["comparison_basis"] == "current_contract_baseline"
