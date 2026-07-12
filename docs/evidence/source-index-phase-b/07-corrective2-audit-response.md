# Phase B — Second Corrective-Commit Audit Response (PB-006 / PB-007 / PB-010 / PB-011)

The AEOS corrective review of `e488136f` VERIFIED FIXED PB-005/008/009 but returned FAIL/NO-GO on PB-006
(parent-symlink escape), PB-007 (FTS/public-search not exercised), and two new Medium findings PB-010
(exhaustion bypasses the ownership guard) + PB-011 (V127 parity narrower than the full-structural contract).
This **third commit** on `phase-b-source-index-architecture-completion` addresses them, preserving both
`80b4d13d` and `e488136f` (no amend). Three plan-review rounds' required changes (PLAN-C2/C2R2-00x) are
incorporated. **No push / PR / deploy / prod DB / watcher activation / prod migration.**

## Finding → fix → test (node IDs)

### FIND-PB-006 (High) — canonical validation of BOTH paths + resolved containment
**Fix.** `normalize_moved_rel_path` (`source_indexer.py`) lexically validates **both** old_rel and new_rel
(reject absolute / `..` / `.` / empty / backslash / non-canonical / protected) with **no filesystem
access**; only normalized values feed lookup / source-id / dest / dedup / lineage.
`resolve_destination` → `DestinationResolution` classifies the destination (`contained` / `absent` /
`indeterminate` / `outside_root` / `not_regular`): `os.lstat` (non-following) rejects a final-component
symlink; `resolve()` + `relative_to(resolved_root)` catches a **symlinked parent** escape. Pre- and
post-transaction re-resolution compares resolved-path **and** identity.
**Accurate guarantee:** an absolute/traversal path is rejected **before any filesystem op**; a
parent-symlink escape may be `lstat`/`resolve`-probed for containment but is rejected **before any source
mutation or content indexing** (a fully probe-free guarantee would need an anchored `dir_fd`/`O_NOFOLLOW`
walk — documented as out of scope for this phase).
**Tests** (`tests/test_source_index_moved_drain.py`): `test_invalid_paths_are_terminal_no_mutation`
(7 params: absolute/traversal/backslash/dup-sep/hidden predecessor + absolute/traversal destination —
`resolve_destination` proven never reached, so no escape is probed);
`test_parent_symlink_escape_rejected_before_mutation` (→ `dest_escapes_root`, old current, outside content
never indexed); `test_symlink_destination_is_terminal_and_keeps_old_current`;
`test_pre_transaction_drift_keeps_old_current`; `test_post_transaction_drift_leaves_old_superseded`.

### FIND-PB-007 (High) — real FTS + public-search invalidation, through the drain
**Fix.** No code change to `_invalidate_content_locked`; the missing PROOF is added.
**Test:** `tests/test_source_index_moved_drain.py::test_move_invalidates_fts_and_public_search_two_stage` —
a destination is pre-indexed with a real `source_intelligence_fts` row (unique `OLD_TOKEN`) discoverable via
`repo.search_source_files(OLD_TOKEN)`; a governed `moved` event is drained in **two controlled passes**:
pass 1 injects an index failure → move commits, FTS row deleted, `OLD_TOKEN` absent from public search,
dest `extraction_status='pending'`, event deferred `dest_reindex_pending`; pass 2 restores indexing → same
event reclaimed (`move_already_applied`) → only `NEW_TOKEN` searchable, `OLD_TOKEN` still absent, lineage
not duplicated. Tokens cannot match path/filename/project metadata.

### FIND-PB-010 (Medium) — attempt-generation ownership on every transition, incl. mutation + exception
**Fix.** `claim_queued` returns the post-increment `attempts` (claim generation). `defer_event` and
`complete_owned_event` (`source_index_repository.py`) guard on `status='processing' AND attempts=?`;
`event_is_owned` re-checks ownership before expensive re-indexing. `apply_owned_confirmed_same_root_move`
runs the ownership `SELECT` **inside the move transaction** (absent → `claim_conflict`, no mutation).
`_apply_moved_event` wraps its body in a guarded `try/except` → `complete_owned_event("error", …)`, so a
moved event can NEVER reach the drain's generic unguarded `complete_event`; all terminal transitions
(skips, `done`, both exhaustion kinds, `moved_invalid`/`unconfigured_root`) are ownership-guarded.
**Tests** (`tests/test_source_index_moved_drain.py`): `test_stale_claim_cannot_complete_or_defer`;
`test_stale_claim_move_is_claim_conflict_no_mutation`;
`test_unexpected_moved_exception_cannot_overwrite_current_claim`;
`test_defer_conflict_when_event_not_processing`; `test_reindex_exhaustion_is_error_not_done`.

### FIND-PB-011 (Medium) — exact structural V127 parity + adaptive lossless repair + always-revalidate
**Fix.** `SQLiteMigrator._events_schema_current` (`store/migrator.py`) validates the COMPLETE column set
with semantically-normalized `(type, notnull, default, pk)`, both indexes' **ordered columns** +
uniqueness, FK/trigger absence, and a live probe (accepts `moved` + a legacy type, rejects an invalid
event_type + invalid status, unique probe id). It runs on **every** `apply()` — a v127-recorded-but-
malformed table is revalidated and rebuilt fail-closed. `_rebuild_v127_events` builds the copy projection
from the OLD table's inspected columns (lossless adaptive repair) and raises
`v127_events_invalid_existing_rows` (whole migration rolls back) on an invalid `event_type`/`status` or
NULL `event_id` — queued work is never coerced/discarded.
**Tests** (`tests/test_migrator_v127_moved_event.py`): `test_fresh_table_is_schema_current_no_false_rebuild`;
`test_missing_attempts_column_rebuilds_losslessly_even_with_v127_recorded`;
`test_wrong_status_default_rebuilds`; `test_index_right_name_wrong_columns_rebuilds`;
`test_invalid_existing_rows_fail_closed_and_roll_back`;
`test_parity_incomplete_table_is_rebuilt_not_marked_applied`;
`test_rebuild_from_old_shape_preserves_rows_and_ids`.

## Validation
- `final-runs/gate-equivalent-corrective2-venv.txt` — full source-index CI-gate test list + the two new
  Phase B corrective files under `.venv/bin/python -m pytest` (CPython 3.14); exact command + collected/
  passed counts + `PYTEST_EXIT` captured in-file. (The gate script's bare `pytest` resolves to system 3.13
  with incompatible FastAPI locally — environment artifact; definitive gate run deferred to CI.)
- `final-runs/ruff-corrective2.txt` — `ruff check` on the 6 touched modules → All checks passed.
- `final-runs/mypy-corrective2.txt` — `mypy` on the 6 touched modules → Success, no issues.
- `#306` count-drift tests remain pre-existing + untouched.

## Commit identity
Recorded in `08-corrective2-committed-tree-identity.md` after this commit (full SHA, parent `e488136f`,
name-status, patch + bundle sha256, final `git status --short`).
