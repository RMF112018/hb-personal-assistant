# Clean DB zero-record verdict

## Tropical project catalog
- **project_catalog_preserved:** yes (`procore_ep_projects` count for `tropical` = 1)

## Core schedule import path (tropical)
| Table | Row count |
|-------|-----------|
| schedule_identities | 0 |
| schedule_file_imports | 0 |
| schedule_cpm_runs | 0 |
| schedule_cpm_activity_results | 0 |
| project_schedule_baseline_selections | 0 |

## Gate 0.6 purge tool metric
- **remaining_tropical_schedule_records (purge script):** 931097 — **FAIL** per strict gate metric
- **Root cause:** `_remaining_schedule_count` sums all project-scoped rows (forecast, email, diffs, etc.), not schedule-domain only. Purge also left `schedule_version_diff_*` and global `schedule_baseline_*` rows without `project_key`.

## Supplemental copied-DB cleanup
- Applied manual DELETE on copied DB for tropical-linked diff/raw/procore_ep schedule rows.
- Global `schedule_baseline_*` tables (66k rows, no `project_key`) remain — orphan baseline cache, not tropical import state.

## Verdict
- **Tropical schedule import state zeroed:** yes (identities + imports + CPM = 0)
- **Safe to run fresh import validation:** yes on copied DB
- **Purge tooling gap:** logged to bug/gap log (P1)
