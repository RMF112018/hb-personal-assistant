# 10 — Runtime Plan/Schema Parity Hotfix (V48)

Hotfix for the production apply crash:
`sqlite3.OperationalError: table procore_ep_prime_contracts has no column named architect`.

## Root cause (two defects)
1. **Object-container promotion.** `projection_registry._classify_path` used
   `_has_scalar_type`, which counted `"null"` as a scalar. A field that is an object in some
   payloads and `null` in others (`object|null`) was misclassified as a scalar leaf and
   promoted to a literal column. The committed registry had **56** such container columns
   (`architect`, `submittal_package`, `submittal_workflow_template`, `location`, `assignee`,
   `cost_code`, `trade`, `type`, …) alongside their correctly-decomposed scalar children.
   The engine tried to INSERT the container column, which the physical table lacked.
2. **Column-level schema drift (no parity gate).** The registry was regenerated after
   physical tables were created, so it referenced decomposed child columns (the 12
   `submittal_package_*` / `submittal_workflow_template_*`) that existing tables lacked, and
   `CREATE TABLE IF NOT EXISTS` cannot add columns. `projection-audit` checked path
   coverage but not runtime insert-column/physical-schema parity.

## Fix
- **Generation:** object-node detection now uses a non-null scalar set
  (`_NON_NULL_SCALARS`); `object|null` containers are `structural` (lossless in
  `payload_sidecar_json`), never columns; scalar children remain columns. Registry
  regenerated — surgical diff: **56 container columns removed, 0 added**, 62 dest flips
  `column → structural`; decomposed children and the 78-table set unchanged.
- **V48 migration:** `LATEST_SCHEMA_VERSION 47 → 48`. The V48 block reconciles physical
  schema to the registry via additive `ALTER TABLE ADD COLUMN` for missing curated columns,
  run **unconditionally** (outside the version-48 gate) so it self-heals drift on every
  `apply()` — proven by a test that drops a column on an at-head DB and re-applies.
- **Parity gate:** `runtime_plan_schema_mismatches` / `projection_schema_audit` verify every
  planned primary + child insert column exists; folded into `projection-audit` `ok` and a
  new `projection-schema-audit` CLI command.
- **Hard pre-write guard:** `projection-reprocess --apply` verifies parity before any write
  and returns a structured `schema_parity_broken` receipt — never `sqlite3.OperationalError`.

## DB-copy validation (no production mutation)
- Production sha256 **before**: `a24b6ab15982fa71ba951a54d1aaeead0a4e4f910f126150bec6ef1a4ac3a8f2`
- Production sha256 **after**:  `a24b6ab15982fa71ba951a54d1aaeead0a4e4f910f126150bec6ef1a4ac3a8f2` — **UNCHANGED ✓**
- On a `/tmp` copy (V47, drifted):
  - parity mismatches **before** reconcile: **12** (the `submittal_package_*` children;
    `architect` is no longer a mismatch because the regenerated registry no longer
    references it).
  - `SQLiteMigrator.apply()` → head **48**; parity mismatches **after** reconcile: **0**.
  - `projection-schema-audit` → `ok=true`, 0 mismatches.
  - `projection-reprocess --apply` (enforce) → **succeeded, no OperationalError**: 10,105
    primary + 22,089 child rows, 0 degraded.
  - `projection-audit` → `ok=true`, `unknown_business_field_paths=0`,
    `runtime_plan_schema_mismatches=0`.
- All 13 originally reported mismatches resolved (1 architect via the registry fix, 12
  submittal via V48 ALTER reconciliation).

## Verification
- `pytest` (full-raw ingestion + structured-analytics foundation + remediation/hotfix
  regression tests) green; lifecycle/data-quality/schema suites green (contract table_count
  stays 347 — no tables added). `ruff check` clean; `mypy` no issues.
