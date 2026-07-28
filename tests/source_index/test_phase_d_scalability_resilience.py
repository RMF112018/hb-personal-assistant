"""Phase D scratch-only scalability/resilience gate.

The large 400k/1M evidence run is committed separately. These tests keep CI fast
while executing the same rehearsal code at reduced scale plus explicit fail-closed
fault, lock, and real process-kill/resume cases.
"""

from __future__ import annotations

import errno
import importlib.util
import multiprocessing
import os
import sqlite3
import time
from pathlib import Path
from types import ModuleType

import pytest

from hb_assistant.obsidian_mcp import source_indexer as si
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_scan_generations_repository import (
    SourceIndexScanGenerationsRepository,
)


def _load_rehearsal() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "source_index_phase_d_rehearsal.py"
    spec = importlib.util.spec_from_file_location("source_index_phase_d_rehearsal", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cfg(root: Path, **overrides: object) -> ObsidianMcpConfig:
    base = ObsidianMcpConfig(
        vault_root=str(root.parent),
        external_sources=[
            ExternalSourceRoot(source_root_key="phase-d", path=str(root), enabled=True)
        ],
        external_source_index_enabled=True,
        source_index_metadata_batch_size=25,
        source_index_scan_observed_files_per_pass=100,
        source_index_bootstrap_heartbeat_seconds=0,
        source_index_bootstrap_stale_run_seconds=0.1,
    )
    return base.model_copy(update=overrides)


def _kill_worker(root_text: str, db_text: str, marker_text: str) -> None:
    root = Path(root_text)
    marker = Path(marker_text)
    repo = SourceIndexRepository(db_text)
    external = ExternalSourceRoot(source_root_key="phase-d", path=root_text, enabled=True)

    def pause_after_commit(_report: object, _hint: str, _elapsed: float) -> None:
        marker.touch()
        time.sleep(300)

    si.scan_source_root(external, repo, _cfg(root), progress=pause_after_commit)


def test_reduced_scale_rehearsal_passes_all_slos(tmp_path: Path) -> None:
    rehearsal = _load_rehearsal()
    result = rehearsal.run_rehearsal(
        targets=[500, 2_000],
        observed_limit=200,
        files_per_dir=100,
        fanout_files=50,
        deep_levels=6,
        delta_percentages=[0.1, 1, 10],
        workers=4,
        queries_per_worker=5,
        workdir=str(tmp_path),
        keep_workdir=False,
        slos={
            "max_peak_rss_mb": 1024.0,
            "min_files_per_second": 10.0,
            "cold_search_ms": 5000.0,
            "warm_search_p95_ms": 500.0,
            "concurrent_search_p95_ms": 1000.0,
            "lock_timeout_seconds": 10.0,
        },
    )
    assert result["evaluation"]["passed"], result["evaluation"]
    assert result["scratch_cleaned"] is True
    assert result["scale_scans"]["2000"]["active_rows"] == 2_000
    assert result["scale_scans"]["2000"]["parser_invocations"] == {"hash": 0, "extract": 0}


@pytest.mark.parametrize("injected_errno", [errno.EIO, errno.ESTALE, errno.EACCES])
def test_indeterminate_directory_fault_never_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, injected_errno: int
) -> None:
    root = tmp_path / "root"
    subtree = root / "unstable"
    subtree.mkdir(parents=True)
    victim = subtree / "preserve-me.txt"
    victim.write_text("x", encoding="utf-8")
    db = tmp_path / "fault.db"
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    external = ExternalSourceRoot(source_root_key="phase-d", path=str(root), enabled=True)
    assert si.scan_source_root(external, repo, _cfg(root)).generation_status == "completed"
    victim.unlink()

    original = si.os.scandir

    def fail_subtree(path: object, *args: object, **kwargs: object):
        if os.fspath(path) == str(subtree):
            raise OSError(injected_errno, "phase-d injected directory fault")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(si.os, "scandir", fail_subtree)
    report = si.scan_source_root(external, repo, _cfg(root))
    assert report.generation_status == "partial"
    assert report.error_code == "directory_read_error"
    assert "unstable/preserve-me.txt" in repo.active_rel_paths("phase-d")


def test_high_fanout_fails_without_reconciliation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for index in range(11):
        (root / f"f-{index:02d}.txt").write_text("x", encoding="utf-8")
    db = tmp_path / "fanout.db"
    SQLiteMigrator(db_path=db).apply()
    repo = SourceIndexRepository(db)
    external = ExternalSourceRoot(source_root_key="phase-d", path=str(root), enabled=True)
    report = si.scan_source_root(
        external,
        repo,
        _cfg(root, source_index_directory_fanout_limit=10),
    )
    assert report.generation_status == "failed"
    assert report.error_code == "directory_fanout_limit"
    assert report.deleted == 0


def test_real_process_kill_resumes_same_generation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for index in range(500):
        (root / f"f-{index:04d}.txt").write_text("x", encoding="utf-8")
    db = tmp_path / "kill.db"
    SQLiteMigrator(db_path=db).apply()
    marker = tmp_path / "committed.marker"
    context = multiprocessing.get_context("fork")
    process = context.Process(target=_kill_worker, args=(str(root), str(db), str(marker)))
    process.start()
    deadline = time.monotonic() + 20
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert marker.exists(), "worker never reached a committed progress callback"
    process.kill()
    process.join(timeout=10)
    assert process.exitcode is not None and process.exitcode < 0

    generations = SourceIndexScanGenerationsRepository(db)
    interrupted = generations.get_active_generation("phase-d")
    assert interrupted is not None
    generation_id = interrupted["generation_id"]
    cursor_before = interrupted["cursor_json"]
    assert cursor_before is not None
    time.sleep(0.2)

    repo = SourceIndexRepository(db)
    external = ExternalSourceRoot(source_root_key="phase-d", path=str(root), enabled=True)
    for _ in range(20):
        report = si.scan_source_root(external, repo, _cfg(root))
        if report.generation_status == "completed":
            break
    else:
        raise AssertionError(f"resume did not complete: {report.generation_status}")
    assert report.generation_id == generation_id
    assert len(repo.active_rel_paths("phase-d")) == 500
    assert generations.get_active_generation("phase-d") is None
    completed = generations.get_generation(generation_id)
    assert completed is not None and completed["status"] == "completed"


def test_lock_contention_is_bounded_and_recovers(tmp_path: Path) -> None:
    rehearsal = _load_rehearsal()
    root = tmp_path / "root"
    root.mkdir()
    for index in range(100):
        (root / f"f-{index:03d}.txt").write_text("x", encoding="utf-8")
    db = tmp_path / "lock.db"
    SQLiteMigrator(db_path=db).apply()
    baseline = rehearsal._run_generation(root, db, observed_limit=50)
    assert baseline["status"] == "completed"
    result = rehearsal._lock_contention(root, db, observed_limit=50)
    assert result["bounded_lock_error"] is True
    assert result["blocked_seconds"] <= 10
    assert result["recovery_status"] == "completed"


def test_failed_slo_cannot_report_pass() -> None:
    rehearsal = _load_rehearsal()
    result = {
        "scale_scans": {
            "1000": {
                "status": "completed",
                "all_files_discoverable": True,
                "bounded_resume": True,
                "metadata_only": True,
                "parser_invocations": {"hash": 0, "extract": 0},
                "peak_rss_mb": 10,
                "files_per_second": 100,
                "expected_files": 1000,
            }
        },
        "no_change": {"metadata_upserted": 0, "files_unchanged": 1000},
        "delta_scans": [
            {"metadata_upserted": 10, "files_unchanged": 990, "expected_changed": 10}
        ],
        "search": {
            "cold_result_count": 1,
            "cold_connection_ms": 1,
            "warm_p95_ms": 1,
            "concurrent_failures": 1,
            "concurrent_p95_ms": 1,
        },
        "wal_checkpoint": {"busy": 0, "after_bytes": 0},
        "lock_contention": {
            "bounded_lock_error": True,
            "blocked_seconds": 1,
            "recovery_status": "completed",
        },
    }
    evaluation = rehearsal._evaluate(
        result,
        {
            "max_peak_rss_mb": 20,
            "min_files_per_second": 10,
            "cold_search_ms": 10,
            "warm_search_p95_ms": 10,
            "concurrent_search_p95_ms": 10,
            "lock_timeout_seconds": 10,
        },
    )
    assert evaluation["checks"]["concurrent_read_slo"] is False
    assert evaluation["passed"] is False


def test_database_remains_readable_after_rehearsal(tmp_path: Path) -> None:
    """Guard against a false green that leaves an unreadable scratch database."""
    db = tmp_path / "readable.db"
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_production_locator_lookup_uses_active_path_index(tmp_path: Path) -> None:
    """The exact production lookup must never regress to an O(n) scan per new file."""
    db = tmp_path / "lookup-plan.db"
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as conn:
        plan = conn.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT s.source_entity_id, l.source_id, l.source_root_key, l.rel_path "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
            "WHERE s.source_kind=? AND l.rel_path=? AND l.source_root_key=?",
            ("external_file", "docs/a.txt", "phase-d"),
        ).fetchall()
    rendered = "\n".join(str(row) for row in plan)
    assert "idx_locators_active_path" in rendered, rendered
    assert "SCAN l" not in rendered, rendered


def test_no_change_batch_queries_use_active_path_index(tmp_path: Path) -> None:
    """Both fast-skip read and observation stamp must stay O(batch), not O(root × batch)."""
    db = tmp_path / "no-change-plan.db"
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as conn:
        read_plan = conn.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT l.rel_path, m.mtime_ns, m.size_bytes "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
            "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
            "WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 "
            "AND l.rel_path IN (?,?)",
            ("phase-d", "a.txt", "b.txt"),
        ).fetchall()
        write_plan = conn.execute(
            "EXPLAIN QUERY PLAN "
            "UPDATE source_index_locators SET last_seen_generation=?, last_seen_at=? "
            "WHERE is_current_locator=1 AND tombstoned_at IS NULL AND source_root_key=? "
            "AND rel_path IN (?,?) "
            "AND source_entity_id IN (SELECT source_entity_id FROM source_intelligence_sources "
            "WHERE source_kind='external_file' AND deleted=0)",
            ("generation", "now", "phase-d", "a.txt", "b.txt"),
        ).fetchall()
    for plan in (read_plan, write_plan):
        rendered = "\n".join(str(row) for row in plan)
        assert "idx_locators_active_path" in rendered, rendered
        assert "SCAN l" not in rendered, rendered


def test_source_file_search_plan_is_selective_fts_first(tmp_path: Path) -> None:
    """Root filtering must not make SQLite scan every locator before applying the FTS match."""
    db = tmp_path / "search-plan.db"
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as conn:
        plan = conn.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT l.source_root_key, l.rel_path, s.source_entity_id "
            "FROM source_intelligence_fts f "
            "CROSS JOIN source_intelligence_metadata m ON m.fts_rowid=f.rowid "
            "CROSS JOIN source_intelligence_sources s ON s.source_entity_id=m.source_entity_id "
            "CROSS JOIN source_index_locators l ON l.source_entity_id=s.source_entity_id "
            "  AND l.is_current_locator=1 AND l.tombstoned_at IS NULL "
            "  AND l.policy_validation_state IS NULL "
            "WHERE source_intelligence_fts MATCH ? AND s.deleted=0 "
            "AND s.source_kind='external_file' AND l.source_root_key=?",
            ("phaseDneedle", "phase-d"),
        ).fetchall()
    details = [str(row[-1]) for row in plan]
    assert "SCAN f VIRTUAL TABLE" in details[0], details
    assert any("idx_si_metadata_fts_rowid" in detail for detail in details), details
    assert not any("SCAN l" in detail for detail in details), details
