# Known Limitations & Risks — Phase 9A.1

## Scope (by design)
- **Backend + type only.** No UI rendering — Schedule Health does not yet *display* the
  `computed_cpm_health` envelope. The cockpit layout (9A.2) and CPM Intelligence panel (9A.3) are
  later stacked PRs. This PR makes the data available and typed.
- **No recompute, no schema migration, no source mutation, no capability-writer edit.**

## Carried caveats (must surface in the 9A.3 UI)
- `computed_critical_outside_longest_path`: in the real sample, 1312 activities are computed-critical
  while the longest path holds 45. The UI must present this caveat and must not flatten it into a
  single "critical path = N" claim.
- `graph_diagnostics` run status reads `not_implemented` (diagnostics-only scope) — surfaced
  verbatim in `run_chain`. The 9A.3 UI should render it as an informational/warning state, not a
  failure or blank.
- Real-sample float profile is dominated by **negative** total float (1308 of 1507; longest-path
  total float −296) — this schedule is behind plan. That is correct data, not a bug; the UI should
  frame negative-float counts as risk signals, not errors.

## Product constants / decisions
- `HIGH_TOTAL_FLOAT_DAYS = 44.0` (DCMA high-total-float convention) is a documented product
  constant, surfaced as `high_total_float_threshold_days`. If a different threshold is wanted, change
  the constant; it is not a derived value.

## Validation notes
- `api.py` carries **37 pre-existing ruff errors** (FastAPI `B008` arg defaults, import-org) on both
  `origin/main` and this branch — identical count, so this PR adds none. Out of scope to fix here.
- Backend validation runs with `HB_ASSISTANT_DB_PATH` unset (fixture DBs only); the 3.8 GB evidence
  DB is used only for the read-only `sample-health-response.json` capture.
- Worktree had no `.venv`/`node_modules`; backend ran on the main checkout's venv, frontend via a
  fresh `npm ci` in the worktree (lockfile unchanged).

## Runtime reminder (from the CPM evaluation)
`create_app()` without `db_path` leaves `app.state.db_path=None` → endpoints report unavailable.
Evidence/runtime launches must pass `create_app(db_path=...)` (or a future patch makes it honor
`HB_ASSISTANT_DB_PATH`). Unchanged by this PR; relevant when the cockpit is exercised live.
