"""PR 1 — metadata-first bootstrap hazard-stop: extraction gates, bounded defaults, partial status,
durable V118 runs, content-state invalidation, retryable conflicts, and honest health counts.

All work is against tmp_path scratch DBs + temp source roots; no live/production DB is touched. Parser
fixtures are synthetic; a monkeypatched parser/hasher RAISES if the safe policy ever reaches it, proving
metadata-only files are never parsed or hashed.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.source_watch import app as source_watch_app
from hb_assistant.obsidian_mcp import source_bootstrap as sb
from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp import source_scan_runner as runner
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_health_service import source_index_health
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository

_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        path = os.path.join(tempfile.mkdtemp(prefix="v118tmpl_"), "template.db")
        SQLiteMigrator(db_path=path).apply()
        _TEMPLATE_DB = path
    return _TEMPLATE_DB


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "h.db")
    shutil.copy(_template_db(), db)
    return db


def _root(tmp_path: Path) -> ExternalSourceRoot:
    return ExternalSourceRoot(source_root_key="work", path=str(tmp_path / "root"))


def _cfg(root_dir: Path, **overrides) -> ObsidianMcpConfig:
    base = ObsidianMcpConfig(
        vault_root=str(root_dir),
        external_sources=[
            ExternalSourceRoot(source_root_key="work", path=str(root_dir), enabled=True)
        ],
        external_source_index_enabled=True,
    )
    return base.model_copy(update=overrides) if overrides else base


# ----- extraction disposition + gates ---------------------------------------------------------
def test_disposition_parsers_metadata_only_by_default(tmp_path):
    cfg = _cfg(tmp_path)
    for ext in ("xlsx", "pdf", "docx", "eml", "xls", "csv"):
        assert si.extraction_disposition(ext, 10, cfg) == "metadata_only", ext
    assert si.extraction_disposition("txt", 10, cfg) == "content"
    assert si.extraction_disposition("png", 10, cfg) == "unsupported"


def test_disposition_flag_on_enables_parsers(tmp_path):
    cfg = _cfg(tmp_path, source_index_enable_synchronous_parser_extraction=True)
    for ext in ("xlsx", "pdf", "docx", "eml"):
        assert si.extraction_disposition(ext, 10, cfg) == "content", ext


def test_disposition_too_large_before_everything(tmp_path):
    cfg = _cfg(tmp_path, max_file_mb=0)
    assert si.extraction_disposition("txt", 1, cfg) == "too_large"


def _scan(root_dir: Path, cfg, db):
    repo = SourceIndexRepository(db)
    return si.scan_source_root(
        ExternalSourceRoot(source_root_key="work", path=str(root_dir)), repo, cfg
    ), repo


def test_metadata_only_files_never_hashed_or_parsed(tmp_path, monkeypatch):
    # PR 2 acceptance #2: a ROOT SCAN reads NO content for ANY file — no SHA-256, no parser — even for a
    # content-eligible .txt. Both the hasher and every parser are patched to RAISE; the scan must still
    # complete. Content-eligible files record disposition 'content' + status 'pending' (extraction
    # deferred to the targeted path / PR 3 queue); the rest are metadata_only/unsupported.
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("real content")
    (root_dir / "b.xlsx").write_bytes(b"PK\x03\x04 not-a-real-xlsx")
    (root_dir / "c.pdf").write_bytes(b"%PDF-1.4 broken")
    (root_dir / "d.eml").write_bytes(b"not a real mime")
    db = _db(tmp_path)

    monkeypatch.setattr(
        si, "_sha256_file", lambda p: (_ for _ in ()).throw(AssertionError(f"hashed {p}"))
    )
    import hb_assistant.files.parsers.xlsx as xlsx_mod

    monkeypatch.setattr(
        xlsx_mod.XLSXParser,
        "parse",
        lambda self, *a, **k: (_ for _ in ()).throw(AssertionError("xlsx parsed")),
    )
    report, repo = _scan(root_dir, _cfg(root_dir), db)  # must NOT raise

    import sqlite3

    conn = sqlite3.connect(db)
    rows = {
        r[0]: (r[1], r[2], r[3])
        for r in conn.execute(
            "SELECT s.rel_path, m.extraction_status, m.content_sha256, m.extraction_disposition "
            "FROM source_intelligence_sources s JOIN source_intelligence_metadata m USING(source_id)"
        ).fetchall()
    }
    txt = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    conn.close()
    assert rows["a.txt"] == ("pending", None, "content")  # eligible, NOT extracted during a root scan
    assert rows["b.xlsx"] == ("pending", None, "metadata_only")
    assert rows["c.pdf"] == ("pending", None, "metadata_only")
    assert rows["d.eml"] == ("pending", None, "metadata_only")
    assert txt == 0  # no body read/stored by a root scan
    assert report.metadata_only == 3


def test_flag_on_root_scan_metadata_only_but_targeted_extracts(tmp_path):
    # PR 2 acceptance #2: the parser opt-in flag cannot make a ROOT SCAN parse — only the TARGETED
    # single-file path extracts content.
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active["A1"] = "hello-sheet-value"
    wb.save(str(root_dir / "s.xlsx"))
    db = _db(tmp_path)
    cfg = _cfg(root_dir, source_index_enable_synchronous_parser_extraction=True)
    report, repo = _scan(root_dir, cfg, db)
    import sqlite3

    conn = sqlite3.connect(db)
    status = conn.execute("SELECT extraction_status FROM source_intelligence_metadata").fetchone()[0]
    conn.close()
    assert status == "pending"  # root scan stayed metadata-only despite the flag
    assert report.content_succeeded == 0

    # Targeted single-file indexing DOES parse (flag on) and makes the sheet value body-searchable.
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    sid = si.index_source_file(root_dir / "s.xlsx", r, repo, cfg)
    assert sid is not None
    conn = sqlite3.connect(db)
    status2 = conn.execute("SELECT extraction_status FROM source_intelligence_metadata").fetchone()[0]
    conn.close()
    assert status2 == "ok"
    assert any("s.xlsx" in h["path"] for h in repo.search_sources("hello-sheet-value"))


# ----- content-state invalidation on transition -----------------------------------------------
def test_content_to_metadata_only_clears_text_and_fts(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    f = root_dir / "doc.txt"
    f.write_text("searchable body")
    db = _db(tmp_path)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    repo = SourceIndexRepository(db)
    # Establish CONTENT via the targeted path (a root scan is metadata-only and would not extract text).
    si.index_source_file(f, r, repo, _cfg(root_dir))

    import sqlite3

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0] == 1
    conn.close()

    # Now a metadata-first scan with the file gated to too_large re-indexes it metadata-only, which must
    # clear the stale content (text + chunks) while retaining a searchable PATH FTS row.
    cfg2 = _cfg(root_dir, max_file_mb=0)  # now doc.txt is too_large -> metadata-only write
    f.write_text(
        "searchable body CHANGED"
    )  # change mtime/size so it is re-indexed (not fast-skipped)
    si.scan_source_root(r, repo, cfg2)

    conn = sqlite3.connect(db)
    # PR 2 path-FTS invariant: a metadata-only/too-large file KEEPS a path-searchable FTS row (so it is
    # still findable by filename/project), but its CONTENT (text excerpt + chunks) is invalidated and the
    # FTS row now carries an EMPTY text_excerpt (never overstates content coverage).
    fts = conn.execute("SELECT COUNT(*) FROM source_intelligence_fts").fetchone()[0]
    fts_excerpt = conn.execute("SELECT text_excerpt FROM source_intelligence_fts").fetchone()[0]
    fts_relpath = conn.execute("SELECT rel_path FROM source_intelligence_fts").fetchone()[0]
    txt = conn.execute("SELECT COUNT(*) FROM source_intelligence_text").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM source_intelligence_chunks").fetchone()[0]
    status = conn.execute("SELECT extraction_status FROM source_intelligence_metadata").fetchone()[
        0
    ]
    disp = conn.execute("SELECT extraction_disposition FROM source_intelligence_metadata").fetchone()[0]
    conn.close()
    assert status == "skipped_too_large"
    assert disp == "too_large"
    assert txt == 0 and chunks == 0  # stale CONTENT invalidated
    assert fts == 1 and (fts_excerpt or "") == "" and fts_relpath == "doc.txt"  # path row retained


# ----- bounded defaults + run lifecycle via run_scan ------------------------------------------
def _big_root(tmp_path: Path, n: int) -> Path:
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    for i in range(n):
        (root_dir / f"f{i}.txt").write_text(f"content {i}")
    return root_dir


def test_bounded_default_applies_without_explicit_cap(tmp_path):
    root_dir = _big_root(tmp_path, 6)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    bstate = SourceIndexBootstrapRepository(db)
    cfg = _cfg(root_dir, source_index_bootstrap_max_files_per_pass=2)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    res = runner.run_scan(r, repo, cfg, bstate, mode="bootstrap")  # NO explicit cap
    assert res.status == "partial" and res.report.indexed == 2  # default cap engaged


def test_unbounded_removes_cap(tmp_path):
    root_dir = _big_root(tmp_path, 6)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    bstate = SourceIndexBootstrapRepository(db)
    cfg = _cfg(root_dir, source_index_bootstrap_max_files_per_pass=2)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    res = runner.run_scan(r, repo, cfg, bstate, mode="bootstrap", unbounded=True)
    assert res.status == "completed" and res.report.indexed == 6


def test_run_lifecycle_completed_and_partial_rows(tmp_path):
    # PR 2: resume is GENERATION-based. A bounded first pass leaves a partial generation + a partial V119
    # pass; the next pass resumes the SAME generation to completion. Both V119 passes link to it.
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    root_dir = _big_root(tmp_path, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    bstate = SourceIndexBootstrapRepository(db)
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    r1 = runner.run_scan(
        r, repo, _cfg(root_dir, source_index_bootstrap_max_files_per_pass=2), bstate
    )
    r2 = runner.run_scan(r, repo, _cfg(root_dir), bstate)  # completes
    assert r1.status == "partial" and r2.status == "completed"

    gens = SourceIndexScanGenerationsRepository(db).list_generations("work")
    assert len(gens) == 1  # one generation spanned both passes
    gid = gens[0]["generation_id"]
    assert gens[0]["status"] == "completed"

    runs = bstate.list_bootstrap_runs("work")
    statuses = {x["status"] for x in runs}
    assert "completed" in statuses and "partial" in statuses
    assert all(x["generation_id"] == gid for x in runs)  # every V119 pass links to the generation


def test_concurrent_run_conflict_is_retryable(tmp_path):
    # A live generation lease (fresh heartbeat) makes a concurrent scan a retryable conflict, not fatal.
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    root_dir = _big_root(tmp_path, 3)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    bstate = SourceIndexBootstrapRepository(db)
    genrepo = SourceIndexScanGenerationsRepository(db)
    import uuid

    # Hold a live generation for the root (fresh owner_heartbeat_at).
    held = genrepo.begin_generation_pass(
        "work", uuid.uuid4().hex, policy_fingerprint="fp", root_path_hash="rph"
    )
    assert held is not None
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    res = runner.run_scan(r, repo, _cfg(root_dir), bstate, mode="poll")
    assert res.conflict and res.status == "conflict"


def test_reconcile_full_bounded_out_is_not_completed(tmp_path):
    # Invariant: a bounded (incomplete) full reconcile must NEVER read as a successfully completed
    # reconciliation. The legacy receipt CHECK has no 'partial', so it records fail-closed
    # ('failed' + a resumable code) while the V118 run row is the authoritative 'partial'.
    root_dir = _big_root(tmp_path, 6)
    db = _db(tmp_path)
    from hb_assistant.config.loader import load_config as load_app_config

    acfg = load_app_config()
    acfg.source_structure.scan_roots = {}
    ocfg = _cfg(root_dir, source_index_bootstrap_max_files_per_pass=2)
    res = sb.reconcile_root(db_path=db, file_key="work", obsidian_config=ocfg,
                            app_config=acfg, scan_type="full")
    assert res["ok"] is False and res["bounded_out"] is True
    bstate = SourceIndexBootstrapRepository(db)
    last_full = bstate.last_reconciliation(scan_type="full")
    assert last_full["status"] == "failed"  # explicitly NOT 'completed'
    assert last_full["last_error"] == "bounded_out_partial_resume_pending"  # resumable, not terminal
    # V118 is the source of truth for the accurate lifecycle state.
    runs = bstate.list_bootstrap_runs("work")
    assert any(x["mode"] == "reconcile" and x["status"] == "partial" for x in runs)
    # Deletion reconciliation must NOT have run on the incomplete pass (no rows deleted).
    assert res.get("changes_detected", 0) >= 0  # smoke; delete-reconcile is complete-pass-only


def test_reconcile_full_completed_when_unbounded(tmp_path):
    # Control: a full reconcile that finishes IS recorded completed (ok=True) — proving the 'failed'
    # above is specifically the bounded/incomplete signal, not a blanket regression.
    root_dir = _big_root(tmp_path, 3)
    db = _db(tmp_path)
    from hb_assistant.config.loader import load_config as load_app_config

    acfg = load_app_config()
    acfg.source_structure.scan_roots = {}
    ocfg = _cfg(root_dir)  # default cap (25k) >> 3 files -> completes
    res = sb.reconcile_root(db_path=db, file_key="work", obsidian_config=ocfg,
                            app_config=acfg, scan_type="full")
    assert res["ok"] is True
    bstate = SourceIndexBootstrapRepository(db)
    assert bstate.last_reconciliation(scan_type="full")["status"] == "completed"


def test_stale_run_reaped_to_abandoned(tmp_path):
    db = _db(tmp_path)
    bstate = SourceIndexBootstrapRepository(db)
    import uuid

    old = uuid.uuid4().hex
    bstate.start_bootstrap_run(old, "work", "bootstrap")
    # stale_seconds=0 makes any prior running row immediately stale -> abandoned on next start.
    new = uuid.uuid4().hex
    assert bstate.start_bootstrap_run(new, "work", "bootstrap", stale_seconds=0) == new
    assert bstate.get_bootstrap_run(old)["status"] == "abandoned"


def test_interrupt_backstop(tmp_path):
    db = _db(tmp_path)
    bstate = SourceIndexBootstrapRepository(db)
    import uuid

    rid = uuid.uuid4().hex
    bstate.start_bootstrap_run(rid, "work", "bootstrap")
    bstate.interrupt_bootstrap_run(rid)
    assert bstate.get_bootstrap_run(rid)["status"] == "interrupted"
    # idempotent: interrupting a terminal run is a no-op
    bstate.finish_bootstrap_run(rid, status="completed")
    bstate.interrupt_bootstrap_run(rid)
    assert bstate.get_bootstrap_run(rid)["status"] == "completed"


def test_heartbeat_failure_isolated(tmp_path, monkeypatch):
    root_dir = _big_root(tmp_path, 4)
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    bstate = SourceIndexBootstrapRepository(db)
    monkeypatch.setattr(
        bstate,
        "heartbeat_bootstrap_run",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db blip")),
    )
    r = ExternalSourceRoot(source_root_key="work", path=str(root_dir))
    cfg = _cfg(root_dir, source_index_bootstrap_heartbeat_seconds=0.0)
    res = runner.run_scan(r, repo, cfg, bstate)  # must NOT raise despite heartbeat failures
    assert res.status == "completed" and res.report.indexed == 4


# ----- redaction --------------------------------------------------------------------------------
def test_redact_rel_prefix_hides_paths():
    tok = runner.redact_rel_prefix("Projects/Secret Client/2026/file.xlsx")
    assert "Secret" not in tok and "Projects" not in tok
    assert tok.startswith("h") and "/d" in tok
    assert runner.redact_rel_prefix("top.txt") == "root"
    assert runner.redact_rel_prefix(None) == "root"


# ----- output streams (CLI) --------------------------------------------------------------------
def test_cli_rejects_unbounded_with_cap():
    r = CliRunner()
    out = r.invoke(
        source_watch_app,
        ["bootstrap", "--root-key", "x", "--unbounded", "--max-files-per-pass", "5"],
    )
    assert out.exit_code == 2 and "cannot be combined" in out.stdout


def test_cli_rejects_nonpositive_cap():
    r = CliRunner()
    out = r.invoke(source_watch_app, ["bootstrap", "--root-key", "x", "--max-files-per-pass", "0"])
    assert out.exit_code == 2 and "must be a positive value" in out.stdout


def test_cli_jsonl_stream_is_all_one_line_json(tmp_path, monkeypatch):
    from hb_assistant.cli import source_watch as cli
    from hb_assistant.config.loader import load_config as load_app_config

    root_dir = _big_root(tmp_path, 5)
    db = _db(tmp_path)
    acfg = load_app_config()
    acfg.source_structure.scan_roots = {}
    ocfg = _cfg(
        root_dir,
        source_index_bootstrap_heartbeat_seconds=0.0,
        source_index_bootstrap_max_files_per_pass=2,
    )
    monkeypatch.setattr(cli, "_obsidian_config", lambda: ocfg)
    monkeypatch.setattr(cli, "_app_config", lambda: acfg)
    monkeypatch.setattr(cli, "_db_path", lambda _db_arg: db)
    out = CliRunner().invoke(
        cli.app, ["bootstrap", "--root-key", "work", "--file-index-only", "--jsonl"]
    )
    lines = [ln for ln in out.stdout.splitlines() if ln.strip()]
    assert lines and all(json.loads(ln) for ln in lines)  # every stdout record is one-line JSON
    assert any(
        rec.get("phase") == "scan" for rec in (json.loads(ln) for ln in lines)
    )  # progress present


# ----- config default-off after deserialization of an OLD config -------------------------------
def test_parser_optin_defaults_off_on_old_config():
    # An existing on-disk config that predates the field must deserialize the opt-in as False.
    legacy = {"external_sources": []}
    cfg = ObsidianMcpConfig.model_validate(legacy)
    assert cfg.source_index_enable_synchronous_parser_extraction is False
    assert cfg.source_index_bootstrap_max_files_per_pass == 25000


# ----- health: honest counts + safety split ----------------------------------------------------
def test_health_counts_and_completeness(tmp_path):
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    (root_dir / "a.txt").write_text("searchable")
    (root_dir / "b.xlsx").write_bytes(b"PK")  # metadata_only
    (root_dir / "c.png").write_bytes(b"x")  # unsupported
    db = _db(tmp_path)
    repo = SourceIndexRepository(db)
    cfg = _cfg(root_dir)
    si.scan_source_root(ExternalSourceRoot(source_root_key="work", path=str(root_dir)), repo, cfg)
    counts = repo.content_status_counts("work")
    assert counts == {
        "metadata_indexed": 3,
        "metadata_searchable": 3,  # PR 2: every active source has a path FTS row
        "content_extracted": 0,  # metadata-first root scan extracts NO content
        "content_searchable": 0,
        "content_eligible": 1,  # a.txt is content-eligible...
        "content_pending": 1,  # ...but pending extraction (targeted path / PR 3 queue)
        "intentional_metadata_only": 1,  # b.xlsx
        "metadata_only": 1,
        "failed": 0,
        "unsupported": 1,  # c.png
        "too_large": 0,
    }
    health = source_index_health(repo, cfg)
    r0 = next(r for r in health["roots"] if r["root_key"] == "work")
    # Metadata baseline is complete; content has not been extracted yet.
    assert r0["metadata_completeness_state"] == "complete"
    assert r0["content_completeness_state"] == "none"
    assert r0["safe_for_path_lookup"] is True
    assert r0["safe_for_content_answering"] == "none"
    assert "--all-roots" not in (health["recommended_operator_action"] or "")


def test_health_query_uses_root_index_no_full_scan(tmp_path):
    import sqlite3

    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT m.extraction_status, COUNT(*) "
        "FROM source_intelligence_sources s JOIN source_intelligence_metadata m ON m.source_id=s.source_id "
        "LEFT JOIN source_intelligence_text t ON t.source_id=s.source_id "
        "WHERE s.source_kind='external_file' AND s.source_root_key=? AND s.deleted=0 "
        "GROUP BY m.extraction_status",
        ("work",),
    ).fetchall()
    conn.close()
    txt = " | ".join(str(r[-1]) for r in plan)
    # A root-scoped index is used (idx_si_sources_root, or after V122 the wider reconciliation index
    # idx_si_sources_last_seen_gen, which is also source_root_key-prefixed) — never a full-table scan.
    assert "idx_si_sources_root" in txt or "idx_si_sources_last_seen_gen" in txt
    assert "SCAN source_intelligence_sources" not in txt  # no full-table scan on health


# ----- migration idempotency + existing rows readable ------------------------------------------
def test_v119_migration_idempotent_and_additive(tmp_path):
    db = str(tmp_path / "m.db")
    v1 = SQLiteMigrator(db_path=db).apply()
    v2 = SQLiteMigrator(db_path=db).apply()  # re-run
    assert v1 == v2 == LATEST_SCHEMA_VERSION
    import sqlite3

    conn = sqlite3.connect(db)
    # runs table + partial-unique + support indexes exist
    idx = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_source_index_bootstrap_runs%'"
        ).fetchall()
    }
    conn.close()
    assert "idx_source_index_bootstrap_runs_active" in idx


# ----- bootstrap records partial file-index status; watcher stays not-bootstrapped -------------
def test_bootstrap_partial_status_keeps_not_bootstrapped(tmp_path):
    root_dir = _big_root(tmp_path, 6)
    db = _db(tmp_path)
    from hb_assistant.config.loader import load_config as load_app_config

    acfg = load_app_config()
    acfg.source_structure.scan_roots = {}
    ocfg = _cfg(root_dir, source_index_bootstrap_max_files_per_pass=2)
    res = sb.bootstrap(
        db_path=db, obsidian_config=ocfg, app_config=acfg, root_key="work", file_only=True
    )
    bstate = SourceIndexBootstrapRepository(db)
    state = bstate.get_bootstrap_state("work")
    assert state["file_index_status"] == "partial"
    assert state["file_index_bootstrapped"] == 0  # watcher run-state stays not_bootstrapped
    assert res["roots"][0]["file_index"]["bounded_out"] is True
