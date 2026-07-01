# Real DB Baseline Selection Proof

**STAMP:** 20260701T072640Z  
**Proof type:** real local DB + real API (live uvicorn :8000)

## Flow

1. `GET /api/projects/tropical/schedule/baselines` — all slots `missing` → `api-real-baselines-before.json`
2. `PUT /api/projects/tropical/schedule/baselines` with three selections → `api-real-baselines-put.json`
3. `GET` after PUT — all slots `selected` → `api-real-baselines-after.json`

## Selections applied

| Slot | schedule_version_key |
|------|---------------------|
| current_contract_baseline | `tropical\|815\|2025-08-07 08:00` |
| previous_progress_update_baseline | `tropical\|1069\|2026-05-26 08:00` |
| secondary_progress_update_baseline | `tropical\|851\|2025-11-28 08:00` |

## Verification

- All selected versions are prior to current `tropical\|1071\|2026-06-23 08:00`
- No duplicate keys across slots
- Rows persisted in `project_schedule_named_baseline_slots` (is_active=1)
