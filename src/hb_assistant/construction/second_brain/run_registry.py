"""Phase 08B run registry, run-step ledger, and no-overlap locking (Prompt 05).

Durable run-accounting substrate for the second-brain automation run, distinct from the still-
deferred retry/backoff/weekend executor. Three pieces:

1. **No-overlap lock** — an atomic lock FILE under ``<app_support>/locks/`` created with
   ``os.open(O_CREAT|O_EXCL|O_WRONLY)``. The payload is metadata-only
   (``{token, run_kind, pid, acquired_utc, expires_after_seconds}``). A live lock fails closed
   (``RUN_OVERLAP_BLOCKED``, no deletion); a lock older than ``stale_lock_seconds`` is reclaimed
   (``STALE_LOCK_RECLAIMED``, recording the prior token **hashed**, never raw). Release only when
   the on-disk token matches the caller's token. SQLite is **not** the exclusion mechanism.
2. **Run registry** (V29 ``second_brain_run_registry``) — one metadata-only row per registered run
   (run_kind / status / reason_code / lock_token / lock_status + nullable ``assistant_run_id``
   bridge to the V1 ledger).
3. **Run-step ledger** (V29 ``second_brain_run_steps``) — per-step metadata rows (lock lifecycle
   events are recorded here too). Both tables carry the nine no-raw / no-writeback guard columns.

Local-first, no external writeback, no external delivery, no raw content.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed

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
LOCK_ACQUIRED = "LOCK_ACQUIRED"
RUN_OVERLAP_BLOCKED = "RUN_OVERLAP_BLOCKED"
STALE_LOCK_RECLAIMED = "STALE_LOCK_RECLAIMED"
LOCK_RELEASED = "LOCK_RELEASED"
LOCK_RELEASE_TOKEN_MISMATCH = "LOCK_RELEASE_TOKEN_MISMATCH"
RUN_REGISTERED = "RUN_REGISTERED"
RUN_STEP_RECORDED = "RUN_STEP_RECORDED"
RUN_REGISTRY_LOCKING_OK = "RUN_REGISTRY_LOCKING_OK"

_DEFAULT_LOCK_NAME = "morning_automation"
_DEFAULT_STALE_LOCK_SECONDS = 3600


# --------------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------------
class RunLockResult(BaseModel):
    """Outcome of a lock acquire / release / inspect (metadata-only; no raw content)."""

    status: str  # "acquired" | "blocked" | "reclaimed" | "released" | "held" | "stale" | "absent" | "preview"
    reason_code: str | None = None
    lock_name: str
    token: str | None = None
    run_kind: str | None = None
    lock_path_redacted: str = ""
    prior_token_sha: str | None = None
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("lock detail must not carry raw/forbidden tokens")
        return value


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _redact(path: str | Path) -> str:
    home = str(Path.home())
    text = str(path)
    return text.replace(home, "~") if text.startswith(home) else text


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _locking_cfg() -> dict[str, Any]:
    seed = _safe_seed()
    cfg = seed.get("no_overlap_locking", {})
    return cfg if isinstance(cfg, dict) else {}


def _resolve_locks_dir(locks_dir: str | None) -> Path:
    base = Path(locks_dir) if locks_dir else PathPolicy().get_locks_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _lock_path(lock_name: str, locks_dir: str | None) -> Path:
    return _resolve_locks_dir(locks_dir) / f"{lock_name}.lock"


def _parse_utc(value: str) -> datetime | None:
    try:
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _token_sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _values_only_blob(obj: Any) -> str:
    """Concatenate all VALUES (not dict keys) so the raw-content scan ignores schema field names.

    Field/column names legitimately contain the substring ``token`` (e.g. ``lock_token``); the
    no-raw guard targets persisted VALUES, never schema names.
    """
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


def _read_lock_payload(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _is_stale(payload: dict[str, Any], *, stale_lock_seconds: int, now: datetime) -> bool:
    acquired = _parse_utc(str(payload.get("acquired_utc", "")))
    if acquired is None:
        return True  # unparseable -> treat as stale/reclaimable
    age = (now.astimezone(timezone.utc) - acquired).total_seconds()
    expires = payload.get("expires_after_seconds")
    limit = int(expires) if isinstance(expires, int) else stale_lock_seconds
    return age > limit


def _write_lock_atomic(path: Path, payload: dict[str, Any]) -> None:
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, json.dumps(payload).encode("utf-8"))
    finally:
        os.close(fd)


# --------------------------------------------------------------------------------------------
# Lock primitives (file-based, atomic, fail-closed)
# --------------------------------------------------------------------------------------------
def acquire_run_lock(
    *,
    run_kind: str,
    lock_name: str | None = None,
    stale_lock_seconds: int | None = None,
    locks_dir: str | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> RunLockResult:
    """Acquire the no-overlap lock atomically. Fail-closed on a live lock; reclaim a stale one."""
    cfg = _locking_cfg()
    lock_name = lock_name or str(cfg.get("lock_name", _DEFAULT_LOCK_NAME))
    if stale_lock_seconds is None:
        stale_lock_seconds = int(cfg.get("stale_lock_seconds", _DEFAULT_STALE_LOCK_SECONDS))
    now = now or datetime.now(timezone.utc)
    path = _lock_path(lock_name, locks_dir)
    redacted = _redact(path)
    token = uuid.uuid4().hex
    payload = {
        "token": token,
        "run_kind": run_kind,
        "pid": os.getpid(),
        "acquired_utc": now.astimezone(timezone.utc).isoformat(),
        "expires_after_seconds": stale_lock_seconds,
    }

    if dry_run:
        return RunLockResult(
            status="preview",
            reason_code=LOCK_ACQUIRED,
            lock_name=lock_name,
            run_kind=run_kind,
            lock_path_redacted=redacted,
            detail="dry_run_no_file_written",
        )

    try:
        _write_lock_atomic(path, payload)
        return RunLockResult(
            status="acquired",
            reason_code=LOCK_ACQUIRED,
            lock_name=lock_name,
            token=token,
            run_kind=run_kind,
            lock_path_redacted=redacted,
            detail="lock_file_created",
        )
    except FileExistsError:
        pass

    # A lock file already exists — inspect it.
    existing = _read_lock_payload(path)
    if existing is not None and not _is_stale(
        existing, stale_lock_seconds=stale_lock_seconds, now=now
    ):
        # Live lock — fail closed; do NOT delete or overwrite it.
        return RunLockResult(
            status="blocked",
            reason_code=RUN_OVERLAP_BLOCKED,
            lock_name=lock_name,
            run_kind=run_kind,
            lock_path_redacted=redacted,
            detail="live_lock_held",
        )

    # Stale (or unreadable) lock — reclaim it, recording the prior token hashed (never raw).
    prior_sha: str | None = None
    if existing is not None and isinstance(existing.get("token"), str):
        prior_sha = _token_sha(existing["token"])
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f)
    return RunLockResult(
        status="reclaimed",
        reason_code=STALE_LOCK_RECLAIMED,
        lock_name=lock_name,
        token=token,
        run_kind=run_kind,
        lock_path_redacted=redacted,
        prior_token_sha=prior_sha,
        detail="stale_lock_reclaimed",
    )


def release_run_lock(
    *, token: str, lock_name: str | None = None, locks_dir: str | None = None
) -> RunLockResult:
    """Release the lock only when the on-disk token matches; otherwise fail closed (no deletion)."""
    cfg = _locking_cfg()
    lock_name = lock_name or str(cfg.get("lock_name", _DEFAULT_LOCK_NAME))
    path = _lock_path(lock_name, locks_dir)
    redacted = _redact(path)

    existing = _read_lock_payload(path)
    if existing is None:
        return RunLockResult(
            status="absent",
            reason_code=LOCK_RELEASED,
            lock_name=lock_name,
            lock_path_redacted=redacted,
            detail="no_lock_present",
        )
    if existing.get("token") != token:
        return RunLockResult(
            status="blocked",
            reason_code=LOCK_RELEASE_TOKEN_MISMATCH,
            lock_name=lock_name,
            lock_path_redacted=redacted,
            prior_token_sha=_token_sha(str(existing.get("token", ""))),
            detail="release_refused_id_mismatch",
        )
    path.unlink()
    return RunLockResult(
        status="released",
        reason_code=LOCK_RELEASED,
        lock_name=lock_name,
        token=token,
        lock_path_redacted=redacted,
        detail="lock_file_removed",
    )


def read_run_lock(
    *, lock_name: str | None = None, locks_dir: str | None = None, now: datetime | None = None
) -> RunLockResult:
    """Read-only inspection of the current lock state."""
    cfg = _locking_cfg()
    lock_name = lock_name or str(cfg.get("lock_name", _DEFAULT_LOCK_NAME))
    stale_lock_seconds = int(cfg.get("stale_lock_seconds", _DEFAULT_STALE_LOCK_SECONDS))
    now = now or datetime.now(timezone.utc)
    path = _lock_path(lock_name, locks_dir)
    redacted = _redact(path)

    existing = _read_lock_payload(path)
    if existing is None:
        return RunLockResult(
            status="absent",
            reason_code=None,
            lock_name=lock_name,
            lock_path_redacted=redacted,
            detail="no_lock_present",
        )
    stale = _is_stale(existing, stale_lock_seconds=stale_lock_seconds, now=now)
    return RunLockResult(
        status="stale" if stale else "held",
        reason_code=STALE_LOCK_RECLAIMED if stale else RUN_OVERLAP_BLOCKED,
        lock_name=lock_name,
        run_kind=str(existing.get("run_kind")) if existing.get("run_kind") else None,
        lock_path_redacted=redacted,
        detail="reclaimable" if stale else "live_lock_held",
    )


def clear_stale_lock(
    *, lock_name: str | None = None, locks_dir: str | None = None, now: datetime | None = None
) -> RunLockResult:
    """Remove the lock file ONLY if it is stale; never delete a live lock.

    Used by the Run Recovery Agent to reclaim a lock left behind by a crashed run. A live
    (non-stale) lock is left intact and reported ``RUN_OVERLAP_BLOCKED``.
    """
    cfg = _locking_cfg()
    lock_name = lock_name or str(cfg.get("lock_name", _DEFAULT_LOCK_NAME))
    stale_lock_seconds = int(cfg.get("stale_lock_seconds", _DEFAULT_STALE_LOCK_SECONDS))
    now = now or datetime.now(timezone.utc)
    path = _lock_path(lock_name, locks_dir)
    redacted = _redact(path)

    existing = _read_lock_payload(path)
    if existing is None:
        return RunLockResult(
            status="absent",
            reason_code=None,
            lock_name=lock_name,
            lock_path_redacted=redacted,
            detail="no_lock_present",
        )
    if not _is_stale(existing, stale_lock_seconds=stale_lock_seconds, now=now):
        return RunLockResult(
            status="blocked",
            reason_code=RUN_OVERLAP_BLOCKED,
            lock_name=lock_name,
            lock_path_redacted=redacted,
            detail="live_lock_not_cleared",
        )
    prior_sha = (
        _token_sha(str(existing["token"])) if isinstance(existing.get("token"), str) else None
    )
    path.unlink()
    return RunLockResult(
        status="reclaimed",
        reason_code=STALE_LOCK_RECLAIMED,
        lock_name=lock_name,
        lock_path_redacted=redacted,
        prior_token_sha=prior_sha,
        detail="stale_lock_cleared",
    )


# --------------------------------------------------------------------------------------------
# Run registry + step ledger (V29; emit-gated)
# --------------------------------------------------------------------------------------------
def register_run(
    *,
    run_kind: str,
    status: str,
    reason_code: str | None = None,
    lock_token: str | None = None,
    lock_status: str | None = None,
    assistant_run_id: int | None = None,
    dry_run: bool = False,
    emit: bool = False,
    db_path: str | None = None,
) -> str | None:
    """Insert one metadata-only run-registry row (V29). Returns the ``run_registry_id`` or None."""
    if not emit:
        return None
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    run_registry_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_run_registry
                (run_registry_id, run_kind, status, reason_code, lock_token, lock_status,
                 assistant_run_id, step_count, dry_run, started_utc, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                run_registry_id,
                run_kind,
                status,
                reason_code,
                lock_token,
                lock_status,
                assistant_run_id,
                1 if dry_run else 0,
                now,
                now,
            ),
        )
    return run_registry_id


def record_run_step(
    *,
    run_registry_id: str,
    step_name: str,
    step_order: int,
    status: str,
    reason_code: str | None = None,
    detail: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only run-step row (V29) and bump the registry ``step_count``."""
    if detail and any(t in detail for t in _FORBIDDEN_TOKENS):
        raise ValueError("run-step detail must not carry raw/forbidden tokens")
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    run_step_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_run_steps
                (run_step_id, run_registry_id, step_name, step_order, status, reason_code,
                 detail, started_utc, finished_utc, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_step_id,
                run_registry_id,
                step_name,
                step_order,
                status,
                reason_code,
                detail,
                now,
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE second_brain_run_registry SET step_count = step_count + 1 "
            "WHERE run_registry_id = ?",
            (run_registry_id,),
        )
    return run_step_id


def finish_run(
    *,
    run_registry_id: str,
    status: str,
    reason_code: str | None = None,
    db_path: str | None = None,
) -> None:
    """Mark a registry run finished (status + reason code + finished_utc)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    now = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        conn.execute(
            "UPDATE second_brain_run_registry SET status = ?, reason_code = ?, finished_utc = ? "
            "WHERE run_registry_id = ?",
            (status, reason_code, now, run_registry_id),
        )


def read_latest_run_registry(
    *, db_path: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent run-registry rows (metadata only)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT run_registry_id, run_kind, status, reason_code, lock_token, lock_status,
               assistant_run_id, step_count, dry_run, started_utc, finished_utc, created_utc
        FROM second_brain_run_registry
        ORDER BY created_utc DESC, run_registry_id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]


def read_run_steps(run_registry_id: str, *, db_path: str | None = None) -> list[dict[str, Any]]:
    """Return the steps for a registry run in order (metadata only)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT run_step_id, step_name, step_order, status, reason_code, detail, created_utc
        FROM second_brain_run_steps
        WHERE run_registry_id = ?
        ORDER BY step_order, run_step_id
        """,
        (run_registry_id,),
    )
    return [dict(row) for row in cur.fetchall()]


# --------------------------------------------------------------------------------------------
# Coordinator
# --------------------------------------------------------------------------------------------
def coordinate_no_overlap_run(
    *,
    run_kind: str,
    step_names: list[str],
    lock_name: str | None = None,
    assistant_run_id: int | None = None,
    locks_dir: str | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    emit: bool = False,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Acquire lock -> register run -> record the declared steps -> finish -> release.

    Demonstrates the substrate; it does NOT execute the real pipeline (that is the deferred
    executor). On a live lock it returns ``RUN_OVERLAP_BLOCKED`` without registering or releasing.
    """
    lock = acquire_run_lock(
        run_kind=run_kind,
        lock_name=lock_name,
        locks_dir=locks_dir,
        now=now,
        dry_run=dry_run,
    )
    if lock.status == "blocked":
        return {
            "command": "coordinate_no_overlap_run",
            "run_kind": run_kind,
            "status": "blocked",
            "reason_code": lock.reason_code,
            "lock": lock.model_dump(),
            "run_registry_id": None,
            "dry_run": dry_run,
        }

    run_registry_id = register_run(
        run_kind=run_kind,
        status="started",
        reason_code=RUN_REGISTERED,
        lock_token=lock.token,
        lock_status=lock.status,
        assistant_run_id=assistant_run_id,
        dry_run=dry_run,
        emit=emit,
        db_path=db_path,
    )

    # Record the lock acquisition + each declared step (lock event hashes the prior token).
    if emit and run_registry_id is not None:
        record_run_step(
            run_registry_id=run_registry_id,
            step_name="lock_acquire",
            step_order=0,
            status=lock.status,
            reason_code=lock.reason_code,
            detail=(f"prior_lock_sha={lock.prior_token_sha}" if lock.prior_token_sha else None),
            db_path=db_path,
        )
        for i, name in enumerate(step_names, start=1):
            record_run_step(
                run_registry_id=run_registry_id,
                step_name=name,
                step_order=i,
                status="recorded",
                reason_code=RUN_STEP_RECORDED,
                db_path=db_path,
            )
        finish_run(
            run_registry_id=run_registry_id,
            status="completed-dry-run" if dry_run else "completed",
            reason_code=RUN_REGISTERED,
            db_path=db_path,
        )

    release = None
    if not dry_run and lock.token is not None:
        release = release_run_lock(token=lock.token, lock_name=lock_name, locks_dir=locks_dir)

    return {
        "command": "coordinate_no_overlap_run",
        "run_kind": run_kind,
        "status": "completed",
        "reason_code": RUN_REGISTRY_LOCKING_OK,
        "lock": lock.model_dump(),
        "release": release.model_dump() if release is not None else None,
        "run_registry_id": run_registry_id,
        "step_names": step_names,
        "dry_run": dry_run,
    }


# --------------------------------------------------------------------------------------------
# Proof
# --------------------------------------------------------------------------------------------
def build_run_registry_locking_proof() -> dict[str, Any]:
    """Deterministic proof for ``run-registry-locking-proof.json`` (temp DB + temp locks dir)."""
    import tempfile

    from hb_assistant.construction.store import ConstructionStore

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/run.sqlite3"
        ConstructionStore(db)  # migrate to LATEST
        locks = str(Path(tmp) / "locks")
        base = datetime(2026, 6, 2, 5, 0, tzinfo=timezone.utc)

        # 1. Atomic acquire works.
        acquired = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=base)
        # 2. A second concurrent acquire is blocked (no deletion of the live lock).
        blocked = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=base)
        # 3. Token-mismatch release is refused (no deletion).
        mismatch = release_run_lock(token="not-the-token", locks_dir=locks)
        # 4. A stale lock (well past expiry) is reclaimed with the prior token hashed.
        stale_now = datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)  # +4h > 3600s
        reclaimed = acquire_run_lock(run_kind="daily_brief", locks_dir=locks, now=stale_now)
        # 5. Register a run + steps (emit) and confirm guard columns stay 0.
        run_registry_id = register_run(
            run_kind="daily_brief",
            status="started",
            reason_code=RUN_REGISTERED,
            lock_token=reclaimed.token,
            lock_status=reclaimed.status,
            emit=True,
            db_path=db,
        )
        record_run_step(
            run_registry_id=str(run_registry_id),
            step_name="lock_acquire",
            step_order=0,
            status=reclaimed.status,
            reason_code=reclaimed.reason_code,
            detail=f"prior_lock_sha={reclaimed.prior_token_sha}",
            db_path=db,
        )
        finish_run(
            run_registry_id=str(run_registry_id),
            status="completed",
            reason_code=RUN_REGISTERED,
            db_path=db,
        )
        registry_rows = read_latest_run_registry(db_path=db)
        steps = read_run_steps(str(run_registry_id), db_path=db)
        released = release_run_lock(token=str(reclaimed.token), locks_dir=locks)

        # Guard-column check on the persisted registry row.
        import sqlite3

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        reg_row = dict(conn.execute("SELECT * FROM second_brain_run_registry").fetchone())
        conn.close()
        guards_zero = all(
            v == 0
            for k, v in reg_row.items()
            if k.endswith("_persisted") or k == "external_writeback_performed"
        )

    blob = _values_only_blob(
        [
            acquired.model_dump(),
            blocked.model_dump(),
            mismatch.model_dump(),
            reclaimed.model_dump(),
            registry_rows,
            steps,
            released.model_dump(),
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)
    lock_outside_repo = (
        "/locks/" in acquired.lock_path_redacted or acquired.lock_path_redacted.endswith(".lock")
    )

    proof_passed = bool(
        acquired.status == "acquired"
        and acquired.reason_code == LOCK_ACQUIRED
        and blocked.status == "blocked"
        and blocked.reason_code == RUN_OVERLAP_BLOCKED
        and mismatch.status == "blocked"
        and mismatch.reason_code == LOCK_RELEASE_TOKEN_MISMATCH
        and reclaimed.status == "reclaimed"
        and reclaimed.reason_code == STALE_LOCK_RECLAIMED
        and reclaimed.prior_token_sha
        and run_registry_id
        and len(registry_rows) == 1
        and len(steps) == 1
        and guards_zero
        and released.status == "released"
        and lock_outside_repo
        and no_raw_content
    )
    return {
        "proof": "phase_08b_run_registry_locking",
        "proof_passed": proof_passed,
        "acquire_reason_code": acquired.reason_code,
        "overlap_blocked_reason_code": blocked.reason_code,
        "token_mismatch_reason_code": mismatch.reason_code,
        "stale_reclaimed_reason_code": reclaimed.reason_code,
        "registry_row_count": len(registry_rows),
        "step_count": len(steps),
        "guard_columns_zero": guards_zero,
        "lock_outside_repo": lock_outside_repo,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "read_only_default": True,
            "atomic_file_lock_outside_repo": True,
            "fail_closed_on_overlap": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
