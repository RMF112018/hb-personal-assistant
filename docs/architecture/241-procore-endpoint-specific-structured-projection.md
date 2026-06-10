# 241 — Procore Endpoint-Specific Structured Projection (V47)

## Problem

PR #18 (doc 200) persists full, transport-scrubbed Procore payloads in
`procore_endpoint_raw_payloads.payload_json`. The V46 structured analytics foundation
(doc 240) added 44 generic `procore_raw_*` "bronze" tables — but they all share **one
shallow flat schema** (`record_number/title/status/amount/quantity/…`). Endpoint-specific
scalar fields and every nested array/object (`change_items[]`, `attachments[]`,
`markup_items[]`, `budget_code.segment_items[]`, line items, …) were never projected, so
the local DB was a raw store but not a useful analytical read model.

## Design

A **registry-driven, generic projection engine** produces one endpoint-specific primary
table per endpoint plus child/detail tables for nested business-object arrays. A single
committed registry is the source of truth for the schema, the projection, and the audit —
they can never disagree.

### Components (`src/hb_assistant/procore/`)
- **`projection_paths.py`** — shared path walker (list indices collapsed to `[]`),
  business-category classifier, high-value detection, transport-secret exclusion (reuses
  `AUTH_SECRET_KEY_RE`), and SQL identifier sanitisation.
- **`projection_registry.py` + `projection_registry.json`** — the committed *allow-list*.
  `build_registry()` is a pure function over a structural inventory (paths + types only,
  never values). Each observed `(endpoint, json_path)` maps to exactly one destination:
  `column` (first-class), `child` (nested array → child table), `sidecar` (declared
  lossless `payload_sidecar_json`), `exclude` (auth secret), or `structural` (container).
  `build_v47_ddl()` derives the migration DDL from the registry.
- **`projection_engine.py`** — `project_endpoint_specific()` (idempotent primary upsert +
  child delete/replace, source-quality precedence, fail-closed) and
  `backfill_endpoint_specific_from_raw_payloads()` (replay; no live calls).
- **`projection_audit.py`** — `projection_inventory()` (Gate B) and `projection_audit()`
  (Gate C + sidecar-coverage metric).

### Schema (migration V47, `store/migrator.py`)
- All tables use the `procore_ep_` prefix (a discoverable layer, collision-proof against
  existing `procore_*` tables).
- Every table carries standard identity columns (record/parent/project/company ids +
  hashes, `raw_payload_id`, `payload_hash`, `source_quality`, `is_current`, timestamps),
  curated business columns, a lossless `payload_sidecar_json`, and zero-CHECK guards
  (`external_writeback_performed`, `raw_payload_emitted_to_read_model`,
  `raw_payload_emitted_to_evidence`). Child tables add `primary_record_key`,
  `parent_item_id`, `item_id`, `child_index`, `array_path`.
- DDL is generated from the registry via `build_v47_ddl()`; `CREATE … IF NOT EXISTS`
  keeps the migration additive and idempotent. All V46/V7 tables are retained.

### Allow-list semantics (fail closed)
The registry is an explicit allow-list, not a wildcard. A live payload path absent from
it is `unknown`:
- **enforce mode** (audit, `projection-reprocess --apply`) raises / exits non-zero;
- **live mode** (inside `upsert_full_raw_payload_and_structured`) degrades the receipt
  (`state = degraded_unknown_projection_fields`, `ok = false`) without writing a partial
  projection — the full raw payload is already persisted, so nothing is lost.

This reconciles "zero unmapped on the observed corpus" with "a NEW field must fail": the
registry is generated from the observed corpus (so all current paths are covered) and a
future field never seen at generation time is caught.

### Quality gates (operator amendments)
- **High-value fields are always first-class columns** (money, quantity, unit cost, cost
  code, WBS/segment, vendor/company, status, title/description, date, responsible-party,
  identity) — never sidecar-only.
- **Sidecar coverage is measured** per endpoint; any endpoint over 25% sidecar-only
  carries an explicit, reviewed justification (`SIDECAR_JUSTIFICATIONS`) and is otherwise
  not marked complete.

## Runtime plan/schema parity + column reconciliation (V48 hotfix)
Two follow-on guarantees were added after a production INSERT crash
(`no column named architect`):

- **Object-container classification.** `object|null` containers must be `structural`
  (lossless in the sidecar), never columns — `null` does not make an object container a
  promotable scalar (`_NON_NULL_SCALARS`). Their scalar children remain first-class columns.
- **Schema parity gate.** Path coverage and runtime insert-column/physical-schema parity
  are orthogonal. `runtime_plan_schema_mismatches` / `projection_schema_audit` verify every
  planned primary + child insert column exists physically and every `procore_ep_*` table
  exists; this is folded into `projection-audit` `ok` and surfaced via
  `projection-schema-audit`. `projection-reprocess --apply` runs the check **before any
  write** and returns a structured `schema_parity_broken` receipt instead of
  `sqlite3.OperationalError`.
- **V48 reconciliation migration.** Because the V47 tables are registry-derived and
  `CREATE TABLE IF NOT EXISTS` cannot add columns, a regenerated registry can require
  columns existing tables lack. The V48 migration block reconciles physical schema to the
  registry with additive `ALTER TABLE ADD COLUMN`, run **unconditionally** (outside the
  version gate) so it self-heals column drift on every `apply()`, even on a DB already at
  head. Additive only — never drops or alters existing columns; the table set is unchanged
  (lifecycle contract `table_count` stays 347).

## CLI (`procore analytics`)
`projection-inventory [--emit-candidate]`, `projection-audit`, `projection-coverage`,
`projection-schema-audit`, `projection-reprocess [--apply]`. `--apply` requires `--db`; no
command performs live Procore calls or external writeback.

## Scope (at remediation time)
37 endpoints with full raw payloads → 37 primary + 41 child = 78 `procore_ep_` tables;
2,439 distinct field paths mapped with zero unmapped/unknown business fields. Evidence:
`docs/evidence/procore_endpoint_structured_projection_remediation/`.
