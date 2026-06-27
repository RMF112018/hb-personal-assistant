"""Schedule identity review API tests."""

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
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_schedule_identity_foundation import (
    _op,
    _xer_with_activity_codes,
    _xer_with_data_date,
)


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    db = tmp_path / "identity-review.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    seed_procore_ep_project(db, project_key="other", display_name="Other Project")
    return TestClient(create_app(db_path=str(db))), db


def _commit(
    client: TestClient,
    *,
    filename: str,
    data: bytes,
    project_key: str = "tropical",
) -> dict[str, Any]:
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (filename, data, "application/octet-stream")},
        data={"project_key": project_key},
    )
    assert preview.status_code == 200, preview.text
    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": project_key, "confirm": True},
    )
    assert commit.status_code == 200, commit.text
    return commit.json()


def test_v78_manual_actions_schema_and_contract_count(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    migrator = SQLiteMigrator(db_path=str(db))
    assert migrator.apply() == LATEST_SCHEMA_VERSION >= 80
    assert migrator.apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "schedule_identity_manual_actions" in names
        assert "schedule_version_diff_detail_facts" in names
        assert (
            conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=78").fetchone()[0]
            == 1
        )
    contract = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
        ).read_text()
    )
    assert contract["table_count"] == 471
    assert contract["tables"]["schedule_identity_manual_actions"]["v"] == "V78"
    assert contract["tables"]["schedule_version_diff_detail_facts"]["v"] == "V79"


def test_identity_review_queue_and_manual_reassign_are_append_only_and_redaction_safe(
    tmp_path: Path,
) -> None:
    client, db = _client(tmp_path)
    first = _commit(
        client,
        filename="/Users/bobby/secret/original.xer",
        data=_xer_with_data_date("2026-06-01"),
    )
    review = _commit(
        client,
        filename="/private/tmp/raw-upload/renamed.xer",
        data=_xer_with_activity_codes("B2000", "B2010", project_name="DEMO"),
    )

    queue = client.get("/api/schedules/projects/tropical/identity-review", headers=_op())
    assert queue.status_code == 200, queue.text
    queue_payload = queue.json()
    assert [item["schedule_version_key"] for item in queue_payload["review_items"]] == [
        review["schedule_version_key"]
    ]
    assert find_redaction_leaks(queue_payload) == []
    serialized = json.dumps(queue_payload, sort_keys=True)
    assert "/Users/" not in serialized
    assert "/private/tmp" not in serialized

    reassigned = client.post(
        f"/api/schedules/projects/tropical/versions/{review['schedule_version_key']}/identity",
        headers=_op(),
        json={"target_identity_key": first["schedule_identity_key"], "reason": "same job"},
    )
    assert reassigned.status_code == 200, reassigned.text

    queue_after = client.get("/api/schedules/projects/tropical/identity-review", headers=_op())
    assert queue_after.status_code == 200
    assert queue_after.json()["review_items"] == []

    health = client.get(
        f"/api/schedules/versions/{review['schedule_version_key']}/health-data",
        headers=_op(),
    )
    assert health.status_code == 200
    basis = health.json()["comparison_basis"]
    assert basis["identity_requires_review"] is False
    assert basis["default_prior_schedule_version_key"] == first["schedule_version_key"]
    assert basis["current_schedule_identity_key"] == first["schedule_identity_key"]
    assert basis["default_prior_available"] is True

    with sqlite3.connect(db) as conn:
        action_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_identity_manual_actions"
        ).fetchone()[0]
        match = conn.execute(
            """
            SELECT schedule_identity_key, requires_review, match_status, no_match_reason
            FROM schedule_version_identity_matches WHERE schedule_version_key=?
            """,
            (review["schedule_version_key"],),
        ).fetchone()
    assert action_count == 1
    assert match == (first["schedule_identity_key"], 0, "resolved", None)


def test_split_and_merge_preserve_merged_identity_visibility(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    first = _commit(client, filename="a.xer", data=_xer_with_data_date("2026-06-01"))
    review = _commit(
        client,
        filename="b.xer",
        data=_xer_with_activity_codes("C3000", "C3010", project_name="DEMO"),
    )

    split = client.post(
        f"/api/schedules/projects/tropical/versions/{review['schedule_version_key']}/identity/split",
        headers=_op(),
        json={"canonical_schedule_name": "Separate schedule", "reason": "different phase"},
    )
    assert split.status_code == 200, split.text
    split_key = split.json()["identity"]["schedule_identity_key"]
    assert split_key != first["schedule_identity_key"]

    merged = client.post(
        f"/api/schedules/projects/tropical/identities/{split_key}/merge",
        headers=_op(),
        json={"target_identity_key": first["schedule_identity_key"], "reason": "operator resolved"},
    )
    assert merged.status_code == 200, merged.text

    active = client.get("/api/schedules/projects/tropical/identities", headers=_op()).json()
    assert split_key not in {item["schedule_identity_key"] for item in active["identities"]}
    all_identities = client.get(
        "/api/schedules/projects/tropical/identities?show_merged=true", headers=_op()
    ).json()
    merged_identity = next(
        item for item in all_identities["identities"] if item["schedule_identity_key"] == split_key
    )
    assert merged_identity["identity_status"] == "merged"

    detail = client.get(
        f"/api/schedules/projects/tropical/identities/{split_key}",
        headers=_op(),
    )
    assert detail.status_code == 200
    assert detail.json()["identity"]["identity_status"] == "merged"

    with sqlite3.connect(db) as conn:
        actions = conn.execute(
            "SELECT action_type FROM schedule_identity_manual_actions"
        ).fetchall()
    assert sorted(row[0] for row in actions) == ["merge", "split"]


def test_identity_manual_actions_reject_cross_project_scope(tmp_path: Path) -> None:
    client, _db = _client(tmp_path)
    first = _commit(client, filename="a.xer", data=_xer_with_data_date("2026-06-01"))
    review = _commit(
        client,
        filename="b.xer",
        data=_xer_with_activity_codes("D4000", "D4010", project_name="DEMO"),
    )

    cross = client.post(
        f"/api/schedules/projects/other/versions/{review['schedule_version_key']}/identity",
        headers=_op(),
        json={"target_identity_key": first["schedule_identity_key"], "reason": "bad scope"},
    )
    assert cross.status_code in {404, 409}
