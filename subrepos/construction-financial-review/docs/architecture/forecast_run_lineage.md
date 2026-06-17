# Full-Fresh-Run Lineage State (analysis/crosswalk chain)

`common/run_lineage.py` makes a full fresh Tropical run carry its fresh upstream package lineage
through the **core analysis/crosswalk chain** automatically — with no manual stamp arguments. It
complements the earlier `--context-stamp` pinning of the *forecast* stages (see
`forecast_staffing_basis.md` §2); this layer fixes the *analysis* stages, which previously hardcoded
stale `20260614` package paths at module level.

## Problem

`run-analysis` / `run-mapping-workpaper` / `run-crosswalk-v2` are self-contained scripts that hardcoded:

```python
CTX = ROOT / "forecast_context_package_tropical_20260614_084510"
ANL = ROOT / "forecast_analysis_package_tropical_20260614_095847"
WP  = ROOT / "mapping_discrepancy_workpaper_tropical_20260614_105720"
```

So after `run-context` generated a fresh context, the analysis chain still consumed the stale packages.
The owner-SOV scope crosswalk (`owner_sov_scope_crosswalk_tropical_authoritative_20260614_final`) is a
hand-curated authoritative static input and is intentionally left untouched.

## Run lineage state

A full fresh run mints a **run-specific** state file and exports its path:

```
.cfr_run_state/full_fresh_<project>_<run_id>.json   (gitignored runtime state)
CFR_RUN_LINEAGE_STATE=<that file>
```

```json
{ "project_key": "tropical", "run_started_at_utc": "...", "run_id": "20260617_080320",
  "data_root": ".../2026-June",
  "packages": { "context": {"path": "...", "stamp": "..."}, "analysis": {...},
                "mapping_workpaper": {...}, "crosswalk_v2": {...} } }
```

A fresh `run_id` per `lineage-init` means a stale prior failed run never becomes active by accident.

## Resolution (runtime, never at import)

Each analysis script resolves its upstream packages inside `resolve_inputs()` called by `main()` —
**module import does no filesystem work and never raises** (`ROOT`/`INPUT`/`CTX`/`ANL`/`WP` are `None`
until `main()` runs). `run_lineage.resolve_upstream(ptype, ...)` precedence:

1. **explicit override** stamp (`CFR_CONTEXT_STAMP` / `CFR_ANALYSIS_STAMP` /
   `CFR_MAPPING_WORKPAPER_STAMP`, from debug-only `--*-stamp` flags) → exact package, fail closed if missing;
2. **active run state** (`CFR_RUN_LINEAGE_STATE`) → the recorded package; a missing required upstream
   **fails closed** — never falls back to latest-glob, config names, or hardcoded paths;
3. **latest-glob** only when no run state is active (backwards-compatible standalone use).

`analysis` excludes the `crosswalk_v2` variant of the shared `forecast_analysis_package_<p>_*` prefix.

## CLI + runner

- `lineage-init` mints the state, prints its path; `lineage-record --type <ptype>` validates the newest
  package of that type and records it (must exist, match the prefix, have a `validation_report.json`, sit
  under the run data root, and carry a stamp `>=` the run_id — rejecting pre-run/stale packages);
  `lineage-show [--field context_stamp]` prints the state.
- `cmd_run_generator` forwards `CFR_RUN_LINEAGE_STATE` (inherited) and any debug stamp overrides to the
  generator subprocess.
- `scripts/run_full_fresh_tropical_forecast.sh`: `lineage-init` → `run-context` → record → `run-analysis`
  → record → `run-mapping-workpaper` → record → `run-crosswalk-v2` → record → `lineage-show`; downstream
  forecast stages pin `--context-stamp` derived from the state. **One command, no manual stamps.**

## Disclosure + gates

Each analysis package's `input_inventory.json` + `validation_report.json` record the consumed upstream
packages (path/stamp) and `lineage_source` (`full_fresh_run_state` | `explicit_override` | `latest_glob`),
plus a fail-closed gate folded into the package's `passed`:
`analysis_context_lineage_consistent`, `mapping_workpaper_context_analysis_lineage_consistent`,
`crosswalk_v2_context_analysis_workpaper_lineage_consistent`. "Consistent" = under an active run state,
every consumed upstream was resolved from the state (standalone latest-glob runs are not-applicable/pass).
