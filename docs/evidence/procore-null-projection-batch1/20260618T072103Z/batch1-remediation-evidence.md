# Procore Null Projection Batch 1 Evidence

## Scope

Batch 1 only:

- `procore_ep_punch_items.closed_at`
- `procore_ep_punch_items.closed_by`
- `procore_ep_prime_contracts.show_line_items_to_non_admins`

No Budget Detail projection, scheduled refresh, schema migration, live fetch, or production DB mutation was performed.

## Copied DB

- Source DB: production operator SQLite DB
- Audit copy: `local_audit_outputs/procore-null-projection-batch1-20260618T072103Z/batch1-copy.sqlite`
- Copy method: `sqlite3 ... ".backup '.../batch1-copy.sqlite'"`
- Integrity checks: `PRAGMA integrity_check` -> `ok`; `PRAGMA quick_check` -> `ok`

## Baseline Counts

| table | rows | target non-null counts |
| --- | ---: | --- |
| `procore_ep_punch_items` | 23 | `closed_at=0`, `closed_by=0` |
| `procore_ep_prime_contracts` | 5 | `show_line_items_to_non_admins=0` |
| `procore_ep_budget_detail_rows` | 2496 | nonzero baseline preserved |
| `procore_ep_budget_detail_row_cells` | 225131 | nonzero baseline preserved |

## Remediation Applied

Replay initially failed closed because current raw payloads contained newly observed supporting paths:

- `punch-items`: `closed_by.*` and assignment attachment item paths
- `prime-contracts`: top-level attachment item paths

The remediation was limited to allow-listing those observed supporting paths in `projection_registry.json` as sidecar/structural coverage. No target schema columns were added. No projection extraction code was changed.

## Replay Results On Copied DB

| endpoint | inspected raw rows | primary rows written | child rows written | degraded unknown paths | live calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| `prime-contracts` | 13 | 13 | 0 | 0 | 0 |
| `punch-items` | 36 | 36 | 119 | 0 | 0 |

## Post-Replay Counts

| table | rows | target non-null counts |
| --- | ---: | --- |
| `procore_ep_punch_items` | 36 | `closed_at=13`, `closed_by=13` |
| `procore_ep_prime_contracts` | 7 | `show_line_items_to_non_admins=1` |
| `procore_ep_budget_detail_rows` | 2496 | unchanged |
| `procore_ep_budget_detail_row_cells` | 225131 | unchanged |

## Guardrails

- `projection-schema-audit`: `ok=true`, `runtime_plan_schema_mismatches=0`
- `punch-items` projection audit after registry update: `ok=true`, `unknown_business_field_paths=0`
- `prime-contracts` projection audit after registry update: `ok=true`, `unknown_business_field_paths=0`
- Replay ran against copied DB only.
- `live_procore_calls=0`
- `external_writeback_performed=0`
- CLI receipts emitted counts and field names only, not raw payload values.

## Deferred

- Budget Detail convenience columns remain triage only.
- Broad `company_id` remains deferred.
- No schema deletion, guardrail backfill, threshold weakening, or suspected-defect suppression was performed.
