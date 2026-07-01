"""Phase 10D — project identity attaches at index time + the enriched cards yield graph candidates."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_note_graph as ng
from hb_assistant.obsidian_mcp.config import ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import index_source_file
from hb_assistant.store.migrator import SQLiteMigrator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_index_project_corpus.py"
_spec = importlib.util.spec_from_file_location("index_project_corpus2", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_ROWS = [{"project_key": "tropical", "project_number": "23-435-01",
          "display_name": "23-435-01 - Tropical World Nursery Senior Living Facility",
          "procore_project_id": "2525840"}]


@pytest.fixture(autouse=True)
def _patches(monkeypatch):
    monkeypatch.setattr(mod, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(mod, "_readability", lambda p: "readable")
    import hb_assistant.construction.analytics.project_summary_readmodel as rm

    class _Fake:
        def build(self):
            return {"projects": _ROWS}
    monkeypatch.setattr(rm, "ProjectSummaryReadModelService", lambda *, db_path=None: _Fake())


def _env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    y = tmp_path / "c.yml"
    y.write_text(f"paths:\n  application_support_root: {str(tmp_path / 'as')!r}\n"
                 f"  obsidian_vault: {vault.as_posix()!r}\n")
    monkeypatch.setenv("HB_PA_CONFIG", str(y))
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    base = tmp_path / "synbase"
    troot = base / "NAS - HB" / "Projects" / "2023" / "23-435-01 - Tropical"
    (troot / "10_Preconstruction").mkdir(parents=True)
    (troot / "10_Preconstruction" / "RFI 001 Doors.md").write_text("RFI doors.", encoding="utf-8")
    (troot / "10_Preconstruction" / "Submittal 03 Concrete.md").write_text("Submittal.", encoding="utf-8")
    (troot / "10_Preconstruction" / "Contact List.csv").write_text("a,b\n1,2", encoding="utf-8")
    cfg = {"enabled": True, "vault_root": str(vault), "writes_enabled": True,
           "vault_markdown_write_enabled": True, "source_card_generation_enabled": True,
           "external_source_watch_enabled": False, "source_card_auto_generate_enabled": False,
           "source_summary_auto_generate_enabled": False, "source_note_auto_refresh_enabled": False,
           "external_sources": [{"source_root_key": "syn-work", "path": str(base), "enabled": True}]}
    cfgp = tmp_path / "cfg.json"
    cfgp.write_text(json.dumps(cfg))
    config = ObsidianMcpConfig.model_validate(cfg)
    return {"db": db, "cfgp": str(cfgp), "vault": vault, "base": base, "troot": troot,
            "config": config, "repo": SourceIndexRepository(db)}


def test_index_derives_project_number_including_metadata_only(tmp_path, monkeypatch):
    env = _env(tmp_path, monkeypatch)
    root = env["config"].external_sources[0]
    from hb_assistant.obsidian_mcp.source_value import classify_source_value
    for rel in ("10_Preconstruction/RFI 001 Doors.md", "10_Preconstruction/Contact List.csv"):
        abs_p = env["troot"] / rel
        sid = index_source_file(abs_p, root, env["repo"], env["config"])
        detail = env["repo"].get_source_detail(sid)
        # project_number auto-derived from the rel-path's 23-435-01 code, even for metadata-only files
        assert detail["project_number"] == "23-435-01"
    # the csv is metadata-only but still carries project identity
    csv_detail = env["repo"].get_source_detail(
        env["repo"].lookup_by_path("external_file",
                                   "NAS - HB/Projects/2023/23-435-01 - Tropical/10_Preconstruction/Contact List.csv")
        ["source_id"])
    assert csv_detail["project_number"] == "23-435-01"
    assert classify_source_value(csv_detail, env["config"]).disposition.value == "metadata_only"


def _args(env, *, apply, enrich):
    sr = str(env["troot"])
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--source-root", sr, "--root-key", "syn-work", "--max-files", "100",
         "--evidence-dir", str(Path(env["db"]).parent / "ev"),
         "--backup-dir", str(Path(env["db"]).parent / "bk"), "--json-output",
         "--confirm-project-number", "23-435-01", "--confirm-project-key", "tropical"]
    if apply:
        a += ["--apply", "--confirm-source-root", sr, "--confirm-vault-path", str(env["vault"]),
              "--confirm-db-path", env["db"]]
    if enrich:
        a.append("--enrich")
    return a


def test_apply_enrich_then_graph_yields_candidates(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    rc = mod.main(_args(env, apply=True, enrich=True))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["cards_generated"] == 3 and out["cards_enriched_existing"] == 3
    assert out["project_number_derived"] == 3 and out["queue_delta"] == 0
    # rollback bundle exists
    assert (Path(env["db"]).parent / "bk" / "db-backup.sqlite").is_file()
    assert (Path(env["db"]).parent / "bk" / "rollback-manifest.json").is_file()

    # Enriched cards carry the canonical identity block, and the graph now yields candidates.
    repo = env["repo"]
    work_prefix = "Source Notes/" + "Work/"
    rows = [r for r in repo.list_generated_notes(statuses=("generated",))
            if str(r["note_rel_path"]).startswith(work_prefix)]
    assert len(rows) == 3
    facts = []
    for r in rows:
        text = (env["vault"] / r["note_rel_path"]).read_text(encoding="utf-8")
        assert 'project_key="tropical"' in text  # identity block present
        facts.append(ng.note_fact_from(repo, r, text))
    assert all(f.canonical_project_key == "tropical" for f in facts)
    assert all(f.procore_project_id == "2525840" for f in facts)
    cands = ng.build_candidates(facts, max_per_note=10, max_relationships=50)
    assert len(cands) >= 1  # candidates now emerge from deterministic project identity
    basis = ng.candidate_basis_counts(cands)
    assert basis.get("same_project_number", 0) >= 1
    assert basis.get("same_project_key", 0) >= 1
    assert basis.get("same_procore_id", 0) >= 1


def test_apply_is_idempotent(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, monkeypatch)
    mod.main(_args(env, apply=True, enrich=False))
    capsys.readouterr()
    # second run: everything already indexed + carded → skipped, no new cards
    rc = mod.main(_args(env, apply=True, enrich=False))
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["already_indexed"] == 3 and out["cards_generated"] == 0
    assert out["cards_skipped_existing"] == 3
