# Phase B — Fourth Corrective Audit Response (PB-010 atomic ownership + PB-012 evidence)

The AEOS corrective review of the **third** commit `0464e347` VERIFIED FIXED PB-006/007/011 (and prior
PB-005/008/009) but returned FAIL/NO-GO on **PB-010** (escalated to High) and a new **PB-012** (evidence
defect). This work lands as two immutable commits on `phase-b-source-index-architecture-completion`,
preserving `80b4d13d`, `e488136f`, `0464e347` (no amend):

- **C4** = `5aeb7ab3` — the PB-010 **code + tests only** (base `0464e347`).
- **E5** = this evidence-only commit (audit response + captures + tree-identity), referencing tested
  `tested_code_sha = C4`. `C4..E5` changes only governed evidence files.

Three plan-review rounds (PLAN-C4-00x, C4R5-00x, C4R6-00x) are incorporated.
**No push / PR / deploy / prod DB / watcher activation / prod migration.**

## FIND-PB-010 (High) — ownership and source mutation now share one write transaction

**Root cause (confirmed against repo truth).** `apply_owned_confirmed_same_root_move` proved ownership with
a read-only `SELECT` inside `with transaction(c)`. The shared `transaction()` helper
(`store/connection.py:151`) never emits `BEGIN`, and `get_connection` opens with Python's default
`isolation_level=''` (`connection.py:99`) — the implicit `BEGIN` fires only before the first **DML**, never
before a `SELECT`. The ownership `SELECT` therefore held **no write lock**, so a `requeue_stuck`+reclaim
(attempts 1→2) could commit between the `SELECT` and the first source DML, and a stale attempt mutated
source/lineage under a lost claim.

**Fix** (`source_index_repository.py`, scoped to the owned-move op + its indexer caller; the shared
`transaction()` helper and global connection config are **unchanged**):
- Ownership is proven by a **guarded WRITE as the first statement** —
  `UPDATE … SET updated_at=? WHERE event_id=? AND status='processing' AND attempts=?`. The DML acquires the
  RESERVED write lock immediately, so this connection holds it through `_confirmed_move_locked` and the
  commit; no concurrent reclaim can commit until it finishes. `rowcount` reflects ownership at
  lock-acquisition time (0 → `claim_conflict`, **no mutation**). The write also refreshes the stuck lease.
- The pre-index `event_is_owned` **SELECT** is replaced by a guarded `heartbeat_owned_event` **UPDATE**
  (re-proves ownership AND refreshes the lease before expensive re-indexing).
- `is_sqlite_busy` classifies SQLite BUSY/LOCKED by the **primary** result code (`& 0xFF`, so extended
  codes like `SQLITE_BUSY_SNAPSHOT` are recognized), with a narrow message fallback only when no numeric
  code is available. Only busy/locked is retryable; every other `OperationalError` stays a real error.
- `defer_event` **and** `complete_owned_event` are busy-aware (return `db_busy` on contention). **Every**
  moved transition — the move guard, the heartbeat, defer, terminal complete/skip, exhaustion, and the
  guarded exception path (`source_indexer.py`) — is fail-closed: BUSY/LOCKED leaves the event `processing`
  for `requeue_stuck`, **never a false terminal and never an unguarded fallback**.

**Tests** (`tests/test_source_index_moved_drain.py`) — all four orderings plus the busy/classifier matrix:
- `test_stale_claim_move_is_claim_conflict_no_mutation` — reclaim **before** the guard → `claim_conflict`,
  no mutation.
- `test_concurrent_reclaim_cannot_race_owned_move` — guard **before** reclaim: a two-connection spy fires
  at the mutation boundary and proves a second connection is **blocked** (BUSY/LOCKED by masked primary
  code) until the move commits; the move applies, old superseded, lineage present.
- `test_reclaim_after_move_blocks_stale_indexing` — reclaim **after** the move commit but **before**
  indexing → the pre-index heartbeat returns `conflict` → the stale claim never indexes; dest left pending.
- `test_move_and_heartbeat_refresh_lease_to_controlled_timestamp` — the move boundary and the heartbeat
  each refresh the lease to an injected timestamp (controlled clock); a stale generation cannot refresh.
- `test_db_busy_through_defer_is_recoverable` — a writer holding the lock through the move **and** the
  deferral → no mutation, no terminal transition, recoverable; after release + **deterministic** stuck
  recovery (seeded lease) the move completes.
- `test_db_busy_during_terminal_completion_is_recoverable` — exhaustion + a contended terminal write →
  `db_busy`, event left `processing`; after release the terminal completion persists.
- `test_non_busy_operational_error_is_terminal_error` — a non-busy `OperationalError` surfaces as a
  terminal `error` (not silently retained).
- `test_busy_raised_in_moved_handler_leaves_processing` — a BUSY/LOCKED exception in the handler leaves the
  event `processing` (fail-closed); also exercises the `is_sqlite_busy` message fallback.
- `test_is_sqlite_busy_classifies_primary_and_extended` — primary BUSY, primary LOCKED, an extended busy
  code, and an unrelated `OperationalError` (→ False).
- `test_stale_claim_cannot_complete_or_defer` (extended) — a stale generation can neither complete, defer,
  nor heartbeat-refresh a reclaimed event.

Every contention connection rolls back and closes in a `finally`; stuck recovery is deterministic
(seeded lease, no wall-clock waiting).

## FIND-PB-012 (Medium) — reproducible, pipefail-correct evidence

The gate capture (`final-runs/gate-equivalent-c4-5aeb7ab3.txt`) records the **literal expanded** pytest
command (no `<…>` placeholders), the `python --version`, `tested_code_sha = C4`, the raw pytest output +
summary, and — via `set -o pipefail` + `${PIPESTATUS[0]}` — **pytest's real exit status** (not `tee`'s).
The target list is the source-index CI-gate list plus the two Phase B corrective files, **expanded and
de-duplicated** (30 unique files; no module runs twice). `ruff-c4.txt` and `mypy-c4.txt` carry the raw
tool output + exit codes.

## Validation summary (tested_code_sha = C4 = `5aeb7ab3`)
- `final-runs/gate-equivalent-c4-5aeb7ab3.txt` — 30-file gate-equivalent run: `493 passed, 1 warning in
  382.57s` (0 failed / 0 errored; the 1 warning is the FastAPI/Starlette deprecation), `PYTEST_EXIT=0`.
- `final-runs/ruff-c4.txt` — `RUFF_EXIT=0` (All checks passed) on the two modules + the test file.
- `final-runs/mypy-c4.txt` — `MYPY_EXIT=0` (Success, no issues) on the two modules.
- `#306` count-drift tests remain pre-existing + untouched.

## Commit identity
Recorded in `10-corrective4-committed-tree-identity.md` (C4 SHA + parent, name-status, C4 patch + bundle
sha256; `tested_code_sha`/`evidence_parent_sha`/`evidence_scope`). E5's own SHA and its patch/bundle
checksums are recorded in the **detached manifest** `final-runs/E5-detached-manifest.md` (post-commit —
recording them inside E5 would be cryptographically circular).
