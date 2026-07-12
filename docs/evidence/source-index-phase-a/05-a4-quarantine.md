# A4 — Poison-file quarantine + bounded forward progress

**Checkpoint:** A4 (fifth sub-phase of Phase A). **Parent commit:** A2 corrective #2 `3c5d7738`.
**Branch state after this checkpoint:** GREEN (all 26 new A4 tests pass; only the two disclosed pre-existing
stale-version baseline failures remain). **No push / PR / merge / force / history rewrite.** All work on
scratch SQLite + temp roots + mocked FS failures; no live/production DB, NAS, watcher, or remote MCP surface
was touched.

## Defect addressed (A4 hypothesis, verified on `origin/main` `9c27839b`, schema V124)

On a per-file stat/upsert failure the scan cursor holds **before** the poison file
(`source_indexer._flush`, `last_cursor` set only after a committed observation), the generation is suspended
`partial`/`metadata_walk_error`, and it is retried **forever**. `partial` is outside
`_NO_PROGRESS_ERROR_CODES`, so the block is never surfaced. There was **no quarantine / retry / attempt state
anywhere**, and no per-path column — a single persistent poison file pins a root's generation indefinitely and
starves every later file in walk order. Behavioral prove-red in `a4-prove-red.txt` demonstrates this directly:
at the parent, `f3.txt` is never indexed past a permanently-failing `f2.txt` and the generation stays `partial`
across 8 passes.

## Design implemented

Durable, root-level quarantine + bounded retry so one poison path can't pin a root, **without misusing
`completed`** and **without creating a new infinite loop**.

### 1. V125 additive migration
- **New** `src/hb_assistant/store/source_index_scan_quarantine_tables.py` — `CREATE TABLE IF NOT EXISTS
  source_index_scan_quarantine` with columns `quarantine_id (PK), source_root_key, generation_id (NULLABLE),
  origin_generation_id, source_id, rel_path (root-relative), failure_stage, error_code, attempt_count,
  first_seen_at, last_seen_at, last_attempt_at, status, resolution_state, resolved_at,
  last_successful_observation_at`; a **partial UNIQUE index** on `(source_root_key, rel_path) WHERE
  resolution_state='unresolved'` (at most one active record per (root, path); resolved history may accumulate);
  and a `(source_root_key, resolution_state)` lookup index. No `ON DELETE CASCADE` — the blocker is
  **root-level, not generation-level**.
- `store/migrator.py`: `LATEST_SCHEMA_VERSION = 125`; a version-guarded, parity-guarded V125 block delegating to
  `_v125_statements()` and recording `(125, 'v125_source_index_scan_quarantine')` in `schema_migrations`.
- **Migration integrity** (raw: `a4-migration-evidence.txt`): fresh DB → 125 (table + both indexes present,
  `quick_check`/`integrity_check` = ok); idempotent re-`apply()` → 125 (still one table); simulated V124→V125
  upgrade (drop marker+table, re-apply) → table re-created, `quick_check` ok.

### 2. Repository — bounded attempt accounting, single active record, sanitized storage
`store/source_index_scan_quarantine_repository.py` — connection-composable (`_conn(conn, in_transaction)`) so
the scan loop's write commits in the **same transaction** as the cursor advance:
- `record_failure(...)` → `{"action": "hold"|"quarantine", "attempt_count", "quarantine_id"}`. First failure
  inserts, subsequent failures increment `attempt_count`; `status="quarantined"` once `attempt_count >=
  threshold`, else `retrying`. An `error_code` outside the structured set is coerced to `metadata_upsert_failed`
  (a raw exception string with a host path is **never** stored).
- `resolve_observed(...)` — a below-threshold path observed cleanly this pass is resolved so a genuinely
  transient failure never accumulates (preserves the F-03 hold-and-retry guarantee).
- `resolve(quarantine_id, resolution_state)` — operator resolution (`resolved` / `confirmed_absent`); guarded
  `WHERE resolution_state='unresolved'`, so it is idempotent (a second resolve returns `rowcount==0`).
- Reads: `blocking_count` / `has_blocking` / `blocking_paths` (status=quarantined AND unresolved),
  `troubled_paths` (any unresolved), `blocking_counts_by_root`, `list_quarantine`, `get`, `null_generation_ids`.

### 3. Scan loop — threshold retry, cursor advance, non-authoritative completion
`obsidian_mcp/source_indexer.py`:
- `_classify_observation_error(exc)` maps a stat failure to a **structured** code (EACCES/EPERM →
  `path_unreadable`; ENOENT/ESTALE → `path_changed_during_observation`; else `stat_failed`).
- In `_flush` (inside the existing `with open_connection(...) as c, transaction(c):`): a per-file stat/upsert
  failure or a no-source-id race calls `record_failure(..., conn=c, in_transaction=True)`. **Below threshold**
  → `pass_error=True; break` (hold the cursor, retry next pass — unchanged F-03). **At threshold** → add to the
  in-pass `q_skip` set, **advance the cursor past** the poison file, and continue indexing later files. An
  already-quarantined path in `q_skip` is skipped immediately (cursor advances, never re-attempted). A path in
  `q_retry_watch` observed cleanly is resolved via `resolve_observed`. The report keeps its original
  human-facing `error_codes` labels (`stat_error`, exception type name, `metadata_no_source_id`); the structured
  A4 classification lives only in the quarantine record.
- After the walk exhausts: `if quarantine_repo.has_blocking(root): fail_generation(..., last_error_code=
  "quarantine_unresolved")` → the generation is `failed`, **non-authoritative** (no metadata-walk-complete, no
  reconciliation, never `completed`). Resolving the last quarantine does **not** itself complete it.

### 4. No new infinite loop (automatic-retry suspension)
`store/source_index_scan_generations_repository.py`: `quarantine_unresolved` added to
`_NO_PROGRESS_ERROR_CODES`. `begin_generation_pass` returns the **blocked sentinel** for a latest
`failed(quarantine_unresolved)` generation — so an automatic pass does not walk/reconcile. The block is
**conditional**: `_root_has_blocking_quarantine(c, root_key)` is consulted, so once the operator resolves the
quarantine the block lifts on the next pass. Recovery paths: successful operator retry, a quarantine-affecting
policy change (fingerprint), or an explicit restart.

### 5. Trust (A2 integration)
`obsidian_mcp/source_root_trust.py`: `RootTrustInputs`/`RootTrustDecision` carry `unresolved_quarantine_count`;
`evaluate_root_trust` sets `trust_state = blocked` and appends `RC_QUARANTINE_UNRESOLVED` when the count > 0
(authorized branch). `gather_root_inputs` reads `blocking_count` and **fails closed** (count → 1) if the
quarantine table is unreadable. `source_health_service.py` batches `blocking_counts_by_root` into per-root
inputs. A certified-safe root with a blocking quarantine flips to `blocked` / `quarantine_unresolved`.

### 6. Retry threshold — validated, configurable, policy-fingerprinted
`obsidian_mcp/config.py`: `source_index_quarantine_retry_threshold: int = 3` with a `field_validator` raising
`source_index_quarantine_retry_threshold_must_be_at_least_1` for values < 1. `_policy_fingerprint` includes
`quarantine_retry_threshold`, so changing it invalidates prior generations (the operator's "relevant policy
change" that lifts a block via a fresh generation) — same mechanism as `fanout_limit`.

### 7. Operator CLI (local only; NO remote MCP write surface)
`obsidian_mcp/source_quarantine_ops.py` + `cli/source_watch.py`:
- `quarantine-list` / `quarantine-inspect` — **READ-ONLY**, sanitized (rel_path only; no absolute host path).
- `quarantine-retry --root-key --quarantine-id --max-items --confirm` — operator-only, **bounded**, requires
  `--confirm`; re-observes and resolves ONLY on a trustworthy observation, else RETAINS. Never writes a source
  file, never resolves the whole set blindly. Demonstrated end-to-end on scratch data in
  `a4-operator-cli-demo.txt`. A grep + a live-registration test confirm **no MCP tool** name contains
  "quarantine" (`ALL_ASSISTANT_TOOLS`/`ALL_PA_TOOLS`).

## Binding invariants — where enforced

| Invariant | Enforcement | Test |
|---|---|---|
| **Atomic threshold transition** (attempt finalize + quarantine upsert + cursor advance commit together) | `record_failure(conn=c, in_transaction=True)` inside `_flush`'s single `transaction(c)` | `test_threshold_retry_creates_one_quarantine_and_indexes_later_files` |
| **Generation ownership** (mutations only under a valid lease; lease loss aborts without partial mutation) | `_flush` cursor advance is lease-fenced (rowcount 0 → `_LeaseLost`); the quarantine write shares that transaction and rolls back with it | generation-hardening `test_advance_cursor_returns_zero_when_lease_lost` (unchanged) + shared-transaction design |
| **Failure classification** (structured codes, no raw exceptions / host paths) | `_classify_observation_error`; `record_failure` coerces unknown codes | `test_record_failure_normalizes_unknown_error_code`, `test_stored_rel_path_is_root_relative_no_absolute_host_path` |
| **Missing path during retry ≠ success** | `_observe` returns `confirmed_absent` only when root available + parent listable + genuinely gone; else RETAIN | `test_operator_retry_confirmed_absent_only_when_trustworthy`, `test_operator_retry_retains_when_root_unavailable` |
| **Root-level blocker survives pruning** | `generation_id` nullable, `origin_generation_id` retained, no cascade; `prune_generations` retains the latest blocking generation + nulls pruned generation_ids | `test_generation_retention_preserves_unresolved_quarantine`, `test_pruned_origin_generation_does_not_clear_root_blocker` |
| **Automatic-retry suspension** | `quarantine_unresolved` ∈ `_NO_PROGRESS_ERROR_CODES`; `begin_generation_pass` blocked sentinel (conditional on live quarantine) | `test_unresolved_quarantine_suspends_auto_retry` |
| **Completion semantics** (never `completed` while quarantine remains; resolving last quarantine ≠ completion) | terminal `has_blocking` → `fail_generation(quarantine_unresolved)` before `mark_metadata_walk_complete` | `test_threshold_retry_...` (status `failed`), retry ops docstring/contract |
| **Operator command boundary** (list/inspect read-only; retry bounded + confirmed; no remote write; no blanket ignore) | `source_quarantine_ops` + CLI `--confirm` gate + `max_items` bound | `test_operator_retry_is_bounded_by_max_items`, `test_operator_retry_is_idempotent_on_resolved_record`, `test_no_remote_quarantine_write_tool_exposed`, `test_quarantine_cli_commands_registered_locally` |

## Cursor / quarantine state-transition diagram

```
per-file failure, attempt_count < threshold
    → record_failure -> action="hold"; cursor HELD before file; pass suspends `partial`; retried next pass
per-file failure, attempt_count = threshold
    → record_failure -> action="quarantine"; status=quarantined; cursor ADVANCES past file (same txn);
      later files in the pass still index
walk exhausts holding a blocking quarantine
    → fail_generation(quarantine_unresolved); generation NON-authoritative; reconciliation prohibited;
      automatic retry SUSPENDED (begin_generation_pass returns blocked sentinel)
operator quarantine-retry (--confirm, bounded)
    → _observe: readable → resolve(`resolved`); trustworthily absent → resolve(`confirmed_absent`);
      indeterminate (root/parent unavailable, permission, race) → RETAIN
all quarantines resolved
    → next automatic pass no longer blocked; verifies end-of-walk; metadata walk may complete;
      reconciliation may begin; `completed` permitted only AFTER reconciliation (resolving does not itself complete)
transient failure that clears before threshold
    → next clean observation calls resolve_observed → the `retrying` record is cleared; NEVER quarantined (F-03)
```

## Confirmed-absence contract (`_observe`)

A retry that cannot find the path is **not** automatically success. `confirmed_absent` requires: (a) the root
directory is available (`root_dir.is_dir()`); (b) the parent directory is trustworthily listable
(`os.scandir` succeeds — not a permission/mount artifact); (c) the entry is genuinely gone (not a race
reappearance). Any indeterminate signal — `root_unavailable`, `parent_untrustworthy`, `reappeared_during_retry`,
`path_unreadable` (permission / stale handle / mount loss) — RETAINS the unresolved quarantine.

## Static checks (changed files only)
- `ruff check` — all changed + new modules: **All checks passed** (`python -m ruff`, ruff 0.15.14).
- `ruff format --check` — new modules formatted (`source_quarantine_ops.py`, `source_root_trust.py`,
  quarantine tables/repository); pre-existing-unformatted origin files (e.g. `source_indexer.py`) were **not**
  reformatted.
- `mypy` — `source_index_scan_quarantine_tables.py`, `source_index_scan_quarantine_repository.py`,
  `source_quarantine_ops.py`, `source_root_trust.py`: **Success: no issues found in 4 source files**.

## Validation
See `a4-validation.txt` (raw), `a4-node-ids.txt` (26 green node IDs + timings), `a4-prove-red.txt`,
`a4-migration-evidence.txt`, `a4-operator-cli-demo.txt`. Batch 1 (A4 + A1/A3/A2 core): **191 tests, 190 passed**
(1 disclosed baseline). Batch 2 (watcher/health/connector/manifest/migration): **176 tests, 175 passed** (1
disclosed baseline). A4 focused suite: **26/26 green**.

### Disclosed pre-existing baseline failures (NOT introduced by A4, never absorbed into prove-red)
- `test_source_index_generation_hardening::test_v122_fresh_and_incremental_migration` — `assert 125 == 123`.
- `test_source_index_metadata_first_bootstrap::test_v119_migration_idempotent_and_additive` — `assert 125 == 123`.

Both hardcode `LATEST_SCHEMA_VERSION == 123` and were already red at the parent (V124: `124 == 123`). They are
stale version assertions unrelated to quarantine behavior.

## No-remote-write confirmation
Quarantine mutation exists **only** as local operator CLI commands (`cli/source_watch.py`) requiring
`--confirm`. There is no `@mcp.tool()` for quarantine, no gateway allowlist entry, and no name containing
"quarantine" in `ALL_ASSISTANT_TOOLS`/`ALL_PA_TOOLS` — asserted by `test_no_remote_quarantine_write_tool_exposed`.
