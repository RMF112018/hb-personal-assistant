"""File-descriptor hardening for the scheduled Procore full-pipeline refresh.

A forced production run died with ``OSError: [Errno 24] Too many open files`` while
writing the scheduled receipt: the per-record SQLite helpers opened a fresh connection
each call (``get_connection``) and ``transaction()`` never closed it, so thousands of
records leaked tens of thousands of descriptors. These tests prove the per-record write
path no longer grows the open-FD count, that receipt writing still succeeds under a
constrained FD budget, and that the connection-ownership helpers close/borrow correctly.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.procore.projection_audit import projection_schema_audit
from hb_assistant.procore.projection_engine import backfill_endpoint_specific_from_raw_payloads
from hb_assistant.procore.structured_analytics import upsert_full_raw_payload_and_structured
from hb_assistant.scheduler.daily_source_refresh import (
    _open_fd_count,
    _raise_fd_limit,
    _write_receipt,
)
from hb_assistant.scheduler.models import ScheduledRefreshReceipt
from hb_assistant.store.connection import borrow_connection, get_connection, open_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import extract_people_refs
from hb_assistant.store.procore_history import record_procore_history_for_record
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    upsert_procore_live_record,
)

_NOW = "2026-01-01T00:00:00+00:00"


def _open_fds() -> int | None:
    for path in ("/dev/fd", f"/proc/{os.getpid()}/fd"):
        try:
            return len(os.listdir(path))
        except OSError:
            continue
    return None


def _migrated_db(tmp_path: Path) -> Path:
    db = tmp_path / "fd.sqlite"
    SQLiteMigrator(db).apply()
    # Satisfy the procore_live_records FK on last_sync_run_id.
    record_sync_run_start(
        sync_run_id="run-1",
        endpoint_id="rfis",
        command_endpoint="rfis",
        legacy_endpoint_alias="list-rfis",
        project_key="p",
        procore_project_id="1",
        company_id="5280",
        mode="live_apply",
        started_at_utc=_NOW,
        db_path=db,
    )
    return db


def _exercise_one_record(db: Path, i: int) -> None:
    """Run the per-record write path for one item across all leak-prone helpers."""
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="p",
        procore_project_id="1",
        raw_item={"id": i, "subject": f"rfi {i}", "status": "open"},
        record_id=str(i),
        source_quality="live_full_payload",
        capture_run_id="run-1",
    )
    upsert_procore_live_record(
        project_key="p",
        procore_project_id="1",
        endpoint_id="rfis",
        procore_record_id=str(i),
        parent_procore_id=None,
        normalized_fields={"title": f"rfi {i}", "status": "open"},
        review_required=False,
        sensitive_reason=None,
        source_url_redacted=None,
        last_sync_run_id="run-1",
        now_utc=_NOW,
        db_path=db,
    )
    record_procore_history_for_record(
        project_key="p",
        endpoint_id="rfis",
        parent_procore_id=None,
        procore_record_id=str(i),
        normalized_fields={"title": f"rfi {i}", "status": "open"},
        sync_run_id="run-1",
        now_utc=_NOW,
        db_path=db,
    )
    extract_people_refs([{"id": i, "name": "n"}], now_utc=_NOW, db_path=db)


def test_per_record_write_path_does_not_leak_fds(tmp_path: Path) -> None:
    db = _migrated_db(tmp_path)
    baseline = _open_fds()
    if baseline is None:
        pytest.skip("no /dev/fd or /proc/self/fd on this platform")

    for i in range(60):
        _exercise_one_record(db, i)
    # Per-run projection stage functions too.
    projection_schema_audit(db_path=db)
    backfill_endpoint_specific_from_raw_payloads(db_path=db, apply=True, limit=10000)

    after = _open_fds()
    assert after is not None
    # Pre-fix this would grow by 60 records x several connections; post-fix it is flat.
    assert after - baseline <= 5, f"open FDs grew materially: {baseline} -> {after}"


def test_receipt_write_succeeds_under_constrained_fd_budget(tmp_path: Path) -> None:
    """The exact production failure: receipt write must still have descriptors available
    after the run path completes, even under a tight FD ceiling."""
    resource = pytest.importorskip("resource")
    db = _migrated_db(tmp_path)
    baseline = _open_fds()
    if baseline is None:
        pytest.skip("no /dev/fd or /proc/self/fd on this platform")

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    # Headroom above the current open count, but far below what the leaking path consumed.
    ceiling = baseline + 64
    if hard != resource.RLIM_INFINITY and hard < ceiling:
        pytest.skip("hard FD limit too low to exercise safely")
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (ceiling, hard))
        for i in range(300):  # pre-fix: ~900 leaked descriptors >> ceiling
            _exercise_one_record(db, i)
        receipt = ScheduledRefreshReceipt(
            generated_utc=_NOW,
            environment="production",
            schedule_date="2026-01-01",
            trigger="manual",
            mode="local_only",
            live_reads_enabled=False,
            procore_live=False,
            graph_live=False,
            mock_data=True,
            db_path="redacted",
            orchestrator_status="ok",
        )
        path = _write_receipt(tmp_path / "evidence", receipt)
        assert Path(path).exists()
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_raise_fd_limit_lifts_soft_toward_target() -> None:
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    low = 256 if (hard == resource.RLIM_INFINITY or hard >= 256) else hard
    target = 4096 if (hard == resource.RLIM_INFINITY or hard >= 4096) else hard
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (low, hard))
        info = _raise_fd_limit(target=target)
        new_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert new_soft >= low
        assert new_soft >= min(target, low if hard == resource.RLIM_INFINITY else hard)
        assert info.get("fd_soft_limit") == new_soft
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))


def test_open_fd_count_is_a_nonnegative_int_or_none() -> None:
    n = _open_fd_count()
    assert n is None or (isinstance(n, int) and n >= 0)


def test_open_connection_owns_and_borrow_connection_reuses(tmp_path: Path) -> None:
    db = _migrated_db(tmp_path)

    # open_connection owns: the connection is closed after the block.
    with open_connection(db) as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")

    # borrow_connection(None, db) owns + closes a fresh one.
    with borrow_connection(None, db) as owned:
        owned.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        owned.execute("SELECT 1")

    # borrow_connection(existing) reuses and does NOT close the caller's connection.
    outer = get_connection(db)
    try:
        with borrow_connection(outer, None) as borrowed:
            assert borrowed is outer
        outer.execute("SELECT 1")  # still open after the borrow block
    finally:
        outer.close()
