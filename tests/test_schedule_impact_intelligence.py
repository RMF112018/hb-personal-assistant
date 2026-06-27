"""Phase 4 schedule impact intelligence tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.schedule_diff_intelligence import (
    build_impact_rollups,
    impact_level_for_score,
    score_impact_detail,
)
from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository
from tests.test_schedule_diff_intelligence import _seed_db
from tests.test_schedule_identity_foundation import _op


def test_v79_schema_and_contract(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    migrator = SQLiteMigrator(db_path=str(db))
    assert migrator.apply() == LATEST_SCHEMA_VERSION == 80
    assert migrator.apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "schedule_version_diff_impact_rollups" in names
    assert "idx_schedule_diff_impact_rollups_diff" in indexes
    assert "idx_schedule_diff_impact_rollups_impact_level" in indexes
    contract = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
        ).read_text()
    )
    assert contract["table_count"] == 456
    assert contract["table_count"] == len(contract["tables"])
    assert contract["tables"]["schedule_version_diff_impact_rollups"]["v"] == "V79"


def test_impact_scoring_and_rollup_ids_are_deterministic() -> None:
    row = {
        "diff_id": 10,
        "project_key": "tropical",
        "from_schedule_version_key": "from",
        "to_schedule_version_key": "to",
        "comparison_type": "identity_safe_default",
        "identity_safe": 1,
        "change_domain": "activity",
        "change_type": "date_drift",
        "field_name": "finish_date",
        "activity_id": "A100",
        "activity_name": "Foundation",
        "wbs_code": "WBS1",
        "severity": "critical",
        "day_delta": 12,
        "requires_attention": 1,
        "is_critical_path_related": 1,
    }
    assert score_impact_detail(row) == 65
    assert impact_level_for_score(75) == "critical"
    first = build_impact_rollups([row])
    second = build_impact_rollups([dict(row)])
    assert first == second
    summary = next(r for r in first if r["rollup_type"] == "summary")
    assert summary["impact_score"] == "65"
    assert summary["impact_level"] == "high"
    assert summary["rollup_id"].startswith("sir_")


def test_identity_safe_default_diff_persists_impact_rollups(tmp_path: Path) -> None:
    db = _seed_db(tmp_path)
    diff_id = ScheduleImportService(db_path=str(db))._compute_default_version_diff_best_effort(
        project_key="tropical",
        version_key="tropical|1|2026-07-01",
        package_id=None,
    )
    assert diff_id is not None
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM schedule_version_diff_impact_rollups WHERE diff_id=?",
                (diff_id,),
            )
        ]
    assert rows
    assert any(r["rollup_type"] == "summary" for r in rows)
    assert any(r["rollup_type"] == "wbs" for r in rows)
    assert any(r["requires_attention"] == 1 for r in rows)
    assert all(r["identity_safe"] == 1 for r in rows)
    assert all(r["comparison_type"] == "identity_safe_default" for r in rows)
    detail_count = ScheduleMappingRepository(db_path=str(db)).summarize_diff_detail_facts(
        diff_id
    )["total_change_count"]
    summary = next(r for r in rows if r["rollup_type"] == "summary")
    assert summary["change_count"] == detail_count


def test_rollup_replacement_is_idempotent(tmp_path: Path) -> None:
    db = _seed_db(tmp_path)
    diff_id = ScheduleImportService(db_path=str(db))._compute_default_version_diff_best_effort(
        project_key="tropical",
        version_key="tropical|1|2026-07-01",
        package_id=None,
    )
    assert diff_id is not None
    repo = ScheduleMappingRepository(db_path=str(db))
    details = repo.list_diff_detail_facts(diff_id, limit=10000, offset=0)
    with sqlite3.connect(db) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM schedule_version_diff_impact_rollups WHERE diff_id=?",
            (diff_id,),
        ).fetchone()[0]
        repo.replace_diff_impact_rollups_from_details(conn, diff_id=diff_id, detail_rows=details)
        repo.replace_diff_impact_rollups_from_details(conn, diff_id=diff_id, detail_rows=details)
        after = conn.execute(
            "SELECT COUNT(*) FROM schedule_version_diff_impact_rollups WHERE diff_id=?",
            (diff_id,),
        ).fetchone()[0]
    assert before == after


def test_review_or_different_identity_default_generates_no_impact_rollups(tmp_path: Path) -> None:
    db = _seed_db(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE schedule_version_identity_matches
            SET requires_review=1, match_status='requires_review'
            WHERE schedule_version_key='tropical|1|2026-07-01'
            """
        )
        conn.commit()
    diff_id = ScheduleImportService(db_path=str(db))._compute_default_version_diff_best_effort(
        project_key="tropical",
        version_key="tropical|1|2026-07-01",
        package_id=None,
    )
    assert diff_id is None
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM schedule_version_diff_impact_rollups").fetchone()[0]
    assert count == 0


def test_manual_cross_identity_impact_api_is_labeled_and_redaction_safe(tmp_path: Path) -> None:
    db = _seed_db(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE schedule_version_identity_matches
            SET schedule_identity_key='identity-other'
            WHERE schedule_version_key='tropical|1|2026-07-01'
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_identities (
              schedule_identity_key, project_key, identity_status
            ) VALUES ('identity-other', 'tropical', 'active')
            """
        )
        conn.commit()
    client = TestClient(create_app(db_path=str(db)))
    diff = client.get(
        "/api/schedules/projects/tropical/diff?from=tropical%7C1%7C2026-06-01&to=tropical%7C1%7C2026-07-01",
        headers=_op(),
    )
    assert diff.status_code == 200, diff.text
    impact = client.get(
        f"/api/schedules/projects/tropical/diffs/{diff.json()['diff_id']}/impact?rollup_type=summary",
        headers=_op(),
    )
    assert impact.status_code == 200, impact.text
    payload = impact.json()
    assert payload["metadata"]["identity_safe"] is False
    assert payload["metadata"]["comparison_type"] == "cross_identity_manual"
    assert payload["summary"]["comparison_type"] == "cross_identity_manual"
    assert payload["summary"]["identity_safe"] == 0
    assert find_redaction_leaks(payload) == []


def test_milestone_and_critical_rollups_require_supporting_detail_facts() -> None:
    row = {
        "diff_id": 1,
        "project_key": "tropical",
        "from_schedule_version_key": "from",
        "to_schedule_version_key": "to",
        "comparison_type": "identity_safe_default",
        "identity_safe": 1,
        "change_domain": "activity",
        "change_type": "changed",
        "field_name": "activity_name",
        "activity_id": "MS100",
        "activity_name": "Turnover milestone",
        "severity": "minor",
        "requires_attention": 0,
        "is_critical_path_related": 0,
    }
    rollups = build_impact_rollups([row])
    assert not any(r["rollup_type"] == "milestone" for r in rollups)
    assert not any(r["rollup_type"] == "critical_path" for r in rollups)
