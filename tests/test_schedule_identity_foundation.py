"""Schedule identity foundation tests."""

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
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _client(tmp_path: Path) -> tuple[TestClient, Path]:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return TestClient(create_app(db_path=str(db))), db


def _commit_bytes(
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
    body = preview.json()
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": body["import_id"], "project_key": project_key, "confirm": True},
    )
    assert commit.status_code == 200, commit.text
    return commit.json()


def _xer_with_data_date(date_value: str) -> bytes:
    text = XER_FIXTURE.read_text()
    return text.replace("2026-06-01 08:00", f"{date_value} 08:00").encode()


def _xer_with_activity_codes(*codes: str, project_name: str = "DEMO") -> bytes:
    first, second = codes
    text = XER_FIXTURE.read_text()
    text = text.replace("%R\t1\tDEMO\tCP_Drtn", f"%R\t1\t{project_name}\tCP_Drtn")
    text = text.replace("2026-06-01 08:00", "2026-07-01 08:00")
    text = text.replace("\tA1000\tDriving Task\t", f"\t{first}\tDriving Task\t")
    text = text.replace("\tA1010\tFloat Task\t", f"\t{second}\tFloat Task\t")
    return text.encode()


def _xml_same_source_id_name_different_content() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>1</ObjectId>
    <Id>1</Id>
    <Name>DEMO</Name>
    <DataDate>2026-08-01</DataDate>
  </Project>
  <WBS><ObjectId>WX</ObjectId><Code>OTHER</Code><Name>Other WBS</Name></WBS>
  <Activity>
    <ObjectId>BX1</ObjectId><Id>B2000</Id><Name>Different Work</Name>
    <WBSObjectId>WX</WBSObjectId><PlannedStartDate>2026-08-01</PlannedStartDate>
    <PlannedFinishDate>2026-08-05</PlannedFinishDate>
  </Activity>
  <Activity>
    <ObjectId>BX2</ObjectId><Id>B2010</Id><Name>Different Finish</Name>
    <WBSObjectId>WX</WBSObjectId><PlannedStartDate>2026-08-06</PlannedStartDate>
    <PlannedFinishDate>2026-08-10</PlannedFinishDate>
  </Activity>
  <Relationship>
    <ObjectId>RX1</ObjectId>
    <PredecessorActivityObjectId>BX1</PredecessorActivityObjectId>
    <SuccessorActivityObjectId>BX2</SuccessorActivityObjectId>
    <Type>FS</Type>
  </Relationship>
</APIBusinessObjects>
"""


def test_v76_v77_schedule_identity_schema_fresh_and_v75_self_heal(tmp_path: Path) -> None:
    fresh_db = tmp_path / "fresh.db"
    migrator = SQLiteMigrator(db_path=str(fresh_db))
    assert migrator.apply() == LATEST_SCHEMA_VERSION == 77
    assert migrator.apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(fresh_db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "schedule_identities",
            "schedule_version_identity_matches",
            "schedule_identity_manual_actions",
        } <= tables

    stale_db = tmp_path / "v75.db"
    SQLiteMigrator(db_path=str(stale_db)).apply()
    with sqlite3.connect(stale_db) as conn:
        conn.execute("DROP TABLE schedule_version_identity_matches")
        conn.execute("DROP TABLE schedule_identities")
        conn.execute("DELETE FROM schema_migrations WHERE version >= 76")
        conn.commit()
    seed_procore_ep_project(stale_db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(stale_db)))
    response = client.get("/api/schedules/projects", headers=_op())
    assert response.status_code == 200
    with sqlite3.connect(stale_db) as conn:
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert int(version) == LATEST_SCHEMA_VERSION
    assert {
        "schedule_identities",
        "schedule_version_identity_matches",
        "schedule_identity_manual_actions",
    } <= tables


def test_same_xer_content_different_filenames_share_identity_and_default_diff(
    tmp_path: Path,
) -> None:
    client, db = _client(tmp_path)
    first = _commit_bytes(
        client,
        filename="/Users/bobby/source/original.xer",
        data=_xer_with_data_date("2026-06-01"),
    )
    second = _commit_bytes(
        client,
        filename="/tmp/renamed-copy.xer",
        data=_xer_with_data_date("2026-07-01"),
    )

    assert first["schedule_identity_key"] == second["schedule_identity_key"]
    assert second["identity_match"]["match_status"] == "resolved"
    assert second["identity_match"]["requires_review"] is False
    assert (
        second["identity_match"]["matched_prior_schedule_version_key"]
        == first["schedule_version_key"]
    )
    assert second["default_diff_id"] is not None

    health = client.get(
        f"/api/schedules/versions/{second['schedule_version_key']}/health-data",
        headers=_op(),
    )
    assert health.status_code == 200
    payload = health.json()
    assert (
        payload["identity_match"]["matched_prior_schedule_version_key"]
        == first["schedule_version_key"]
    )
    assert find_redaction_leaks(payload) == []
    serialized = json.dumps(payload, sort_keys=True)
    assert "/Users/" not in serialized
    assert "/tmp/" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "token" not in serialized.lower()

    with sqlite3.connect(db) as conn:
        match_count = conn.execute(
            """
            SELECT COUNT(*) FROM schedule_version_identity_matches
            WHERE schedule_version_key IN (?, ?)
            """,
            (first["schedule_version_key"], second["schedule_version_key"]),
        ).fetchone()[0]
    assert int(match_count) == 2


def test_project_metadata_and_matching_name_without_content_do_not_auto_match(
    tmp_path: Path,
) -> None:
    client, db = _client(tmp_path)
    first = _commit_bytes(client, filename="schedule-a.xer", data=_xer_with_data_date("2026-06-01"))
    second = _commit_bytes(
        client,
        filename="schedule-b.xer",
        data=_xer_with_activity_codes("B2000", "B2010", project_name="DEMO"),
    )

    assert first["schedule_identity_key"] != second["schedule_identity_key"]
    assert second["identity_match"]["requires_review"] is True
    assert second["identity_match"]["no_match_reason"] == "no_content_compatible_match"
    assert second["default_diff_id"] is None
    with sqlite3.connect(db) as conn:
        reason = conn.execute(
            """
            SELECT unavailable_reason FROM schedule_source_capabilities
            WHERE schedule_version_key=? AND capability_key='default_version_diff'
            """,
            (second["schedule_version_key"],),
        ).fetchone()[0]
    assert reason == "identity_requires_review"


def test_cross_format_source_id_alone_does_not_match(tmp_path: Path) -> None:
    client, _db = _client(tmp_path)
    first = _commit_bytes(client, filename="schedule.xer", data=_xer_with_data_date("2026-06-01"))
    second = _commit_bytes(
        client,
        filename="schedule.xml",
        data=_xml_same_source_id_name_different_content(),
    )

    assert first["schedule_identity_key"] != second["schedule_identity_key"]
    assert second["identity_match"]["requires_review"] is True
    assert second["identity_match"]["no_match_reason"] == "no_content_compatible_match"


def test_multiple_content_candidates_become_ambiguous(tmp_path: Path) -> None:
    db = tmp_path / "ambiguous.db"
    SQLiteMigrator(db_path=str(db)).apply()
    repo = ScheduleIdentityRepository(db_path=str(db))
    evidence = repo.build_evidence(
        project_key="tropical",
        schedule_version_key="tropical|1|2026-09-01",
        import_id="imp-new",
        source_format="primavera_xer",
        source_filename="new.xer",
        source_project_id="1",
        source_project_name="DEMO",
        schedule_name="DEMO",
        activities=[{"activity_id": "A1000"}, {"activity_id": "A1010"}],
        relationships=[
            {
                "predecessor_activity_id": "A1000",
                "successor_activity_id": "A1010",
                "relationship_type": "FS",
            }
        ],
        wbs_nodes=[{"wbs_id": "10", "wbs_code": "wbs1", "wbs_name": "WBS Root"}],
    )
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        for idx in (1, 2):
            import_id = f"imp-{idx}"
            version_key = f"tropical|1|2026-0{idx}-01"
            identity_key = f"identity-{idx}"
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, wbs_count, calendar_count,
                  code_count, udf_count, cost_loaded_status, schedule_version_key
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed', 2, 1, 1, 0, 0, 0,
                  'not_cost_loaded', ?)
                """,
                (import_id, version_key),
            )
            for activity_id in ("A1000", "A1010"):
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_activities (
                      project_key, schedule_id, schedule_version_key, import_id,
                      source_type, source_format, activity_id
                    ) VALUES ('tropical', '1', ?, ?, 'xer', 'primavera_xer', ?)
                    """,
                    (version_key, import_id, activity_id),
                )
            conn.execute(
                """
                INSERT INTO schedule_identities (
                  schedule_identity_key, project_key, latest_import_id, latest_schedule_version_key
                ) VALUES (?, 'tropical', ?, ?)
                """,
                (identity_key, import_id, version_key),
            )
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_id_set_fingerprint, wbs_fingerprint,
                  relationship_graph_fingerprint, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, ?, ?, ?, 'tropical', 'primavera_xer', ?, ?, ?, 2, 1, 1,
                  'new_identity', 'resolved', 'seed', '1.00', 0)
                """,
                (
                    f"match-{idx}",
                    identity_key,
                    version_key,
                    import_id,
                    evidence.activity_id_set_fingerprint,
                    evidence.wbs_fingerprint,
                    evidence.relationship_graph_fingerprint,
                ),
            )
        conn.commit()
        resolution = repo.resolve_and_persist(evidence, conn=conn)

    assert resolution.match["match_status"] == "ambiguous"
    assert resolution.match["requires_review"] == 1
    assert resolution.match["no_match_reason"] == "multiple_identity_candidates"
    assert resolution.match["candidate_count"] == 2
