# 57 — Phase 08A: Second-Brain Schema (V26) & Contracts

**Status:** Implemented (Phase 08A Prompt 02). Additive **V26** migration over V25 (no migration of
V1–V25). Schema + machine-readable contracts only — **no builders, no CLI surface, no runtime**. All
21 tables ship empty; later 08A prompts populate them.

## Scope

V26 lands the local-first second-brain substrate: the 16 base tables from
`05_SCHEMA_AND_MIGRATION_PLAN.md` plus 5 addendum tables for the Final-Update operating model
(research → evaluation → synthesis → capture, review tiers, feedback, preference learning, memory
quality). Every table is metadata / bounded-redacted-output only.

### Tables (21)

| Group | Tables | Populating prompt |
|---|---|---|
| Config | `second_brain_runtime_config_receipts` | 03 |
| Obsidian index | `obsidian_index_manifests`, `obsidian_index_entries` | 05 |
| Retrieval | `retrieval_query_receipts`, `retrieval_context_refs` | 07 |
| Query tools | `query_tool_receipts` | 06 |
| Chat | `interactive_chat_sessions`, `interactive_chat_message_receipts` | 08/09 |
| Memory | `long_term_memory_items`, `long_term_memory_source_refs`, `long_term_memory_quality_signals`, `memory_update_candidates`, `memory_update_reviews` | 10 |
| Pipeline (addendum) | `second_brain_research_packets`, `second_brain_evaluation_runs` | 07+ |
| Feedback (addendum) | `second_brain_operator_feedback`, `second_brain_operator_preference_profiles` | 10+ |
| Daily brief | `daily_brief_runs`, `daily_brief_source_refs` | 11/12 |
| Scheduling | `launchd_schedule_previews` | 13 |
| Validation | `phase_08a_validation_runs` | 16 |

**Naming note:** the package SQL proposed `sqlite_query_tool_receipts`, but SQLite reserves the
`sqlite_` table-name prefix (the package was never migrated locally). Renamed to `query_tool_receipts`.

### Guardrails baked into the schema

- **No-raw / no-writeback guard columns** with `CHECK(col = 0)` on every table that can hold a
  summary/receipt — the relevant subset of `raw_email_body_persisted`, `raw_document_text_persisted`,
  `raw_calendar_payload_persisted`, `raw_prompt_persisted`, `raw_response_persisted`,
  `retrieved_context_persisted`, `signed_url_persisted`, `download_url_persisted`,
  `arbitrary_sql_allowed`, `external_writeback_performed`. Only bounded/redacted summaries, hashes,
  counts, enums, reason codes, origin IDs, and source refs are storable.
- **Review tiers** ride on output-bearing tables: `review_tier INTEGER CHECK(… IN (1,2,3))` +
  `review_tier_reason_code` on `retrieval_query_receipts`, `daily_brief_runs`,
  `memory_update_candidates`, `second_brain_research_packets`, `second_brain_evaluation_runs`,
  `second_brain_operator_feedback`. Research packets default to **Tier 3 / pending_review / advisory**
  (most conservative). `advisory_classification CHECK IN ('advisory','actionable')` separates advisory
  intelligence from actionable recommendations.
- **Degradation**: `context_quality_class` + `degradation_mode` on retrieval/research/evaluation so
  insufficient context degrades gracefully instead of overstating.
- **Memory provenance**: `origin_id` + `provenance_class` on memory items/candidates;
  `long_term_memory_quality_signals` captures origin/provenance/quality/freshness/conflict/feedback.
- **Brief linkage**: `daily_brief_runs.research_packet_id` + `evaluation_run_id` tie briefs to their
  research packet and evaluation run.

## Contracts

A read-only loader `construction/second_brain/contracts.py` (`PHASE_08A_CONTRACT_FILES`,
`load_phase_08a_contract`, `load_all_phase_08a_contracts`) mirrors the 07D loader. Installed now (the
entities land in V26): `second_brain_runtime_contract`, `source_reference_contract`,
`long_term_memory_contract`, `memory_update_candidate_contract`, `research_packet_contract`,
`evaluation_criteria_contract`, `operator_feedback_contract`, `operator_preference_profile_contract`,
`review_tier_contract`, `memory_quality_signal_contract`.

`review_tier_contract.json` encodes the hard posture: **Tier 3 is never an accepted fact / never
auto-accepted** (`tier_3_is_accepted_fact: false`, `never_auto_accept_tiers: ["tier_3"]`) and
**sensitive/high-impact (+ legal/contractual/claim/personnel/safety/financial/…) defaults to mandatory
review**.

**Deferred to owning prompts** (not installed now, to avoid the G-07D-02 "contract references an
unbuilt command/surface" drift): retrieval_policy (04), obsidian_index_manifest (05),
sqlite_query_tool (06), interactive_query (08), chat_session_memory (09), daily_brief (11–12),
phase_08a_data_quality_gates (14), phase_08a_validation_matrix (16).

## Lifecycle inventory

All 21 tables registered in `table_lifecycle_status_contract.json` (`table_family:"second_brain_08a"`,
`phase_owner:"08A"`, `v:"V26"`, `operational_empty_expected`); `table_count` 120 → 141. The two
hard-coded inventory count asserts updated 120 → 141.

## Why this is safe against the existing proof

`build_data_quality_no_writeback_proof` scans explicit per-phase table sets, so the new V26 tables are
not yet scanned — the proof stays green. A Phase 08A arm is added later (Prompt 15). The guard
`CHECK(col = 0)` constraints already enforce the no-raw / no-writeback invariant at the DB layer.

## Validation

ruff / `mypy src` (192 files) / compileall clean; pytest **2285 passed, 1 deselected** (new
`tests/test_phase_08a_schema_v26.py` + `tests/test_phase_08a_contracts.py`; one pre-existing 07D
schema assertion loosened from `== 25` to `>= 25`). `construction-agent validate` 4/4 (schema **26**);
`data-quality table-inventory` `contract_table_count=141` with all 21 V26 tables
`operational_empty_expected` and `in_db_not_in_contract=[]`; `data-quality no-writeback-proof`
`proof_passed=true`.

## Files

- `src/hb_assistant/store/migrator.py` (V26: bump + `V26_STATEMENTS` + apply-block).
- `src/hb_assistant/resources/json/` (10 contracts) + `table_lifecycle_status_contract.json` (21 entries, count).
- `src/hb_assistant/construction/second_brain/__init__.py` + `contracts.py` (loader).
- `tests/test_phase_08a_schema_v26.py`, `tests/test_phase_08a_contracts.py` (new);
  `tests/test_data_quality_table_inventory.py`, `tests/test_phase_07d_data_quality_gates.py`,
  `tests/test_phase_07d_schema_v25.py` (count/version assertions updated).

See `docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/02-schema-and-contract-proof.md`.
