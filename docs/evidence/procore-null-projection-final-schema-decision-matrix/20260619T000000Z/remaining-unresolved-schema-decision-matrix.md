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

## Patch 2 Classification Addendum

- Patch 2 evidence: `docs/evidence/procore-null-projection-patch2/20260619T071034Z/`
- Raw strict detector count preserved: `123`
- High-confidence raw-payload-backed scalar mapping candidates: `0`
- Date/datetime mapping candidates: `0`
- Patch 1 scalar decomposition defects: `0`
- Patch 2 does not mark the raw `123` findings fixed. It adds post-proof dispositions showing the remaining items are not current high-confidence scalar mapping defects.
- Post-proof decision counts:
  - `object_container_requires_decomposition_or_deprecation`: `43`
  - `source_absent_in_current_payloads`: `67`
  - `company_id_policy_deferred`: `4`
  - `budget_detail_dead_convenience_column`: `4`
  - `budget_detail_read_model_schema_artifact`: `4`
  - `expected_optional_no_action`: `463`
  - `patch1_scalar_decomposition_verified`: `14`
- Budget Detail read-model artifact count is `4` in Patch 2 because current strict audit also includes Budget Detail row/cell `company_id` columns; they remain no-action artifacts and were not backfilled or derived.
- Raw detector fields remain present as `raw_detection.*`; post-proof closeout fields are emitted separately as `post_proof_decision.*`.

## Patch 4 Addendum

- Patch 4 does not mark raw strict object/container findings fixed. It adds copied-DB reset/replay proof showing which bare object/container columns are post-proof covered by existing scalar decomposition columns, partially covered, or still reserved for separate design decisions.
- Patch 4 target set from Patch 3 `reuse_existing_scalar_decomposition_columns`: `35`.
- `covered_by_existing_scalar_decomposition_columns`: `31`.
- `partially_covered_existing_scalar_columns`: `4`.
- `source_absent_for_specific_scalar_column`: `5` scalar leaves across those 4 partially covered parent containers.
- `remaining_object_container_design_decisions`: `8`.
- `child_table_or_entity_only`: `5`.
- `custom_field_evidence_needed`: `3` before Patch 5.
- Bare object/container columns were not reset or populated by Patch 4. Any non-null bare-column counts observed in copied-DB evidence were preexisting and unchanged across pre-reset, reset, and post-replay counts.

## Patch 5 Addendum

- Patch 5 does not mark raw strict custom-field object/container findings fixed. It adds body-free source-shape and copied-DB reset/replay proof showing the three purchase-order custom-field bare containers are post-proof covered by existing scalar decomposition columns.
- Patch 5 target set: `3` bare custom-field containers and `4` listed scalar destination columns.
- `covered_by_existing_scalar_decomposition_columns`: `3`.
- `custom_field_evidence_needed`: `0` for the Patch 5 target set.
- Out-of-scope comparative sibling columns discovered: `3` `*_value_label` columns. They were recorded as comparative metadata only and did not expand the Patch 5 target set.
- Bare custom-field container columns were not reset or newly populated by Patch 5.

## Decision Matrix

| Decision bucket | Count | Affected families / tables | Evidence basis | Schema decision | Next action |
|---|---:|---|---|---|---|
| Existing-scalar object/container columns covered by scalar decomposition | 31 | Change events, commitments, daily logs, inspections, meetings, observations, owner contracts, projects, purchase orders, RFIs, submittals | Patch 4 copied-DB reset/replay proof reset only existing scalar decomposition columns and replayed endpoint-limited local projections. Source-backed scalar paths repopulated after reset; bare object/container columns were not reset or written by Patch 4. | Treat parent bare containers as no-action/deprecation candidates covered by existing scalar decomposition. Do not map whole objects into bare columns. | `no_action_existing_scalar_decomposition_verified`; consider later bare-column deprecation only through a schema cleanup patch. |
| Existing-scalar object/container columns partially covered | 4 | `procore_ep_daily_log_manpower.contact`, `procore_ep_inspections.location`, `procore_ep_observations.specification_section`, `procore_ep_submittals.location` | Patch 4 proved source-backed scalar paths replay, but found `5` listed scalar leaves source-absent in current payloads. Source-absent scalar leaves are not classified as covered. | Leave mapped/replaying scalar leaves unchanged. Do not guess missing source paths. Keep parent bare containers as partially covered pending endpoint-specific source review. | `review_scalar_source_coverage_before_schema_decision`. |
| Child-table/entity-only object/container decisions | 5 | `procore_ep_inspection_items.item_response`, `response`, `response_set`; `procore_ep_inspections_signature_requests.signature`; `procore_ep_observations_assignees.vendor` | Patch 3 classified these as child-table/entity-only candidates, not existing-scalar parent-table cleanup. Patch 4 intentionally excluded them. | Keep out of Patch 4. Represent only in child tables or entity/reference dimensions if a future schema design approves it. | `approve_child_table_or_entity_design_next`. |
| Purchase-order custom-field containers covered by existing scalar decomposition | 3 | `procore_ep_purchase_order_contracts.custom_fields_custom_field_214072_value`, `custom_fields_custom_field_214078_value`, `custom_fields_custom_field_214087_value` | Patch 5 inspected body-free source-shape metadata and copied-DB reset/replay evidence. The listed scalar destinations replayed from source-backed registry paths: `custom_fields_custom_field_214072_value_id`, `custom_fields_custom_field_214078_value_company_name`, `custom_fields_custom_field_214078_value_id`, `custom_fields_custom_field_214087_value_id`. | Treat these three bare containers as covered/no-action by existing scalar decomposition. Do not map whole custom-field objects into bare columns. Do not expand scope to comparative `*_value_label` sibling columns without explicit approval. | `no_action_existing_scalar_decomposition_verified`; future generic custom-field value-table design remains separate. |
| No current source path in local live payloads | 67 | Billing, budget non-Budget-Detail registry endpoints, commitments, daily logs, inspections, meetings, observations, owner contracts, punch items, purchase orders, RFIs, RFQs, subcontractor invoices, submittals | Generic source audit checked candidate paths and found `source_absent_in_current_payloads`; no non-empty path evidence supports mapping. | Leave unchanged; do not add registry mappings from absent current source. These remain documented optional/source-absent fields until new payload evidence appears. | `no_action_source_absent_current_payloads`; revisit only with new endpoint-limited live/source evidence. |
| Broad `company_id` derivation policy required | 4 | `procore_ep_projects.company_id`, `procore_ep_purchase_order_line_items.company_id`, `procore_ep_rfqs.company_id`, `procore_ep_rfqs_change_event_change_event_line_items.company_id` | Source audit found nested company-object paths such as `$.company.id` or RFQ cost-type company paths, but repo convention already maps nested company IDs to generated nested columns where applicable; standard `company_id` is a separate table convention. | Do not globally backfill or map standard `company_id` from nested object paths in this batch. Requires a repository-wide derivation policy and table convention proof. | `defer_company_id_policy`; approve only a dedicated company-ID derivation policy patch. |
| Budget Detail row convenience/dead columns | 4 | `procore_ep_budget_detail_rows.actual_cost`, `cost_type`, `cost_type_id`, `line_item_type_id` | Batch 2 triage inspected current Budget Detail row payloads and dynamic-cell evidence; no row-level or dynamic-cell support was found for these convenience columns. | Treat as dead/read-model convenience columns, not projection defects. Do not map row-level fields unless future source proof shows stable row-level values. | `approve_deprecation_patch_next` or document as `no_action_dead_column_candidate`. |
| Budget Detail cell currency optional | 1 | `procore_ep_budget_detail_row_cells.currency_iso_code` | Batch 2 triage found local evidence sufficient and classified as `expected_optional`; current table has `225,131` rows and `0` non-null `currency_iso_code`. | Do not patch Budget Detail cell currency projection. Document expected optionality unless a future Budget Detail source contract proves required currency at cell level. | `no_action_expected_optional`. |
| Budget Detail read-model schema artifacts needing documentation | 4 | `procore_ep_budget_detail_columns.company_id`, `procore_ep_budget_detail_columns.visible`, `procore_ep_budget_detail_row_cells.company_id`, `procore_ep_budget_detail_rows.company_id` | Patch 2 strict audit flags these fields all-null and classifies them as `budget_detail_read_model_schema_artifact`. The columns are read-model artifacts outside the generic endpoint registry plan; no approved source-path proof supports mapping or `company_id` derivation. | Treat as read-model schema artifact/documentation decisions. Do not run Budget Detail refresh/reconciliation, derive `company_id`, or add mappings in this branch. | `document_schema_artifact`; consider a later read-model schema cleanup/deprecation patch. |
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
