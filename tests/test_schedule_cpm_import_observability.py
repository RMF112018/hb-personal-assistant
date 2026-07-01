"""CPM import observability after canonical schedule package merge."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)
from tests.schedule_project_test_helpers import seed_procore_ep_project

PACKAGE_FIXTURES = (
    ("TWNU18.zip", 1378, 3718),
    ("TWNU19.zip", 1507, 3921),
)
PACKAGE_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "project_schedule_import_packages"


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path, *, db_name: str) -> tuple[TestClient, Path]:
    db = tmp_path / db_name
    SQLiteMigrator(db_path=str(db)).apply()
    assert LATEST_SCHEMA_VERSION >= 95
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return TestClient(create_app(db_path=str(db))), db


def _import_tw_package(client: TestClient, fixture_name: str, *, supersede: bool = False) -> dict:
    fixture = PACKAGE_FIXTURE_DIR / fixture_name
    assert fixture.exists(), fixture
    data: dict[str, str] = {"project_key": "tropical"}
    if supersede:
        data["confirm_supersede"] = "true"
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": (fixture.name, fixture.read_bytes(), "application/zip")},
        data=data,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={
            "import_id": body["import_id"],
            "project_key": "tropical",
            "confirm": True,
            "confirm_supersede": supersede,
        },
    )
    assert commit.status_code == 200, commit.text
    return commit.json()


def _canonical_counts(db: Path, schedule_version_key: str) -> tuple[int, int]:
    with sqlite3.connect(db) as conn:
        activities = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
            (schedule_version_key,),
        ).fetchone()[0]
        relationships = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?",
            (schedule_version_key,),
        ).fetchone()[0]
    return int(activities), int(relationships)


@pytest.mark.parametrize(
    ("fixture_name", "activity_count", "relationship_count"),
    PACKAGE_FIXTURES,
)
def test_import_commit_triggers_cpm_after_canonical_merge_tw(
    tmp_path: Path,
    fixture_name: str,
    activity_count: int,
    relationship_count: int,
) -> None:
    _assert_import_commit_triggers_cpm(tmp_path, fixture_name, activity_count, relationship_count)


def test_import_commit_triggers_cpm_after_canonical_merge_twNU18(tmp_path: Path) -> None:
    _assert_import_commit_triggers_cpm(tmp_path, "TWNU18.zip", 1378, 3718)


def test_import_commit_triggers_cpm_after_canonical_merge_twNU19(tmp_path: Path) -> None:
    _assert_import_commit_triggers_cpm(tmp_path, "TWNU19.zip", 1507, 3921)


def _assert_import_commit_triggers_cpm(
    tmp_path: Path,
    fixture_name: str,
    activity_count: int,
    relationship_count: int,
) -> None:
    client, db = _client(tmp_path, db_name=f"cpm-{fixture_name}.db")
    committed = _import_tw_package(client, fixture_name)
    assert committed["cpm_recompute_triggered"] is True
    assert committed["cpm_recompute_status"] in {"complete", "partial"}
    assert committed["computed_activity_count"] == activity_count
    assert committed["canonical_input_activity_count"] == activity_count
    assert committed["canonical_input_relationship_count"] == relationship_count
    obs = committed.get("cpm_observability") or {}
    assert obs.get("status") in {"complete", "partial"}
    assert obs.get("canonical_input_activity_count") == activity_count
    assert obs.get("canonical_input_relationship_count") == relationship_count

    row = ScheduleCpmImportObservabilityRepository(db_path=str(db)).get_by_import_id(
        committed["import_id"]
    )
    assert row is not None
    assert row["status"] in {"complete", "partial"}
    assert row["trigger_source"] == "import_commit"

    db_activities, db_relationships = _canonical_counts(db, committed["schedule_version_key"])
    assert db_activities == activity_count
    assert db_relationships == relationship_count


def test_cpm_input_counts_match_canonical_counts(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-counts.db")
    committed = _import_tw_package(client, "TWNU18.zip")
    svk = committed["schedule_version_key"]
    db_activities, db_relationships = _canonical_counts(db, svk)
    obs = ScheduleCpmImportObservabilityRepository(db_path=str(db)).get_by_import_id(
        committed["import_id"]
    )
    assert obs is not None
    assert obs["canonical_input_activity_count"] == db_activities
    assert obs["canonical_input_relationship_count"] == db_relationships
    assert committed["canonical_input_activity_count"] == db_activities
    assert committed["canonical_input_relationship_count"] == db_relationships


def test_import_status_exposes_cpm_success(tmp_path: Path) -> None:
    client, _db = _client(tmp_path, db_name="cpm-status-success.db")
    committed = _import_tw_package(client, "TWNU18.zip")
    status = client.get(
        f"/api/projects/tropical/schedule/imports/{committed['import_id']}/status",
        headers=_operator(),
    )
    assert status.status_code == 200, status.text
    body = status.json()
    cpm = body.get("cpm") or {}
    assert cpm.get("cpm_recompute_status") in {"complete", "partial"}
    assert cpm.get("canonical_input_activity_count") == 1378
    assert cpm.get("canonical_input_relationship_count") == 3718
    assert any(stage["stage"] == "cpm_recompute" and stage["status"] in {"complete", "partial"} for stage in body["stages"])


def test_import_status_exposes_cpm_failure(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-status-failure.db")
    with patch(
        "hb_assistant.construction.analytics.schedule_cpm_service.ScheduleCpmGraphService.run_forward_pass",
        side_effect=RuntimeError("synthetic forward-pass failure"),
    ):
        committed = _import_tw_package(client, "TWNU18.zip")
    assert committed["cpm_recompute_status"] == "failed"
    status = client.get(
        f"/api/projects/tropical/schedule/imports/{committed['import_id']}/status",
        headers=_operator(),
    )
    assert status.status_code == 200, status.text
    body = status.json()
    cpm = body.get("cpm") or {}
    assert cpm.get("cpm_recompute_status") == "failed"
    assert cpm.get("failure_code") == "cpm_chain_failed"
    redacted = str(cpm.get("failure_message_redacted") or "")
    assert redacted
    assert "RuntimeError" not in redacted
    assert "synthetic" not in redacted
    assert "forward pass" in redacted.lower()
    assert "failure_message" not in cpm
    assert cpm.get("failed_step") == "forward_pass"
    assert any(stage["stage"] == "cpm_recompute" and stage["status"] == "failed" for stage in body["stages"])

    row = ScheduleCpmImportObservabilityRepository(db_path=str(db)).get_by_import_id(
        committed["import_id"]
    )
    assert row is not None
    assert row["status"] == "failed"


def test_failed_cpm_run_is_durable(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-failure-durable.db")
    with patch(
        "hb_assistant.construction.analytics.schedule_cpm_service.ScheduleCpmGraphService.run_forward_pass",
        side_effect=RuntimeError("durable failure marker"),
    ):
        committed = _import_tw_package(client, "TWNU19.zip")

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT status, failure_code, failure_message, failed_step, trigger_source "
            "FROM schedule_cpm_import_observability WHERE import_id=?",
            (committed["import_id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == "failed"
    assert row[1] == "cpm_chain_failed"
    assert "durable failure marker" in str(row[2])
    assert row[3] == "forward_pass"
    assert row[4] == "import_commit"


def test_cpm_retry_uses_same_canonical_schedule_version(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-retry-version.db")
    committed = _import_tw_package(client, "TWNU18.zip")
    svk = committed["schedule_version_key"]
    before_activities, before_relationships = _canonical_counts(db, svk)

    retry = client.post(
        f"/api/projects/tropical/schedule/imports/{committed['import_id']}/recompute-cpm",
        headers=_operator(),
    )
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["schedule_version_key"] == svk
    assert body["cpm_recompute_triggered"] is True
    assert body["cpm_recompute_status"] in {"complete", "partial"}

    after_activities, after_relationships = _canonical_counts(db, svk)
    assert after_activities == before_activities
    assert after_relationships == before_relationships

    row = ScheduleCpmImportObservabilityRepository(db_path=str(db)).get_by_import_id(
        committed["import_id"]
    )
    assert row is not None
    assert row["trigger_source"] == "manual_retry"
    assert row["schedule_version_key"] == svk


def test_cpm_retry_does_not_duplicate_canonical_records(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-retry-dedup.db")
    committed = _import_tw_package(client, "TWNU19.zip")
    svk = committed["schedule_version_key"]

    def _table_counts() -> dict[str, int]:
        with sqlite3.connect(db) as conn:
            return {
                "activities": conn.execute(
                    "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (svk,),
                ).fetchone()[0],
                "relationships": conn.execute(
                    "SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?",
                    (svk,),
                ).fetchone()[0],
                "codes": conn.execute(
                    "SELECT COUNT(*) FROM procore_ep_schedule_activity_code_assignments WHERE schedule_version_key=?",
                    (svk,),
                ).fetchone()[0],
                "udfs": conn.execute(
                    "SELECT COUNT(*) FROM procore_ep_schedule_udf_values WHERE schedule_version_key=?",
                    (svk,),
                ).fetchone()[0],
            }

    before = _table_counts()
    for _ in range(2):
        retry = client.post(
            f"/api/projects/tropical/schedule/imports/{committed['import_id']}/recompute-cpm",
            headers=_operator(),
        )
        assert retry.status_code == 200, retry.text
    after = _table_counts()
    assert after == before

    with sqlite3.connect(db) as conn:
        obs_rows = conn.execute(
            "SELECT COUNT(*) FROM schedule_cpm_import_observability WHERE import_id=?",
            (committed["import_id"],),
        ).fetchone()[0]
    assert obs_rows == 1


def test_reimport_does_not_duplicate_canonical_records_or_hide_cpm_status(tmp_path: Path) -> None:
    client, db = _client(tmp_path, db_name="cpm-reimport.db")
    first = _import_tw_package(client, "TWNU18.zip")
    second = _import_tw_package(client, "TWNU18.zip", supersede=True)
    svk = second["schedule_version_key"]
    assert first["schedule_version_key"] == svk
    assert second["cpm_recompute_triggered"] is True
    assert second["cpm_recompute_status"] in {"complete", "partial"}

    with sqlite3.connect(db) as conn:
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?) AS activities,
              (SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?) AS relationships,
              (SELECT COUNT(*) FROM schedule_cpm_import_observability) AS obs_rows
            """,
            (svk, svk),
        ).fetchone()
    assert counts[0] == 1378
    assert counts[1] == 3718
    assert counts[2] == 2

    latest_status = client.get(
        f"/api/projects/tropical/schedule/imports/{second['import_id']}/status",
        headers=_operator(),
    )
    assert latest_status.status_code == 200, latest_status.text
    latest_cpm = latest_status.json().get("cpm") or {}
    assert latest_cpm.get("cpm_recompute_status") in {"complete", "partial"}
    assert latest_cpm.get("canonical_input_activity_count") == 1378

    first_status = client.get(
        f"/api/projects/tropical/schedule/imports/{first['import_id']}/status",
        headers=_operator(),
    )
    assert first_status.status_code == 200, first_status.text
    first_cpm = first_status.json().get("cpm") or {}
    assert first_cpm.get("cpm_recompute_status") in {"complete", "partial", "failed"}
