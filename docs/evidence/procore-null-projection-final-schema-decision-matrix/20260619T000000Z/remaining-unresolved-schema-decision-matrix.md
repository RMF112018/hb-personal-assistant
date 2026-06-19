# Remaining Procore Null Projection Schema Decision Matrix

## Summary

- Evidence date: `2026-06-19`
- Branch: `codex/procore-null-projection-batch1`
- Source strict audit: `docs/evidence/procore-null-projection-corrective-mapping/20260618T193631Z/post-corrective-null-projection-audit.json`
- Source-path audit: `docs/evidence/procore-null-projection-corrective-mapping/20260618T193631Z/raw-payload-source-path-audit.json`
- Punch/date repair audit: `docs/evidence/procore-null-projection-corrective-mapping/20260618T201500Z/punch-date-source-path-audit.json`
- Budget/financial triage: `docs/evidence/procore-null-projection-batch2-triage/20260618T085151Z/budget-financial-source-path-triage.json`
- Strict suspected projection defects remaining: `123`
- High-confidence mapping candidates remaining: `0`
- Source-backed unmapped date fields remaining: `0`
- Raw payload values emitted: `false`

No schema, registry, migration, projection, scheduled-refresh, live-fetch, writeback, Budget Detail refresh/reconciliation, broad replay, production apply, or push was performed for this matrix.

## Patch 1 Verification Addendum

- Patch 1 evidence: `docs/evidence/procore-null-projection-patch1/20260619T064429Z/`
- Verified scalar decomposition fields are not remaining unresolved schema decisions:
  - `procore_ep_commitment_change_orders.change_order_change_reason_id`
  - `procore_ep_commitment_change_orders.change_order_change_reason_change_reason`
  - `procore_ep_commitment_change_orders.designated_reviewer_id`
  - `procore_ep_commitment_change_orders.designated_reviewer_name`
  - `procore_ep_commitment_change_orders.received_from_id`
  - `procore_ep_commitment_change_orders.received_from_name`
  - `procore_ep_commitment_change_orders.reviewed_by_id`
  - `procore_ep_commitment_change_orders.reviewed_by_name`
  - `procore_ep_prime_change_orders.change_order_change_reason_id`
  - `procore_ep_prime_change_orders.change_order_change_reason_change_reason`
  - `procore_ep_prime_change_orders.designated_reviewer_id`
  - `procore_ep_prime_change_orders.designated_reviewer_name`
  - `procore_ep_prime_change_orders.received_from_id`
  - `procore_ep_prime_change_orders.received_from_name`
- Copied-DB reset replay repopulated these scalar fields from existing registry mappings and current local raw payloads.
- Bare object/container columns with the same object names remain governed by the `Object/container columns need decomposition or deprecation, not bare-object projection` decision below.

## Decision Matrix

| Decision bucket | Count | Affected families / tables | Evidence basis | Schema decision | Next action |
|---|---:|---|---|---|---|
| Object/container columns need decomposition or deprecation, not bare-object projection | 43 | RFIs, inspections, observations, daily logs, commitments, owner contracts, purchase orders, submittals, meetings, change events, projects | Current raw payload contains object/container paths, but destination columns are bare object names such as `location`, `cost_code`, `ball_in_court`, `closed_by`, `responsible_contractor`, `project_stage`, `distributed_by`, `event_origin`; generic source audit classifies these as `object_container_requires_decomposition` / `deprecation_candidate`. | Do not map whole objects into these columns. Either add explicit scalar decomposition columns in a separately approved schema design or mark the bare columns deprecated/documented schema artifacts. | `approve_deprecation_patch_next` for bare containers, or `approve_decomposition_schema_design_next` only where analytics require scalar columns. |
| No current source path in local live payloads | 67 | Billing, budget non-Budget-Detail registry endpoints, commitments, daily logs, inspections, meetings, observations, owner contracts, punch items, purchase orders, RFIs, RFQs, subcontractor invoices, submittals | Generic source audit checked candidate paths and found `source_absent_in_current_payloads`; no non-empty path evidence supports mapping. | Leave unchanged; do not add registry mappings from absent current source. These remain documented optional/source-absent fields until new payload evidence appears. | `no_action_source_absent_current_payloads`; revisit only with new endpoint-limited live/source evidence. |
| Broad `company_id` derivation policy required | 4 | `procore_ep_projects.company_id`, `procore_ep_purchase_order_line_items.company_id`, `procore_ep_rfqs.company_id`, `procore_ep_rfqs_change_event_change_event_line_items.company_id` | Source audit found nested company-object paths such as `$.company.id` or RFQ cost-type company paths, but repo convention already maps nested company IDs to generated nested columns where applicable; standard `company_id` is a separate table convention. | Do not globally backfill or map standard `company_id` from nested object paths in this batch. Requires a repository-wide derivation policy and table convention proof. | `defer_company_id_policy`; approve only a dedicated company-ID derivation policy patch. |
| Budget Detail row convenience/dead columns | 4 | `procore_ep_budget_detail_rows.actual_cost`, `cost_type`, `cost_type_id`, `line_item_type_id` | Batch 2 triage inspected current Budget Detail row payloads and dynamic-cell evidence; no row-level or dynamic-cell support was found for these convenience columns. | Treat as dead/read-model convenience columns, not projection defects. Do not map row-level fields unless future source proof shows stable row-level values. | `approve_deprecation_patch_next` or document as `no_action_dead_column_candidate`. |
| Budget Detail cell currency optional | 1 | `procore_ep_budget_detail_row_cells.currency_iso_code` | Batch 2 triage found local evidence sufficient and classified as `expected_optional`; current table has `225,131` rows and `0` non-null `currency_iso_code`. | Do not patch Budget Detail cell currency projection. Document expected optionality unless a future Budget Detail source contract proves required currency at cell level. | `no_action_expected_optional`. |
| Budget Detail read-model schema artifacts needing documentation | 2 | `procore_ep_budget_detail_columns.company_id`, `procore_ep_budget_detail_columns.visible` | Strict audit flags both all-null. They are read-model tables outside the generic endpoint registry plan; current counts are `276` rows with `0` non-null values. No approved source-path proof supports mapping. | Treat as read-model schema artifact/documentation decisions. Do not run Budget Detail refresh/reconciliation or add mappings in this branch. | `document_schema_artifact`; consider a later read-model schema cleanup/deprecation patch. |
| Date/datetime fields | 0 unresolved | All Procore endpoint date-like columns matching `*_at`, `*_date`, `*_on`, `due_date`, `closed_at`, `closed_on`, `created_at`, `updated_at` | Punch/date repair audit inspected `229` date sweep records: `178` already populated, `51` expected optional source-null, `0` source-backed unmapped, `0` mapped-source-present-not-writing. Punch `closed_at` reset replay repopulated `0 -> 13`. | No date schema or mapping patch remains authorized by current evidence. | `no_action_date_sweep_clear`. |
| Punch closeout contradiction | 0 unresolved | `procore_ep_punch_items.closed_at`, `procore_ep_punch_items.closed_by` | Explicit field audit and copied-DB reset replay prove `closed_at` and `closed_by` are mapped/source-backed and repopulate `0 -> 13`. `closed_by` is intentionally scalarized into existing `TEXT` column under current schema. | Resolved. No schema, registry, or projection patch required. | `no_action_already_resolved_by_replay`. |

## Count Reconciliation

| Source | Count |
|---|---:|
| Strict suspected projection defects | 123 |
| Generic source-audited suspected defects | 114 |
| Budget Detail suspected defects handled by Batch 2/read-model decision | 9 |
| Remaining high-confidence mapping candidates | 0 |
| Remaining projection-code repair candidates | 0 |
| Remaining date/datetime mapping candidates | 0 |

## Non-Remediation Guardrails

- Budget Detail refresh/reconciliation remains unchanged.
- Scheduler and `SourceRefreshOrchestrator` were not used.
- No live Procore calls were made for this matrix.
- No raw payload bodies, fragments, sample values, business text, names, emails, comments, notes, descriptions, credentials, or signed URLs are emitted.
- No push was performed.
