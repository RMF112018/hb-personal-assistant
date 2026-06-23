# Forecast Run-Output Live-Write Runbook (Operator)

Populate the **tropical** forecast run-graph — the v58 anchor `forecast_runs` + the v63 run-output
tables + the v66 decision-support tables — into the **managed live DB** so the read-model API
(`/api/forecast/db/*`) and the forecasting UI panel render persisted data instead of "no persisted
forecast outputs yet".

This drives the existing, self-gating CLI `live-db-run-output-project`
(`workflows/live_db_run_output_projection.py`). **It does not introduce new behavior** — the command
performs its own read-only pre-audit, byte-exact backup, single atomic transaction, and post-write
certification. This is an **authorized operator step**: it writes the live DB and must never run in
tests or CI.

> Scope: project_key **tropical** only. The write touches **only** `project_key='tropical'` rows in
> the run-graph tables; no other project and no other table is modified.

## What it writes / does not

- **Writes (replaces tropical rows in):** `forecast_runs` (anchor) + 9 v63 tables
  (`forecast_outputs`, `forecast_output_budget_codes`, `_risks`, `_monthly`, `_probability`,
  `_changes`, `_staffing`, `_commitment_exposure`, `_schedule_phasing`) + 6 v66 tables
  (`forecast_project_maturity_snapshots`, `forecast_data_availability_profiles`,
  `forecast_confidence_scorecards`, `forecast_confidence_factors`, `forecast_method_eligibility`,
  `forecast_model_selection_decisions`).
- **Does not:** migrate the schema, touch any non-tropical row, or write the v59 source-domain
  (v59 must already be present — see preconditions).

## Exit codes

| rc | meaning | operator action |
|----|---------|-----------------|
| **0** | **certified** — `decision = live_db_run_output_certified`; live rows match a fresh reprojection (raw_json digests) | done; verify (step 4), retain evidence |
| **1** | post-write certification **failed** (`not_ready`) — the backup was recorded before the write | investigate; restore from backup (step 5) |
| **3** | **controlled refusal** — a precondition failed; **nothing was written** | fix the input named in `reason`; re-run |

The command prints a single JSON report to stdout. On refusal it prints `{"status":"refused","reason":...}`.

## Preconditions / evidence checklist

Confirm all of these before running (the command also enforces each and refuses with rc 3 if not):

- [ ] **Live DB schema ≥ 66** (`REQUIRED_SCHEMA_VERSION` — v63 + v66 must be present).
- [ ] **Run-graph tables present** in the live DB (all 16 `WRITE_TABLES`).
- [ ] **Tropical v59 source-domain rows present** in the live DB — the v66 derivation reads v59. If
      empty, run the Phase-14 source-domain write (`live-db-source-domain-project`) **first**.
- [ ] **Packages resolved as explicit, non-live paths** (never under the live Synology root):
      - required: `--analysis-package` (a `forecast_analysis_package_…` dir),
        `--source-package` (must be named exactly `twn_cost_forecast_json_package`);
      - optional but recommended for full coverage: `--monthly-package`, `--probability-package`,
        `--comprehensive-package`, `--staffing-package`, `--accuracy-package`,
        `--context-package` (the context package's `canonical/budget_codes.jsonl` drives
        commitment-exposure).
- [ ] **`--work-root`** is a writable path **not** under the live Synology root (holds the backup +
      temp DBs).
- [ ] **`--context-stamp`** and **`--run-id`** supplied **explicitly** (no glob/auto-resolve). If a
      run-lineage state is active, read them from `run_lineage.active_state()`
      (`.get("run_id")`, `.get("packages",{}).get("context",{}).get("stamp")`); otherwise pin them.
- [ ] **Live-DB WAL is 0 bytes** (a non-zero `-wal` blocks the backup — checkpoint/close any process
      holding the DB open first).
- [ ] **`<work_root>/backups/` has no colliding file** — the backup refuses to overwrite
      `hb-personal-assistant.before-phase3-run-output.sqlite`. Use a fresh `--work-root` per run.

Inputs are validated read-only by `common/package_resolution.py::resolve_explicit_package`; the live
DB path resolves via `config/path_policy.py::PathPolicy().get_db_path()` and is guarded by
`construction/forecast/source_domain_engine.py::is_live_db_path` (this command **only** accepts the
live/default DB — a non-live path is refused).

## Operator steps

All commands run from the repo root with the CFR package importable:

```
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"
CFR="python -m construction_financial_review.cli"
```

### 1. Read-only pre-audit

Confirm the live DB is in the expected shape (schema, required tables, migration history) before
touching it. Read-only; no write.

```
$CFR live-db-provenance-audit --project tropical --work-root /tmp/forecast-live-<date>
```

Independently confirm tropical v59 is populated (the write needs it):

```
sqlite3 "$(python -c 'from hb_assistant.config.path_policy import PathPolicy; print(PathPolicy().get_db_path())')" \
  "SELECT COUNT(*) FROM forecast_budget_details WHERE project_key='tropical';"
```

A `0` here means run Phase 14 (`live-db-source-domain-project`) first.

### 2. (Optional) Dry projection to set the `--expect-*` gate

`--expect-outputs` / `--expect-budget-codes` are an optional pre-write row-count gate. The planner is
pure (reads packages only, **opens no database**), so it is safe to compute the counts up front:

```
python -c '
from pathlib import Path
from hb_assistant.construction.forecast import output_projection_engine as e
p = e.plan_run_output_projection(
    analysis_package=Path("<ANALYSIS_PKG>"), project_key="tropical", run_id="<RUN_ID>",
    monthly_package=Path("<MONTHLY_PKG>"), context_package=Path("<CONTEXT_PKG>"))
print(p["counts"])'
```

Record `counts["outputs"]` (normally `1`) and `counts["budget_codes"]` (the tropical canonical
universe, normally `127`) → use them as `--expect-outputs` / `--expect-budget-codes` in step 3. If
you skip this, omit those flags; the built-in backup + post-write certification still protect you.

### 3. Gated LIVE write

Run against the **managed live DB** (omit `--live-db-path` to use the default; this command refuses
any non-live path, so there is no copy/rehearsal target — the protections below stand in for it).

```
$CFR live-db-run-output-project \
  --project tropical \
  --analysis-package <ANALYSIS_PKG> \
  --source-package   <…/twn_cost_forecast_json_package> \
  --work-root        /tmp/forecast-live-<date> \
  --context-stamp    <CONTEXT_STAMP> \
  --run-id           <RUN_ID> \
  --monthly-package <…> --probability-package <…> --comprehensive-package <…> \
  --staffing-package <…> --accuracy-package <…> --context-package <…> \
  --expect-outputs 1 --expect-budget-codes 127 \
  --allow-replace-existing \
  --allow-live-db-write
```

- `--allow-live-db-write` is **required** — without it the command refuses (rc 3) and writes nothing.
- `--allow-replace-existing` is required **only** if the live DB already holds tropical run-graph
  rows (a re-run); omit it for the first population.
- Expected result: **rc 0**, `decision: "live_db_run_output_certified"`. Record from the JSON report:
  the `backup` block (`path`, `size_bytes`, `sha256`, `schema_version`), the
  `write_result.by_table` counts, and the `post_write_certification` block.

What the command does internally (your safety net — no copy rehearsal needed):
read-only pre-audit → fresh **non-live temp** projection → optional `--expect-*` gate (refuses
**before** any backup/write on mismatch) → **byte-exact backup** to
`<work_root>/backups/hb-personal-assistant.before-phase3-run-output.sqlite` → one
`BEGIN IMMEDIATE` transaction that deletes+inserts only tropical rows (rolls back on any error) →
post-write certification by re-projecting a fresh temp and comparing live `raw_json` digests.

### 4. Verify

- The command's own **post-write certification** at rc 0 (top-level
  `decision = live_db_run_output_certified`, and `post_write_certification.decision = certified_match`)
  is the authoritative proof the live run-graph equals a fresh reprojection. This is the primary
  verification.
- Re-run `live-db-provenance-audit` (step 1) for an independent post-write schema/inventory snapshot.
- Confirm the data is reachable through the read-model (serve the analytics app against the managed
  live DB — see `docs/runbooks/forecast-ui-launch-bootstrap.md` — then):

  ```
  curl -s localhost:8000/api/forecast/db/projects/tropical/outputs | jq '.outputs[].output_id'
  curl -s localhost:8000/api/forecast/db/outputs/<output_id> | jq 'keys'
  curl -s localhost:8000/api/forecast/db/outputs/<output_id>/decision-support | jq '.maturity, (.confidence_scorecards|length)'
  ```

  Then open the forecasting UI (Run Center) — the run-output + decision-support panel should now
  render the persisted output instead of the empty state.

### 5. Rollback

The write is atomic, so an **rc 3 refusal leaves the live DB untouched** (nothing to roll back). On
**rc 1** (post-write certification failed) or any doubt, restore the byte-exact backup:

```
# stop any process serving the live DB first
cp "<work_root>/backups/hb-personal-assistant.before-phase3-run-output.sqlite" \
   "$(python -c 'from hb_assistant.config.path_policy import PathPolicy; print(PathPolicy().get_db_path())')"
```

Confirm the restore with `live-db-provenance-audit`. Then investigate the captured report before
re-running.

## Inputs reference

| flag | required | how to resolve |
|------|----------|----------------|
| `--project` | yes | `tropical` (only supported value) |
| `--analysis-package` | yes | explicit `forecast_analysis_package_…` dir; validated by `package_resolution.resolve_explicit_package` (refuses live-root paths) |
| `--source-package` | yes | explicit dir named exactly `twn_cost_forecast_json_package` |
| `--work-root` | yes | fresh writable dir **not** under the live Synology root |
| `--context-stamp` | yes | `run_lineage.active_state()…["packages"]["context"]["stamp"]`, or pin explicitly |
| `--run-id` | yes | `run_lineage.active_state()["run_id"]`, or pin explicitly |
| `--live-db-path` | no | omit → `PathPolicy().get_db_path()` (managed default; only the live DB is accepted) |
| `--allow-live-db-write` | yes (to write) | explicit gate |
| `--allow-replace-existing` | only on re-run | permits replacing existing tropical run-graph rows |
| `--monthly/--probability/--comprehensive/--staffing/--accuracy/--context-package` | no | explicit downstream package dirs for full coverage |
| `--expect-outputs` / `--expect-budget-codes` | no | pre-write count gate; values from step 2 |

## Guardrails (re-statement)

- **Never** run in tests or CI. Authorized operator step only.
- **tropical-only**; the write replaces only `project_key='tropical'` rows.
- All inputs are **explicit, non-live paths**; stamps/run-id are explicit (no glob).
- **Backup precedes the write**; the transaction is **atomic**; the result is **certified**.
- A precondition failure is a safe **rc-3 refusal** — nothing is written.

## Evidence to retain

- The pre- and post-write `live-db-provenance-audit` JSON.
- The `live-db-run-output-project` JSON report: the `backup` block (path + `sha256` + size), the
  `write_result.by_table` counts, and the `post_write_certification` block (`decision = certified_match`).
- The dry-projection `counts` (step 2), if used as the `--expect-*` gate.
