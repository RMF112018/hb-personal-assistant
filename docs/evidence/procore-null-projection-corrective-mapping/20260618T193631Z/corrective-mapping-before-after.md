# Corrective Null Projection Mapping Proof

## Summary

- Corrective evidence timestamp: `20260618T193631Z`
- Strict null audit source proof mode: `enabled`
- Raw source-path audit fields inspected: `406`
- High-confidence registry mapping candidates: `0`
- Registry/projection/schema/migration changes applied in this corrective mapping step: `no`
- Copied-DB endpoint replay run: `no`
- Production projection apply run: `no`
- Live calls run: `no`
- Scheduler / SourceRefreshOrchestrator / all-endpoint refresh used: `no`
- Procore writeback used: `no`
- Raw payload values emitted: `no`

## Superseded Evidence

The prior Batch B/C evidence at `docs/evidence/procore-null-projection-batches-b-c/20260618T151126Z/` is retained for audit trail continuity, but it is marked `SUPERSEDED / NOT ACCEPTED` because it was disposition-only and did not perform source-path proof before clearing suspected projection defects.

## Strict Audit Result

The strict audit restored raw defect detection. It did not suppress fields through hard-coded Batch B/C lists.

| Metric | Count |
|---|---:|
| Tables audited | 86 |
| Columns audited | 3,694 |
| All-null fields | 579 |
| Mostly-null fields | 67 |
| Suspected projection defects | 123 |
| Expected optional fields | 279 |
| Support/guardrail fields | 1,040 |
| Empty tables | 4 |

All `123` suspected projection defects remain classified as `schema_column_not_in_projection_registry` until field-level proof authorizes mapping, deprecation, optional documentation, or schema cleanup.

## Source-Path Decision

The raw-payload source-path audit inspected local raw payloads only and emitted counts/path names only.

| Decision class | Result |
|---|---:|
| High-confidence mapping candidates | 0 |
| Left unmapped with source-path rationale | 406 |
| Raw payload values emitted | false |

No `fix(procore): map source-backed procore null fields` commit was created because the evidence did not authorize any registry/projection mapping.

## Company ID Guardrail

The only initially source-backed scalar-looking findings were `company_id` fields with nested company-object evidence. Repo truth already maps nested `$.company.id` paths to generated columns such as `company_id_col`; the standard `company_id` column follows a separate convention and is not globally remediated by this batch.

| Table | Column | Source evidence | Decision |
|---|---|---|---|
| `procore_ep_projects` | `company_id` | `$.company`, `$.company.id` present | `company_id_requires_derivation_policy` |
| `procore_ep_purchase_order_line_items` | `company_id` | `$.company`, `$.company.id` present | `company_id_requires_derivation_policy` |
| `procore_ep_rfqs` | `company_id` | nested change-event/cost-type company paths present | `company_id_requires_derivation_policy` |
| `procore_ep_rfqs_change_event_change_event_line_items` | `company_id` | nested change-event/cost-type company paths present | `company_id_requires_derivation_policy` |

## Object / Container Fields

Operational object/container fields were not mapped wholesale. They remain candidates for a future explicit decomposition or deprecation patch only when field-specific evidence identifies target scalar columns.

Examples include `ball_in_court`, `cost_code`, `location`, `sub_job`, `closed_by`, `responsible_contractor`, `project_stage`, `assignee`, `designated_reviewer`, `received_from`, and similar object/container columns.

## Copied DB Proof

Copied DB path: `/tmp/procore-null-corrective-20260618T193631Z/hb-personal-assistant.sqlite`

| Check | Result |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA quick_check` | `ok` |

No endpoint-limited `projection-reprocess --apply` was run on the copied DB because there were no approved mapped fields to replay.

## Budget Detail Guardrail

Budget Detail refresh/reconciliation was not called or modified.

| Table | Count |
|---|---:|
| `procore_ep_budget_detail_rows` | 2,496 |
| `procore_ep_budget_detail_row_cells` | 225,131 |

The counts remained nonzero and unchanged because no replay or remediation touched Budget Detail.

## Production Apply

Production apply was not run. The corrective source-path audit authorized zero mappings, so there were no exact affected endpoints or columns to write.

## Validation

| Command | Result |
|---|---|
| `python -m json.tool src/hb_assistant/procore/projection_registry.json` | passed |
| `python -m json.tool raw-payload-source-path-audit.json` | passed |
| `python -m json.tool post-corrective-null-projection-audit.json` | passed |
| `python -m compileall scripts/proofs tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py src/hb_assistant/procore` | passed |
| Focused Ruff on touched proof/test/projection files | passed |
| `pytest tests/test_procore_null_projection_audit.py tests/test_procore_raw_payload_mapping_audit.py tests/test_procore_endpoint_structured_projection_remediation.py -q` | passed, 27 tests |
| `hb-assistant procore analytics projection-schema-audit --json` | passed, 0 mismatches |
| `hb-assistant procore analytics projection-audit --endpoint projects --json` | passed, 0 unknown/unmapped business paths |
| `hb-assistant procore analytics projection-audit --endpoint purchase-order-line-items --json` | passed, 0 unknown/unmapped business paths |
| `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-batches-b-c/20260618T151126Z --json` | passed, 0 unsafe findings |
| `hb-assistant procore analytics no-raw-leak-scan --path docs/evidence/procore-null-projection-corrective-mapping/20260618T193631Z --json` | passed, 0 unsafe findings |

Broader `ruff check scripts/proofs tests src/hb_assistant/procore` was run and failed on unrelated pre-existing files outside this Procore corrective batch:

- `scripts/proofs/frontend_display_copy_check.py`
- `tests/test_agent_registry.py`
- `tests/test_calendar_event_indexing.py`
- `tests/test_phase_10_daily_brief_user_facing_render.py`
- `tests/test_phase_10_daily_run.py`
- `tests/test_phase_10_mcp_packet_hardening.py`
- `tests/test_phase_10_procore_monitor.py`
- `tests/test_phase_10_relationship_entity_report.py`

## Closeout

No schema, registry, migration, projection, scheduled-refresh, live-fetch, writeback, Budget Detail refresh/reconciliation, broad replay, or production apply remediation was applied by this corrective mapping proof.
