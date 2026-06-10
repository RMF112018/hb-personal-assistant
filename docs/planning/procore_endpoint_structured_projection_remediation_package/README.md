# Procore Endpoint-Specific Structured Projection Remediation Package

## Manifest

- **Package:** `procore_endpoint_structured_projection_remediation_package`
- **Version:** `1.0.0`
- **Repository:** `/Users/bobbyfetting/hb-personal-assistant`
- **Target branch:** `fix/procore-endpoint-specific-structured-projections`
- **Base:** current `main` after PR #18 merge
- **Mode:** implementation package, one-shot executable by the local code agent
- **Primary objective:** audit and remediate every Procore endpoint/table so every primary and nested business field returned in full raw payloads is projected into useful local raw/structured content tables.
- **Completion standard:** the agent may not mark this package complete until a mechanical inventory proves zero unmapped primary or nested business fields for every endpoint with available payloads.

## Context

PR #18 fixed the first-order data-quality issue: full Procore endpoint payloads are now persisted locally in `procore_endpoint_raw_payloads.payload_json` with `raw_procore_payload_persisted=1`, while redaction remains an outbound-boundary concern.

That was necessary but not sufficient.

The next issue is structural: endpoint-family tables such as `procore_raw_change_events` are too generic and shallow. They preserve a small subset of scalar fields but do not project all endpoint-specific or nested business fields into relational/raw-content tables.

The concrete proof came from `change-events`:

- `procore_raw_change_events` had mostly full-source rows: 194 `live_full_payload`, 4 `redacted_legacy_projection`.
- Yet many structured columns remained completely empty: `company_id`, `assignee_name`, `responsible_party_name`, `due_at_utc`, `start_at_utc`, `finish_at_utc`, `cost_code`, `cost_type`, `amount`, `currency`, `quantity`, `unit_of_measure`.
- The full raw payloads contained additional fields and nested arrays/objects, including: `company_id`, `project_id`, `description`, `change_reason`, `change_type`, `scope`, `source`, `source_of_revenue_rom`, `currency_configuration`, `custom_fields`, `attachments`, `markup_items`, `production_quantities`, and especially `change_items`.
- The `change_items[]` payloads contained the cost/change intelligence fields that the database needs: `budget_code`, `flat_code`, `segment_items`, `cost_impact`, `budget_impact`, `commitment`, `contract`, `vendor`, `line_item`, `amount`, `amount_project_currency`, `quantity`, `unit_cost`, `unit_of_measure`, `calculation_strategy`, `status`, `title`, and `number`.

This pattern is expected to exist across other endpoint families: invoices, invoice detail items, contracts, contract line items, budget rows, change orders, commitment line items, meeting topics/details, RFIs/responses, submittals/responses, daily logs, inspections, attachments, and dimensions.

## Non-negotiable principles

1. **The private local SQLite DB is the analytical source of truth.**
   - Full raw Procore business payloads remain in `procore_endpoint_raw_payloads`.
   - Endpoint-specific projection tables must make the data queryable without requiring ad hoc JSON spelunking for normal use.

2. **No raw payload bodies leave local runtime boundaries.**
   - No raw Procore bodies in committed docs, tests, evidence, stdout, logs, screenshots, Obsidian, browser output, status JSON, or model prompts.
   - Evidence must contain only counts, field names, table/column names, hashes, null-rate matrices, and redacted examples.

3. **Transport/auth secrets must never be stored or emitted.**
   - Preserve the PR #18 transport-secret scrubber behavior.
   - Do not weaken the security model to improve field coverage.

4. **Projection completeness must be mechanical, not subjective.**
   - For each endpoint with full payloads, inventory every observed top-level key and nested key path.
   - Every observed business field path must map to one of:
     - an endpoint-specific primary table column,
     - a child/detail table column,
     - a dimension table,
     - a many-to-many bridge table,
     - a documented lossless JSON sidecar column inside an endpoint-specific projection table,
     - an explicit non-business exclusion such as stripped transport/auth secret metadata.
   - Completion requires `unmapped_primary_business_fields = 0` and `unmapped_nested_business_fields = 0` for every endpoint with available full raw payloads.

5. **Generic V46 tables are not enough.**
   - Keep existing `procore_raw_*` tables for compatibility if useful.
   - Add endpoint-specific tables where required.
   - Do not claim completion merely because `procore_raw_*` has one row per record.

6. **No production DB mutation during implementation validation.**
   - Use `/tmp` copies of the production SQLite DB.
   - Record production DB sha256 before/after validation and prove unchanged.
   - Runtime code may support production apply after merge, but this implementation package validates on copies.

## Expected implementation shape

The exact schema should be determined by repo truth and payload inventory, but the result should follow this pattern:

### 1. Endpoint primary tables

Create endpoint-specific tables for first-class business objects. Examples:

- `procore_change_events`
- `procore_rfis`
- `procore_rfi_responses`
- `procore_submittals`
- `procore_submittal_responses`
- `procore_meetings`
- `procore_meeting_topics`
- `procore_meeting_details`
- `procore_observations`
- `procore_punch_items`
- `procore_inspections`
- `procore_inspection_sections`
- `procore_inspection_items`
- `procore_daily_log_*` or a normalized daily-log event table plus endpoint-specific detail tables
- `procore_contracts`
- `procore_contract_line_items`
- `procore_change_orders`
- `procore_change_order_line_items`
- `procore_invoices`
- `procore_invoice_items`
- `procore_budget_rows`
- `procore_budget_columns`
- `procore_budget_views`
- `procore_budget_modifications`
- `procore_budget_changes`
- `procore_attachments`

Primary tables must carry stable identity, project/company identity, endpoint key, source quality, raw payload linkage, Procore timestamps, and endpoint-specific scalar fields.

### 2. Nested child/detail tables

Create child/detail tables for repeated or nested objects. Examples:

- `procore_change_event_items`
- `procore_change_event_item_budget_segments`
- `procore_change_event_attachments`
- `procore_change_event_markup_items`
- `procore_change_event_custom_fields`
- `procore_change_event_production_quantities`
- `procore_invoice_detail_items`
- `procore_invoice_change_order_items`
- `procore_contract_line_item_segments`
- `procore_budget_row_cells`
- `procore_daily_log_manpower_entries`
- `procore_daily_log_delivery_entries`
- `procore_inspection_item_observations`
- `procore_meeting_topic_assignments`
- `procore_rfi_response_attachments`
- `procore_submittal_response_attachments`

The names above are examples. The agent must derive the exact table set from endpoint payload inventories and repo truth.

### 3. Field-path mapping registry

Implement a machine-readable field mapping registry, ideally committed as code and/or JSON/YAML under `src/hb_assistant/procore/`, that maps each endpoint's observed field paths to table/column targets.

The registry must include:
- endpoint id,
- payload JSON path,
- table target,
- column target or sidecar target,
- field type,
- cardinality (`scalar`, `object`, `array`),
- business category (`identity`, `status`, `date`, `money`, `quantity`, `person`, `company`, `cost_code`, `attachment`, `custom_field`, `nested_line_item`, etc.),
- extraction function if non-trivial,
- nullability expectation,
- explicit exclusion reason, only for non-business/auth/transport fields.

### 4. Projection engine

Implement deterministic projection from `procore_endpoint_raw_payloads.payload_json` into endpoint-specific tables.

Required behavior:
- Idempotent replay.
- Source-quality precedence retained.
- Raw payload id linkage retained.
- Existing `procore_raw_*` compatibility tables retained or populated.
- Child rows delete/replace or upsert deterministically per parent payload hash.
- No external writeback.
- No raw body output.
- Fail closed if a payload has fields absent from the mapping registry and not explicitly excluded.

### 5. CLI surfaces

Add or extend CLI commands for:
- endpoint payload field inventory,
- projection coverage,
- projection replay/backfill from full raw payloads,
- unmapped field reporting,
- null-rate matrix,
- endpoint/table status,
- no-raw-leak scan.

Suggested command family:

```bash
hb-assistant procore analytics projection-inventory --db "$DB" --json
hb-assistant procore analytics projection-audit --db "$DB" --json
hb-assistant procore analytics projection-reprocess --db "$DB" --apply --json
hb-assistant procore analytics projection-coverage --db "$DB" --json
```

Do not rename existing commands unless necessary. Preserve backwards-compatible output keys where feasible.

## Required package execution sequence

The local agent must execute the prompt files in `prompts/` in numeric order:

1. `00-repo-truth-baseline.md`
2. `01-payload-field-inventory-engine.md`
3. `02-endpoint-projection-matrix.md`
4. `03-schema-design-and-migration.md`
5. `04-projection-registry-and-extractors.md`
6. `05-implement-endpoint-projections.md`
7. `06-backfill-and-cli-surfaces.md`
8. `07-tests-fixtures-and-regression.md`
9. `08-db-copy-validation-and-evidence.md`
10. `09-no-leak-and-security-proof.md`
11. `10-final-handoff.md`

## Completion gates

The agent may not declare completion unless all gates pass:

### Gate A — repo truth and schema

- Current schema head identified.
- All Procore endpoint registry entries inventoried.
- All existing `procore_raw_*` tables inventoried.
- All live full raw payload endpoint keys inventoried.
- All held endpoints accounted for.

### Gate B — payload field inventory

For every endpoint with full raw payloads:
- top-level fields inventoried,
- nested paths inventoried,
- array cardinalities inventoried,
- object field paths inventoried,
- field occurrence counts measured,
- field null/empty rates measured.

### Gate C — mapping completeness

For every observed payload field path:
- mapped to a table/column,
- mapped to a child/detail table,
- mapped to a dimension/bridge table,
- mapped to a documented lossless JSON sidecar,
- or explicitly excluded as non-business/transport/auth metadata.

Completion requires:
- `unmapped_primary_business_fields = 0`
- `unmapped_nested_business_fields = 0`
- `unknown_business_field_paths = 0`

### Gate D — projection coverage

For every endpoint with full raw payloads:
- endpoint primary table row count equals expected parent record count, unless documented no-data condition.
- child table row counts equal observed nested array cardinalities.
- source-quality precedence prevents legacy downgrade.
- all rows link back to `raw_payload_id`.
- all generated tables have `external_writeback_performed = 0`.

### Gate E — evidence

Evidence must be written under:

```text
docs/evidence/procore_endpoint_structured_projection_remediation/
```

Evidence may include:
- counts,
- field names,
- endpoint ids,
- table names,
- null-rate percentages,
- hash prefixes,
- schema diffs,
- classified leak-scan output.

Evidence must not include:
- raw payload bodies,
- project/private business text,
- raw URLs,
- tokens,
- secrets,
- `.sqlite` / `.db` files,
- JSON payload dumps.

### Gate F — validation

Minimum validation:

```bash
python -m pip install -e .
PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_full_raw_payload_ingestion.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_structured_analytics_foundation.py -q
PYTHONPATH="$PWD/src" python -m pytest tests/test_procore_endpoint_structured_projection_remediation.py -q
ruff check src/hb_assistant/procore src/hb_assistant/cli tests/test_procore_endpoint_structured_projection_remediation.py
mypy src/hb_assistant/procore src/hb_assistant/cli
```

If the repo’s current tooling uses different exact test paths, adapt based on repo truth and document the adaptation.

### Gate G — DB-copy proof

On a `/tmp` copy of the production DB:
- run migration,
- run projection inventory,
- run projection reprocess,
- run projection coverage,
- prove no unmapped business field paths,
- prove no production DB hash change.

## Final handoff requirements

The final handoff must include:
- branch,
- commit SHA,
- schema migration decision,
- list of new/modified tables,
- endpoint coverage matrix summary,
- unmapped field count by endpoint, all zero or explicitly held/no-data,
- validation commands and results,
- no-leak proof,
- production DB untouched proof,
- exact post-merge production apply runbook.

## Stop conditions

Stop and report instead of guessing if:
- a schema change would be destructive,
- a payload contains auth/transport secrets after PR #18 scrubber,
- a field path cannot be classified safely,
- an endpoint path is unresolved or fail-closed,
- live calls are needed but not explicitly gated,
- completing all endpoints would require raw payload evidence in repo,
- a migration would drop legacy compatibility tables,
- validation would require modifying the production DB.

Do not mark this package complete if any endpoint with available full payloads still has unmapped primary or nested business fields.
