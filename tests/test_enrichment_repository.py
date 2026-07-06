"""N8C-5 — enrichment queue repository: schema, idempotency, atomic claim, leases, receipts.

All work is against ``tmp_path`` scratch DBs. The repository writes only to the two enrichment
tables — never a source/import table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.enrichment_models import EnrichmentValidationError
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.store.migrator import SQLiteMigrator

PAST = "2000-01-01T00:00:00+00:00"
NOW = "2025-01-01T00:00:00+00:00"


@pytest.fixture()
def db(tmp_path: Path) -> str:
    path = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=path).apply()
    return path


@pytest.fixture()
def repo(db: str) -> EnrichmentRepository:
    return EnrichmentRepository(db)


# --- schema / migration -----------------------------------------------------------------
def test_migration_creates_enrichment_tables(db: str) -> None:
    with sqlite3.connect(db) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_enrichment%'")}
        v101 = conn.execute("SELECT name FROM schema_migrations WHERE version = 101").fetchone()
    assert names == {"assistant_enrichment_jobs", "assistant_enrichment_receipts"}
    # Assert the V101 slice is recorded (not the exact head number) so this stays valid under any
    # later additive migration.
    assert v101 is not None and v101[0] == "v101_assistant_enrichment"


def test_migration_idempotent(tmp_path: Path) -> None:
    path = str(tmp_path / "d.sqlite")
    first = SQLiteMigrator(db_path=path).apply()
    second = SQLiteMigrator(db_path=path).apply()
    assert first == second and first >= 101  # idempotent, and at least the V101 slice is applied


def test_check_constraints_enforced(db: str) -> None:
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):  # bad job_type
            conn.execute("INSERT INTO assistant_enrichment_jobs (job_id,job_type,source_id) "
                         "VALUES ('a','nope','s')")
        with pytest.raises(sqlite3.IntegrityError):  # provenance required
            conn.execute("INSERT INTO assistant_enrichment_jobs (job_id,job_type) "
                         "VALUES ('b','source_summary')")


# --- enqueue idempotency ----------------------------------------------------------------
def test_queue_job_requires_provenance(repo: EnrichmentRepository) -> None:
    with pytest.raises(EnrichmentValidationError):
        repo.queue_job(job_type="source_summary")


def test_queue_job_rejects_bad_type(repo: EnrichmentRepository) -> None:
    with pytest.raises(EnrichmentValidationError):
        repo.queue_job(job_type="claim_validation_bogus", source_id="s1")


def test_requeue_is_idempotent_no_duplicate(repo: EnrichmentRepository) -> None:
    a = repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d1")
    b = repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d2")
    assert a["created"] is True and b["created"] is False
    assert a["job_id"] == b["job_id"]
    assert repo.count_jobs() == 1
    # a still-queued job's digest is refreshed in place
    assert repo.get_job(a["job_id"])["source_digest"] == "d2"


def test_payload_over_cap_rejected(repo: EnrichmentRepository) -> None:
    with pytest.raises(EnrichmentValidationError):
        repo.queue_job(job_type="source_summary", source_id="s1",
                       payload={"blob": "z" * 20000})


# --- atomic claim + lease ---------------------------------------------------------------
def test_atomic_claim_two_workers_one_job(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    first = repo.claim_next_job("wA", 300)
    second = repo.claim_next_job("wB", 300)
    assert first is not None and second is None
    assert first["lease_owner"] == "wA"
    assert first["status"] == "claimed"
    assert first["attempt_count"] == 1


def test_atomic_claim_separate_connections(db: str) -> None:
    EnrichmentRepository(db).queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    got_a = EnrichmentRepository(db).claim_next_job("wA", 300)
    got_b = EnrichmentRepository(db).claim_next_job("wB", 300)
    assert bool(got_a) ^ bool(got_b) is False or (got_a and not got_b)  # exactly one wins
    assert (got_a is not None) and (got_b is None)


def test_heartbeat_extends_lease_owner_only(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    job = repo.claim_next_job("wA", 300, now=NOW)
    before = repo.get_job(job["job_id"])["lease_expires_at"]
    assert repo.heartbeat_job(job["job_id"], "wA", 600, now=NOW) is True
    after = repo.get_job(job["job_id"])["lease_expires_at"]
    assert after != before
    assert repo.heartbeat_job(job["job_id"], "wB", 600) is False  # wrong owner


def test_expired_lease_released_and_requeued(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    job = repo.claim_next_job("wA", 300, now=PAST)  # lease already in the past
    released = repo.release_expired_leases(now=NOW)
    assert released == 1
    row = repo.get_job(job["job_id"])
    assert row["status"] == "queued" and row["lease_owner"] is None


# --- completion + receipts + ownership --------------------------------------------------
def test_complete_requires_ownership(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    job = repo.claim_next_job("wA", 300)
    assert repo.complete_job(job["job_id"], "wRogue", status="completed", result_json="{}",
                             applied_status="stored_only") is False
    repo.mark_running(job["job_id"], "wA")
    ok = repo.complete_job(job["job_id"], "wA", status="completed", result_json='{"ok":1}',
                           applied_status="stored_only",
                           receipt_metadata={"worker_id": "wA", "runtime": "fake",
                                             "model_name": "qwen2.5:14b", "prompt_version": "v1",
                                             "input_digest": "i", "output_digest": "o"})
    assert ok is True
    receipts = repo.list_receipts(job_id=job["job_id"])
    assert len(receipts) == 1
    r = receipts[0]
    assert r["applied_status"] == "stored_only" and r["model_name"] == "qwen2.5:14b"
    assert r["input_digest"] == "i" and r["output_digest"] == "o"
    assert repo.get_job(job["job_id"])["status"] == "completed"


def test_fail_requeues_then_exhausts(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d", max_attempts=2)
    j1 = repo.claim_next_job("wF", 300)
    r1 = repo.fail_job(j1["job_id"], "wF", "boom")
    assert r1 == {"status": "queued", "requeued": True}
    j2 = repo.claim_next_job("wF", 300)
    assert j2["job_id"] == j1["job_id"]
    r2 = repo.fail_job(j2["job_id"], "wF", "boom-again")
    assert r2 == {"status": "failed", "requeued": False}
    assert repo.get_job(j1["job_id"])["status"] == "failed"
    assert len(repo.list_receipts(job_id=j1["job_id"])) == 2  # a receipt per failed attempt


def test_peek_next_job_is_read_only(repo: EnrichmentRepository) -> None:
    repo.queue_job(job_type="source_summary", source_id="s1", source_digest="d")
    peeked = repo.peek_next_job()
    assert peeked is not None and peeked["status"] == "queued"
    # peeking does not claim: the job is still queued and unleased
    again = repo.get_job(peeked["job_id"])
    assert again["status"] == "queued" and again["lease_owner"] is None
