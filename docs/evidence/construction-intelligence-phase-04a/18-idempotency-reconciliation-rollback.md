# Phase 04A — Prompt 11: Idempotency, reconciliation, and rollback

## Objective

Prove the Phase 04A live apply pipeline is (1) idempotent under replay,
(2) count-reconciled between sync-run receipts and persisted
`procore_live_records` rows, and (3) rollback-capable by receipt id
(`sync_run_id`) and by WAL-safe SQLite backup restore. No live Procore
call, no schema change, no new CLI surface — one repository function and
one aggregated proof test.

## Source

- **Repository function** (new):
  `src/hb_assistant/store/procore_repositories.py::delete_procore_live_records_by_sync_run`.
  Keyword-only args, `dry_run=True` by default, returns
  `{sync_run_id, would_delete | deleted, dry_run}`. Preserves the
  matching `procore_live_sync_runs` audit row.
- **Schema invariants** (existing, reused):
  - V6 `procore_live_records.last_sync_run_id` → groups rows by the run
    that last touched them.
  - V6 `procore_live_records` PK
    `(project_key, endpoint_id, parent_procore_id, procore_record_id)` →
    upsert is by-PK; replay is structurally update-only.
  - V6 `procore_live_sync_runs.{request_count, retrieved_count,
    normalized_count, sqlite_upserted_count}` → the receipt-side
    counts.
  - V6 CHECK constraints `raw_body_persisted = 0` and
    `redaction_applied = 1` → unchanged, still active.
- **Tests** (new):
  `tests/test_procore_live_apply_idempotency_reconciliation_rollback_proof.py`.
- **Existing per-family idempotency tests** (reused as supporting
  evidence): `test_procore_rfi_sqlite_idempotency.py`,
  `test_procore_observation_sqlite_idempotency.py`,
  `test_procore_daily_log_sqlite_idempotency.py`,
  `test_procore_repositories_v6.py::test_upsert_inserts_then_updates`.
- **Documentation**: architecture addendum in
  `docs/architecture/14-procore-live-sync-phase-04a.md`; rollback
  recipes in `docs/operations/procore-operator-runbook.md`.

## Idempotency proof

`test_second_apply_produces_only_updates_zero_new_inserts` pins the
strongest invariant: when the same payloads are replayed under a new
`sync_run_id`, every `upsert_procore_live_record` call returns
`"updated"` (not `"inserted"`), `count_procore_live_records` returns the
same value as before the replay, and every persisted row's
`last_sync_run_id` advances to the new run id.

Backed by the per-family pre-existing tests:

- `test_procore_rfi_sqlite_idempotency.py::test_rfi_apply_is_idempotent_on_second_run`
- `test_procore_observation_sqlite_idempotency.py::test_observation_apply_is_idempotent_on_second_run`
- `test_procore_daily_log_sqlite_idempotency.py::test_daily_log_apply_is_idempotent_on_second_run`

And by `test_procore_repositories_v6.py::test_upsert_inserts_then_updates`
at the lowest layer (the upsert primitive).

## Reconciliation proof

`test_first_apply_receipt_counts_reconcile_with_sqlite_row_count`
pins the receipt-↔-SQLite reconciliation in the single-run case:

```
get_sync_run(sync_run_id)["sqlite_upserted_count"]
  == count_procore_live_records(project_key, endpoint_id)
  == normalized_count
  == retrieved_count
```

`test_count_reconciliation_by_sync_run_id` extends this to the
multi-run case using the canonical grouping SQL:

```sql
SELECT COUNT(*) FROM procore_live_records WHERE last_sync_run_id = ?
```

The test seeds two disjoint runs (A → 3 rows, B → 2 rows) and asserts
each group's count matches its own receipt-side `sqlite_upserted_count`,
plus the total equals 5.

Sample receipt-side fields the proof checks (synthetic, from the test):

```json
{
  "sync_run_id": "run-recon-1",
  "status": "success",
  "state": "success",
  "request_count": 1,
  "retrieved_count": 5,
  "normalized_count": 5,
  "sqlite_upserted_count": 5,
  "raw_body_persisted": 0,
  "redaction_applied": 1,
  "no_live_call_performed": 0
}
```

## Rollback recipes

### By receipt id (sync_run_id)

`test_delete_by_sync_run_id_rolls_back_only_targeted_rows` exercises the
new repository function end-to-end:

```python
from hb_assistant.store.procore_repositories import (
    delete_procore_live_records_by_sync_run,
)

# Dry-run preview (default; mutates nothing).
delete_procore_live_records_by_sync_run(sync_run_id="run-rollback-a", dry_run=True)
# -> {"sync_run_id": "run-rollback-a", "would_delete": 3, "dry_run": True}

# Apply the rollback.
delete_procore_live_records_by_sync_run(sync_run_id="run-rollback-a", dry_run=False)
# -> {"sync_run_id": "run-rollback-a", "deleted": 3, "dry_run": False}

# Idempotent — the same call again finds zero rows.
delete_procore_live_records_by_sync_run(sync_run_id="run-rollback-a", dry_run=False)
# -> {"sync_run_id": "run-rollback-a", "deleted": 0, "dry_run": False}
```

The matching `procore_live_sync_runs` row for `run-rollback-a` is
intentionally preserved as an audit trail; the rolled-back run remains
discoverable via `get_sync_run(sync_run_id)`. The disjoint sync run
`run-rollback-b` and its 2 rows are untouched.

### By backup restore

`test_backup_restore_round_trip_restores_pre_apply_state` pins the
WAL-safe primitive — `sqlite3.Connection.backup()`. The test snapshots
the migrated DB, performs an apply that writes 4 rows + 1 sync-run row,
restores the snapshot, and asserts both the records table and the
sync-runs table are back to zero.

Operator-side equivalent (documented in
`docs/operations/procore-operator-runbook.md`):

```bash
DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
BACKUP="$DB.bak.$(date +%Y%m%d%H%M%S)"

sqlite3 "$DB" ".backup '$BACKUP'"   # snapshot before the apply
# ...run an apply that you may want to roll back...
sqlite3 "$DB" ".restore '$BACKUP'"  # reverses every change since the snapshot
```

`shutil.copyfile` is NOT used as the rollback primitive — it is not
WAL-safe and can miss in-flight pages. The `sqlite3 .backup` /
`Connection.backup()` API copies the database in a consistent way
regardless of WAL state.

## No-raw-body / no-secret attestation (unchanged from Prompt 10)

The Prompt 10 schema-level invariants are not regressed by this slice:

- V6 CHECK `raw_body_persisted = 0` on `procore_live_records` and
  `procore_live_sync_runs` — still active; exercised by
  `tests/test_procore_sensitive_routing_proof_corpus.py::test_v6_check_constraint_rejects_raw_body_persisted_on_records`.
- V6 CHECK `redaction_applied = 1` on `procore_live_sync_runs` — still
  active; exercised by
  `tests/test_procore_sensitive_routing_proof_corpus.py::test_v6_check_constraint_rejects_redaction_applied_zero_on_runs`.
- The new `delete_procore_live_records_by_sync_run` cannot write rows
  (DELETE-only); the only mutation is row removal.

## Verification

```
$ python -m pytest -q tests/test_procore_live_apply_idempotency_reconciliation_rollback_proof.py
5 passed

$ python -m pytest -q --no-header
959 passed, 2 skipped in 20.22s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 182 source files

$ python -m compileall -q src tests
(clean — no output)

$ hb-assistant procore validate --json
27/28   # 28th (mapping_consistent) is the pre-existing pending-projects
        # failure from procore_projects.seed.yaml — unchanged from prior commits.

$ hb-assistant procore tools list --json     # canonical envelope returned
$ hb-assistant procore mapping validate --json  # canonical envelope returned
```

## Stop conditions honored

- No live Procore call performed (Live API Policy explicit; all proofs
  use a tmp SQLite + synthetic payloads).
- No non-GET introduced (the rollback path is a local SQLite DELETE, not
  an HTTP call).
- No client secret, access token, or refresh token literal appears in
  any test payload, any evidence excerpt, or any rollback receipt.
- No raw body persisted (the new repository function cannot create
  rows; existing CHECK constraints stay active).
- The matching `procore_live_sync_runs` row is preserved across receipt-
  id rollback so the audit trail remains discoverable.

## Related references

- Architecture addendum: `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Idempotency, reconciliation, and rollback (Prompt 11)").
- Operator runbook: `docs/operations/procore-operator-runbook.md`
  (section "Rollback (Prompt 11)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/17-sensitive-routing-and-redaction-proof.md`.
- Repository entry-point added in this slice:
  `src/hb_assistant/store/procore_repositories.py::delete_procore_live_records_by_sync_run`.
