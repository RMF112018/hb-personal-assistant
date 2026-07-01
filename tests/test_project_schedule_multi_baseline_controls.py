"""Phase 7 multi-baseline schedule controls tests."""

from __future__ import annotations

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
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_controls_text
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_baseline_selection import _operator
from tests.test_project_schedule_hub_api import _seed_comparable_versions
from tests.test_project_schedule_review_workbench import _seed_driver_chain, _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "multi-baseline.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _select_contract_baseline(client: TestClient) -> None:
    response = client.put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        json={
            "selections": {
                "current_contract_baseline": {
                    "schedule_version_key": "tropical|S1|2026-06-01",
                    "display_name": "Contract baseline issued 2026-06-01",
                }
            }
        },
        params={"as_of": "2026-07-03"},
    )
    assert response.status_code == 200


def test_baselines_get_returns_three_slots(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    client = _client(db)
    body = client.get("/api/projects/tropical/schedule/baselines", headers=_viewer()).json()
    assert body["available"] is True
    assert len(body["slots"]) == 3
    assert {slot["slot_key"] for slot in body["slots"]} == {
        "current_contract_baseline",
        "previous_progress_update_baseline",
        "secondary_progress_update_baseline",
    }


def test_baselines_get_returns_available_versions(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    body = _client(db).get("/api/projects/tropical/schedule/baselines", headers=_viewer()).json()
    assert len(body["available_versions"]) >= 2
    current = next(v for v in body["available_versions"] if v["is_current_as_of"])
    assert current["eligible_baseline"] is False


def test_put_saves_current_contract_baseline(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    client = _client(db)
    _select_contract_baseline(client)
    slot = next(s for s in client.get("/api/projects/tropical/schedule/baselines", headers=_viewer(), params={"as_of": "2026-07-03"}).json()["slots"] if s["slot_key"] == "current_contract_baseline")
    assert slot["status"] == "selected"
    assert slot["selection"]["schedule_version_key"] == "tropical|S1|2026-06-01"


def _seed_third_version(db: Path) -> None:
    import sqlite3

    with sqlite3.connect(db) as conn:
        for import_id, version_key, filename, created in (
            ("imp-early", "tropical|S1|2026-05-01", "TWNU17.xer", "2026-05-01"),
            ("imp-mid", "tropical|S1|2026-06-15", "TWNU18b.xer", "2026-06-15"),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  1, 0, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, version_key, filename, created),
            )
        conn.commit()


def test_put_saves_all_three_slots(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_third_version(db)
    client = _client(db)
    dup = client.put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        params={"as_of": "2026-07-03"},
        json={
            "selections": {
                "current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"},
                "previous_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"},
            }
        },
    )
    assert dup.status_code == 400
    assert dup.json()["detail"] == "duplicate_schedule_version_across_slots"

    ok = client.put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        params={"as_of": "2026-07-03"},
        json={
            "selections": {
                "current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"},
                "previous_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-06-15"},
                "secondary_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-05-01"},
            }
        },
    )
    assert ok.status_code == 200
    selected = [s for s in ok.json()["slots"] if s["status"] == "selected"]
    assert len(selected) == 3


def test_put_clears_slot(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    client = _client(db)
    _select_contract_baseline(client)
    cleared = client.put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        json={"selections": {"current_contract_baseline": None}},
        params={"as_of": "2026-07-03"},
    )
    assert cleared.status_code == 200
    slot = next(s for s in cleared.json()["slots"] if s["slot_key"] == "current_contract_baseline")
    assert slot["status"] == "missing"


def test_put_rejects_unknown_slot(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    response = _client(db).put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        json={"selections": {"unknown_slot": {"schedule_version_key": "tropical|S1|2026-06-01"}}},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "unknown_slot_key"


def test_put_rejects_other_project_version(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    import sqlite3

    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-other', 'other', 'xer', 'primavera_xer', 'committed',
              0, 0, 'not_cost_loaded', 'other|S9|2026-06-01', 'OTHER.xer', '2026-06-01')
            """
        )
        conn.commit()
    response = _client(db).put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        json={"selections": {"current_contract_baseline": {"schedule_version_key": "other|S9|2026-06-01"}}},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "baseline_project_mismatch"


def test_put_rejects_current_schedule_version(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    response = _client(db).put(
        "/api/projects/tropical/schedule/baselines",
        headers=_operator(),
        json={"selections": {"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-07-01"}}},
        params={"as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "baseline_cannot_equal_current_schedule_version"


def test_viewer_can_get_not_put(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    client = _client(db)
    assert client.get("/api/projects/tropical/schedule/baselines", headers=_viewer()).status_code == 200
    denied = client.put(
        "/api/projects/tropical/schedule/baselines",
        headers=_viewer(),
        json={"selections": {"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}}},
    )
    assert denied.status_code == 403


def test_controls_prior_update_unchanged(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="prior_update"
    )
    assert payload["available"] is True
    assert payload["baseline_context"]["selection_status"] == "not_applicable"


def test_controls_named_baseline_resolves(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    svc = ProjectScheduleNamedBaselineService(db_path=str(db))
    svc.update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert payload["available"] is True
    assert payload["comparison_basis"] == "current_contract_baseline"
    assert payload["baseline_context"]["slot_label"] == "Current Contract Baseline"


def test_controls_named_missing_returns_baseline_not_selected(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert payload["available"] is False
    assert payload["reason"] == "baseline_not_selected"


def test_controls_top_controls_use_named_label(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert payload["top_controls"]
    combined = " ".join(
        [payload["summary"].get("headline", "")]
        + list(payload["summary"].get("supporting_points") or [])
        + [c.get("summary", "") for c in payload["top_controls"]]
    )
    assert "Current Contract Baseline" in combined


def test_controls_named_includes_workbench_links(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert "review_workbench" in payload["links"]
    assert "comparison_basis=current_contract_baseline" in payload["links"]["review_workbench"]
    for control in payload["top_controls"]:
        if control.get("activity_id"):
            assert control["links"]["review_item"]
            assert control["links"]["driver_detail"]
            break
    else:
        pytest.fail("expected at least one activity-backed control")


def test_controls_language_qa_passes_named_baseline(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    ProjectScheduleNamedBaselineService(db_path=str(db)).update_baselines(
        "tropical",
        selections={"current_contract_baseline": {"schedule_version_key": "tropical|S1|2026-06-01"}},
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="current_contract_baseline",
    )
    assert validate_controls_text(payload)["passed"] is True

def test_controls_previous_and_secondary_named_bases(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_third_version(db)
    svc = ProjectScheduleNamedBaselineService(db_path=str(db))
    svc.update_baselines(
        "tropical",
        selections={
            "previous_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-06-15"},
            "secondary_progress_update_baseline": {"schedule_version_key": "tropical|S1|2026-05-01"},
        },
        as_of=date(2026, 7, 3),
        selected_by="operator",
    )
    prev = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="previous_progress_update_baseline"
    )
    sec = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical", as_of=date(2026, 7, 3), comparison_basis="secondary_progress_update_baseline"
    )
    assert prev["available"] is True
    assert sec["available"] is True
    assert prev["baseline_context"]["slot_label"] == "Previous Progress Update Baseline"
    assert sec["baseline_context"]["slot_label"] == "Secondary Progress Update Baseline"


def test_controls_get_unknown_basis_returns_400(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    response = _client(db).get(
        "/api/projects/tropical/schedule/controls",
        headers=_viewer(),
        params={"comparison_basis": "mystery_basis", "as_of": "2026-07-03"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_comparison_basis"


def test_controls_get_omitted_basis_defaults_prior_update(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    response = _client(db).get(
        "/api/projects/tropical/schedule/controls",
        headers=_viewer(),
        params={"as_of": "2026-07-03"},
    )
    assert response.status_code == 200
    assert response.json()["comparison_basis"] == "prior_update"


def test_controls_get_invalid_basis_does_not_return_prior_update_payload(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    bad = _client(db).get(
        "/api/projects/tropical/schedule/controls",
        headers=_viewer(),
        params={"comparison_basis": "mystery_basis"},
    )
    assert bad.status_code == 400
    body = bad.json()
    assert body.get("detail") == "invalid_comparison_basis"
    assert "top_controls" not in body
    assert "comparison_basis" not in body


def test_controls_service_rejects_unknown_basis(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    with pytest.raises(ValueError, match="invalid_comparison_basis"):
        ProjectScheduleControlsService(db_path=str(db)).build_controls(
            "tropical",
            comparison_basis="mystery_basis",
        )

