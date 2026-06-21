# Live-Data Generation Validation — All Four DB-Config-Backed Generators

**Date:** 2026-06-21 · **Stamp:** 20260621T131846Z · **Branch base:** `origin/main` @ PR #68 merge

## What this proves

PR #68 wired DB-config-backed forecast generation for all four generator kinds. This bundle is
the first **real, end-to-end** validation: each kind was generated **twice** — once via the CFR
CLI and once via the operator UI route — consuming the **live config snapshot** held in the live
app DB (opened read-only), against the **real tropical data root**, into **isolated work roots**.
The live DB is proven **byte-exact unchanged** before and after all eight runs.

This is a validation/evidence exercise. **No production source was changed.**

## Environment

- **Live config DB:** `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
  — schema **v61**, opened `mode=ro` only.
- **Live config snapshot (default selection):** `tropical-phase16-live-config-20260619T085305Z`,
  id `c3b4a67d…415b698`, **194 items**, snapshot_sha256 `d42f2db6…613847a`.
- **Data root (== project `default_data_root` == LIVE_ROOT):**
  `…/SynologyDrive-BFmacSync/…/Forecasts/Data/2026-June` — read-only input; all required
  predecessor packages present (see `data_root_inventory.txt`). `frequency_enabled = True`.
- **Work roots:** CLI → `/tmp/fdcg_proof/<kind>`; UI → `/tmp/fdcg_ui_runs/<run_id>` — both outside
  the live root / data root.
- **UI path:** fresh analytics app on `127.0.0.1:8011` with `HB_FORECAST_DB_CONFIG_RUN_ENABLED=1`,
  `HB_FORECAST_DATA_ROOT`, `HB_FORECAST_RUNS_ROOT` set via env (no persisted settings write); the
  pre-existing server on :8000 was untouched. POSTs used header `X-HB-UI-Role: operator`.

## Results

### CLI runs (`forecast-db-config-backed-generate`)

| Kind | rc | status | consumed_config_domains | fidelity | validation | live_db_unchanged |
|------|----|--------|--------------------------|----------|------------|-------------------|
| comprehensive  | 0 | generated | forecast_controls, forecast_model_controls, project | pass | pass | ✅ |
| model_controls | 0 | generated | forecast_model_controls | pass | pass | ✅ |
| monthly        | 0 | generated | forecast_controls, forecast_model_controls, forecast_staffing, project | pass | pass | ✅ |
| probability    | 0 | generated | owner_sov_crosswalk, project | pass | pass | ✅ |

Every CLI report additionally asserts: `config_snapshot_consumed=true`, `snapshot_item_count=194`,
`db_schema_version=61`, `reads_materialized_config=true`, `safety.live_db_written=false`,
`safety.live_db_opened_read_only=true`, `safety.live_db_migrated=false`,
`safety.live_db_imported=false`, `safety.source_config_mutated=false`, and the per-kind
`<generator>_run=true`. `consumed_config_domains` matches the expected set per kind exactly.
Probability used the deterministic defaults `runs=10000, seed=20260614`.

### UI service runs (`POST /api/forecast/runs/db-config`, operator role)

| Kind | http | status | consumed | live_db_unchanged | no_live_writes | redaction_leaks |
|------|------|--------|----------|-------------------|----------------|-----------------|
| comprehensive  | 200 | generated | true | true | true | `[]` |
| model_controls | 200 | generated | true | true | true | `[]` |
| monthly        | 200 | generated | true | true | true | `[]` |
| probability    | 200 | generated | true | true | true | `[]` |

`GET /api/forecast/runs/db-config` lists all four runs, all `generated`, `find_redaction_leaks=[]`.

### Live-DB mutation proof (top-level, external to the runs' self-reports)

`baseline_live_db.json` vs `final_live_db.json` after all eight runs:

- **main db** size + mtime_ns + **sha256** identical (`99614d4c…77645a`).
- `PRAGMA data_version` unchanged (`2 → 2`) — no committed write occurred.
- `-wal` and `-shm` also byte-identical — the DB stayed fully quiescent throughout.

**Verdict: LIVE DB CANONICAL STATE UNCHANGED.**

## Files

- `baseline_live_db.json` / `final_live_db.json` — live-DB fingerprints (size/mtime_ns/sha256 +
  data_version) before/after.
- `data_root_inventory.txt` — data root, frequency flag, required-predecessor presence, per-kind globs.
- `snapshot_selection.txt` / `db_schema_version.txt` — selected live snapshot + schema v61.
- `cli_<kind>_report.json` ×4 — full (path-saturated, audit) CLI reports.
- `ui_<kind>_summary.json` ×4 + `ui_list_runs.json` — redacted operator-path summaries.
- `package_manifests.txt` — generated package file names + sha256 (full packages not committed).

## Notes / discipline

- Raw CLI reports embed absolute paths — acceptable in an audit bundle. The redaction gate
  (`find_redaction_leaks == []`) applies to the **UI payloads**, captured separately and asserted clean.
- All four kinds generated cleanly; **no rc-3 refusals** occurred (all predecessor packages present
  and the live DB was quiescent). Had any predecessor been missing or the DB non-quiescent, the run
  would have refused (rc 3) and that would be recorded here as a finding rather than papered over.
