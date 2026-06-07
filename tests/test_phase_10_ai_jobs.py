"""Phase 10 Prompt 05 — AI job queue + run receipts tests.

Covers enqueue (idempotent, dry-run zero writes, invalid job_type blocked), the run lifecycle
(dry-run zero writes; apply → ai_job_runs + queue succeeded + hash-only local_model_run_receipts),
no-overlap (held lock blocks a run), retry/backoff (failed job increments retry_count, lands failed
at max_retries, backoff suppresses re-claim), environment isolation, and the no-raw/no-writeback
guard invariant. Fully offline — no Ollama, no network.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai.ai_jobs import (
    enqueue_ai_job_request,
    run_ai_jobs,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.second_brain.run_registry import (
    acquire_run_lock,
    release_run_lock,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_T0 = "2026-06-07T10:00:00+00:00"
_T_WITHIN = "2026-06-07T10:00:10+00:00"
_T_AFTER = "2026-06-07T10:01:00+00:00"
_T_LATER = "2026-06-07T12:00:00+00:00"


def _store(td: str) -> tuple[ConstructionStore, str]:
    db = str(Path(td) / "p10p05.db")
    return ConstructionStore(db_path=db), db


def _enqueue(store: ConstructionStore, *, environment: str = "dev") -> str:
    res = enqueue_ai_job_request(
        store=store, job_type="extract_email_tasks", environment=environment, dry_run=False
    )
    assert res["status"] == "enqueued"
    return res["job_id"]


def _guard_sum(db: str, table: str) -> int:
    conn = sqlite3.connect(db)
    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
    val = conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]
    conn.close()
    return int(val or 0)


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------
def test_enqueue_apply_then_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        first = enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="dev", dry_run=False
        )
        assert first["status"] == "enqueued" and first["enqueued"] is True
        again = enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="dev", dry_run=False
        )
        assert again["status"] == "exists" and again["enqueued"] is False
        assert len(store.list_ai_jobs(environment="dev")) == 1


def test_enqueue_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        res = enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="dev", dry_run=True
        )
        assert res["status"] == "preview" and res["enqueued"] is False
        assert store.list_ai_jobs() == []


def test_enqueue_invalid_job_type_blocked() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        res = enqueue_ai_job_request(
            store=store, job_type="not_a_job", environment="dev", dry_run=False
        )
        assert res["status"] == "blocked"
        assert "invalid_job_type" in res["blockers"]
        assert store.list_ai_jobs() == []


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------
def test_run_dry_run_zero_writes() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        _enqueue(store)
        res = run_ai_jobs(store=store, environment="dev", dry_run=True, locks_dir=f"{td}/locks")
        assert res["status"] == "ok" and res["dry_run"] is True
        assert res["claimed"] == 1
        # No queue mutation, no run rows, no receipts.
        assert store.list_ai_jobs(environment="dev")[0]["status"] == "queued"
        assert store.ai_job_status_summary(environment="dev")["runs"]["run_count"] == 0
        assert store.list_local_model_run_receipts() == []


def test_run_apply_succeeds_and_writes_hash_only_receipts() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, db = _store(td)
        _enqueue(store)
        res = run_ai_jobs(store=store, environment="dev", dry_run=False, locks_dir=f"{td}/locks")
        assert res["status"] == "ok" and res["succeeded"] == 1
        job = store.list_ai_jobs(environment="dev")[0]
        assert job["status"] == "succeeded"
        assert store.ai_job_status_summary(environment="dev")["runs"]["run_count"] == 1
        receipts = store.list_local_model_run_receipts()
        assert len(receipts) >= 1
        # Hash-only + guard-clean across both V41 receipt tables.
        assert _guard_sum(db, "ai_job_runs") == 0
        assert _guard_sum(db, "local_model_run_receipts") == 0
        assert all(len(r["input_context_hash"]) == 12 for r in receipts)


def test_no_overlap_blocks_second_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        _enqueue(store)
        locks = f"{td}/locks"
        held = acquire_run_lock(run_kind="ai_jobs_run", lock_name="ai_jobs_dev", locks_dir=locks)
        assert held.status == "acquired"
        try:
            res = run_ai_jobs(store=store, environment="dev", dry_run=False, locks_dir=locks)
            assert res["status"] == "blocked"
            assert "run_overlap_blocked" in res["blockers"]
        finally:
            release_run_lock(token=held.token, lock_name="ai_jobs_dev", locks_dir=locks)


# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------
def test_retry_backoff_then_failed_at_max_retries() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        _enqueue(store)
        locks = f"{td}/locks"
        bad = StaticOutputClient(raise_unavailable=True)  # forces failure

        # Attempt 1 → retry_scheduled, retry_count 1, back to queued, redacted error recorded.
        r1 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks, now=_T0
        )
        assert r1["results"][0]["outcome"] == "retry_scheduled"
        job = store.list_ai_jobs(environment="dev")[0]
        assert job["retry_count"] == 1 and job["status"] == "queued"
        assert job["last_error_redacted"] == "ollama_request_failed"

        # Within the backoff window → not re-claimed.
        r2 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now=_T_WITHIN,
        )
        assert r2["claimed"] == 0

        # After backoff → attempt 2 → failed (retry_count == max_retries).
        r3 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now=_T_AFTER,
        )
        assert r3["results"][0]["outcome"] == "failed"
        job = store.list_ai_jobs(environment="dev")[0]
        assert job["retry_count"] == 2 and job["status"] == "failed"

        # Permanently failed → never re-claimed.
        r4 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now=_T_LATER,
        )
        assert r4["claimed"] == 0


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------
def test_environment_isolation() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _store(td)
        # Same job_type + default idempotency key in two environments coexist.
        _enqueue(store, environment="dev")
        _enqueue(store, environment="production")
        assert len(store.list_ai_jobs(environment="dev")) == 1
        assert len(store.list_ai_jobs(environment="production")) == 1
        # Running dev does not touch the production queue.
        run_ai_jobs(store=store, environment="dev", dry_run=False, locks_dir=f"{td}/locks")
        assert store.list_ai_jobs(environment="dev")[0]["status"] == "succeeded"
        assert store.list_ai_jobs(environment="production")[0]["status"] == "queued"


# ---------------------------------------------------------------------------
# CLI surfaces
# ---------------------------------------------------------------------------
def test_cli_enqueue_status_run_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        _, db = _store(td)
        enq = runner.invoke(
            app,
            ["ai-jobs", "enqueue", "--job-type", "extract_email_tasks", "--environment", "dev",
             "--apply", "--db", db, "--json"],
        )
        assert enq.exit_code == 0, enq.output
        assert json.loads(enq.output)["status"] == "enqueued"

        lst = runner.invoke(
            app, ["ai-jobs", "status", "--environment", "dev", "--list", "--db", db, "--json"]
        )
        assert lst.exit_code == 0, lst.output
        body = json.loads(lst.output)
        assert body["queue_total"] == 1 and body["jobs"][0]["status"] == "queued"

        run = runner.invoke(
            app, ["ai-jobs", "run", "--environment", "dev", "--apply", "--db", db, "--json"]
        )
        assert run.exit_code == 0, run.output
        rbody = json.loads(run.output)
        assert rbody["status"] == "ok" and rbody["succeeded"] == 1


def test_cli_enqueue_invalid_job_type_exit_two() -> None:
    with tempfile.TemporaryDirectory() as td:
        _, db = _store(td)
        res = runner.invoke(
            app, ["ai-jobs", "enqueue", "--job-type", "bogus", "--apply", "--db", db, "--json"]
        )
        assert res.exit_code == 2
        assert json.loads(res.output)["status"] == "blocked"
