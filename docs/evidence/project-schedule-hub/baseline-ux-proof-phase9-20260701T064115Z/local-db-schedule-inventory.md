# Local DB Schedule Inventory

**Proof type:** real local DB (read-only)  
**Path:** `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`  
**Date:** 2026-07-01

## Projects with committed imports

| project_key | version_count |
|---|---|
| tropical | 10 |
| caretta | 1 |
| pga-modern-garage | 1 |

## tropical schedule versions (candidate for PM proof)

10 committed imports spanning 2025-08-07 through 2026-06-23 data dates — sufficient for current + multiple prior baselines.

## Named baseline slots

Table `project_schedule_named_baseline_slots` not present in this local DB schema (pre-v96 or unmigrated). Named baseline proof uses **fixture DB** for slot selection/API workflow; tropical real DB used for version inventory only.

## Recommended proof project

- **Fixture DB:** `tropical` (tests) — full named baseline workflow
- **Real DB:** `tropical` — confirms production-like version depth (10 imports)
