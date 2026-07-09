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
from tests._ss_helpers import assert_no_absolute_paths

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   └── RFIs
└── @eaDir
/Backup/MacBook-Pro.local
└── Documents
/mcp-outputs
└── AI Outputs
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
    body = r.json()
    # Backup + generated roots must be explicitly avoided for a construction-project query...
    assert "macbook-pro-local" in body["avoided_roots"]
    assert "mcp-outputs" in body["avoided_roots"]
    # ...and no preferred folder may come from an avoided root.
    avoided = set(body["avoided_roots"])
    assert all(f["root_key"] not in avoided for f in body["preferred_folders"])
    # The construction-work root leads the preferred roots.
    assert body["preferred_roots"][0]["root_class"] == "construction_work"
    assert body["confidence"] >= 0.5


def test_project_map_route(client):
    r = client.get("/api/assistant/source-structure/project-map?project_number=21-801-01")
    assert r.status_code == 200
    assert "submittal" in r.json()["doc_family_coverage"]


def test_quality_route(client):
    r = client.get("/api/assistant/source-structure/quality")
    assert r.status_code == 200
    assert "findings" in r.json()


def test_readiness_route(client):
    r = client.get("/api/assistant/source-structure/readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["roots_indexed"] >= 1
    assert body["open_error_findings"] == 0
    assert body["gate_on_recommended"] is True


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


def test_no_absolute_paths_in_any_route(client):
    """Recursively assert every one of the 7 read routes leaks no absolute path anywhere."""
    fid = client.get(
        "/api/assistant/source-structure/folders?root_key=nas-hb"
    ).json()["folders"][0]["folder_id"]
    routes = [
        "/api/assistant/source-structure/status",
        "/api/assistant/source-structure/roots?query_family=construction_project",
        "/api/assistant/source-structure/folders?root_key=nas-hb&include_noise=true",
        f"/api/assistant/source-structure/folder-summary?folder_id={fid}",
        "/api/assistant/source-structure/search-route?project_number=21-801-01&doc_family=submittal",
        "/api/assistant/source-structure/project-map?project_number=21-801-01",
        "/api/assistant/source-structure/quality",
    ]
    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert_no_absolute_paths(resp.json(), label=route)
