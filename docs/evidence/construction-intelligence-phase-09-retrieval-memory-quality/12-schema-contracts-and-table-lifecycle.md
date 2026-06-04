# Phase 09 Prompt 12 — Schema Contracts and Table Lifecycle (V38)

**Evidence artifact:** `phase_09_schema_contracts_and_table_lifecycle` · **Companion JSON:** `12-schema-contracts-and-table-lifecycle.json`
**Classification:** Phase 09 implementation — additive schema + contracts + table lifecycle (the first build prompt after preflight Prompts 00–11).
**Schema:** V37 → **V38** (additive; V1–V37 untouched). **Version:** 1.3.0.
**Posture:** additive, local-only, metadata-only, fail-closed. **No LlamaIndex / embeddings / vector / semantic-retrieval code** is introduced — the substrate ships empty and is populated by later Phase 09 prompts (13–39).
**Builds on:** records 120–130 (Prompts 00–11); the Phase 08D V37 MCP-bridge guard-column pattern; `retrieval/`/`memory/` subpackages.

---

## 1. Purpose

Phase 09 adds a semantic retrieval plane (LlamaIndex / embeddings / a vector index behind the existing
Retrieval Broker) plus memory-quality / consolidation and agent-performance agents. The package
implementation order requires the **schema and table-lifecycle records to exist before any runtime
code**. Prompt 12 lays that foundation: an additive **V38** migration creating the full nineteen-table
Phase 09 substrate, each table guarded at the SQLite layer, plus the contracts and a read-only status
surface that distinguish *intentionally empty* tables from *failed operational population*.

Guardrails honored: never persist raw source content / prompts / responses / tokens / secrets /
signed or download URLs / arbitrary SQL / unsafe paths / vector content; no Graph / Procore / email /
calendar / source-system / external writeback; no raw vector search through MCP; no final financial /
legal / contractual / claim / entitlement / payment / schedule / safety determinations.

## 2. What changed

### V38 migration (`src/hb_assistant/store/migrator.py`)
- `LATEST_SCHEMA_VERSION` 37 → **38**; `V38_STATEMENTS` (19 `CREATE TABLE IF NOT EXISTS` + 9
  `CREATE INDEX IF NOT EXISTS`) + an idempotent apply() block (`v38_phase_09_retrieval_memory_agent_schema`).
- The nineteen tables: 14 `second_brain_retrieval_*` (config snapshots, approved source manifests,
  vector-index runs/items, embedding-model evals, hybrid query runs/results, eval sets/cases/runs,
  benchmark runs, source-linked proof runs, unsupported-claim checks, context-budget runs),
  3 `second_brain_memory_*` (quality-review runs, consolidation candidates, consolidation review items),
  `second_brain_agent_performance_feedback_runs`, and `second_brain_phase_09_validation_runs`.
- Each table is metadata-only (ids, hashes, counts, labels, enums, refs, review tier, confidence class,
  freshness, status, policy/schema version) and carries the **full twenty-three guard columns**, each
  `INTEGER NOT NULL DEFAULT 0 CHECK(<col> = 0)`: the twenty no-raw / no-writeback / no-direct-api /
  no-determination guards plus the three Phase 09 guards `unsupported_claim_performed`,
  `raw_vector_content_persisted`, `semantic_retrieval_bypassed_policy`.

### Contracts
- `table_lifecycle_status_contract.json`: **171 → 190** tables; the nineteen new tables classified
  `placeholder_deferred` / `expected_population_status: empty` / `phase_owner: 09` / `v: V38`
  (families `retrieval_v38` ×14, `memory_v38` ×3, `agent_quality_v38` ×2). `table-inventory` reports
  **0 unmapped**.
- New `phase_09_table_lifecycle_contract.json` (`phase_09_table_lifecycle_contract/v1`): the richer
  Phase 09 lifecycle vocabulary (`blocked_preflight`, `operational_empty_expected`, `pilot_only`,
  `active_operational`, `validation_only`, `deprecated`, `deferred_future_phase`) mapping each of the
  nineteen tables to its lifecycle state + owning future prompt (index/query/eval/memory/agent →
  `blocked_preflight`; `second_brain_phase_09_validation_runs` → `validation_only`; none
  `active_operational` yet).

### Helper + CLI (read-only, fail-closed)
- `construction/second_brain/phase_09_schema.py`: `PHASE_09_V38_TABLES` (19), `PHASE_09_GUARD_COLUMNS`
  (23), `load_phase_09_lifecycle_contract()` (fail-closed), and `build_phase_09_schema_status_report()`
  — opens the DB `mode=ro`, verifies schema head (V38), every table present with all 23 guards
  (PRAGMA table_info), each table empty, and the contract loaded; returns `overall_status`.
- CLI `second-brain data-quality phase-09-schema-status --json` — exit 0 when `ready`, 3 otherwise
  (including a missing/invalid contract — fail-closed).

## 3. Key results (live)

- **`phase-09-schema-status`**: `overall_status = ready`, schema **38**, all 19 tables present, all 23
  guards present, all rows zero, contract loaded, `read_only = true`.
- **`table-inventory`**: schema **38**, contract **190**, `in_db_not_in_contract = []` (0 unmapped),
  19 new tables `placeholder_deferred`.
- **Migration**: additive + idempotent (re-apply → one `schema_migrations` row for 38; V1–V37 tables
  intact); each guard `CHECK(=0)` rejects a non-zero insert.
- **Operator DB**: schema advanced **37 → 38** adding the nineteen empty tables; **0 data rows** across
  the V38 tables — the operator data is unmutated (only additive schema, as intended).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**281** source files) ·
`pytest -m "not live and not integration and not manual"` → **3069 passed / 0 failed / 1 deselected**
(prior 3056 + 13 new V38/status tests) · `construction-agent validate` 4/4 schema **V38** ·
`construction-agent data-quality table-inventory` 190 contract / 0 unmapped ·
`construction-agent data-quality no-writeback-proof` `proof_passed=true` ·
`second-brain data-quality phase-08a-gates` / `phase-08b-gates` ok ·
`second-brain mcp no-raw-access` / `mcp no-writeback` `proof_passed=true` ·
`second-brain data-quality phase-09-schema-status` ready (exit 0).
`phase-08c-gates` deliberately skipped (its append-only ledger writes the operator DB — disclosed in
Prompts 02/05). Raw command captures + exit codes under `validation-outputs-prompt-12/`.

## 5. Guardrails & stop conditions

Read-only over the operator DB (`mode=ro`); additive schema only; metadata-only tables guarded by 23
`CHECK(=0)` columns; no LlamaIndex / embeddings / vector / semantic-retrieval code; no external
writeback; no determinations; review tier / confidence class / source refs / freshness preserved in the
table column design. No stop condition triggered (no raw-content persistence, no writeback, no
unapproved indexing, no semantic retrieval bypassing Research Packet / Evaluation).

## 6. Deferred / owning prompts

The nineteen tables ship empty by design; population is owned by later Phase 09 prompts (per
`phase_09_table_lifecycle_contract.json`): index/config 13–14, manifests 15, vector build 18–19,
hybrid broker 20, eval 24, benchmark 25–26, context-budget 27, claim/hallucination 28–29, source-linked
proof 34, memory 30–31, agent feedback 32, validation 36–39.
