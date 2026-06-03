# Phase 08D — Prompt 02: Schema, Contracts, and Table Lifecycle Proof

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/schema-and-contract-proof.md`
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `92632a5` · **Schema:** V36 → **V37** (additive)
**Scope:** Data foundation only — additive migration + contracts + seeds + lifecycle + loader + tests. **No MCP server, transport, tool broker, CLI dispatch, builders, or gate evaluators** (Prompts 03–14). The substrate ships empty.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only posture preserved. The
ten new tables are **metadata-only** (hashes, counts, status, reason codes,
policy/schema version, evidence path, correlation id) and carry the full **twenty**
no-raw / no-writeback / no-direct-API / no-determination guard columns
`CHECK(<flag> = 0)`. Nothing here exposes raw SQLite, arbitrary SQL, raw files/Obsidian,
direct Graph/Procore, email send, calendar update, source-system writeback, raw
financial payloads, signed/download URLs, raw prompts, or raw responses. Additive only —
V1–V36 untouched.

---

## 2. V37 migration (`src/hb_assistant/store/migrator.py`)

`LATEST_SCHEMA_VERSION = 37`. New `V37_STATEMENTS` (ten `CREATE TABLE IF NOT EXISTS`)
applied idempotently and recorded as `schema_migrations` row
`(37, 'v37_phase_08d_mcp_bridge_schema')`, mirroring the V35/V36 pattern.

| # | Table | Key metadata columns |
|---|---|---|
| 1 | `second_brain_mcp_server_config_snapshots` | transport, config_hash, policy_version, schema_version |
| 2 | `second_brain_mcp_tool_registry_snapshots` | allowed_tool_count, denied_action_count, registry_hash |
| 3 | `second_brain_mcp_resource_registry_snapshots` | resource_count, registry_hash |
| 4 | `second_brain_mcp_prompt_registry_snapshots` | prompt_count, registry_hash |
| 5 | `second_brain_mcp_tool_call_receipts` | tool_name, decision∈(allowed,denied), workflow_wrapper, args_hash, result_hash, output_classification, source_count, result_count |
| 6 | `second_brain_mcp_denial_receipts` | requested_action, decision=denied (CHECK), denial_reason_code, request_hash |
| 7 | `second_brain_mcp_permission_audit_runs` | status, checks_json, finding_count |
| 8 | `second_brain_mcp_policy_gate_runs` | ok∈(0,1), status_counts_json, readiness_overstated∈(0,1) |
| 9 | `second_brain_mcp_claude_desktop_config_previews` | client_name, safe∈(0,1), transport, command_redacted, args_json, env_keys_json, config_hash |
| 10 | `second_brain_phase_08d_validation_runs` | ok∈(0,1), command/pass/warning/fail counts, validation_json |

**Twenty guard columns on every table** (all `INTEGER NOT NULL DEFAULT 0 CHECK(= 0)`):
`raw_email_body_persisted`, `raw_document_text_persisted`, `raw_calendar_payload_persisted`,
`raw_procore_payload_persisted`, `raw_financial_source_payload_persisted`,
`raw_prompt_persisted`, `raw_response_persisted`, `signed_url_persisted`,
`download_url_persisted`, `external_writeback_performed`, `graph_api_call_performed`,
`procore_api_call_performed`, `email_send_performed`, `calendar_update_performed`,
`source_system_writeback_performed`, `arbitrary_sql_performed`, `raw_store_access_performed`,
`financial_determination_performed`, `payment_decision_performed`,
`claim_or_entitlement_decision_performed`. Receipts persist **hashes only**
(`args_hash`/`result_hash`/`request_hash`) — no raw argument/result/content columns.

---

## 3. Contracts, seeds, loader, lifecycle

- **JSON contracts (dual-written, matching the 08C precedent):** 11 files in **both**
  `src/hb_assistant/resources/json/` (the tree the loader reads) and repo-root
  `resources/json/` — the 9 `phase_08d_mcp_*_contract.json`,
  `phase_08d_data_quality_gates_contract.json`, `phase_08d_validation_matrix.json`, and
  `claude_desktop_config_preview.schema.json`. Verbatim from the package.
- **YAML seeds:** 7 `phase_08d_mcp_*.seed.yaml` in the repo-canonical seed dir
  `resources/config/` (stdio-only fail-closed server policy pinned to schema 37;
  permission policy all `allow_*: false`; metadata-only receipt policy).
- **Loader:** `PHASE_08D_CONTRACT_FILES` + `load_phase_08d_contract` /
  `load_all_phase_08d_contracts` in
  `src/hb_assistant/construction/second_brain/contracts.py` (10 registered contracts; the
  Claude Desktop schema ships as a plain resource for Prompt 09).
- **Lifecycle registration** (`table_lifecycle_status_contract.json`, src-only):
  `table_count` 161 → **171**; ten new entries (`table_family: mcp_bridge_v37`,
  `phase_owner: 08D`, `lifecycle_status: operational_empty_expected`, `v: V37`).
- **Count-bump:** the 11 hard-coded `contract_table_count == 161` assertions across the
  schema/inventory tests updated to `171` (the global table total genuinely changed).

---

## 4. Validation commands + results (HEAD `92632a5` + working tree)

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (migrator, contracts, 2 new tests) | All checks passed |
| `mypy src` | Success — no issues in 259 source files |
| `pytest test_phase_08d_schema_v37 + test_phase_08d_contracts + test_data_quality_table_inventory + test_phase_08c_schema_v35 + test_phase_08b_schema_v34 + test_phase_08a_schema_v26 + test_phase_07d_data_quality_gates` | **67 passed** |
| `construction-agent validate --json` | `schema_version=37`, checks ok |
| `construction-agent data-quality table-inventory --json` | schema **37**, contract **171**, live **167**, `in_db_not_in_contract=[]`, ten 08D tables `source=contract` / `operational_empty_expected` |
| `second-brain data-quality phase-08c-no-writeback-proof --json` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain data-quality no-writeback-proof --json` (08A/08B) | `proof_passed=true` |

Direct migration check: a fresh `SQLiteMigrator(tmpdb).apply()` returns 37; all ten
tables exist and are empty; every guard column is present with `CHECK(=0)`; a
guard-violating insert and an out-of-enum `decision` both raise
`sqlite3.IntegrityError`; re-applying the migration is idempotent (single
`schema_migrations` row for v37); prior 08B/08C tables remain.

**Validation-subset rationale:** focused on the touched surfaces (V37 schema, the loader,
the lifecycle/inventory count) plus the three no-writeback proofs, per the
validation-minimum rule. The full matrix runs at Prompt 15.

---

## 5. Closed-phase evidence immutability

The three no-writeback proofs write into their phases' closed evidence bundles with a
fresh `repo_sha`/timestamp only. They were re-run to confirm `proof_passed=true`, then the
churned **closed** 08C bundle was restored to its committed state. The new V37 guards are
independently proven by `tests/test_phase_08d_schema_v37.py`. Pre-existing unrelated
working-tree drift (06/07a/08b/mvp/remediation) was left untouched.

---

## 6. Deferred / scope statement

- **MCP is not yet runtime-active.** No server entrypoint, stdio transport, tool broker,
  allowed/denied tool wrappers, resources, prompts, receipts writer, CLI surface, or gate
  evaluator exists — those are Prompts 03–14. The `mcp_exposure` data-quality gate remains
  `deferred_not_blocking` until the server/broker land.
- The ten tables are `operational_empty_expected`; nothing writes to them in this prompt.
- Contracts/seeds are **declarative** specifications consumed by later prompts.

**Verdict:** the Phase 08D data foundation (V37 schema + contracts + seeds + lifecycle +
loader + tests) is landed, additive, fully guarded, and green. Cleared for Prompt 03
(MCP server foundation).
