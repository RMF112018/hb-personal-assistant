# P3 — DB-native model input accessors (evidence)

**Phase:** P3 (gap #3, "high") · **Stamp:** 20260623T193155Z · **Branch:** `feature/forecast-db-native-inputs-p3` off `origin/main@398c6140`

## What shipped

Behind the new default-off flag `HB_FORECAST_DB_BACKED_INPUTS_ENABLED`, `forecast_run_service.start_run`
now routes a run through the existing CFR controlled workflow in `db` mode — sourcing the three
covered source domains (`budget_details`, `cost_entries`, `monthly_actuals`) from a **non-live** v59
DB read-only — instead of the source JSONL package. The file package remains the default and the
fallback. No schema change, no new DB-read adapter, no live-DB write.

- `forecast_runtime_config.py` — new flag (ENV const + `DEFAULT_CONFIG` key + `resolve_db_backed_inputs_enabled` + surfaced in `build_runtime_status` + `save_runtime_config` handling), mirroring the existing 4-flag trio pattern.
- `forecast_run_service.py` — `start_run` resolves the flag locally (lazy import → no circular dep), selects `mode="db"` + a resolved non-live `db_path`, and **fails closed before the workflow** when the flag is on but the db_path is the live/default DB or unconfigured. `_summarize_report` now reports `no_live_writes` from `work_root_outside_live_root` (holds for both modes). `record["mode"]` branched at both sites.
- `forecast_run_dto.py` — corrected the stale `no_live_writes` comment.

## Acceptance — how it is proven

The DB-read **machinery** (file-vs-DB package parity) is proven independently and is green here
(`machinery_parity.txt`); P3 adds the **run-service routing + flag + fail-closed** logic, proven by
7 green tests (`p3_tests.txt`) and the `routing_proof.json` capture:

| Scenario | Result |
|---|---|
| flag OFF (default) | `mode="file"`, `db_path=None`, succeeded, `no_live_writes=true` |
| flag OFF + ambient `HB_FORECAST_DB_PATH` | still `mode="file"` (ambient db env ignored) |
| flag ON + non-live db_path | `mode="db"`, db_path threaded, succeeded, `no_live_writes=true` |
| flag ON + **live/default** db_path | **failed, fail-closed, workflow never called** |
| flag ON + unconfigured db_path | failed, fail-closed, workflow never called |

`routing_proof.json` is a real `start_run` capture (workflow spied to isolate routing; no live DB,
no subprocess). `resolve_db_path()` defaults to the live DB, so a flag-on run with no explicit
non-live db_path is refused — a run NEVER silently reads the live DB.

## Honest scope note (not dressed up)

A full heavy **end-to-end** db-mode run (Phase 6 context → Phase 7 analysis subprocess → Phase 8
chain) is **not runnable in this environment**: the CFR analysis subprocess fails with
`ImportError: attempted relative import with no known parent package` because
`construction_financial_review` is not installed in the venv. This is the pre-existing **Group D /
known-red** condition documented for **P10** ("durable env fix"), reproducible on clean
`origin/main` — it is **not** introduced by P3. P3's acceptance therefore rests on the green
machinery parity (Phase 6) + the run-service routing/flag/fail-closed proofs above, not on a heavy
E2E that the environment cannot currently execute.

Also pre-existing on clean `origin/main` (P10's remit, not touched here):
`test_forecast_context_runner_phase6.py::test_unsupported_project_refused` (P4-era message
straggler: asserts "unsupported project_key" vs actual "...is not eligible; allowed: [...]").

## Files

- `routing_proof.json` — real `start_run` routing capture (file / db / fail-closed).
- `p3_tests.txt` — 7 P3 routing/flag/fail-closed tests (all PASSED).
- `machinery_parity.txt` — Phase 6 file-vs-db package parity + db-backed run (PASSED).
