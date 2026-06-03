# 106 — Phase 08D Schema, Contracts, and Table Lifecycle (Prompt 02)

**Baseline**: Post-08D-P00/P01 evidence at `92632a5` (on 08C closeout `2052f93`). Schema **V36** / 161 contract tables / 157 live pre this prompt. Additive **V37** only.

**Objective** (per prompt): Add the additive V37 schema for the ten Phase 08D local-MCP-bridge metadata tables (from package), all twenty mandatory hard guard columns `CHECK(... = 0)` on every table, the MCP JSON contracts + YAML seeds, the contract loader, lifecycle/inventory registration + version/count asserts, and tests; generate `schema-and-contract-proof.md`. **No MCP server, transport, tool broker, CLI dispatch, builders, or gate evaluators** — data foundation only; the substrate ships empty.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/schema-and-contract-proof.md`
- `docs/architecture/106-phase-08d-mcp-schema-contracts-and-table-lifecycle.md` (this)
- `tests/test_phase_08d_schema_v37.py`, `tests/test_phase_08d_contracts.py`
- `src/hb_assistant/store/migrator.py` (V37)
- `src/hb_assistant/resources/json/phase_08d_*.json` (+ repo-root `resources/json/` mirror) + `resources/config/phase_08d_mcp_*.seed.yaml`
- `src/hb_assistant/construction/second_brain/contracts.py` (loader), `table_lifecycle_status_contract.json` (registration), and the eleven schema/inventory count-bump test edits.

## Tables Added (V37)
All ten are metadata-only (hashes, counts, status, reason codes, policy/schema version, evidence path, correlation id):
- second_brain_mcp_server_config_snapshots
- second_brain_mcp_tool_registry_snapshots
- second_brain_mcp_resource_registry_snapshots
- second_brain_mcp_prompt_registry_snapshots
- second_brain_mcp_tool_call_receipts (decision∈allowed/denied; args_hash/result_hash only)
- second_brain_mcp_denial_receipts (decision=denied CHECK; request_hash only)
- second_brain_mcp_permission_audit_runs
- second_brain_mcp_policy_gate_runs (ok∈0/1; readiness_overstated∈0/1)
- second_brain_mcp_claude_desktop_config_previews (safe∈0/1; command_redacted)
- second_brain_phase_08d_validation_runs

**Mandatory guards** (every table, all `INTEGER NOT NULL DEFAULT 0 CHECK(= 0)`):
raw_email_body / raw_document_text / raw_calendar_payload / raw_procore_payload /
raw_financial_source_payload / raw_prompt / raw_response (persisted),
signed_url / download_url (persisted), external_writeback / graph_api_call /
procore_api_call / email_send / calendar_update / source_system_writeback /
arbitrary_sql / raw_store_access / financial_determination / payment_decision /
claim_or_entitlement_decision (performed). Receipts persist hashes only — no raw
argument/result/content columns.

## Contracts & Seeds
- **JSON contracts** (dual-written to both `src/hb_assistant/resources/json/` and repo-root `resources/json/`, matching the 08C precedent): the nine `phase_08d_mcp_*_contract.json`, `phase_08d_data_quality_gates_contract.json`, `phase_08d_validation_matrix.json`, and `claude_desktop_config_preview.schema.json`.
- **YAML seeds** (`resources/config/`): server policy (stdio-only, fail-closed, schema 37), allowed/denied tools, permission policy (all `allow_*: false`), prompts, receipt policy (metadata-only), resources.
- **Loader**: `PHASE_08D_CONTRACT_FILES` + `load_phase_08d_contract` / `load_all_phase_08d_contracts` (10 registered; Claude Desktop schema is a plain resource for Prompt 09).

## Lifecycle / Inventory
`table_lifecycle_status_contract.json` `table_count` 161 → **171** with ten `phase_owner: 08D` / `mcp_bridge_v37` / `operational_empty_expected` entries. `construction-agent data-quality table-inventory` now reports schema 37 / contract 171 / live 167 / `in_db_not_in_contract=[]`. The eleven hard-coded `contract_table_count == 161` test asserts updated to `171`.

## Boundary (data foundation only)
No server entrypoint, stdio transport, tool broker, allowed/denied wrappers, resources, prompts, receipt writer, CLI surface, or gate evaluator is added (Prompts 03–14). The `mcp_exposure` data-quality gate stays `deferred_not_blocking` until the server/broker land. Additive only; V1–V36 untouched.

## Validation
compileall exit 0; `ruff check` clean (touched); `mypy src` clean (259 files); focused pytest **67 passed**; `validate` schema 37; `table-inventory` 171/167 clean; 08C / construction-agent / 08A-08B no-writeback proofs all `proof_passed=true` (closed 08C bundle restored afterward). Full matrix deferred to Prompt 15.
