# Batch 2 Budget/Financial Source-Path Triage

## Executive Summary

- Target fields: `7`
- Local evidence sufficient fields: `7`
- Approve mapping patch next: `2`
- Dynamic-cell already handled: `0`
- Dead column candidates: `4`
- Schema artifacts to document: `0`
- Deferred pending live source evidence: `0`

## Target Field Matrix

| Table | Column | Rows | Null Rate | Audit Root Cause | Paths Checked | Local Evidence | Classification | Next Action |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| procore_ep_budget_detail_rows | actual_cost | 2496 | 1.0 | schema_column_not_in_projection_registry | $.actual_cost | sufficient | read_model_convenience_or_dead_column | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | cost_type | 2496 | 1.0 | schema_column_not_in_projection_registry | $.cost_type<br>$.line_item_type | sufficient | read_model_convenience_or_dead_column | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | cost_type_id | 2496 | 1.0 | schema_column_not_in_projection_registry | $.cost_type_id<br>$.cost_type.id<br>$.line_item_type_id<br>$.line_item_type.id | sufficient | read_model_convenience_or_dead_column | no_action_dead_column_candidate |
| procore_ep_budget_detail_rows | line_item_type_id | 2496 | 1.0 | schema_column_not_in_projection_registry | $.line_item_type_id<br>$.line_item_type.id | sufficient | read_model_convenience_or_dead_column | no_action_dead_column_candidate |
| procore_ep_budget_detail_row_cells | currency_iso_code | 225131 | 1.0 | schema_column_not_in_projection_registry | $.currency_iso_code<br>$.currency_code<br>$.currency_configuration.currency_iso_code | sufficient | expected_optional | no_action_expected_optional |
| procore_ep_change_events_change_items | cost_impact_contract_confirmed | 2816 | 1.0 | schema_column_not_in_projection_registry | $.change_items[].cost_impact.contract_confirmed<br>$.change_items[].cost_impact.contract.confirmed | sufficient | row_level_source_field_exists | approve_mapping_patch_next |
| procore_ep_change_events_change_items | cost_impact_vendor_confirmed | 2816 | 1.0 | schema_column_not_in_projection_registry | $.change_items[].cost_impact.vendor_confirmed<br>$.change_items[].cost_impact.vendor.confirmed | sufficient | row_level_source_field_exists | approve_mapping_patch_next |

## Body-Free Path Evidence

### procore_ep_budget_detail_rows.actual_cost

- Endpoint: `budget-detail-rows`
- Classification: `read_model_convenience_or_dead_column`
- Next action: `no_action_dead_column_candidate`
- Rationale: Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.actual_cost` | 2496 | 0 | 0 | 2496 |

- Dynamic cell evidence:
  - aliases checked: `actualcost, actualcosts`
  - cell rows inspected: `225131`
  - matching cell rows: `0`
  - matching decimal rows: `0`

### procore_ep_budget_detail_rows.cost_type

- Endpoint: `budget-detail-rows`
- Classification: `read_model_convenience_or_dead_column`
- Next action: `no_action_dead_column_candidate`
- Rationale: Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.cost_type` | 2496 | 0 | 0 | 2496 |
| `$.line_item_type` | 2496 | 0 | 0 | 2496 |

### procore_ep_budget_detail_rows.cost_type_id

- Endpoint: `budget-detail-rows`
- Classification: `read_model_convenience_or_dead_column`
- Next action: `no_action_dead_column_candidate`
- Rationale: Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.cost_type_id` | 2496 | 0 | 0 | 2496 |
| `$.cost_type.id` | 2496 | 0 | 0 | 2496 |
| `$.line_item_type_id` | 2496 | 0 | 0 | 2496 |
| `$.line_item_type.id` | 2496 | 0 | 0 | 2496 |

### procore_ep_budget_detail_rows.line_item_type_id

- Endpoint: `budget-detail-rows`
- Classification: `read_model_convenience_or_dead_column`
- Next action: `no_action_dead_column_candidate`
- Rationale: Current rows exist, but neither row-level source nor dynamic-cell evidence supports projection.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.line_item_type_id` | 2496 | 0 | 0 | 2496 |
| `$.line_item_type.id` | 2496 | 0 | 0 | 2496 |

### procore_ep_budget_detail_row_cells.currency_iso_code

- Endpoint: `budget-detail-rows`
- Classification: `expected_optional`
- Next action: `no_action_expected_optional`
- Rationale: Candidate row-level source paths are present only as null or empty values.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.currency_iso_code` | 2496 | 0 | 0 | 2496 |
| `$.currency_code` | 2496 | 0 | 0 | 2496 |
| `$.currency_configuration.currency_iso_code` | 2496 | 2496 | 0 | 0 |

- Cell currency evidence:
  - cell rows inspected: `225131`
  - currency non-null rows: `0`
  - currency null rows: `225131`

### procore_ep_change_events_change_items.cost_impact_contract_confirmed

- Endpoint: `change-events`
- Classification: `row_level_source_field_exists`
- Next action: `approve_mapping_patch_next`
- Rationale: A checked cost-impact confirmation path exists with non-empty source data.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.change_items[].cost_impact.contract_confirmed` | 2652 | 0 | 0 | 2652 |
| `$.change_items[].cost_impact.contract.confirmed` | 2652 | 2646 | 1973 | 6 |

### procore_ep_change_events_change_items.cost_impact_vendor_confirmed

- Endpoint: `change-events`
- Classification: `row_level_source_field_exists`
- Next action: `approve_mapping_patch_next`
- Rationale: A checked cost-impact confirmation path exists with non-empty source data.

| JSON Path | Inspected | Present | Non-Empty | Missing |
| --- | ---: | ---: | ---: | ---: |
| `$.change_items[].cost_impact.vendor_confirmed` | 2652 | 0 | 0 | 2652 |
| `$.change_items[].cost_impact.vendor.confirmed` | 2652 | 2646 | 1973 | 6 |

## Guardrails

- No live calls were made.
- No scheduler or SourceRefreshOrchestrator path was called.
- No Budget Detail refresh or reconciliation path was called.
- No schema, registry, projection, migration, or writeback change was applied.
- Raw payload bodies, fragments, and values were not emitted.

## Closeout

No remediation was applied; null projection counts were intentionally unchanged.
