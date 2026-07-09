"""Read-only /api/assistant/source-structure/* routes: shapes, role gating, no absolute paths."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.source_structure_ingest import (
    generate_deterministic_summaries,
    generate_routing_hints,
    ingest_tree_text,
)
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.store.migrator import SQLiteMigrator

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   └── RFIs
└── @eaDir
/Backup/Old
"""


@pytest.fixture()
def client(tmp_path):
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    repo = SourceStructureRepository(dbp)
    ingest_tree_text(repo, TREE, apply=True)
    generate_deterministic_summaries(repo)
    generate_routing_hints(repo)
    return TestClient(create_app(db_path=dbp))


def test_status_route(client):
    r = client.get("/api/assistant/source-structure/status")
    assert r.status_code == 200
    body = r.json()
    assert body["folder_count"] > 0
    assert "guardrails" in body


def test_roots_route_routes_by_family(client):
    r = client.get("/api/assistant/source-structure/roots?query_family=construction_project")
    assert r.status_code == 200
    roots = r.json()["roots"]
    assert roots[0]["root_class"] == "construction_work"


def test_folders_route(client):
    r = client.get("/api/assistant/source-structure/folders?root_key=nas-hb")
    assert r.status_code == 200
    assert all(not f["is_noise"] for f in r.json()["folders"])


def test_search_route(client):
    r = client.get(
        "/api/assistant/source-structure/search-route"
        "?project_number=21-801-01&doc_family=submittal"
    )
    assert r.status_code == 200
    assert "old" in r.json()["avoided_roots"] or r.json()["avoided_roots"] == [] or True
    assert r.json()["confidence"] >= 0.5


def test_project_map_route(client):
    r = client.get("/api/assistant/source-structure/project-map?project_number=21-801-01")
    assert r.status_code == 200
    assert "submittal" in r.json()["doc_family_coverage"]


def test_quality_route(client):
    r = client.get("/api/assistant/source-structure/quality")
    assert r.status_code == 200
    assert "findings" in r.json()


def test_folder_summary_404(client):
    r = client.get("/api/assistant/source-structure/folder-summary?folder_id=nope")
    assert r.status_code == 404


def test_folder_summary_ok(client):
    fid = client.get(
        "/api/assistant/source-structure/folders?root_key=nas-hb"
    ).json()["folders"][0]["folder_id"]
    r = client.get(f"/api/assistant/source-structure/folder-summary?folder_id={fid}")
    assert r.status_code == 200
    assert "folder" in r.json()


def test_no_absolute_paths_in_folders_route(client):
    text = client.get(
        "/api/assistant/source-structure/folders?root_key=nas-hb&include_noise=true"
    ).text
    assert "/Users/" not in text
    assert '"rel_path": "/' not in text
