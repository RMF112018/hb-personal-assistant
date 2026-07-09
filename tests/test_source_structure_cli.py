"""CLI (`hb-assistant source-structure`) — dry-run/apply semantics + read commands + refusals."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.source_structure import app
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   └── RFIs
└── @eaDir
"""


def _db(tmp_path) -> str:
    dbp = str(tmp_path / "pa.db")
    SQLiteMigrator(dbp).apply()
    return dbp


def _tree_file(tmp_path) -> str:
    p = tmp_path / "tree.txt"
    p.write_text(TREE, encoding="utf-8")
    return str(p)


def test_ingest_tree_dry_run_writes_nothing(tmp_path):
    dbp = _db(tmp_path)
    r = runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is False
    assert SourceStructureRepository(dbp).status()["folder_count"] == 0


def test_ingest_tree_apply_persists(tmp_path):
    dbp = _db(tmp_path)
    r = runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    assert r.exit_code == 0
    body = json.loads(r.stdout)
    assert body["applied"] is True
    assert body["counts"]["folders"] > 0
    assert SourceStructureRepository(dbp).status()["folder_count"] > 0


def test_scan_roots_refuses_unconfigured(tmp_path):
    dbp = _db(tmp_path)
    # No scan roots configured in the default config → exit code 2 refusal.
    r = runner.invoke(app, ["scan-roots", "--roots", "nope", "--db", dbp])
    assert r.exit_code == 2
    assert json.loads(r.stdout)["ok"] is False


def test_quality_dry_run_vs_apply(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    dry = runner.invoke(app, ["quality", "--db", dbp])
    assert json.loads(dry.stdout)["applied"] is False
    applied = runner.invoke(app, ["quality", "--db", dbp, "--apply"])
    assert json.loads(applied.stdout)["applied"] is True


def test_inspect_root_and_project_map(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    ir = runner.invoke(app, ["inspect-root", "--root", "nas-hb", "--db", dbp])
    assert json.loads(ir.stdout)["root"]["root_class"] == "construction_work"
    pm = runner.invoke(app, ["project-map", "--project", "21-801-01", "--db", dbp])
    assert "submittal" in json.loads(pm.stdout)["doc_family_coverage"]


def test_export_evidence_writes_files(tmp_path):
    dbp = _db(tmp_path)
    runner.invoke(app, ["ingest-tree", "--input", _tree_file(tmp_path), "--db", dbp, "--apply"])
    out = tmp_path / "ev"
    r = runner.invoke(app, ["export-evidence", "--output-dir", str(out), "--db", dbp])
    assert r.exit_code == 0
    files = {f.split("/")[-1] for f in json.loads(r.stdout)["files"]}
    assert "source_structure_counts.json" in files
    assert (out / "quality_findings.json").exists()
