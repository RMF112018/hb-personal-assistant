# Punch Items Contradiction Analysis

## Summary

- Evidence timestamp: `20260618T201500Z`
- Worktree: `procore-null-projection-batch1`
- Branch: `codex/procore-null-projection-batch1`
- Production apply: `no`
- Live Procore calls: `no`
- Scheduler / SourceRefreshOrchestrator / broad refresh: `no`
- Budget Detail refresh/reconciliation: `no`
- Procore writeback: `no`
- Raw payload values emitted: `no`

## Root Cause

The corrected raw source-path audit reported `0` high-confidence mapping candidates because it was counting unmapped registry candidates only. `procore_ep_punch_items.closed_at` and `procore_ep_punch_items.closed_by` were already registry-mapped and already partially populated in the current DB, so they correctly did not appear as new mapping candidates.

This was an audit explainability gap, not a punch-items projection defect.

## Prior Batch 1 Proof

Prior evidence path: `docs/evidence/procore-null-projection-batch1/20260618T072103Z/batch1-remediation-evidence.md`

| Field | Prior copied-DB baseline | Prior copied-DB after replay |
|---|---:|---:|
| `procore_ep_punch_items.closed_at` | 0 | 13 |
| `procore_ep_punch_items.closed_by` | 0 | 13 |
| `procore_ep_prime_contracts.show_line_items_to_non_admins` | 0 | 1 |

Batch 1 did not add target columns or projection extraction code. It allow-listed supporting paths so endpoint-specific replay could fail closed cleanly and write existing mapped columns.

## Current Strict Audit Finding

Source audit: `docs/evidence/procore-null-projection-corrective-mapping/20260618T193631Z/post-corrective-null-projection-audit.json`

| Field | Rows | Non-null | Null | Null rate | Current status |
|---|---:|---:|---:|---:|---|
| `procore_ep_punch_items.closed_at` | 36 | 13 | 23 | 0.638889 | partially populated, not suspected defect |
| `procore_ep_punch_items.closed_by` | 36 | 13 | 23 | 0.638889 | partially populated, not suspected defect |

## Registry And Source Paths

Endpoint key: `punch-items`

| Destination column | Registry path | Raw rows inspected | Path non-empty | Path present |
|---|---|---:|---:|---:|
| `closed_at` | `$.closed_at` | 36 | 13 | 36 |
| `closed_by` | `$.closed_by` | 36 | 13 | 36 |

Current raw landing coverage for `punch-items`: `36` `live_full_payload` rows.

## `closed_by` Semantics

`closed_by` text scalarization is intentional and tested for the current schema.

Repo truth:

- `procore_ep_punch_items` has `closed_by TEXT`.
- `procore_ep_punch_items` does not have `closed_by_id`, `closed_by_name`, or `closed_by_login` columns.
- The registry maps `$.closed_by` to the primary `closed_by` column and tracks `closed_by.*` paths as sidecar/coverage paths.
- The projection scalarizer collapses objects by representative keys, preferring name-like fields before ID.
- `tests/test_procore_endpoint_structured_projection_remediation.py` asserts a punch payload with object-valued `closed_by` writes the expected text scalar to `closed_by`.

## Explicit Field And Date Sweep Audit

Audit files:

- `punch-date-source-path-audit.json`
- `punch-date-source-path-audit.md`

| Metric | Count |
|---|---:|
| Fields audited | 637 |
| Explicit fields inspected | 2 |
| Date field sweep records | 229 |
| High-confidence mapping candidates | 0 |
| Raw payload values emitted | false |

Date sweep classifications:

| Classification | Count |
|---|---:|
| `already_populated` | 178 |
| `expected_optional_source_null` | 51 |
| `source_path_exists_not_mapped` | 0 |
| `mapped_source_present_projection_not_writing` | 0 |
| `source_absent_in_current_payloads` | 0 |
| `schema_artifact_candidate` | 0 |

The date sweep found no source-backed unmapped date fields requiring a mapping patch.

## Copied DB Proof

Copied DB path: `/tmp/procore-punch-contradiction-20260618T201500Z/hb-personal-assistant.sqlite`

| Check | Result |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA quick_check` | `ok` |

Baseline copied-DB counts:

| Table | Rows / counts |
|---|---:|
| `procore_ep_punch_items` rows | 36 |
| `procore_ep_punch_items.closed_at` non-null | 13 |
| `procore_ep_punch_items.closed_by` non-null | 13 |
| `procore_ep_budget_detail_rows` rows | 2,496 |
| `procore_ep_budget_detail_row_cells` rows | 225,131 |

Endpoint-limited copied-DB replay:

| Endpoint | Raw rows inspected | Primary rows written | Child rows written | Degraded unknown paths | Live calls | Writeback |
|---|---:|---:|---:|---:|---:|---:|
| `punch-items` | 36 | 36 | 119 | 0 | 0 | 0 |

After idempotent replay:

| Field | Before | After |
|---|---:|---:|
| `closed_at` non-null | 13 | 13 |
| `closed_by` non-null | 13 | 13 |

Controlled copied-DB reset proof:

| Field | After copied-DB reset | After endpoint replay |
|---|---:|---:|
| `closed_at` non-null | 0 | 13 |
| `closed_by` non-null | 0 | 13 |

Budget Detail row/cell counts remained unchanged and nonzero.

## Corrected Next Action

- No punch-items registry, projection, or schema fix is needed for `closed_at` or `closed_by`.
- Keep the explicit field and date sweep audit repair so future reports can explain already-mapped, already-populated fields separately from unmapped candidates.
- No date mapping patch is authorized by this sweep because it found no source-backed unmapped date fields.

## Validation

| Command | Result |
|---|---|
| `python -m compileall scripts/proofs/procore_raw_payload_mapping_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py` | passed |
| `python -m json.tool punch-date-source-path-audit.json` | passed |
| `ruff check scripts/proofs/procore_raw_payload_mapping_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py` | passed |
| `pytest tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py -q` | passed, 25 tests |
| `hb-assistant procore analytics projection-schema-audit --json` | passed, 0 mismatches |
| `hb-assistant procore analytics projection-audit --endpoint punch-items --json` | passed, 0 unknown/unmapped business paths |
| `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-corrective-mapping/20260618T201500Z --json` | passed, 0 unsafe findings |
