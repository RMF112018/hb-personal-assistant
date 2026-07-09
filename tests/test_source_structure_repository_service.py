"""Repository + ingest + service + quality integration (no absolute-path leakage; bounded reads)."""

from __future__ import annotations

import pytest

from hb_assistant.obsidian_mcp.source_structure_ingest import (
    generate_deterministic_summaries,
    generate_routing_hints,
    ingest_tree_text,
)
from hb_assistant.obsidian_mcp.source_structure_quality import compute_findings
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.obsidian_mcp.source_structure_service import SourceStructureService
from hb_assistant.store.migrator import SQLiteMigrator

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   ├── RFIs
│   └── Pay Applications
├── @eaDir
└── 21-801-01 NORA COPY
    └── Submittals
/Backup/MacBook-Pro.local
└── Documents
"""


@pytest.fixture()
def seeded(tmp_path):
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    repo = SourceStructureRepository(dbp)
    ingest_tree_text(repo, TREE, apply=True)
    generate_deterministic_summaries(repo)
    generate_routing_hints(repo)
    repo.replace_findings(compute_findings(repo))
    return dbp, repo


def test_dry_run_writes_nothing(tmp_path):
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    repo = SourceStructureRepository(dbp)
    res = ingest_tree_text(repo, TREE, apply=False)
    assert res["applied"] is False
    assert repo.status()["folder_count"] == 0


def test_apply_persists_rows(seeded):
    _dbp, repo = seeded
    st = repo.status()
    assert st["root_count"] == 2
    assert st["folder_count"] > 0
    assert st["entity_count"] == 1  # one project


def test_root_map_prefers_construction_and_downranks_backup(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    roots = svc.root_map(query_family="construction_project")["roots"]
    assert roots[0]["root_class"] == "construction_work"
    backup = next(r for r in roots if r["root_class"] == "backup_mirror")
    assert backup["default_search_rank"] > roots[0]["default_search_rank"]


def test_search_route_avoids_backup_and_finds_project(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    sr = svc.search_route(project_number="21-801-01", doc_family="submittal")
    assert "macbook-pro-local" in sr["avoided_roots"]
    assert any(f["project_number"] == "21-801-01" for f in sr["preferred_folders"])


def test_project_map_covers_doc_families_via_inheritance(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    pm = svc.project_map("21-801-01")
    assert set(pm["doc_family_coverage"]) >= {"submittal", "rfi", "pay_app"}


def test_duplicate_project_folder_finding(seeded):
    _dbp, repo = seeded
    findings = compute_findings(repo)
    assert any(f["finding_type"] == "duplicate_project_folder" for f in findings)


def test_folder_map_excludes_noise_by_default(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    default = svc.folder_map(root_key="nas-hb")
    assert all(not f["is_noise"] for f in default["folders"])
    with_noise = svc.folder_map(root_key="nas-hb", include_noise=True)
    assert with_noise["total"] >= default["total"]


def test_no_absolute_paths_in_any_client_surface(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    payloads = [
        svc.root_map(),
        svc.folder_map(root_key="nas-hb", include_noise=True, limit=200),
        svc.search_route(project_number="21-801-01"),
        svc.project_map("21-801-01"),
        svc.quality(limit=200),
    ]
    blob = repr(payloads)
    assert "/Users/" not in blob
    assert "/Volumes/" not in blob
    assert "'rel_path': '/" not in blob


def test_folder_map_pagination_cursor(seeded):
    dbp, _repo = seeded
    svc = SourceStructureService(dbp)
    page1 = svc.folder_map(root_key="nas-hb", include_noise=True, limit=2)
    assert len(page1["folders"]) <= 2
    if page1["next_cursor"]:
        page2 = svc.folder_map(root_key="nas-hb", include_noise=True, limit=2,
                               cursor=page1["next_cursor"])
        ids1 = {f["folder_id"] for f in page1["folders"]}
        ids2 = {f["folder_id"] for f in page2["folders"]}
        assert ids1.isdisjoint(ids2)


def test_forbidden_path_finding_fires_on_absolute_rel_path(tmp_path):
    """A folder row with an absolute rel_path must raise the hard safety finding."""
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    repo = SourceStructureRepository(dbp)
    from hb_assistant.obsidian_mcp.source_structure_classifier import classify_folder, classify_root
    from hb_assistant.obsidian_mcp.source_structure_models import FolderSample

    root = classify_root("nas-hb", "NAS - HB")
    repo.upsert_root(root)
    cls = classify_folder(FolderSample(root_key="nas-hb", rel_path="/Users/x/secret",
                                       name="secret", depth=1), root)
    repo.upsert_folder(root_key="nas-hb", rel_path="/Users/x/secret", name="secret", depth=1,
                       parent_rel_path=None, classification=cls, child_folder_count=0,
                       file_count=0, dominant_extensions=[], sample_names=[])
    findings = compute_findings(repo)
    assert any(f["finding_type"] == "forbidden_path_exposed" and f["severity"] == "error"
               for f in findings)
