"""Schedule quality API tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.schedule_quality_service import ScheduleQualityService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"

MSP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project/2007">
  <Name>MSP Quality API Test</Name>
  <UID>msp-quality-api-test</UID>
  <Tasks>
    <Task>
      <UID>1</UID>
      <ID>10</ID>
      <Name>Critical zero slack</Name>
      <Critical>1</Critical>
      <TotalSlack>0</TotalSlack>
      <FreeSlack>0</FreeSlack>
    </Task>
    <Task>
      <UID>2</UID>
      <ID>20</ID>
      <Name>Noncritical positive slack</Name>
      <Critical>0</Critical>
      <TotalSlack>960</TotalSlack>
      <FreeSlack>480</FreeSlack>
    </Task>
  </Tasks>
</Project>
"""


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _client(tmp_path: Path) -> TestClient:
    db = tmp_path / "quality_api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return TestClient(create_app(db_path=str(db)))


def _client_with_db(tmp_path: Path) -> tuple[TestClient, Path]:
    db = tmp_path / "quality_api.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return TestClient(create_app(db_path=str(db))), db


def _commit_version(client: TestClient) -> str:
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("minimal_schedule.xml", FIXTURE.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    body = commit.json()
    assert body.get("quality_evaluation_status") in {"pending", "completed"}
    return body["schedule_version_key"]


def test_quality_summary_after_commit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _commit_version(client)
    resp = client.get(f"/api/schedules/versions/{svk}/quality", headers=_viewer())
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule_version_key"] == svk
    assert body["assessment_profile"] == "dcma_14_point_plus_gao"
    assert "disclaimer" in body
    assert isinstance(body.get("metrics"), list)


def test_quality_rerun_and_run_detail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    svk = _commit_version(client)
    rerun = client.post(f"/api/schedules/versions/{svk}/quality/rerun", headers=_op())
    assert rerun.status_code == 200
    run_id = rerun.json()["evaluation_run_id"]
    detail = client.get(f"/api/schedules/quality/runs/{run_id}", headers=_viewer())
    assert detail.status_code == 200
    assert detail.json()["evaluation_run_id"] == run_id


def test_project_quality_summary(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _commit_version(client)
    resp = client.get("/api/schedules/projects/tropical/quality/summary", headers=_viewer())
    assert resp.status_code == 200
    assert resp.json()["project_key"] == "tropical"
    assert len(resp.json()["versions"]) >= 1


def test_msp_quality_summary_exposes_source_export_metric(tmp_path: Path) -> None:
    client, db = _client_with_db(tmp_path)
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("msp-source.xml", MSP_XML, "application/xml")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]
    ScheduleQualityService(db_path=str(db)).process_next_pending()

    quality = client.get(f"/api/schedules/versions/{svk}/quality", headers=_viewer())
    assert quality.status_code == 200
    body = quality.json()
    metrics = {m["metric_code"]: m for m in body.get("metrics") or []}
    assert metrics["dcma_critical_path_test"]["status"] == "not_measurable_requires_recalculation"
    source = metrics["source_msp_critical_slack_available"]
    assert source["metric_family"] == "source_export"
    assert source["status"] == "measured_from_msp_critical_flag"
    assert source["numerator"] == "2"
    assert source["denominator"] == "2"
    readiness = body["downstream_readiness"]
    assert readiness["critical_path_analytics"] == "available_source_export_only"
    assert readiness["critical_path_readiness_evidence"]["available_cpm_recalculated"] is False
    assert (
        readiness["critical_path_readiness_evidence"]["critical_path_requires_cpm_recalculation"]
        is True
    )
    assert "critical_path_requires_cpm_recalculation" in readiness["blockers"]


@pytest.mark.parametrize("filename", ["TWNU07.xml", "TWNU16.xml", "TWNU18.xml"])
def test_twnu_quality_scorecard_when_zip_present(tmp_path: Path, filename: str) -> None:
    zip_path = Path("/Users/bobbyfetting/Downloads/schedule-xml-files.zip")
    if not zip_path.exists():
        pytest.skip("schedule-xml-files.zip not present in Downloads")

    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            data = zf.read(filename)
    except PermissionError:
        pytest.skip(f"schedule fixture zip not readable: {zip_path}")

    client = _client(tmp_path)
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (filename, data, "application/xml")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]

    quality = client.get(f"/api/schedules/versions/{svk}/quality", headers=_viewer())
    assert quality.status_code == 200
    body = quality.json()
    assert body["status"] == "completed"
    assert body["assessment_profile"] == "dcma_14_point_plus_gao"
    assert len(body.get("metrics") or []) >= 14
    assert body.get("disclaimer")
    cpli = next(
        (m for m in body.get("metrics") or [] if m.get("metric_code") == "dcma_cpli"),
        None,
    )
    assert cpli is not None
    assert cpli.get("status") == "not_measurable_missing_data"
    metrics = {m["metric_code"]: m for m in body.get("metrics") or []}
    assert metrics["dcma_high_float"]["status"] == "measured_from_derived_finish_float"
    assert metrics["dcma_negative_float"]["status"] == "measured_from_derived_finish_float"
    assert metrics["dcma_critical_path_test"]["status"] == "not_measurable_requires_recalculation"
