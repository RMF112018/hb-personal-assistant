# Phase B — Corrective-Commit Audit Response (FIND-PB-005…009)

This corrective commit addresses the AEOS Implementation-Audit **FAIL** on Phase B commit `80b4d13d`
(three High B4 trust/deletion defects + two non-blocking parser findings) and the **three rounds** of AEOS
plan-review required changes. It is a **new commit** on branch `phase-b-source-index-architecture-completion`
— `80b4d13d` is left intact (the audited commit + finding→fix trail are preserved). **No push / PR / deploy
/ production DB / watcher activation / production migration.**

Root architectural change: the same-root rename/move is no longer executed on the watchdog **observer
thread**. `on_moved` now enqueues one governed **`moved`** event (old + new rel_path); the readiness-gated,
symlink/identity-safe, transactional lineage move + destination re-extraction runs in the **drain**, with
**bounded-backoff deferral** for every recoverable condition so a move is never terminally consumed while
it could still succeed, and the old row is never superseded until the move is proven safe.

## Finding → fix → test

### FIND-PB-005 (High) — observer-thread mutation + no readiness gate + commit-then-enqueue
**Fix.** `source_watch.apply_same_root_move` (observer-thread mutation) **deleted**; new module-level
`source_watch.enqueue_move` enqueues ONE `moved` event and does no stat/DB work (`source_watch.py`).
V127 rebuilds `source_intelligence_events` to carry a literal `moved` type + `dest_rel_path` +
`next_attempt_at` (`store/migrator.py`, `store/source_intelligence_tables.py::EVENT_TYPE_VALUES_V127`).
`enqueue_event`/`claim_queued` thread `dest_rel_path`; new `defer_event` gives bounded backoff
(`source_index_repository.py`). The drain `moved` branch (`source_indexer.py::_apply_moved_event`) gates on
`_probe_root_dir == "usable"` then `load_root_trust(...).safe_for_watcher_activation`, does the whole
move+reindex in one governed iteration (no commit-then-enqueue split), and DEFERS recoverable conditions.
**Tests.** `test_source_index_moved_drain.py`: `test_ready_root_move_applies`,
`test_stale_root_defers_then_applies_after_recovery`, `test_unavailable_mount_defers_not_consumed`;
`test_source_index_rename_lineage.py::test_watcher_same_root_move_enqueues_moved_event_no_mutation`.

### FIND-PB-006 (High) — symlink-following destination confirmation
**Fix.** The drain confirms the destination with `os.lstat` (non-following): a symlink/non-regular dest is
terminal `dest_not_regular`; `pathsafe.symlink_escapes` rejects a regular-file escape (`dest_escapes_root`);
`pathsafe.path_blocked` rejects protected paths (`dest_denied`). Pre- and post-transaction `lstat` identity
re-checks (`_same_identity`) close the probe→mutate→index TOCTOU window.
**Tests.** `test_symlink_destination_is_terminal_and_keeps_old_current`,
`test_pre_transaction_drift_keeps_old_current`, `test_post_transaction_drift_leaves_old_superseded`.

### FIND-PB-007 (High) — stale destination content retained on an overwrite move
**Fix.** New `_invalidate_content_locked` fully invalidates the destination's content representation
(drops the FTS row via its current `fts_rowid`, DELETEs the `source_intelligence_text` excerpt + chunks,
nulls `content_sha256/fts_rowid/page_count/paragraph_count/sheet_count/extraction_failure_code/
extraction_disposition/content_indexed_at` + sets `extraction_status='pending'`, stales the dest's OWN
generated card). Called inside `apply_confirmed_same_root_move`'s transaction; the metadata `ON CONFLICT`
also re-asserts `content_sha256=''`/`fts_rowid=NULL`.
**Tests.** `test_source_index_rename_lineage.py::test_move_over_indexed_destination_invalidates_content`
(asserts metadata reset, excerpt+chunks gone, dest card `stale`).

### FIND-PB-008 (Med) — CPU rlimit not derived from the timeout
**Fix.** `files/parsers/isolated.py::_cpu_limits(timeout_s)` derives `(soft, hard)` from the wall timeout;
`timeout_s` is threaded through `_worker_main` / `ctx.Process` / `_apply_child_limits`.
**Test.** `test_source_file_parser_isolation.py::test_cpu_limits_derived_from_timeout`.

### FIND-PB-009 (Low) — SIGKILL misclassified as resource-exhaustion
**Fix.** `_classify_dead_child`: only `SIGXCPU` → `parser_resource_exceeded`; `SIGKILL` (ambiguous) →
`parser_failed`. The child's catchable `MemoryError` (RLIMIT_AS) still maps to `parser_resource_exceeded`.
**Tests.** `test_sigkill_classified_parser_failed`, `test_sigxcpu_classified_resource_exceeded`.

## Plan-review contract corrections (3 rounds) → where satisfied

| Contract correction | Where |
|---|---|
| Recoverable conditions **deferred**, not terminally consumed (backoff) | `defer_event` + `_apply_moved_event` matrix; `test_stale_root_defers_then_applies_after_recovery` |
| Moved dedup on **both** paths (A→B vs A→C distinct) | `enqueue_event` moved-branch dedup; `test_distinct_move_destinations_not_deduplicated` |
| V127 parity validates **more than column presence** (probe `moved` INSERT + indexes) | `SQLiteMigrator._events_schema_current`; `test_parity_incomplete_table_is_rebuilt_not_marked_applied` |
| Rebuild **preserves rows + event_ids** (faithful full-column copy; no AUTOINCREMENT/triggers/FKs) | V127 block; `test_rebuild_from_old_shape_preserves_rows_and_ids` |
| Reindex failure **retryable** after a committed move; distinguishable move `result` | `apply_confirmed_same_root_move` result enum + `_apply_moved_event`; `test_reindex_failure_is_retryable_then_succeeds` |
| Mount/dest **transient-vs-terminal** dispositions | matrix (defer root_unavailable/dest_absent/dest_indeterminate; terminal dest_not_regular/dest_escapes_root/moved_invalid) |
| Probe→mutation **pre/post identity** validation | `_same_identity` pre+post `lstat`; pre/post drift tests |
| Content invalidation covers the **complete** search/read surface | `_invalidate_content_locked`; overwrite-invalidation test |
| Generated-note **explicit** stale invariant (collision case) | `_invalidate_content_locked` + relink; overwrite-invalidation test asserts `stale` |
| V127 rollback / code-rollback posture documented | V127 migration comment (§below) |
| `source_missing` **indexes the destination** (no lineage), not a silent drop | result `source_missing` → drain indexes dest; `test_source_missing_indexes_destination_as_ordinary` |
| Post-transaction drift → old **superseded** (not "current") | `test_post_transaction_drift_leaves_old_superseded` |
| Reindex exhaustion → **`error`/dest_reindex_exhausted`**, not `done` | `_apply_moved_event`; `test_reindex_exhaustion_is_error_not_done` |
| Current event-type authority named; public `enqueue_event("moved")` accepted | `EVENT_TYPE_VALUES_V127`; `test_moved_and_legacy_types_accepted` |
| `index_source_file` returning `None` defers (not complete on bare no-throw) | `_apply_moved_event`; `test_reindex_failure_is_retryable_then_succeeds` |
| `defer_event` fails closed if not `processing` | guarded UPDATE; `test_defer_conflict_when_event_not_processing` |

## V127 rebuild recovery / rollback posture
- **Atomic:** the entire `SQLiteMigrator.apply()` runs under one `with transaction(conn)` — the V127
  CREATE/INSERT/DROP/RENAME is all-or-nothing; a crash rolls the whole migration back and cannot lose
  queued rows (they survive in the pre-rebuild table).
- **Idempotent + self-healing:** version-guarded on 127; `_events_schema_current` re-validates AFTER the
  rebuild and records V127 only on success. A parity-incomplete table (columns present but stale CHECK, or
  a missing index) is detected and rebuilt on the next apply — never marked applied on column presence.
- **No AUTOINCREMENT / triggers / FKs** on the events table (`event_id` is a client uuid TEXT PK), so
  there is no sequence/trigger/FK to preserve across the rebuild.
- **Code-rollback caveat:** after V127, OLD application code cannot read/insert `moved` rows — therefore
  Phase B does not deploy or migrate production (Phase C owns the prod schema-copy + backup/restore proof).

## Test results
See `final-runs/gate-equivalent-corrective-venv.txt` — the full source-index CI-gate test list plus the two
new Phase B corrective files (`test_source_index_moved_drain.py`, `test_migrator_v127_moved_event.py`), run
under `.venv/bin/python -m pytest` (CPython 3.14). The gate script uses bare `pytest`, which on this machine
resolves to system Python 3.13 with an incompatible FastAPI (environment artifact, not a code regression —
see `02-limitations-and-reviewer-notes.md`); definitive gate execution is deferred to CI under an activated
venv. `ruff check` + `mypy` clean on every touched module.

## Commit identity
Recorded in `06-corrective-committed-tree-identity.md` after the corrective commit (full SHA, parent
`80b4d13d`, name-status, patch/bundle sha256). The count-drift `#306` tests remain pre-existing + untouched.
