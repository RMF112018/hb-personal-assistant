# Patch 4 Existing Scalar Container Projection Evidence

Generated at: `2026-06-19T08:09:06Z`

## Objective

Verify the 35 Patch 3 bare object/container fields that should be represented through existing scalar decomposition columns. This proof does not populate the bare object/container columns.

## Starting Commit

`aee1304e8dc5fbbecd4bd2a15c9efc789924b2ba`

## Summary

- Target bare object/container fields: `35`
- Parent decision counts: `{'covered_by_existing_scalar_decomposition_columns': 31, 'partially_covered_existing_scalar_columns': 4}`
- Scalar status counts: `{'already_replays_existing_scalar_columns': 114, 'source_absent_for_specific_scalar_column': 5}`
- Raw strict findings are not described as fixed; Patch 4 records post-proof covered/no-action/review dispositions.
- Source-absent scalar leaves are not classified as covered.
- Bare object/container non-null counts, where present, are preexisting/unchanged counts; Patch 4 does not reset or populate bare object/container columns.
- Raw payload values emitted: `false`

## Files Changed

- `scripts/proofs/procore_existing_scalar_container_projection_proof.py`
- `tests/test_procore_existing_scalar_container_projection_proof.py`
- `docs/evidence/procore-null-projection-final-schema-decision-matrix/20260619T000000Z/remaining-unresolved-schema-decision-matrix.md`
- `docs/evidence/procore-null-projection-patch4-existing-scalar-containers/20260619T080633Z/`

No registry JSON, projection engine, schema migration, Budget Detail, or `company_id` implementation file was changed.

## Target Endpoint/Table/Column Inventory

`target-field-inventory.json` records the 35 Patch 3 targets selected from `reuse_existing_scalar_decomposition_columns`. The utility fails closed unless exactly 35 targets are present.

Affected endpoints: `change-events`, `commitment-change-orders`, `daily-log-inspections`, `daily-log-manpower`, `daily-log-notes`, `inspections`, `meetings`, `observations`, `prime-change-orders`, `projects`, `purchase-order-contracts`, `rfis`, `submittals`.

## Field Outcomes

| Table | Bare column | Endpoint | Decision | Bare non-null after replay |
| --- | --- | --- | --- | ---: |
| `procore_ep_change_events` | `event_origin` | `change-events` | `covered_by_existing_scalar_decomposition_columns` | 5 |
| `procore_ep_commitment_change_orders` | `change_order_change_reason` | `commitment-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_commitment_change_orders` | `designated_reviewer` | `commitment-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_commitment_change_orders` | `received_from` | `commitment-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_commitment_change_orders` | `reviewed_by` | `commitment-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_daily_log_inspections` | `location` | `daily-log-inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_daily_log_manpower` | `contact` | `daily-log-manpower` | `partially_covered_existing_scalar_columns` | 0 |
| `procore_ep_daily_log_manpower` | `cost_code` | `daily-log-manpower` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_daily_log_manpower` | `location` | `daily-log-manpower` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_daily_log_notes` | `location` | `daily-log-notes` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_inspections` | `closed_by` | `inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_inspections` | `location` | `inspections` | `partially_covered_existing_scalar_columns` | 0 |
| `procore_ep_inspections` | `point_of_contact` | `inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_inspections` | `responsible_contractor` | `inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_inspections` | `specification_section` | `inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_inspections` | `trade` | `inspections` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_meetings` | `distributed_by` | `meetings` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_observations` | `assignee` | `observations` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_observations` | `assignee_vendor` | `observations` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_observations` | `location` | `observations` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_observations` | `origin` | `observations` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_observations` | `specification_section` | `observations` | `partially_covered_existing_scalar_columns` | 0 |
| `procore_ep_observations` | `trade` | `observations` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_prime_change_orders` | `change_order_change_reason` | `prime-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_prime_change_orders` | `designated_reviewer` | `prime-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_prime_change_orders` | `received_from` | `prime-change-orders` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_projects` | `project_stage` | `projects` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_purchase_order_contracts` | `assignee` | `purchase-order-contracts` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_rfis` | `ball_in_court` | `rfis` | `covered_by_existing_scalar_decomposition_columns` | 54 |
| `procore_ep_rfis` | `cost_code` | `rfis` | `covered_by_existing_scalar_decomposition_columns` | 30 |
| `procore_ep_rfis` | `location` | `rfis` | `covered_by_existing_scalar_decomposition_columns` | 76 |
| `procore_ep_rfis` | `sub_job` | `rfis` | `covered_by_existing_scalar_decomposition_columns` | 63 |
| `procore_ep_submittals` | `location` | `submittals` | `partially_covered_existing_scalar_columns` | 32 |
| `procore_ep_submittals` | `submittal_package` | `submittals` | `covered_by_existing_scalar_decomposition_columns` | 0 |
| `procore_ep_submittals` | `submittal_workflow_template` | `submittals` | `covered_by_existing_scalar_decomposition_columns` | 0 |

## Replay Receipts

- `change-events`: ok=`True`, returncode=`0`, primary_rows_written=`2656`
- `commitment-change-orders`: ok=`True`, returncode=`0`, primary_rows_written=`100`
- `daily-log-inspections`: ok=`True`, returncode=`0`, primary_rows_written=`114`
- `daily-log-manpower`: ok=`True`, returncode=`0`, primary_rows_written=`921`
- `daily-log-notes`: ok=`True`, returncode=`0`, primary_rows_written=`92`
- `inspections`: ok=`True`, returncode=`0`, primary_rows_written=`74`
- `meetings`: ok=`True`, returncode=`0`, primary_rows_written=`103`
- `observations`: ok=`True`, returncode=`0`, primary_rows_written=`215`
- `prime-change-orders`: ok=`True`, returncode=`0`, primary_rows_written=`63`
- `projects`: ok=`True`, returncode=`0`, primary_rows_written=`14`
- `purchase-order-contracts`: ok=`True`, returncode=`0`, primary_rows_written=`10`
- `rfis`: ok=`True`, returncode=`0`, primary_rows_written=`2008`
- `submittals`: ok=`True`, returncode=`0`, primary_rows_written=`1900`

## Registry Mapping Status

- Source-backed scalar columns with registry/write-path copied-DB replay proof: `114`.
- Source-absent scalar columns: `5`.
- Missing scalar registry mappings: `0`.
- Projection write-path repair candidates: `0`.
- High-confidence mapping candidates after Patch 4 proof: `0`.

## Copied-DB Reset/Replay Result

- Copied DB: `/tmp/hb-procore-null-projection-patch4-existing-scalar-containers.sqlite`.
- Integrity check output: `copied-db-integrity-check.txt`.
- Pre-reset counts: `pre-replay-scalar-counts.json`.
- Reset counts: `reset-scalar-counts.json`.
- Post-replay counts: `post-replay-scalar-counts.json`.
- Reset scope: only Patch 4 target scalar decomposition columns on the copied DB.
- Production DB mutation: `false`.

## Scalar Columns Repopulated

`114` source-backed existing scalar decomposition columns repopulated after reset. Counts and path names are in `classification-summary.json`; no raw scalar values are emitted.

## Scalar Columns Source-Absent/Optional

`5` scalar leaves had no current non-empty source evidence and are not classified as covered:

- `procore_ep_daily_log_manpower.contact_login_information_id`
- `procore_ep_daily_log_manpower.contact_vendor_name`
- `procore_ep_inspections.location_code`
- `procore_ep_observations.specification_section_viewable_document_id`
- `procore_ep_submittals.location_parent_id`

## Bare Object/Container Columns

Patch 4 did not reset, map, or populate bare object/container columns. Non-null bare counts for `procore_ep_change_events.event_origin`, selected `procore_ep_rfis` bare columns, and `procore_ep_submittals.location` were preexisting and unchanged across pre-reset, reset, and post-replay evidence.

## Out-of-Scope Exclusions Confirmed

- Child-table/entity-only candidates remained out of scope.
- Custom-field evidence-needed candidates remained out of scope.
- `company_id` policy deferrals remained out of scope.
- Budget Detail rows, cells, columns, refresh/reconciliation, currency, and read-model artifacts remained untouched.

## Tests Run

- `python -m compileall scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py scripts/proofs/procore_existing_scalar_container_projection_proof.py tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py tests/test_procore_existing_scalar_container_projection_proof.py`: passed.
- `python -m compileall src tests`: passed.
- `ruff check scripts/proofs/procore_null_projection_audit.py scripts/proofs/procore_raw_payload_mapping_audit.py scripts/proofs/procore_existing_scalar_container_projection_proof.py tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py tests/test_procore_existing_scalar_container_projection_proof.py`: passed.
- `pytest tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py tests/test_procore_existing_scalar_container_projection_proof.py -q`: passed, `36` tests.
- `pytest tests -k "procore and (projection or null or raw_payload or schema or endpoint or container)" -q`: passed.
- `ruff check .`: diagnostic only; failed on pre-existing unrelated lint outside Patch 4 scope.

## Audit Receipts

- `projection-schema-audit.json`: ok, `0` runtime plan/schema mismatches.
- Endpoint projection audit JSON files: all 13 affected endpoints returned ok.
- `no-raw-leak-scan.json`: ok, `unsafe_finding_count=0`.

## Guardrails

- Bare object/container columns were not reset or populated by Patch 4.
- Budget Detail was not changed.
- `company_id` was not derived or backfilled.
- No live Procore calls, scheduler runs, SourceRefreshOrchestrator runs, writeback, production DB mutation, broad refresh, or push were performed.

## Remaining Decisions After Patch 4

- `31` bare object/container fields are covered by existing scalar decomposition replay proof and should remain no-action/deprecation candidates, not whole-object mapping candidates.
- `4` parent containers remain partially covered because `5` scalar leaves are source-absent in current payloads.
- `5` child-table/entity-only object/container decisions remain deferred to a future schema design.
- `3` custom-field object/container decisions remain pending additional body-free source evidence.
- Raw strict detector findings remain preserved; Patch 4 adds post-proof dispositions only.
