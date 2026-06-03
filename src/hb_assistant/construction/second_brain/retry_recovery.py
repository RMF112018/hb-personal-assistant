"""Phase 08B retry/backoff receipts + Run Recovery Agent (Prompt 06).

Two deterministic, local-first pieces built on the Prompt-05 run registry + lock substrate:

1. **Retry/backoff** — a policy-driven decision + receipt surface (NOT an executor). Given an
   attempt outcome it decides ``RETRY_SCHEDULED`` (with the policy backoff), ``RETRY_EXHAUSTED``,
   or ``RETRY_SUCCEEDED``, and persists a metadata-only V30 ``second_brain_retry_receipts`` row.
2. **Run Recovery Agent** — detects orphaned/interrupted runs (a V29 registry row left ``started``)
   and stale locks, and (apply, dry-run by default) recovers them: marks the orphan ``recovered``
   and clears a stale lock. A live lock blocks recovery (the run may still be active). Recovery
   mutates only LOCAL state; an emit-gated V28 agent-run receipt records the run.

No external writeback, no external delivery, no raw content. The retry/backoff EXECUTION wiring
(weekend execution, alerting delivery, the full morning pipeline) stays deferred.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .run_registry import (
    clear_stale_lock,
    finish_run,
    read_run_lock,
    register_run,
)

_FORBIDDEN_TOKENS = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)

# Reason codes (declared in the Phase 08B automation policy + gate contracts).
RETRY_SCHEDULED = "RETRY_SCHEDULED"
RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
RETRY_SUCCEEDED = "RETRY_SUCCEEDED"
RETRY_ATTEMPT_RECORDED = "RETRY_ATTEMPT_RECORDED"
RECOVERY_NEEDED = "RECOVERY_NEEDED"
RECOVERY_NOT_NEEDED = "RECOVERY_NOT_NEEDED"
RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
RUN_ORPHANED = "RUN_ORPHANED"
RUN_RECOVERED = "RUN_RECOVERED"
RETRY_RECOVERY_OK = "RETRY_RECOVERY_OK"

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF = [60, 300, 900]
_DEFAULT_ORPHAN_STATUS = "started"


# --------------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------------
class RetryDecision(BaseModel):
    """Outcome of a retry/backoff decision (metadata-only)."""

    status: str  # "scheduled" | "exhausted" | "succeeded"
    reason_code: str
    attempt_number: int
    max_attempts: int
    backoff_seconds: int = 0
    next_attempt_utc: str | None = None
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("retry detail must not carry raw/forbidden tokens")
        return value


class RunRecoveryStatus(BaseModel):
    """Run Recovery Agent snapshot (metadata-only; no raw content)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    orphaned_run_ids: list[str] = []
    orphan_count: int = 0
    lock_status: str = "absent"
    lock_reason_code: str | None = None
    recovered_count: int = 0
    dry_run: bool = True
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("recovery detail must not carry raw/forbidden tokens")
        return value


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _values_only_blob(obj: Any) -> str:
    """Concatenate VALUES (not dict keys) so the raw-content scan ignores schema field names."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif node is not None:
            out.append(str(node))

    walk(obj)
    return " ".join(out)


def load_retry_policy() -> dict[str, Any]:
    """Resolve the retry policy from the seed (max_attempts, backoff_seconds, reason codes)."""
    retry = _safe_seed().get("retry", {})
    retry = retry if isinstance(retry, dict) else {}
    backoff = retry.get("backoff_seconds")
    if not isinstance(backoff, list) or not backoff:
        backoff = list(_DEFAULT_BACKOFF)
    return {
        "max_attempts": int(retry.get("max_attempts", _DEFAULT_MAX_ATTEMPTS)),
        "backoff_seconds": [int(b) for b in backoff],
        "exhausted_reason_code": str(retry.get("exhausted_reason_code", RETRY_EXHAUSTED)),
        "scheduled_reason_code": str(retry.get("scheduled_reason_code", RETRY_SCHEDULED)),
        "succeeded_reason_code": str(retry.get("succeeded_reason_code", RETRY_SUCCEEDED)),
    }


# --------------------------------------------------------------------------------------------
# Retry / backoff (deterministic; no execution)
# --------------------------------------------------------------------------------------------
def plan_retry_schedule(*, run_kind: str) -> dict[str, Any]:
    """Return the planned retry/backoff schedule for ``run_kind`` (read-only)."""
    policy = load_retry_policy()
    backoff = policy["backoff_seconds"]
    attempts = [
        {
            "attempt_number": i,
            "backoff_seconds": backoff[min(i - 1, len(backoff) - 1)]
            if i < policy["max_attempts"]
            else 0,
        }
        for i in range(1, policy["max_attempts"] + 1)
    ]
    return {
        "run_kind": run_kind,
        "max_attempts": policy["max_attempts"],
        "backoff_seconds": backoff,
        "attempts": attempts,
    }


def evaluate_retry(
    *, attempt_number: int, succeeded: bool, now: datetime | None = None
) -> RetryDecision:
    """Decide whether to retry (with backoff), report exhaustion, or success. Deterministic."""
    policy = load_retry_policy()
    max_attempts = policy["max_attempts"]
    backoff = policy["backoff_seconds"]
    now = now or datetime.now(timezone.utc)

    if succeeded:
        return RetryDecision(
            status="succeeded",
            reason_code=policy["succeeded_reason_code"],
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            detail="attempt_succeeded",
        )
    if attempt_number >= max_attempts:
        return RetryDecision(
            status="exhausted",
            reason_code=policy["exhausted_reason_code"],
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            detail="max_attempts_reached",
        )
    backoff_seconds = backoff[min(attempt_number - 1, len(backoff) - 1)]
    next_attempt = now.astimezone(timezone.utc) + timedelta(seconds=backoff_seconds)
    return RetryDecision(
        status="scheduled",
        reason_code=policy["scheduled_reason_code"],
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        next_attempt_utc=next_attempt.isoformat(),
        detail="retry_scheduled_with_backoff",
    )


def record_retry_attempt(
    *,
    run_kind: str,
    attempt_number: int,
    max_attempts: int,
    outcome: str,
    reason_code: str,
    backoff_seconds: int = 0,
    next_attempt_utc: str | None = None,
    run_registry_id: str | None = None,
    emit: bool = False,
    db_path: str | None = None,
) -> str | None:
    """Insert one metadata-only retry receipt (V30). Returns the ``retry_receipt_id`` or None."""
    if not emit:
        return None
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    retry_receipt_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_retry_receipts
                (retry_receipt_id, run_kind, run_registry_id, attempt_number, max_attempts,
                 outcome, reason_code, backoff_seconds, next_attempt_utc, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                retry_receipt_id,
                run_kind,
                run_registry_id,
                attempt_number,
                max_attempts,
                outcome,
                reason_code,
                backoff_seconds,
                next_attempt_utc,
                now,
            ),
        )
    return retry_receipt_id


def read_latest_retry_receipts(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent retry receipts (metadata only)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT retry_receipt_id, run_kind, run_registry_id, attempt_number, max_attempts,
               outcome, reason_code, backoff_seconds, next_attempt_utc, created_utc
        FROM second_brain_retry_receipts
        ORDER BY created_utc DESC, retry_receipt_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


# --------------------------------------------------------------------------------------------
# Run Recovery Agent
# --------------------------------------------------------------------------------------------
def _orphan_status() -> str:
    rc = _safe_seed().get("run_recovery", {})
    rc = rc if isinstance(rc, dict) else {}
    return str(rc.get("orphan_status", _DEFAULT_ORPHAN_STATUS))


def _orphaned_run_ids(db_path: str | None) -> list[str]:
    """V29 registry rows left in the non-terminal orphan status (read-only)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        "SELECT run_registry_id FROM second_brain_run_registry WHERE status = ? "
        "ORDER BY created_utc, run_registry_id",
        (_orphan_status(),),
    )
    return [row[0] for row in cur.fetchall()]


def evaluate_run_recovery(
    *, db_path: str | None = None, locks_dir: str | None = None, now: datetime | None = None
) -> RunRecoveryStatus:
    """Detect orphaned runs + stale locks (read-only). A live lock blocks recovery."""
    orphans = _orphaned_run_ids(db_path)
    lock = read_run_lock(locks_dir=locks_dir, now=now)
    live_lock = lock.status == "held"

    if not orphans:
        return RunRecoveryStatus(
            overall_status="ok",
            reason_code=RECOVERY_NOT_NEEDED,
            orphaned_run_ids=[],
            orphan_count=0,
            lock_status=lock.status,
            lock_reason_code=lock.reason_code,
            detail="no_orphaned_runs",
        )
    if live_lock:
        # A run may still be active behind the live lock — do not recover.
        return RunRecoveryStatus(
            overall_status="attention",
            reason_code=RECOVERY_BLOCKED,
            orphaned_run_ids=orphans,
            orphan_count=len(orphans),
            lock_status=lock.status,
            lock_reason_code=lock.reason_code,
            detail="orphans_present_but_live_lock_held",
        )
    return RunRecoveryStatus(
        overall_status="attention",
        reason_code=RECOVERY_NEEDED,
        orphaned_run_ids=orphans,
        orphan_count=len(orphans),
        lock_status=lock.status,
        lock_reason_code=lock.reason_code,
        detail="orphaned_runs_recoverable",
    )


def run_run_recovery_agent(
    *,
    mode: str = "dry_run",
    db_path: str | None = None,
    locks_dir: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
) -> tuple[RunRecoveryStatus, str | None]:
    """Detect (read-only) and — in ``apply`` mode — recover orphaned runs + clear a stale lock.

    Apply mutates LOCAL state only (registry status -> ``recovered``, stale lock cleared). Returns
    ``(status, agent_run_id|None)``; the emit-gated V28 receipt records that a recovery run happened.
    """
    generated = datetime.now(timezone.utc).isoformat()
    status = evaluate_run_recovery(db_path=db_path, locks_dir=locks_dir, now=now)
    dry_run = mode != "apply"

    recovered = 0
    if not dry_run and status.reason_code == RECOVERY_NEEDED:
        for run_registry_id in status.orphaned_run_ids:
            finish_run(
                run_registry_id=run_registry_id,
                status="recovered",
                reason_code=RUN_RECOVERED,
                db_path=db_path,
            )
            recovered += 1
        # Clear a stale lock if present (never a live one).
        if status.lock_status == "stale":
            clear_stale_lock(locks_dir=locks_dir, now=now)

    final = RunRecoveryStatus(
        overall_status=status.overall_status,
        reason_code=status.reason_code,
        orphaned_run_ids=status.orphaned_run_ids,
        orphan_count=status.orphan_count,
        lock_status=status.lock_status,
        lock_reason_code=status.lock_reason_code,
        recovered_count=recovered,
        dry_run=dry_run,
        detail=status.detail,
    )

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="run_recovery_agent",
            run_kind="run_recovery",
            status=final.overall_status,
            reason_code=final.reason_code,
            started_utc=generated,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return final, agent_run_id


# --------------------------------------------------------------------------------------------
# Proof
# --------------------------------------------------------------------------------------------
def build_retry_recovery_proof() -> dict[str, Any]:
    """Deterministic proof for ``retry-recovery-proof.json`` (temp DB + temp locks dir)."""
    import sqlite3
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/retry.sqlite3"
        ConstructionStore(db)  # migrate to LATEST
        locks = str(Path(tmp) / "locks")
        base = datetime(2026, 6, 2, 5, 0, tzinfo=timezone.utc)
        policy = load_retry_policy()

        # Retry decisions: scheduled -> exhausted -> succeeded.
        plan = plan_retry_schedule(run_kind="daily_brief")
        scheduled = evaluate_retry(attempt_number=1, succeeded=False, now=base)
        exhausted = evaluate_retry(attempt_number=policy["max_attempts"], succeeded=False, now=base)
        succeeded = evaluate_retry(attempt_number=2, succeeded=True, now=base)

        # Persist a metadata-only retry receipt.
        retry_receipt_id = record_retry_attempt(
            run_kind="daily_brief",
            attempt_number=scheduled.attempt_number,
            max_attempts=scheduled.max_attempts,
            outcome="failed",
            reason_code=scheduled.reason_code,
            backoff_seconds=scheduled.backoff_seconds,
            next_attempt_utc=scheduled.next_attempt_utc,
            emit=True,
            db_path=db,
        )
        retry_rows = read_latest_retry_receipts(db_path=db)

        # Recovery: no orphans -> not needed.
        not_needed = evaluate_run_recovery(db_path=db, locks_dir=locks, now=base)
        # Register an orphaned run (status='started') -> needed -> apply recovers it.
        orphan_id = register_run(
            run_kind="daily_brief",
            status="started",
            reason_code="RUN_REGISTERED",
            emit=True,
            db_path=db,
        )
        needed = evaluate_run_recovery(db_path=db, locks_dir=locks, now=base)
        recovered, _ = run_run_recovery_agent(mode="apply", db_path=db, locks_dir=locks, now=base)

        # Guard-column check on the persisted retry receipt.
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        retry_row = dict(conn.execute("SELECT * FROM second_brain_retry_receipts").fetchone())
        # Confirm the orphan row is now recovered.
        recovered_status = conn.execute(
            "SELECT status FROM second_brain_run_registry WHERE run_registry_id = ?",
            (orphan_id,),
        ).fetchone()[0]
        conn.close()
        guards_zero = all(
            v == 0
            for k, v in retry_row.items()
            if k.endswith("_persisted") or k == "external_writeback_performed"
        )

    blob = _values_only_blob(
        [
            plan,
            scheduled.model_dump(),
            exhausted.model_dump(),
            succeeded.model_dump(),
            retry_rows,
            not_needed.model_dump(),
            needed.model_dump(),
            recovered.model_dump(),
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        len(plan["attempts"]) == policy["max_attempts"]
        and scheduled.reason_code == RETRY_SCHEDULED
        and scheduled.backoff_seconds == policy["backoff_seconds"][0]
        and exhausted.reason_code == RETRY_EXHAUSTED
        and succeeded.reason_code == RETRY_SUCCEEDED
        and retry_receipt_id
        and len(retry_rows) == 1
        and guards_zero
        and not_needed.reason_code == RECOVERY_NOT_NEEDED
        and needed.reason_code == RECOVERY_NEEDED
        and recovered.recovered_count == 1
        and recovered_status == "recovered"
        and no_raw_content
    )
    return {
        "proof": "phase_08b_retry_recovery",
        "proof_passed": proof_passed,
        "retry_scheduled_reason_code": scheduled.reason_code,
        "retry_exhausted_reason_code": exhausted.reason_code,
        "retry_succeeded_reason_code": succeeded.reason_code,
        "recovery_not_needed_reason_code": not_needed.reason_code,
        "recovery_needed_reason_code": needed.reason_code,
        "recovered_count": recovered.recovered_count,
        "retry_receipt_count": len(retry_rows),
        "guard_columns_zero": guards_zero,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only_default": True,
            "apply_mutates_local_state_only": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }


def classify_execution_failure(
    e: Exception | None = None,
    stage_name: str | None = None,
    result: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Classify a stage execution failure as transient (local, retryable) or permanent (policy/safety/no-input/no-writeback etc).

    Returns (is_transient_local, reason_code).
    - Transient local: DB/IO/lock contention, certain transient surface errors that are local-only.
    - Permanent (do not retry for this run): policy/safety/missing input, no-writeback violations, already delivered, disabled_by_policy, eval hard fail, external asset etc.
    Used by P04 executor to decide whether to call evaluate_retry + sleep/record V30 or immediate fail + downstream skip.
    """
    text = ""
    if e is not None:
        text = str(e).lower()
    if result is not None:
        text += " " + str(result).lower()
    text = text or ""

    # Permanent / do-not-retry (policy, safety, no-input, no-writeback, already done, disabled, hard eval fail, external)
    permanent_markers = (
        "policy",
        "safety",
        "no_input",
        "no writeback",
        "writeback",
        "already_delivered",
        "disabled_by_policy",
        "external_asset",
        "eval_failed",
        "hard fail",
        "blocked",
    )
    if any(m in text for m in permanent_markers):
        return False, "RETRY_PERMANENT_POLICY_OR_SAFETY"

    # Transient local (DB lock, IO, contention, temp unavail, retryable local surface)
    transient_markers = (
        "lock",
        "database is locked",
        "sqlite",
        "ioerror",
        "oserror",
        "timeout",
        "temporarily",
        "stale",
        "contention",
        "busy",
    )
    if any(m in text for m in transient_markers):
        return True, "RETRY_TRANSIENT_LOCAL"

    # Default: treat unknown as non-transient (fail closed for retry to avoid loops on unexpected)
    return False, "RETRY_PERMANENT_UNKNOWN"
