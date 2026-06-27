"""Schedule version-over-version diff tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

MINIMAL = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "minimal_schedule.xml"
GMA = Path(__file__).resolve().parent / "fixtures" / "schedules" / "xml" / "gma_sample.xml"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _commit(client: TestClient, fixture: Path, filename: str) -> str:
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (filename, fixture.read_bytes(), "application/xml")},
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
    return str(commit.json()["schedule_version_key"])


def test_version_diff_across_imports(tmp_path: Path) -> None:
    db = tmp_path / "diff.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    from_v = _commit(client, MINIMAL, "minimal_a.xml")
    to_v = _commit(client, GMA, "gma_b.xml")

    resp = client.get(
        f"/api/schedules/projects/tropical/diff?from={from_v}&to={to_v}",
        headers=_op(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert find_redaction_leaks(body) == []
    assert body["from_schedule_version_key"] == from_v
    assert body["to_schedule_version_key"] == to_v
    assert body["activity_added_count"] >= 0
    assert body["diff_type"] == "activity_id_aligned"


@pytest.mark.parametrize(
    "filename,expected_acts,expected_rels",
    [
        ("TWNU07.xml", 1177, 2658),
        ("TWNU16.xml", 1420, 3780),
        ("TWNU18.xml", 1378, 3718),
    ],
)
def test_twnu_import_counts_when_zip_present(
    tmp_path: Path, filename: str, expected_acts: int, expected_rels: int
) -> None:
    zip_path = Path("/Users/bobbyfetting/Downloads/schedule-xml-files.zip")
    if not zip_path.exists():
        pytest.skip("schedule-xml-files.zip not present in Downloads")

    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            data = zf.read(filename)
    except PermissionError:
        pytest.skip(f"schedule fixture zip not readable: {zip_path}")

    db = tmp_path / f"{filename}.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))

    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": (filename, data, "application/xml")},
        data={"project_key": "tropical"},
    )
    assert preview.status_code == 200
    assert preview.json()["activity_count"] == expected_acts
    assert preview.json()["relationship_count"] == expected_rels

    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    assert commit.status_code == 200
    svk = commit.json()["schedule_version_key"]

    acts = client.get(f"/api/schedules/versions/{svk}/activities?limit=10000")
    assert acts.json()["total_count"] == expected_acts
    assert len(acts.json()["activities"]) == expected_acts
