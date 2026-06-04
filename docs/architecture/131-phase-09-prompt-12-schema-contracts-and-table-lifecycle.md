# 131 — Phase 09 Prompt 12: Schema Contracts and Table Lifecycle (V38)

**Status:** Implementation — additive **V38** schema + contracts + table lifecycle (the first build prompt after preflight Prompts 00–11). Schema-only; no retrieval runtime.
**Schema:** V37 → **V38** (additive; V1–V37 untouched, idempotent). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `8703bfa`, Prompt 11 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/12-schema-contracts-and-table-lifecycle.md` (+ `.json`, `validation-outputs-prompt-12/`).
**Builds on:** records 120–130 (Prompts 00–11); the V37 Phase 08D guard-column pattern (`migrator.py`); `construction/data_quality/table_inventory.py`; the `retrieval/`/`memory/` subpackages.

---

## 1. Purpose

Phase 09 will add a semantic-retrieval plane (LlamaIndex / embeddings / a vector index behind the
existing Retrieval Broker) plus memory-quality / consolidation and agent-performance agents. The
package's implementation contract requires schema and table-lifecycle records to land **before** any
runtime code (define contracts → additive schema → dry-run surfaces → proofs). Prompt 12 establishes
that foundation: the full nineteen-table V38 substrate, guarded at the SQLite layer, plus the lifecycle
contracts and a read-only status surface — explicitly with **no LlamaIndex / embeddings / vector /
semantic-retrieval code** (the substrate ships empty; later prompts populate it).

## 2. Design

### Migration (additive, guarded, empty)
`migrator.py` bumps `LATEST_SCHEMA_VERSION` 37→38 and adds `V38_STATEMENTS` (19 `CREATE TABLE IF NOT
EXISTS` + 9 `CREATE INDEX IF NOT EXISTS`) with an idempotent apply() block following the V37/V35
unconditional-create-then-guard-insert idiom. Every table is metadata-only (TEXT PK, `created_at_utc`,
`policy_version`, `schema_version`, then minimal identity/refs/labels) and carries the **full
twenty-three guard columns** `INTEGER NOT NULL DEFAULT 0 CHECK(<col> = 0)`. V38 extends the V37
twenty-guard block with three Phase 09 guards: `unsupported_claim_performed`,
`raw_vector_content_persisted`, `semantic_retrieval_bypassed_policy` — encoding, at the storage layer,
that the retrieval plane may never persist a vector body, emit an unsupported claim, or bypass policy.

Minimal skeleton columns (not full data shapes) are deliberate: later prompts (13–39) add their real
columns via further additive migrations, so a thin skeleton minimizes churn while fixing table names,
guard columns, and lifecycle classification now.

### Two lifecycle contracts
- The canonical `table_lifecycle_status_contract.json` (single source consumed by `table-inventory`)
  grows 171→190 with the nineteen tables classified `placeholder_deferred` / `phase_owner 09` / `V38`
  — keeping the inventory at **0 unmapped** the moment the migration lands (atomic with it).
- A new `phase_09_table_lifecycle_contract.json` captures the richer Phase 09 lifecycle vocabulary
  (`blocked_preflight` … `deferred_future_phase`) and maps each table to its lifecycle state + owning
  prompt — distinguishing *intentionally empty* from *failed population*, which the coarse
  `placeholder_deferred` cannot.

### Read-only status surface
`construction/second_brain/phase_09_schema.py` exposes `PHASE_09_V38_TABLES` (19),
`PHASE_09_GUARD_COLUMNS` (23), the fail-closed `load_phase_09_lifecycle_contract()`, and
`build_phase_09_schema_status_report()` — opens the DB `mode=ro`, verifies schema head, every table's
presence + all 23 guards (PRAGMA table_info), row-emptiness, and the contract, and returns
`overall_status`. CLI `second-brain data-quality phase-09-schema-status --json` (exit 0 ready / 3
not-ready or contract failure).

## 3. Verification

Migration smoke (temp DB): `apply() == 38`, 19 tables, 0 rows, idempotent (one v38 `schema_migrations`
row), each guard `CHECK(=0)` rejects a non-zero insert. Live: `phase-09-schema-status` ready;
`table-inventory` 190 / 0 unmapped / schema 38. Full matrix: compileall/ruff clean, mypy 281 files,
pytest **3069 passed** (3056 + 13 new), `construction-agent validate` 4/4 V38, 08A/08B/MCP gates +
no-raw/no-writeback proofs pass. Operator DB advanced schema 37→38 with **0 data rows** in the V38
tables (additive-only). `phase-08c-gates` skipped (mutating append-only ledger, disclosed Prompts 02/05).

## 4. Guardrails & stop conditions

Additive schema only (V1–V37 immutable); metadata-only tables guarded by 23 `CHECK(=0)` columns;
helper/CLI strictly read-only (`mode=ro`), DB unmutated; no LlamaIndex/embeddings/vector/semantic code;
no external writeback; no determinations; review tier / confidence class / source refs / freshness
preserved in the column design. No stop condition triggered.
