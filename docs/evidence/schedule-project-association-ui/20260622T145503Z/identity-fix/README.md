# Evidence — Schedule Project Picker Identity Fix (PR #93)

**Date stamp:** 20260622T161500Z
**Branch:** `feature/schedule-project-association-ui`

## What changed

- Replaced `MAX(display_name)` aggregation in `schedule_project_catalog.py` with deterministic
  canonical row resolution (`is_current` → newest `updated_utc`).
- Exposed `identity_warning`, `project_identity_label`, and full identity diagnostics on
  `/api/schedules/projects`.
- Updated `ScheduleProjectPicker` labels to always lead with `project_key`; append `⚠` when
  identity warnings are present.

## Live DB diagnostic summary

- 6 `project_key` values in `procore_ep_projects`, each with **7 rows** and **7 distinct**
  display_name/project_number values (projection contamination).
- All 7 rows per key are `is_current = 1`.
- 7 display_name + project_number pairs each map to 6 distinct `project_key` values.

See `live_db_identity_diagnostic.txt`.

## Merge gate

Picker options are no longer indistinguishable: every option label starts with the immutable
`project_key`. Identity warnings surface projection defects without hiding canonical keys.

**Out of scope:** fixing underlying Procore projection replay contamination.

## Proof files

- `api_payload_before.json` — broken MAX()-based label shape
- `api_payload_after.json` — live DB payload after fix
- `option_labels_after.txt` — distinct key-first option labels
- `backend_tests.txt` — association + full schedule suite
- `frontend_proof.txt` — vitest + `npm run build`