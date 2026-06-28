"""Phase 3 schedule detailed diff intelligence tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.schedule_diff_intelligence import (
    classify_date_drift,
    summarize_detail_facts,
)
from hb_assistant.construction.analytics.schedule_import_service import ScheduleImportService
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_schedule_identity_foundation import _op


def _seed_version(
    conn: sqlite3.Connection,
    *,
    import_id: str,
    version_key: str,
    identity_key: str,
    activities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    wbs: list[dict[str, Any]] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO schedule_file_imports (
          import_id, project_key, source_type, source_format, import_status,
          activity_count, relationship_count, wbs_count, calendar_count, code_count,
          udf_count, cost_loaded_status, schedule_version_key, created_at
        ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
          ?, ?, ?, 0, 0, 0, 'not_cost_loaded', ?, ?)
        """,
        (
            import_id,
            len(activities),
            len(relationships),
            len(wbs or []),
            version_key,
            version_key.split("|")[-1],
        ),
    )
    for activity in activities:
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_activities (
              project_key, schedule_id, schedule_version_key, import_id,
              source_type, source_format, activity_id, activity_name, start_date,
              finish_date, activity_status, duration_remaining, total_float,
              is_critical, is_milestone, wbs_id, wbs_code, calendar_id
            ) VALUES ('tropical', '1', ?, ?, 'xer', 'primavera_xer', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_key,
                import_id,
                activity["activity_id"],
                activity.get("activity_name"),
                activity.get("start_date"),
                activity.get("finish_date"),
                activity.get("activity_status"),
                activity.get("duration_remaining"),
                activity.get("total_float"),
                activity.get("is_critical", 0),
                activity.get("is_milestone", 0),
                activity.get("wbs_id"),
                activity.get("wbs_code"),
                activity.get("calendar_id"),
            ),
        )
    for rel in relationships:
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_relationships (
              project_key, schedule_id, schedule_version_key, import_id,
              predecessor_activity_id, successor_activity_id, relationship_type,
              lag_value, lag_unit
            ) VALUES ('tropical', '1', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_key,
                import_id,
                rel["predecessor_activity_id"],
                rel["successor_activity_id"],
                rel.get("relationship_type"),
                rel.get("lag_value"),
                rel.get("lag_unit"),
            ),
        )
    for node in wbs or []:
        conn.execute(
            """
            INSERT INTO procore_ep_schedule_wbs_nodes (
              project_key, schedule_id, schedule_version_key, import_id,
              wbs_id, parent_wbs_id, wbs_code, wbs_name, wbs_path
            ) VALUES ('tropical', '1', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_key,
                import_id,
                node["wbs_id"],
                node.get("parent_wbs_id"),
                node.get("wbs_code"),
                node.get("wbs_name"),
                node.get("wbs_path"),
            ),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO schedule_identities (
          schedule_identity_key, project_key, identity_status,
          first_import_id, first_schedule_version_key, latest_import_id,
          latest_schedule_version_key
        ) VALUES (?, 'tropical', 'active', ?, ?, ?, ?)
        """,
        (identity_key, import_id, version_key, import_id, version_key),
    )
    conn.execute(
        """
        INSERT INTO schedule_version_identity_matches (
          match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
          source_format, activity_id_set_fingerprint, activity_count, relationship_count,
          wbs_count, match_type, match_status, match_rule, confidence_score, requires_review
        ) VALUES (?, ?, ?, ?, 'tropical', 'primavera_xer', ?, ?, ?, ?,
          'seed', 'resolved', 'seed', '1.00', 0)
        """,
        (
            f"match-{import_id}",
            identity_key,
            version_key,
            import_id,
            f"fp-{identity_key}",
            len(activities),
            len(relationships),
            len(wbs or []),
        ),
    )


def _seed_db(tmp_path: Path) -> Path:
    db = tmp_path / "diff-intel.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    with sqlite3.connect(db) as conn:
        _seed_version(
            conn,
            import_id="imp-a",
            version_key="tropical|1|2026-06-01",
            identity_key="identity-main",
            activities=[
                {
                    "activity_id": "A1000",
                    "activity_name": "Start",
                    "start_date": "2026-06-01",
                    "finish_date": "2026-06-05",
                    "is_critical": 1,
                    "wbs_id": "W1",
                    "wbs_code": "WBS1",
                },
                {
                    "activity_id": "A1010",
                    "activity_name": "Finish",
                    "start_date": "2026-06-06",
                    "finish_date": "2026-06-10",
                    "wbs_id": "W1",
                    "wbs_code": "WBS1",
                },
            ],
            relationships=[
                {
                    "predecessor_activity_id": "A1000",
                    "successor_activity_id": "A1010",
                    "relationship_type": "FS",
                    "lag_value": "0",
                    "lag_unit": "d",
                }
            ],
            wbs=[{"wbs_id": "W1", "wbs_code": "WBS1", "wbs_name": "Base"}],
        )
        _seed_version(
            conn,
            import_id="imp-b",
            version_key="tropical|1|2026-07-01",
            identity_key="identity-main",
            activities=[
                {
                    "activity_id": "A1000",
                    "activity_name": "Start Updated",
                    "start_date": "2026-06-01",
                    "finish_date": "2026-06-17",
                    "is_critical": 1,
                    "wbs_id": "W2",
                    "wbs_code": "WBS2",
                },
                {
                    "activity_id": "A1020",
                    "activity_name": "New Work",
                    "start_date": "2026-06-18",
                    "finish_date": "2026-06-20",
                    "wbs_id": "W2",
                    "wbs_code": "WBS2",
                },
            ],
            relationships=[
                {
                    "predecessor_activity_id": "A1000",
                    "successor_activity_id": "A1020",
                    "relationship_type": "SS",
                    "lag_value": "2",
                    "lag_unit": "d",
                }
            ],
            wbs=[{"wbs_id": "W2", "wbs_code": "WBS2", "wbs_name": "Changed"}],
        )
        conn.commit()
    return db


def test_v79_schema_and_contract(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION >= 80
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "schedule_version_diff_detail_facts" in names
    assert "idx_schedule_diff_detail_diff" in indexes
    contract = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
        ).read_text()
    )
    assert contract["table_count"] == 477
    assert contract["tables"]["schedule_version_diff_detail_facts"]["v"] == "V79"


def test_severity_classification_thresholds() -> None:
    assert classify_date_drift(2) == "minor"
    assert classify_date_drift(5) == "moderate"
    assert classify_date_drift(10) == "major"
    assert classify_date_drift(11) == "critical"


def test_identity_safe_default_diff_persists_detail_rows_and_summary(tmp_path: Path) -> None:
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
                "SELECT * FROM schedule_version_diff_detail_facts WHERE diff_id=?",
                (diff_id,),
            )
        ]
    assert rows
    assert any(r["change_domain"] == "activity" and r["change_type"] == "added" for r in rows)
    assert any(r["change_domain"] == "activity" and r["change_type"] == "removed" for r in rows)
    assert any(r["change_type"] == "date_drift" and r["day_delta"] == 12 for r in rows)
    assert any(r["change_domain"] == "relationship" for r in rows)
    assert any(r["change_domain"] == "wbs" for r in rows)
    assert all(r["identity_safe"] == 1 for r in rows)
    assert all(r["comparison_type"] == "identity_safe_default" for r in rows)
    summary = summarize_detail_facts(rows)
    assert summary["total_change_count"] == len(rows)
    assert summary["critical_severity_count"] >= 1
    assert summary["requires_attention_count"] >= 1


def test_manual_cross_identity_diff_is_labeled_not_identity_safe(tmp_path: Path) -> None:
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
    response = client.get(
        "/api/schedules/projects/tropical/diff?from=tropical%7C1%7C2026-06-01&to=tropical%7C1%7C2026-07-01",
        headers=_op(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["comparison_type"] == "cross_identity_manual"
    assert payload["identity_safe"] is False
    detail = client.get(
        f"/api/schedules/projects/tropical/diffs/{payload['diff_id']}/details?severity=critical",
        headers=_op(),
    )
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["metadata"]["identity_safe"] is False
    assert detail_payload["metadata"]["comparison_type"] == "cross_identity_manual"
    assert find_redaction_leaks(detail_payload) == []


def test_different_identity_default_generates_no_detail_rows(tmp_path: Path) -> None:
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
    diff_id = ScheduleImportService(db_path=str(db))._compute_default_version_diff_best_effort(
        project_key="tropical",
        version_key="tropical|1|2026-07-01",
        package_id=None,
    )
    assert diff_id is None
    with sqlite3.connect(db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM schedule_version_diff_detail_facts").fetchone()[0]
    assert count == 0
