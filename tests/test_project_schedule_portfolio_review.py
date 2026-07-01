"""Phase 18 portfolio schedule review dashboard tests."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_rendered_text
from hb_assistant.construction.analytics.project_schedule_portfolio_review_service import (
    SCHEDULE_STALENESS_THRESHOLD_DAYS,
    ProjectSchedulePortfolioReviewService,
    resolve_recommended_next_action,
    staleness_from_data_date,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain

_FORBIDDEN_PM_FIELD_KEYS = frozenset(
    {
        "schedule_version_key",
        "schedule_identity_key",
        "import_id",
        "package_id",
        "cpm_run_id",
        "source_export_proxy",
        "source_record_id",
        "procore_project_id",
        "file_sha256",
        "file_path",
        "failure_message",
    }
)

_FORBIDDEN_LANGUAGE = re.compile(
    r"\b(claim|liability|responsibility|fault|compensable|entitlement|delay damages|caused|causation|forensic)\b",
    re.IGNORECASE,
)


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "portfolio-phase18.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    seed_procore_ep_project(db, project_key="palm", display_name="Palm Shores", project_id="9002")
    return db


def _client(db: Path) -> TestClient:
    return TestClient(create_app(db_path=str(db)))


def _seed_current_schedule(
    db: Path,
    *,
    project_key: str = "tropical",
    version_suffix: str = "2026-07-01",
    import_id: str = "imp-current",
) -> str:
    version_key = f"{project_key}|S1|{version_suffix}"
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES (?, ?, 'xer', 'primavera_xer', 'committed',
              2, 1, 'not_cost_loaded', ?, ?, '2026-07-01T10:00:00Z')
            """,
            (import_id, project_key, version_key, f"{import_id}.xer"),
        )
        for activity_id, name in (("A100", "Area work"), ("A200", "Milestone")):
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, wbs_code, duration_remaining, is_milestone
                ) VALUES (?, 'S1', ?, ?, 'xer', 'primavera_xer', ?, ?, '2026-07-01', '2026-07-10', 'WBS', '5', ?)
                """,
                (project_key, version_key, import_id, activity_id, name, 1 if activity_id == "A200" else 0),
            )
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_relationships (
              project_key, schedule_id, schedule_version_key, import_id,
              predecessor_activity_id, successor_activity_id, relationship_type
            ) VALUES (?, 'S1', ?, ?, 'A100', 'A200', 'FS')
            """,
            (project_key, version_key, import_id),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO schedule_identities (
              schedule_identity_key, project_key, identity_status, latest_import_id,
              latest_schedule_version_key
            ) VALUES ('identity-main', ?, 'active', ?, ?)
            """,
            (project_key, import_id, version_key),
        )
        conn.execute(
            """
            INSERT INTO schedule_version_identity_matches (
              match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
              source_format, activity_count, relationship_count, wbs_count,
              match_type, match_status, match_rule, confidence_score, requires_review
            ) VALUES (?, 'identity-main', ?, ?, ?, 'primavera_xer',
              2, 1, 0, 'seed', 'resolved', 'seed', '1.00', 0)
            """,
            (f"match-{import_id}", version_key, import_id, project_key),
        )
        conn.commit()
    return version_key


def test_staleness_from_data_date_rules() -> None:
    assert staleness_from_data_date(None, has_schedule=False, as_of=__import__("datetime").date(2026, 7, 1)) == (
        "missing",
        None,
    )
    status, age = staleness_from_data_date("2026-06-20", has_schedule=True, as_of=__import__("datetime").date(2026, 7, 1))
    assert status == "current"
    assert age == 11
    status, age = staleness_from_data_date("2026-01-01", has_schedule=True, as_of=__import__("datetime").date(2026, 7, 1))
    assert status == "stale"
    assert age is not None and age > SCHEDULE_STALENESS_THRESHOLD_DAYS


def test_portfolio_includes_projects_with_and_without_schedules(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db, project_key="tropical")
    svc = ProjectSchedulePortfolioReviewService(db_path=str(db))
    dashboard = svc.build_dashboard(as_of=__import__("datetime").date(2026, 7, 3))
    keys = {row["project_key"] for row in dashboard["projects"]}
    assert "tropical" in keys
    assert "palm" in keys
    palm = next(row for row in dashboard["projects"] if row["project_key"] == "palm")
    assert palm["schedule_staleness_status"] == "missing"
    assert palm["operator_action_required"] is True
    assert dashboard["portfolio_summary"]["projects_without_schedule"] >= 1


def test_stale_schedule_detection(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db, project_key="tropical", version_suffix="2026-01-01")
    svc = ProjectSchedulePortfolioReviewService(db_path=str(db))
    row = next(r for r in svc.build_dashboard(as_of=__import__("datetime").date(2026, 7, 3))["projects"] if r["project_key"] == "tropical")
    assert row["schedule_staleness_status"] == "stale"
    assert row["portfolio_status"] in {"stale", "operator_action_required", "degraded", "needs_review"}


def test_operator_action_required_for_missing_schedule(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db, project_key="tropical")
    row = next(
        r
        for r in ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
            as_of=__import__("datetime").date(2026, 7, 3)
        )["projects"]
        if r["project_key"] == "palm"
    )
    assert row["schedule_staleness_status"] == "missing"
    assert row["operator_action_required"] is True
    assert row["portfolio_status"] in {"missing", "operator_action_required"}
    assert row["recommended_next_action"]["action_key"] == "schedule_import_needed"


def test_review_counts_roll_up(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    repo.upsert_review_item(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        stable_item_key="driver:DRV-A",
        item_type="driver",
        item_title="Driver Activity",
        priority=90,
        evidence={"materializable": True},
        source_activity_id="DRV-A",
    )
    row = next(
        r
        for r in ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
            as_of=__import__("datetime").date(2026, 7, 3)
        )["projects"]
        if r["project_key"] == "tropical"
    )
    assert row["review_status"]["persisted_item_count"] >= 1
    assert row["review_status"]["needs_review"] >= 1
    assert row["portfolio_status"] in {"needs_review", "operator_action_required", "blocked", "degraded"}


def test_pm_redaction_and_no_raw_ids(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    dashboard = ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
        as_of=__import__("datetime").date(2026, 7, 3)
    )
    assert find_redaction_leaks(dashboard) == []
    payload = json.dumps(dashboard)
    for forbidden in _FORBIDDEN_PM_FIELD_KEYS:
        assert f'"{forbidden}"' not in payload
    assert "tropical|S1|" not in payload


def test_next_action_priority_rules() -> None:
    base_review = {"needs_review": 0, "preview_cue_count": 0}
    missing = resolve_recommended_next_action(
        project_key="palm",
        has_schedule=False,
        schedule_resolved=False,
        staleness_status="missing",
        analytics_trust_status="unavailable",
        identity_trust_status="unavailable",
        identity_gate=None,
        cpm_trust_status="unavailable",
        quality_trust_status="unavailable",
        review_status=base_review,
    )
    assert missing["action_key"] == "schedule_import_needed"
    stale = resolve_recommended_next_action(
        project_key="tropical",
        has_schedule=True,
        schedule_resolved=True,
        staleness_status="stale",
        analytics_trust_status="ready",
        identity_trust_status="trusted",
        identity_gate="ready",
        cpm_trust_status="ready",
        quality_trust_status="ready",
        review_status=base_review,
    )
    assert stale["action_key"] == "schedule_update_stale"
    review = resolve_recommended_next_action(
        project_key="tropical",
        has_schedule=True,
        schedule_resolved=True,
        staleness_status="current",
        analytics_trust_status="ready",
        identity_trust_status="trusted",
        identity_gate="ready",
        cpm_trust_status="ready",
        quality_trust_status="ready",
        review_status={"needs_review": 2, "preview_cue_count": 3},
    )
    assert review["action_key"] == "review_items_need_disposition"


def test_all_projects_ready_empty_filter_state(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db, project_key="tropical", version_suffix="2026-07-01")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM procore_ep_projects WHERE project_key='palm'")
        conn.commit()
    dashboard = ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
        status="ready",
        as_of=__import__("datetime").date(2026, 7, 3),
    )
    tropical_rows = [row for row in dashboard["projects"] if row["project_key"] == "tropical"]
    if tropical_rows and tropical_rows[0].get("ready"):
        assert dashboard["portfolio_summary"]["ready_count"] >= 1
    filtered = ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
        status="ready",
        as_of=__import__("datetime").date(2026, 7, 3),
    )
    assert all(row.get("portfolio_status") == "ready" for row in filtered["projects"])


def test_dashboard_api_summary_filters_and_roles(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    client = _client(db)
    body = client.get("/api/projects/schedule-review-dashboard", headers=_viewer(), params={"as_of": "2026-07-03"}).json()
    assert "portfolio_summary" in body
    assert "projects" in body
    assert body["portfolio_summary"]["project_count"] >= 2
    blocked = client.get(
        "/api/projects/schedule-review-dashboard",
        headers=_viewer(),
        params={"status": "missing", "as_of": "2026-07-03"},
    ).json()
    assert all(row["schedule_staleness_status"] == "missing" for row in blocked["projects"])
    denied = client.get(
        "/api/projects/schedule-review-dashboard",
        headers=_viewer(),
        params={"include_technical": 1, "as_of": "2026-07-03"},
    )
    assert denied.status_code == 403
    technical = client.get(
        "/api/projects/schedule-review-dashboard",
        headers=_operator(),
        params={"include_technical": 1, "as_of": "2026-07-03"},
    ).json()
    assert any("technical" in row for row in technical.get("projects") or [])


def test_dashboard_priority_sort_stable(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_current_schedule(db, project_key="tropical", version_suffix="2026-01-01")
    dashboard = ProjectSchedulePortfolioReviewService(db_path=str(db)).build_dashboard(
        as_of=__import__("datetime").date(2026, 7, 3)
    )
    ranks = [row.get("portfolio_status") for row in dashboard["projects"]]
    order = {
        "blocked": 0,
        "operator_action_required": 1,
        "needs_review": 2,
        "stale": 3,
        "degraded": 4,
        "ready": 5,
        "missing": 1,
        "unknown": 6,
    }
    for left, right in zip(ranks, ranks[1:]):
        assert order.get(str(left), 99) <= order.get(str(right), 99)


def test_portfolio_export_markdown_redaction_and_language(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    md = ProjectSchedulePortfolioReviewService(db_path=str(db)).build_export_markdown()
    assert "## Portfolio Schedule Review Status" in md
    assert "## Priority Projects" in md
    assert str(SCHEDULE_STALENESS_THRESHOLD_DAYS) in md
    assert find_redaction_leaks({"body": md}) == []
    qa = validate_rendered_text(md, surface="portfolio_export")
    assert qa["passed"] is True
    assert not _FORBIDDEN_LANGUAGE.search(md)
    client = _client(db)
    response = client.get("/api/projects/schedule-review-dashboard/export", headers=_viewer())
    assert response.status_code == 200
    assert "Portfolio Schedule Review Status" in response.text
