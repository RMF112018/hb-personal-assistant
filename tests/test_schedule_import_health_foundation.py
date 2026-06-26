"""Schedule import health foundation tests."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
try:
    from fastapi.testclient import TestClient
except RuntimeError as exc:  # pragma: no cover - environment guard
    pytest.skip(str(exc), allow_module_level=True)

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.schedule_xml_parser import parse_pmxml_package_bytes
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _baseline_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<APIBusinessObjects>
  <Project>
    <ObjectId>100</ObjectId>
    <Id>CUR</Id>
    <Name>Current Schedule</Name>
    <DataDate>2026-06-01</DataDate>
    <CurrentBaselineProjectObjectId>200</CurrentBaselineProjectObjectId>
  </Project>
  <WBS><ObjectId>W1</ObjectId><Code>ROOT</Code><Name>Root</Name></WBS>
  <Activity>
    <ObjectId>A1O</ObjectId><Id>A1</Id><Name>Start Work</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-06-01</PlannedStartDate>
    <PlannedFinishDate>2026-06-05</PlannedFinishDate>
    <UDF><UDFType>Risk</UDFType><UDFValue>Low</UDFValue></UDF>
  </Activity>
  <Activity>
    <ObjectId>A2O</ObjectId><Id>A2</Id><Name>Finish Work</Name>
    <WBSObjectId>W1</WBSObjectId><PlannedStartDate>2026-06-06</PlannedStartDate>
    <PlannedFinishDate>2026-06-10</PlannedFinishDate>
  </Activity>
  <Relationship>
    <ObjectId>R1</ObjectId><PredecessorActivityObjectId>A1O</PredecessorActivityObjectId>
    <SuccessorActivityObjectId>A2O</SuccessorActivityObjectId><Type>FS</Type>
  </Relationship>
  <BaselineProject>
    <ObjectId>200</ObjectId>
    <Id>BL1</Id>
    <Name>Approved Baseline</Name>
    <OriginalProjectObjectId>100</OriginalProjectObjectId>
    <DataDate>2026-05-01</DataDate>
    <WBS><ObjectId>BW1</ObjectId><Code>ROOT</Code><Name>Root</Name></WBS>
    <Activity>
      <ObjectId>BA1O</ObjectId><Id>A1</Id><Name>Start Work</Name>
      <WBSObjectId>BW1</WBSObjectId><PlannedStartDate>2026-05-01</PlannedStartDate>
      <PlannedFinishDate>2026-05-05</PlannedFinishDate>
      <UDF><UDFType>BaselineFlag</UDFType><UDFValue>Y</UDFValue></UDF>
    </Activity>
    <Activity>
      <ObjectId>BA2O</ObjectId><Id>A2</Id><Name>Finish Work</Name>
      <WBSObjectId>BW1</WBSObjectId><PlannedStartDate>2026-05-06</PlannedStartDate>
      <PlannedFinishDate>2026-05-10</PlannedFinishDate>
    </Activity>
    <Relationship>
      <ObjectId>BR1</ObjectId><PredecessorActivityObjectId>BA1O</PredecessorActivityObjectId>
      <SuccessorActivityObjectId>BA2O</SuccessorActivityObjectId><Type>FS</Type>
    </Relationship>
  </BaselineProject>
</APIBusinessObjects>
"""


def _zip_payload() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("schedule.xml", _baseline_xml())
        zf.writestr("notes.txt", "ignored")
    return buf.getvalue()


def test_v75_schedule_import_health_tables_present(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION >= 75
    with sqlite3.connect(db) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "schedule_import_packages" in tables
    assert "schedule_baseline_projects" in tables
    assert "schedule_version_diff_facts" in tables


def test_pmxml_package_parser_separates_current_and_baseline() -> None:
    entities = parse_pmxml_package_bytes(_baseline_xml(), source_file_id="xml-1")
    current = [e for e in entities if e.role == "current"]
    baselines = [e for e in entities if e.role == "baseline"]
    assert len(current) == 1
    assert len(baselines) == 1
    assert [a["activity_id"] for a in current[0].activities] == ["A1", "A2"]
    assert [a["activity_id"] for a in baselines[0].activities] == ["A1", "A2"]
    assert current[0].activities[0]["planned_start"] == "2026-06-01"
    assert baselines[0].activities[0]["planned_start"] == "2026-05-01"
    assert baselines[0].udf_values[0]["udf_type_name"] == "BaselineFlag"


def test_zip_package_import_persists_baseline_and_health_data(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("schedule-package.zip", _zip_payload(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["package_mode"] == "zip_package"
    assert body["activity_count"] == 2
    assert body["baseline_project_candidates"][0]["project_id"] == "BL1"
    assert any(w["code"] == "unsupported_package_file_ignored" for w in body["warnings"])

    commit = client.post(
        "/api/schedules/import-commit",
        headers=_operator(),
        json={"import_id": body["import_id"], "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    commit_body = commit.json()
    assert commit_body["baseline_project_count"] == 1
    assert commit_body["baseline_activity_count"] == 2

    svk = commit_body["schedule_version_key"]
    with sqlite3.connect(db) as conn:
        baseline_count = conn.execute(
            "SELECT COUNT(*) FROM schedule_baseline_activities WHERE current_schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
        current_count = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
            (svk,),
        ).fetchone()[0]
    assert current_count == 2
    assert baseline_count == 2

    health = client.get(f"/api/schedules/versions/{svk}/health-data", headers=_operator())
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["import_package"]["package_mode"] == "zip_package"
    assert health_body["baseline_projects"][0]["baseline_project_id"] == "BL1"
    assert health_body["deferred_domains"]["cost_schedule_correlation"] == "deferred"


def test_zip_rejects_path_traversal(tmp_path: Path) -> None:
    db = tmp_path / "api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w") as zf:
        zf.writestr("../escape.xml", _baseline_xml())

    resp = client.post(
        "/api/schedules/import-preview",
        headers=_operator(),
        files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
        data={"project_key": "tropical"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "schedule_zip_unsafe_path"
