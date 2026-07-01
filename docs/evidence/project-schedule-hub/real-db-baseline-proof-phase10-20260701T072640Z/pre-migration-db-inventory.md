# Pre-Migration DB Inventory

**STAMP:** 20260701T072640Z  
**Proof type:** real local DB (read-only)

## Schema version

| Source | Value |
|--------|-------|
| `MAX(schema_migrations.version)` | **95** (`v95_cpm_import_observability`) |
| `PRAGMA user_version` | 0 (informational) |

## Named baseline slots table

`project_schedule_named_baseline_slots` — **NOT PRESENT** (pre-v96)

Legacy baseline tables present: `schedule_baseline_*`, `project_schedule_baseline_selections`

## Projects with committed imports

| project_key | committed_imports |
|-------------|-------------------|
| tropical | 10 |
| pga-modern-garage | 1 |
| caretta | 1 |

## Tropical schedule versions (committed)

| import_id | schedule_version_key | source | created_at |
|-----------|---------------------|--------|------------|
| b5b87f9190ce | tropical\|TWNU07\|2025-08-07T08:00:00 | TWNU07.xml | 2026-06-22 |
| 508129b6843b | tropical\|TWNU16\|2026-01-29T08:00:00 | TWNU16.xml | 2026-06-22 |
| 7898325a1aca | tropical\|TWNU18\|2026-05-26T08:00:00 | TWNU18.xml | 2026-06-22 |
| a2778cdf208b | tropical\|24836\|2026-06-23 08:00 | TWNU19.xer | 2026-06-24 |
| d99fec1afb5a | tropical\|TWNU19\|2026-06-23T08:00:00 | TWNU19.xml | 2026-06-26 |
| 55b57c7ea49f | tropical\|815\|2025-08-07 08:00 | TWNU07.zip | 2026-06-28 |
| 0f4bc830b623 | tropical\|851\|2025-11-28 08:00 | TWNU14.zip | 2026-06-28 |
| 1aba677fcf98 | tropical\|957\|2026-01-29 08:00 | TWNU16.zip | 2026-06-28 |
| 9a20e3de7c74 | tropical\|1069\|2026-05-26 08:00 | TWNU18.zip | 2026-06-28 |
| beeb6dea0360 | tropical\|1071\|2026-06-23 08:00 | TWNU19.zip | 2026-06-28 |

## Candidate project

**tropical** — 10 committed imports; sufficient for current + multiple prior baselines after API eligibility filtering.
