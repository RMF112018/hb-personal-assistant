# Patch 6 Bare-Container Deprecation/Reporting Policy Evidence

Generated at: `2026-06-19T08:56:40Z`
Starting commit: `c22daa5e11ea39c1c442a2340e62716a5b905927`

## Summary

- Raw strict findings are preserved. Patch 6 does not fix, erase, drop, rename, hide, migrate, or populate bare container columns.
- `bare_container_deprecated_covered_by_scalar_decomposition` means deprecated in reporting/audit policy only.
- Covered/deprecated bare containers total: `34`.
- Non-custom Patch 4 covered subtype: `31`.
- Patch 5 custom-field covered subtype: `3`.
- Partially covered bare containers: `4`.
- Source-absent scalar leaves: `5`.
- Child/entity-only deferred: `5`.
- Company ID policy deferred: `4`.
- Budget Detail remains unchanged.
- High-confidence mapping candidates: `0`.
- Projection-code repair candidates: `0`.
- Date/datetime mapping candidates: `0`.
- Legacy non-null bare-container warnings: `6`.
- Raw payload values emitted: `false`.

## Covered/Deprecated Containers

| Table | Column | Endpoint | Subtype | Legacy non-null warning |
| --- | --- | --- | --- | --- |
| `procore_ep_change_events` | `event_origin` | `change-events` | `bare_container_deprecated_covered_by_scalar_decomposition` | `True` |
| `procore_ep_commitment_change_orders` | `change_order_change_reason` | `commitment-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_commitment_change_orders` | `designated_reviewer` | `commitment-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_commitment_change_orders` | `received_from` | `commitment-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_commitment_change_orders` | `reviewed_by` | `commitment-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_daily_log_inspections` | `location` | `daily-log-inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_daily_log_manpower` | `cost_code` | `daily-log-manpower` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_daily_log_manpower` | `location` | `daily-log-manpower` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_daily_log_notes` | `location` | `daily-log-notes` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_inspections` | `closed_by` | `inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_inspections` | `point_of_contact` | `inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_inspections` | `responsible_contractor` | `inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_inspections` | `specification_section` | `inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_inspections` | `trade` | `inspections` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_meetings` | `distributed_by` | `meetings` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_observations` | `assignee` | `observations` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_observations` | `assignee_vendor` | `observations` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_observations` | `location` | `observations` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_observations` | `origin` | `observations` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_observations` | `trade` | `observations` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_prime_change_orders` | `change_order_change_reason` | `prime-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_prime_change_orders` | `designated_reviewer` | `prime-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_prime_change_orders` | `received_from` | `prime-change-orders` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_projects` | `project_stage` | `projects` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_purchase_order_contracts` | `assignee` | `purchase-order-contracts` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214072_value` | `purchase-order-contracts` | `bare_container_custom_field_covered_by_scalar_decomposition` | `False` |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214078_value` | `purchase-order-contracts` | `bare_container_custom_field_covered_by_scalar_decomposition` | `False` |
| `procore_ep_purchase_order_contracts` | `custom_fields_custom_field_214087_value` | `purchase-order-contracts` | `bare_container_custom_field_covered_by_scalar_decomposition` | `False` |
| `procore_ep_rfis` | `ball_in_court` | `rfis` | `bare_container_deprecated_covered_by_scalar_decomposition` | `True` |
| `procore_ep_rfis` | `cost_code` | `rfis` | `bare_container_deprecated_covered_by_scalar_decomposition` | `True` |
| `procore_ep_rfis` | `location` | `rfis` | `bare_container_deprecated_covered_by_scalar_decomposition` | `True` |
| `procore_ep_rfis` | `sub_job` | `rfis` | `bare_container_deprecated_covered_by_scalar_decomposition` | `True` |
| `procore_ep_submittals` | `submittal_package` | `submittals` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |
| `procore_ep_submittals` | `submittal_workflow_template` | `submittals` | `bare_container_deprecated_covered_by_scalar_decomposition` | `False` |

## Partially Covered Containers

| Table | Column | Endpoint | Source-absent scalar leaves | Legacy non-null warning |
| --- | --- | --- | ---: | --- |
| `procore_ep_daily_log_manpower` | `contact` | `daily-log-manpower` | 2 | `False` |
| `procore_ep_inspections` | `location` | `inspections` | 1 | `False` |
| `procore_ep_observations` | `specification_section` | `observations` | 1 | `False` |
| `procore_ep_submittals` | `location` | `submittals` | 1 | `True` |

## Guardrails

- No registry, projection, schema, migration, Budget Detail, company_id, live call, scheduler, SourceRefreshOrchestrator, writeback, production DB mutation, broad refresh, push, or GitHub remote action was performed by this evidence generator.
