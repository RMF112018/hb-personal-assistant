"""One-row-per-project_key repair for procore_ep_projects projection."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from hb_assistant.procore import projection_engine as eng
from hb_assistant.procore.projects_projection import (
    PROJECTS_PRIMARY_TABLE,
    dedupe_procore_ep_projects,
    projects_record_key_for_project_key,
)
from hb_assistant.procore.structured_analytics import scrub_transport_secrets
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project_row

TROPICAL_ID = "2525840"
RYBOVICH_ID = "3133242"


def _project_payload(*, project_id: str, display_name: str, project_number: str) -> dict[str, Any]:
    return {
        "id": int(project_id),
        "display_name": display_name,
        "project_number": project_number,
    }


def _project(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    project_key: str,
    procore_project_id: str,
) -> dict[str, Any]:
    scrubbed = scrub_transport_secrets(payload)
    return eng.project_endpoint_specific(
        conn,
        endpoint_id="projects",
        project_key=project_key,
        procore_project_id=procore_project_id,
        record_id=str(payload["id"]),
        parent_record_id=None,
        payload=scrubbed,
        raw_payload_id=f"raw-{project_key}-{payload['id']}",
        payload_hash=f"hash-{project_key}-{payload['id']}",
        source_quality="fixture_full",
        fetched_at="2026-06-22T00:00:00Z",
        now_utc="2026-06-22T00:00:00Z",
        mode=eng.MODE_ENFORCE,
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    db = tmp_path / "projects.db"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    return db


def test_projects_projection_skips_non_matching_company_list_items(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        tropical = _project_payload(
            project_id=TROPICAL_ID,
            display_name="Tropical - S L",
            project_number="23-435-01",
        )
        rybovich = _project_payload(
            project_id=RYBOVICH_ID,
            display_name="Rybovich Safe Harbor",
            project_number="25-745-01",
        )
        skip = _project(conn, rybovich, project_key="tropical", procore_project_id=TROPICAL_ID)
        assert skip["endpoint_specific_projection_status"] == "skipped_non_matching_project"

        ok = _project(conn, tropical, project_key="tropical", procore_project_id=TROPICAL_ID)
        assert ok["primary_rows"] == 1
        conn.commit()

        count = conn.execute(f"SELECT COUNT(*) FROM {PROJECTS_PRIMARY_TABLE}").fetchone()[0]
        assert count == 1
        row = conn.execute(
            f"SELECT project_key, record_id, display_name FROM {PROJECTS_PRIMARY_TABLE}"
        ).fetchone()
        assert row[0] == "tropical"
        assert row[1] == TROPICAL_ID
        assert row[2] == "Tropical - S L"
    finally:
        conn.close()


def test_projects_projection_upserts_one_row_per_project_key(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        tropical = _project_payload(
            project_id=TROPICAL_ID,
            display_name="Tropical - S L",
            project_number="23-435-01",
        )
        _project(conn, tropical, project_key="tropical", procore_project_id=TROPICAL_ID)
        tropical["display_name"] = "Tropical Updated"
        _project(conn, tropical, project_key="tropical", procore_project_id=TROPICAL_ID)
        conn.commit()

        rows = conn.execute(
            f"SELECT project_key, record_key, display_name FROM {PROJECTS_PRIMARY_TABLE}"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "tropical"
        assert rows[0][1] == projects_record_key_for_project_key("tropical")
        assert rows[0][2] == "Tropical Updated"
    finally:
        conn.close()


def test_dedupe_and_unique_index_leave_one_row_per_project_key(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP INDEX IF EXISTS idx_procore_ep_projects_project_key_unique")
        conn.commit()
    for idx, display_name in enumerate(
        ["Wrong A", "Wrong B", "Tropical - S L"],
        start=1,
    ):
        seed_procore_ep_project_row(
            db_path,
            project_key="tropical",
            display_name=display_name,
            project_number="23-435-01",
            project_id=TROPICAL_ID,
            record_key=f"rk-tropical-{idx}",
            updated_utc=f"2026-06-2{idx}T00:00:00Z",
        )
    with sqlite3.connect(db_path) as conn:
        result = dedupe_procore_ep_projects(conn)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_procore_ep_projects_project_key_unique
            ON procore_ep_projects(project_key)
            """
        )
        conn.commit()
        assert result["deleted_primaries"] == 2
        count = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_projects WHERE project_key='tropical'"
        ).fetchone()[0]
        assert count == 1
        row = conn.execute(
            "SELECT record_key, record_id, project_id, display_name FROM procore_ep_projects WHERE project_key='tropical'"
        ).fetchone()
        assert row[0] == projects_record_key_for_project_key("tropical")
        assert row[1] == TROPICAL_ID
        assert row[2] == TROPICAL_ID
        assert row[3] == "Tropical - S L"