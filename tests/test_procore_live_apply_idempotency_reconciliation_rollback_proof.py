"""Phase 04A Prompt 11: idempotency, reconciliation, and rollback proof.

Five orthogonal proofs against the Phase 04A V6 schema:

  1. ``test_first_apply_receipt_counts_reconcile_with_sqlite_row_count`` —
     the ``sqlite_upserted_count`` recorded on a completed sync run matches
     the actual row count in ``procore_live_records`` for the scope.
  2. ``test_second_apply_produces_only_updates_zero_new_inserts`` —
     replaying the exact same payloads under a new sync_run_id yields
     every upsert returning ``"updated"`` (not ``"inserted"``), the row
     count stays unchanged, and ``last_sync_run_id`` advances on every
     existing row.
  3. ``test_count_reconciliation_by_sync_run_id`` — two disjoint sync runs
     are individually reconcilable: a per-sync_run_id ``SELECT COUNT(*)``
     equals each run's receipt-side ``sqlite_upserted_count``.
  4. ``test_delete_by_sync_run_id_rolls_back_only_targeted_rows`` — the
     new ``delete_procore_live_records_by_sync_run`` repository function
     removes exactly the rows attributed to one sync_run_id, leaves all
     other rows alone, and preserves the matching ``procore_live_sync_runs``
     audit row.
  5. ``test_backup_restore_round_trip_restores_pre_apply_state`` — a
     ``sqlite3 Connection.backup()`` snapshot taken before an apply,
     restored afterward, leaves the ``procore_live_records`` table empty
     and the ``procore_live_sync_runs`` table reverted. (``Connection.backup()``
     is WAL-safe; the operator runbook documents the same primitive via the
     ``sqlite3 db.sqlite ".backup backup.db"`` shell form.)

No live Procore call, no real token, no PII — every payload is built from
benign synthetic fields. Mirrors the fake-transport posture of
``tests/test_procore_live_sync_verified_chain.py``.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Tuple

import pytest

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_repositories import (
    count_procore_live_records,
    delete_procore_live_records_by_sync_run,
    get_sync_run,
    record_sync_run_complete,
    record_sync_run_start,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_PROJECT = "tropical"
_PROCORE_PROJECT_ID = "2525840"
_COMPANY_ID = "5280"
_ENDPOINT = "rfis"


def _new_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _seed_run_start(db: Path, sync_run_id: str) -> None:
    record_sync_run_start(
        sync_run_id=sync_run_id,
        endpoint_id=_ENDPOINT,
        command_endpoint=_ENDPOINT,
        legacy_endpoint_alias="list-rfis",
        project_key=_PROJECT,
        procore_project_id=_PROCORE_PROJECT_ID,
        company_id=_COMPANY_ID,
        mode="live_apply",
        started_at_utc="2026-05-29T00:00:00+00:00",
        db_path=db,
    )


def _seed_run_complete(db: Path, sync_run_id: str, *, upserted: int) -> None:
    record_sync_run_complete(
        sync_run_id=sync_run_id,
        status="success",
        state="success",
        reason_codes=[],
        request_count=1,
        retrieved_count=upserted,
        normalized_count=upserted,
        sqlite_upserted_count=upserted,
        evidence_path="docs/evidence/construction-intelligence-phase-04a/18-idempotency-reconciliation-rollback.md",
        completed_at_utc="2026-05-29T00:01:00+00:00",
        no_live_call_performed=False,
        db_path=db,
    )


def _payloads(count: int, *, prefix: str = "RFI") -> Tuple[Tuple[str, dict], ...]:
    return tuple(
        (
            str(1000 + i),
            {
                "number": f"{prefix}-{1000 + i}",
                "subject": f"benign subject {i}",
                "status": "open",
                "updated_at": "2026-05-29",
            },
        )
        for i in range(count)
    )


def _upsert_batch(
    db: Path,
    sync_run_id: str,
    payloads: Tuple[Tuple[str, dict], ...],
) -> list[str]:
    """Return the list of upsert results ("inserted" / "updated")."""
    return [
        upsert_procore_live_record(
            project_key=_PROJECT,
            procore_project_id=_PROCORE_PROJECT_ID,
            endpoint_id=_ENDPOINT,
            procore_record_id=record_id,
            parent_procore_id=None,
            normalized_fields=fields,
            review_required=False,
            sensitive_reason=None,
            source_url_redacted=f"/rest/v1.0/projects/{_PROCORE_PROJECT_ID}/rfis",
            last_sync_run_id=sync_run_id,
            now_utc="2026-05-29T00:00:30+00:00",
            db_path=db,
        )
        for record_id, fields in payloads
    ]


# ---------------------------------------------------------------------------
# 1. Receipt counts reconcile with SQLite row count.
# ---------------------------------------------------------------------------


def test_first_apply_receipt_counts_reconcile_with_sqlite_row_count() -> None:
    db = _new_db()
    sync_run_id = "run-recon-1"
    payloads = _payloads(5)

    _seed_run_start(db, sync_run_id)
    results = _upsert_batch(db, sync_run_id, payloads)
    _seed_run_complete(db, sync_run_id, upserted=len(payloads))

    assert results == ["inserted"] * 5

    receipt = get_sync_run(sync_run_id=sync_run_id, db_path=db)
    assert receipt is not None
    assert receipt["sqlite_upserted_count"] == 5
    assert receipt["normalized_count"] == 5
    assert receipt["retrieved_count"] == 5
    assert receipt["raw_body_persisted"] == 0
    assert receipt["redaction_applied"] == 1

    actual = count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db)
    assert actual == receipt["sqlite_upserted_count"]


# ---------------------------------------------------------------------------
# 2. Re-apply yields zero new inserts; existing rows advance last_sync_run_id.
# ---------------------------------------------------------------------------


def test_second_apply_produces_only_updates_zero_new_inserts() -> None:
    db = _new_db()
    payloads = _payloads(4)

    first_run = "run-idem-1"
    _seed_run_start(db, first_run)
    first_results = _upsert_batch(db, first_run, payloads)
    _seed_run_complete(db, first_run, upserted=len(payloads))
    assert first_results == ["inserted"] * 4

    second_run = "run-idem-2"
    _seed_run_start(db, second_run)
    second_results = _upsert_batch(db, second_run, payloads)
    _seed_run_complete(db, second_run, upserted=len(payloads))

    # Stop condition: re-apply must be an update-only operation.
    assert second_results == ["updated"] * 4

    # Row count must not grow.
    assert count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db) == 4

    # Every row's last_sync_run_id must now point at the second run.
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("SELECT last_sync_run_id FROM procore_live_records").fetchall()
    finally:
        conn.close()
    assert rows and all(r[0] == second_run for r in rows)


# ---------------------------------------------------------------------------
# 3. Per-sync_run_id reconciliation across two disjoint runs.
# ---------------------------------------------------------------------------


def test_count_reconciliation_by_sync_run_id() -> None:
    db = _new_db()

    run_a = "run-recon-a"
    run_b = "run-recon-b"
    payloads_a = _payloads(3, prefix="A")
    payloads_b = tuple(
        (
            str(2000 + i),
            {
                "number": f"B-{2000 + i}",
                "subject": f"second-batch {i}",
                "status": "open",
                "updated_at": "2026-05-29",
            },
        )
        for i in range(2)
    )

    _seed_run_start(db, run_a)
    _upsert_batch(db, run_a, payloads_a)
    _seed_run_complete(db, run_a, upserted=len(payloads_a))

    _seed_run_start(db, run_b)
    _upsert_batch(db, run_b, payloads_b)
    _seed_run_complete(db, run_b, upserted=len(payloads_b))

    receipt_a = get_sync_run(sync_run_id=run_a, db_path=db)
    receipt_b = get_sync_run(sync_run_id=run_b, db_path=db)
    assert receipt_a is not None and receipt_b is not None

    conn = sqlite3.connect(str(db))
    try:
        actual_a = conn.execute(
            "SELECT COUNT(*) FROM procore_live_records WHERE last_sync_run_id = ?",
            (run_a,),
        ).fetchone()[0]
        actual_b = conn.execute(
            "SELECT COUNT(*) FROM procore_live_records WHERE last_sync_run_id = ?",
            (run_b,),
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM procore_live_records").fetchone()[0]
    finally:
        conn.close()

    assert actual_a == receipt_a["sqlite_upserted_count"] == 3
    assert actual_b == receipt_b["sqlite_upserted_count"] == 2
    assert total == 5


# ---------------------------------------------------------------------------
# 4. Rollback by receipt id: dry-run preview + apply, audit row preserved.
# ---------------------------------------------------------------------------


def test_delete_by_sync_run_id_rolls_back_only_targeted_rows() -> None:
    db = _new_db()

    run_a = "run-rollback-a"
    run_b = "run-rollback-b"
    _seed_run_start(db, run_a)
    _upsert_batch(db, run_a, _payloads(3, prefix="A"))
    _seed_run_complete(db, run_a, upserted=3)

    _seed_run_start(db, run_b)
    _upsert_batch(
        db,
        run_b,
        tuple((str(3000 + i), {"number": f"B-{3000 + i}", "status": "open"}) for i in range(2)),
    )
    _seed_run_complete(db, run_b, upserted=2)

    # Dry-run preview must report the right count and mutate nothing.
    preview = delete_procore_live_records_by_sync_run(sync_run_id=run_a, db_path=db, dry_run=True)
    assert preview == {
        "sync_run_id": run_a,
        "would_delete": 3,
        "dry_run": True,
    }
    assert (
        count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db) == 5
    ), "dry-run preview must not delete"

    # Apply the rollback.
    result = delete_procore_live_records_by_sync_run(sync_run_id=run_a, db_path=db, dry_run=False)
    assert result == {
        "sync_run_id": run_a,
        "deleted": 3,
        "dry_run": False,
    }

    # Only run B's rows survive.
    assert count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db) == 2

    # Audit trail preserved: the procore_live_sync_runs row for A still exists.
    audit = get_sync_run(sync_run_id=run_a, db_path=db)
    assert audit is not None
    assert audit["status"] == "success"
    assert audit["sqlite_upserted_count"] == 3

    # Idempotency of rollback itself: a second apply finds zero rows.
    second = delete_procore_live_records_by_sync_run(sync_run_id=run_a, db_path=db, dry_run=False)
    assert second == {
        "sync_run_id": run_a,
        "deleted": 0,
        "dry_run": False,
    }


# ---------------------------------------------------------------------------
# 5. Backup-and-restore round trip restores pre-apply state.
# ---------------------------------------------------------------------------


def _sqlite_backup(src: Path, dst: Path) -> None:
    """WAL-safe DB-to-DB snapshot using the sqlite3 backup API."""
    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dst))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()


def test_backup_restore_round_trip_restores_pre_apply_state(tmp_path: Path) -> None:
    db = _new_db()
    backup = tmp_path / "backup.sqlite"
    _sqlite_backup(db, backup)

    # Sanity: backup is empty (no rows, no sync_run row).
    conn = sqlite3.connect(str(backup))
    try:
        records_before = conn.execute("SELECT COUNT(*) FROM procore_live_records").fetchone()[0]
        runs_before = conn.execute("SELECT COUNT(*) FROM procore_live_sync_runs").fetchone()[0]
    finally:
        conn.close()
    assert records_before == 0
    assert runs_before == 0

    # Apply against the live DB.
    sync_run_id = "run-backup-1"
    _seed_run_start(db, sync_run_id)
    _upsert_batch(db, sync_run_id, _payloads(4))
    _seed_run_complete(db, sync_run_id, upserted=4)

    assert count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db) == 4
    assert get_sync_run(sync_run_id=sync_run_id, db_path=db) is not None

    # Restore the backup over the live DB (backup direction reversed).
    _sqlite_backup(backup, db)

    # Restored state matches pre-apply state on both tables.
    assert count_procore_live_records(project_key=_PROJECT, endpoint_id=_ENDPOINT, db_path=db) == 0
    assert get_sync_run(sync_run_id=sync_run_id, db_path=db) is None
