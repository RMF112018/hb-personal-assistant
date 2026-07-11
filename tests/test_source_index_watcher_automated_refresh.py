"""NAS source-index bootstrap + watcher-readiness + reconciliation (V117) — focused suite.

Covers: root-key mapping (amendment 2), bootstrap (dry-run/apply/partial/idempotent/fail-closed),
watcher-readiness gating + run-state enum (amendment 5), reconciliation (file + folder drift), and the
extended assistant_source_index_health sections incl. drift surfacing (amendment 1) and path-safety.

All work is against tmp_path scratch DBs + temp source roots; no live/production DB is touched.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.config.loader import load_config as load_app_config
from hb_assistant.obsidian_mcp import source_bootstrap as sb
from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_health_service import source_index_health
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.obsidian_mcp.source_indexer import drain_queue
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_bootstrap_repository import SourceIndexBootstrapRepository
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)

# A fully-migrated DB is ~6s to build; migrate ONCE into a session template and copy it per test.
_TEMPLATE_DB: str | None = None


def _template_db() -> str:
    global _TEMPLATE_DB
    if _TEMPLATE_DB is None:
        import tempfile

        path = os.path.join(tempfile.mkdtemp(prefix="v117tmpl_"), "template.db")
        SQLiteMigrator(db_path=path).apply()
        _TEMPLATE_DB = path
    return _TEMPLATE_DB


def _make_env(tmp_path: Path, *, watch_enabled: bool = True, structure: bool = True):
    db = str(tmp_path / "h.db")
    shutil.copy(_template_db(), db)  # migrated schema, isolated writable copy
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "a.md").write_text("alpha", encoding="utf-8")
    (root / "sub" / "b.txt").write_text("beta", encoding="utf-8")
    ocfg = ObsidianMcpConfig(
        external_sources=[ExternalSourceRoot(source_root_key="k", path=str(root))],
        external_source_index_enabled=True,
        external_source_watch_enabled=watch_enabled,
    )
    acfg = load_app_config()
    acfg.source_structure.scan_roots = {"k": str(root)} if structure else {}
    return db, root, ocfg, acfg


def _bootstrap(db, ocfg, acfg, **kw):
    return sb.bootstrap(db_path=db, obsidian_config=ocfg, app_config=acfg, **kw)


# ------------------------------------------------------------------ root-key mapping (amendment 2)
def test_mapping_exact_match():
    assert sb.resolve_structure_key("k", {"k": "/x"}) == "k"


def test_mapping_explicit_map_mismatched_keys():
    assert sb.resolve_structure_key("fileK", {"structK": "/x"}, {"fileK": "structK"}) == "structK"


def test_mapping_file_root_with_no_structure_root():
    assert sb.resolve_structure_key("k", {}) is None


def test_mapping_structure_root_with_no_file_root():
    roots = [ExternalSourceRoot(source_root_key="k", path="/tmp/x")]
    mapped = sb.map_roots(roots, {"other": "/y"})
    assert mapped[0]["structure_configured"] is False


# ------------------------------------------------------------------------------------- bootstrap
def test_bootstrap_dry_run_writes_nothing(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    res = _bootstrap(db, ocfg, acfg, all_roots=True, dry_run=True)
    assert res["mode"] == "dry_run"
    assert SourceIndexRepository(db).active_rel_paths("k") == set()  # no index rows written
    assert SourceIndexBootstrapRepository(db).get_bootstrap_state("k") is None  # no state written


def test_bootstrap_all_roots_apply_sets_watcher_ready(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    res = _bootstrap(db, ocfg, acfg, all_roots=True)
    assert res["ok"] is True
    assert res["roots"][0]["watcher_ready"] is True
    assert SourceIndexRepository(db).active_rel_paths("k") == {"a.md", "sub/b.txt"}


def test_bootstrap_root_specific(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    res = _bootstrap(db, ocfg, acfg, root_key="k")
    assert res["root_count"] == 1 and res["roots"][0]["root_key"] == "k"


def test_bootstrap_idempotent_second_run(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    res2 = _bootstrap(db, ocfg, acfg, all_roots=True)
    assert res2["roots"][0]["file_index"]["indexed"] == 0  # nothing changed -> nothing re-indexed
    assert res2["roots"][0]["file_index"]["skipped"] == 2
    assert res2["roots"][0]["watcher_ready"] is True


def test_bootstrap_file_only_does_not_touch_structure(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    res = _bootstrap(db, ocfg, acfg, all_roots=True, file_only=True)
    assert "structure_index" not in res["roots"][0]
    st = SourceIndexBootstrapRepository(db).get_bootstrap_state("k")
    assert st["file_index_bootstrapped"] == 1
    assert st["structure_index_bootstrapped"] == 0  # untouched -> default 0
    assert st["watcher_ready"] == 0  # file-only alone is not watcher-ready


def test_bootstrap_structure_only(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    res = _bootstrap(db, ocfg, acfg, all_roots=True, structure_only=True)
    assert "file_index" not in res["roots"][0]
    st = SourceIndexBootstrapRepository(db).get_bootstrap_state("k")
    assert st["structure_index_bootstrapped"] == 1
    assert st["file_index_bootstrapped"] == 0


def test_bootstrap_failed_file_index_not_watcher_ready(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    ocfg.external_sources[0].path = str(tmp_path / "does_not_exist")
    res = _bootstrap(db, ocfg, acfg, all_roots=True)
    assert res["roots"][0]["file_index"]["success"] is False
    assert res["roots"][0]["watcher_ready"] is False


def test_bootstrap_structure_not_configured_not_ready(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path, structure=False)
    res = _bootstrap(db, ocfg, acfg, all_roots=True)
    assert res["roots"][0]["structure_index"]["status"] == "not_configured"
    assert res["roots"][0]["watcher_ready"] is False


def test_bootstrap_no_absolute_path_leak(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    st = SourceIndexBootstrapRepository(db).get_bootstrap_state("k")
    assert str(root) not in json.dumps(st)


# ---------------------------------------------------------------- readiness gating + run-state (am5)
def test_run_state_disabled_by_config(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path, watch_enabled=False)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == (sb.RUN_STATE_DISABLED)


def test_run_state_not_bootstrapped(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == (sb.RUN_STATE_NOT_BOOTSTRAPPED)


def test_run_state_backend_unavailable(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=False
    ) == (sb.RUN_STATE_BACKEND_UNAVAILABLE)


def test_run_state_running(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == (sb.RUN_STATE_RUNNING)


# ------------------------------------------------------------------------------- reconciliation
def test_reconcile_detects_new_modified_deleted(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    # new + modified(future mtime) + deleted
    (root / "c.md").write_text("gamma", encoding="utf-8")
    os.utime(root / "a.md", (time.time() + 10, time.time() + 10))
    (root / "sub" / "b.txt").unlink()
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert rec["events_enqueued"] == 3  # c added, a modified, b deleted
    drain_queue(repo, ocfg, batch=50)
    assert repo.active_rel_paths("k") == {"a.md", "c.md"}  # b removed, c added


def test_reconcile_deleted_file_no_longer_active(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    (root / "a.md").unlink()
    sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    drain_queue(repo, ocfg, batch=50)
    assert "a.md" not in repo.active_rel_paths("k")


def test_reconcile_folder_drift_flagged(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    # no change first -> no drift
    r0 = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert r0["directory_change_detected"] is False
    # add a new folder with a file -> drift
    (root / "newproj").mkdir()
    (root / "newproj" / "d.md").write_text("delta", encoding="utf-8")
    r1 = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert r1["directory_change_detected"] is True
    assert r1["structure_refresh_recommended"] is True


def test_reconcile_records_run_row(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg,
                      scan_type="lightweight")
    last = SourceIndexBootstrapRepository(db).last_reconciliation("k", scan_type="lightweight")
    assert last is not None and last["status"] == "completed"


# --------------------------------------------------------------------------- health (amendment 1)
def test_health_before_bootstrap_recommends_bootstrap(tmp_path):
    db, _root, ocfg, _acfg = _make_env(tmp_path)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert h["bootstrap"]["all_roots_watcher_ready"] is False
    assert "bootstrap" in (h["recommended_operator_action"] or "")


def test_health_sections_present_after_bootstrap(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    for section in ("bootstrap", "watcher", "file_index", "structure_index", "reconciliation"):
        assert section in h
    assert h["structure_index"]["dirty_bridge_enabled"] is False
    assert h["bootstrap"]["all_roots_watcher_ready"] is True


def test_health_surfaces_drift(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    (root / "newproj").mkdir()
    (root / "newproj" / "d.md").write_text("delta", encoding="utf-8")
    sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert h["structure_index"]["directory_change_detected"] is True
    assert h["structure_index"]["structure_refresh_recommended"] is True
    assert "structure-only" in (h["recommended_operator_action"] or "")


def test_health_watcher_disabled_reported(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path, watch_enabled=False)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert h["watcher"]["enabled"] is False
    assert h["roots"][0]["run_state"] == "disabled_by_config"


def test_health_no_absolute_path_leak(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    blob = json.dumps(source_index_health(SourceIndexRepository(db), ocfg), default=str)
    assert str(root) not in blob
    assert str(tmp_path) not in blob


def test_health_bounded_roots(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    h = source_index_health(SourceIndexRepository(db), ocfg)
    assert len(h["roots"]) <= 50


# --------------------------------------------------------------------------------------- CLI
def _patch_cli(monkeypatch, ocfg, acfg):
    import hb_assistant.cli.source_watch as sw

    monkeypatch.setattr(sw, "_obsidian_config", lambda: ocfg)
    monkeypatch.setattr(sw, "_app_config", lambda: acfg)


def test_cli_help():
    res = CliRunner().invoke(app, ["source-watch", "--help"])
    assert res.exit_code == 0
    for cmd in ("bootstrap", "run", "status", "drain", "reconcile"):
        assert cmd in res.stdout


def test_cli_bootstrap_dry_run(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    res = CliRunner().invoke(app, ["source-watch", "bootstrap", "--all-roots", "--dry-run",
                                    "--db", db])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["mode"] == "dry_run"


def test_cli_run_refuses_unbootstrapped_then_runs(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    r = CliRunner()
    refused = r.invoke(app, ["source-watch", "run", "--db", db])
    assert refused.exit_code == 2
    assert json.loads(refused.stdout)["roots"][0]["run_state"] == "not_bootstrapped"
    r.invoke(app, ["source-watch", "bootstrap", "--all-roots", "--db", db])
    after = r.invoke(app, ["source-watch", "run", "--db", db])
    assert after.exit_code == 0
    assert json.loads(after.stdout)["roots"][0]["run_state"] == "running"


def test_cli_run_bootstrap_if_needed(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    res = CliRunner().invoke(app, ["source-watch", "run", "--bootstrap-if-needed", "--db", db])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["roots"][0]["run_state"] == "running"


def test_cli_status_path_safe(tmp_path, monkeypatch):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    r = CliRunner()
    r.invoke(app, ["source-watch", "bootstrap", "--all-roots", "--db", db])
    res = r.invoke(app, ["source-watch", "status", "--db", db])
    assert res.exit_code == 0
    assert str(root) not in res.stdout


def test_cli_reconcile_and_drain(tmp_path, monkeypatch):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    r = CliRunner()
    r.invoke(app, ["source-watch", "bootstrap", "--all-roots", "--db", db])
    (root / "c.md").write_text("gamma", encoding="utf-8")
    rec = r.invoke(app, ["source-watch", "reconcile", "--root-key", "k", "--db", db])
    assert rec.exit_code == 0
    assert json.loads(rec.stdout)["results"][0]["events_enqueued"] >= 1
    drained = r.invoke(app, ["source-watch", "drain", "--max-items", "100", "--db", db])
    assert json.loads(drained.stdout)["processed"] >= 1


def test_cli_bootstrap_requires_target(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _patch_cli(monkeypatch, ocfg, acfg)
    res = CliRunner().invoke(app, ["source-watch", "bootstrap", "--db", db])
    assert res.exit_code == 2


@pytest.mark.parametrize("scan_type", ["lightweight", "full"])
def test_reconcile_scan_types(tmp_path, scan_type):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg,
                            scan_type=scan_type)
    assert rec["ok"] is True and rec["scan_type"] == scan_type


# ============================================================ ROUND-8 blocker regressions ========
# Blocker 1: lightweight reconciliation must never falsely delete valid records (indeterminate NAS read,
# accessible-but-empty mountpoint, or a root that vanishes between deletion-enqueue and drain).
def _events(db):
    import sqlite3

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT event_type, status, error_code, rel_path FROM source_intelligence_events "
        "ORDER BY rowid"
    ).fetchall()
    conn.close()
    return rows


def test_r8_lightweight_reconcile_indeterminate_read_suspends_deletions(tmp_path, monkeypatch):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    before = repo.active_rel_paths("k")
    assert before == {"a.md", "sub/b.txt"}

    # An INDETERMINATE (non-ENOENT) read failure across the walk — a permission / stale-handle / flaky
    # mount. The walker must fail closed: no deletions, and a non-success receipt.
    def _boom(_path):
        raise OSError(errno.EIO, "io error")

    monkeypatch.setattr(si.os, "scandir", _boom)
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert rec["ok"] is False
    assert rec["files_seen"] == 0
    monkeypatch.undo()
    # NO deleted events were enqueued, and every indexed row survives.
    assert not any(e[0] == "deleted" for e in _events(db))
    assert repo.active_rel_paths("k") == before
    last = SourceIndexBootstrapRepository(db).last_reconciliation("k", scan_type="lightweight")
    assert last["status"] == "failed" and last["last_error"] == "lightweight_walk_indeterminate"


def test_r8_lightweight_reconcile_confirmed_removal_still_reconciles(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    (root / "sub" / "b.txt").unlink()  # a genuine, confirmed removal (ENOENT)
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert rec["ok"] is True
    assert any(e[0] == "deleted" and e[3] == "sub/b.txt" for e in _events(db))


def test_r8_lightweight_reconcile_empty_root_blast_radius_guard(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    ocfg = ocfg.model_copy(update={"source_index_empty_root_delete_threshold": 1})
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    assert len(repo.active_rel_paths("k")) == 2  # a.md, sub/b.txt
    # Every file vanishes at once from an ACCESSIBLE root (an unmounted-but-present mountpoint looks
    # exactly like this). With 2 active rows over a threshold of 1, deletions must be suppressed.
    (root / "a.md").unlink()
    (root / "sub" / "b.txt").unlink()
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert rec["ok"] is False
    assert not any(e[0] == "deleted" for e in _events(db))
    assert len(repo.active_rel_paths("k")) == 2  # nothing deleted
    last = SourceIndexBootstrapRepository(db).last_reconciliation("k", scan_type="lightweight")
    assert last["last_error"] == "lightweight_empty_root_guard"


def test_r8_lightweight_reconcile_emptying_under_threshold_reconciles(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    ocfg = ocfg.model_copy(update={"source_index_empty_root_delete_threshold": 5})
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    (root / "a.md").unlink()
    (root / "sub" / "b.txt").unlink()  # 2 gone, at/under threshold 5 -> a real, bounded emptying
    rec = sb.reconcile_root(db_path=db, file_key="k", obsidian_config=ocfg, app_config=acfg)
    assert rec["ok"] is True
    assert sum(1 for e in _events(db) if e[0] == "deleted") == 2
    drain_queue(repo, ocfg, batch=50)
    assert repo.active_rel_paths("k") == set()


def test_r8_drain_deleted_still_present_is_skipped(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="deleted", rel_path="a.md", source_root_key="k")  # still on disk
    drain_queue(repo, ocfg, batch=50)
    assert "a.md" in repo.active_rel_paths("k")  # survivor: never deleted
    ev = [e for e in _events(db) if e[0] == "deleted"][-1]
    assert ev[1] == "skipped" and ev[2] == "still_present"


def test_r8_drain_deleted_absent_under_usable_root_is_deleted(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    (root / "a.md").unlink()  # confirmed gone, root still usable
    repo.enqueue_event(event_type="deleted", rel_path="a.md", source_root_key="k")
    drain_queue(repo, ocfg, batch=50)
    assert "a.md" not in repo.active_rel_paths("k")


def test_r8_drain_deleted_root_unavailable_is_skipped(tmp_path):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="deleted", rel_path="a.md", source_root_key="k")
    shutil.rmtree(root)  # the whole mount drops BETWEEN enqueue and drain
    drain_queue(repo, ocfg, batch=50)
    assert "a.md" in repo.active_rel_paths("k")  # unproven deletion -> row preserved
    ev = [e for e in _events(db) if e[0] == "deleted"][-1]
    assert ev[1] == "skipped" and ev[2] == "root_unavailable"


def test_r8_drain_deleted_unconfigured_root_is_skipped(tmp_path):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="deleted", rel_path="x.md", source_root_key="ghost")
    drain_queue(repo, ocfg, batch=50)  # must not raise
    ev = [e for e in _events(db) if e[0] == "deleted"][-1]
    assert ev[1] == "skipped" and ev[2] == "unconfigured_root"


def test_r8_drain_deleted_indeterminate_probe_is_skipped(tmp_path, monkeypatch):
    db, root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    repo = SourceIndexRepository(db)
    repo.enqueue_event(event_type="deleted", rel_path="a.md", source_root_key="k")
    real_stat = os.stat
    # The drainer builds the candidate as ``Path(root.path) / rel_path`` (root.path is the UNRESOLVED
    # configured path), so match that form — never ``.resolve()`` (macOS /var -> /private/var would miss).
    target = os.fspath(Path(root) / "a.md")

    def _stat(path, *a, **k):
        if os.fspath(path) == target:
            raise OSError(errno.EACCES, "denied")
        return real_stat(path, *a, **k)

    monkeypatch.setattr(si.os, "stat", _stat)
    drain_queue(repo, ocfg, batch=50)
    monkeypatch.undo()
    assert "a.md" in repo.active_rel_paths("k")  # indeterminate -> never deleted
    ev = [e for e in _events(db) if e[0] == "deleted"][-1]
    assert ev[1] == "skipped" and ev[2] == "indeterminate"


# Blocker 2: watcher run-state must derive from the latest generation + current policy + structure map,
# never the stale persisted readiness bit alone; every new read fails closed.
def test_r8_run_state_fingerprint_mismatch_not_running(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    assert SourceIndexBootstrapRepository(db).get_bootstrap_state("k")["watcher_ready"] == 1
    # Current policy fingerprint no longer matches the completed generation's stored fingerprint.
    monkeypatch.setattr(si, "_root_fingerprint", lambda *a, **k: "DIFFERENT-FP")
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == sb.RUN_STATE_NOT_BOOTSTRAPPED


def test_r8_run_state_fingerprint_compute_failure_fails_closed(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)

    def _boom(*a, **k):
        raise RuntimeError("fp compute failed")

    monkeypatch.setattr(si, "_root_fingerprint", _boom)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == sb.RUN_STATE_NOT_BOOTSTRAPPED


def test_r8_run_state_generation_read_failure_fails_closed(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)

    def _boom(self, *a, **k):
        raise RuntimeError("gen repo read failed")

    monkeypatch.setattr(SourceIndexScanGenerationsRepository, "latest_generations", _boom)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == sb.RUN_STATE_NOT_BOOTSTRAPPED


def test_r8_run_state_no_folder_map_not_running(tmp_path):
    # A completed generation but NO structure folder map -> not watcher-ready (structure baseline missing).
    db, _root, ocfg, acfg = _make_env(tmp_path, structure=False)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == sb.RUN_STATE_NOT_BOOTSTRAPPED


def test_r8_run_state_legacy_root_honors_persisted_bit(tmp_path):
    # A root with NO V122 generation falls back to the persisted legacy readiness bit.
    db, _root, ocfg, acfg = _make_env(tmp_path)
    SourceIndexBootstrapRepository(db).upsert_bootstrap_state("k", watcher_ready=1)
    assert SourceIndexScanGenerationsRepository(db).latest_generations().get("k") is None
    assert sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    ) == sb.RUN_STATE_RUNNING


def test_r8_run_state_agrees_with_health_watcher_ready(tmp_path, monkeypatch):
    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    monkeypatch.setattr(si, "_root_fingerprint", lambda *a, **k: "DIFFERENT-FP")
    run_state = sb.resolve_run_state(
        "k", db_path=db, obsidian_config=ocfg, app_config=acfg, backend_available=True
    )
    h = source_index_health(SourceIndexRepository(db), ocfg)
    root_h = h["roots"][0]
    assert root_h["bootstrap"]["watcher_ready"] is False
    assert root_h["run_state"] == run_state == sb.RUN_STATE_NOT_BOOTSTRAPPED


# Blocker 3: a malformed last_indexed_at must fail closed across the FULL trust surface (not just client
# answering) and must not read as healthy/ready in the aggregate.
def test_r8_health_malformed_last_indexed_closes_full_trust_surface(tmp_path):
    import sqlite3

    db, _root, ocfg, acfg = _make_env(tmp_path)
    _bootstrap(db, ocfg, acfg, all_roots=True)
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE source_structure_roots SET last_indexed_at='not-a-date' WHERE root_key='k'"
    )
    conn.commit()
    conn.close()
    h = source_index_health(SourceIndexRepository(db), ocfg)
    r = h["roots"][0]
    assert r["freshness_status"] == "unknown"
    assert r["safe_for_client_answering"] is False
    assert r["safe_for_content_answering"] == "none"
    assert r["safe_for_path_lookup"] is False
    assert r["index_only_available"] is False
    assert "unparseable" in r["diagnostic_summary"] or "invalid" in r["diagnostic_summary"]
    assert h["overall_freshness"] != "fresh"
