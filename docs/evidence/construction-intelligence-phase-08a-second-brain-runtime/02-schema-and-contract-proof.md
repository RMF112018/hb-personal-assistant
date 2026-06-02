# 02 — Second-Brain Schema (V26) & Contract Proof (Phase 08A Prompt 02)

Additive **V26** migration + foundational Phase 08A contracts. Schema-and-contracts only — no
builders, no CLI surface, no runtime, no policy YAML seeds. All 21 tables ship **empty**. Baseline at
prompt start: HEAD `c2656e1…`, schema V25, 120 contract tables.

## V26 tables (21) — guard-column matrix

Guard columns are **per-table** (the subset relevant to what each table can hold); all are
`CHECK(col = 0)`. `RC` = retrieved_context_persisted, `SQL` = arbitrary_sql_allowed,
`WB` = external_writeback_performed, `URLs` = signed_url + download_url, `bodies` = raw_email/document/
calendar, `pr/rs` = raw_prompt/raw_response.

| Table | Guard columns | Other safety |
|---|---|---|
| second_brain_runtime_config_receipts | bodies, pr, rs, RC, URLs, SQL, WB | mode CHECK |
| obsidian_index_manifests | bodies, pr, rs, RC, URLs, SQL, WB | mode CHECK |
| obsidian_index_entries | (refs/hashes only) | path redacted+hashed; UNIQUE |
| retrieval_query_receipts | bodies, pr, rs, RC, URLs, SQL, WB | review_tier CHECK(1,2,3); advisory CHECK |
| retrieval_context_refs | (refs only) | — |
| query_tool_receipts | SQL, WB | renamed from `sqlite_query_tool_receipts` (reserved prefix) |
| interactive_chat_sessions | pr, rs, RC | bounded_summary_redacted only |
| interactive_chat_message_receipts | pr, rs | hashes only |
| long_term_memory_items | pr, rs, RC | review_status CHECK; origin/provenance |
| long_term_memory_source_refs | (refs only) | — |
| long_term_memory_quality_signals | pr, rs | signal_type CHECK |
| memory_update_candidates | pr, rs | review_required default 1; review_tier CHECK; status CHECK |
| memory_update_reviews | (decision only) | decision CHECK |
| second_brain_research_packets | bodies, pr, rs, RC, URLs, SQL, WB | review_tier default 3; review_status/advisory CHECK |
| second_brain_evaluation_runs | pr, rs, RC, WB | review_tier CHECK; mode CHECK |
| second_brain_operator_feedback | pr, rs | feedback_class CHECK; review_tier CHECK |
| second_brain_operator_preference_profiles | pr, rs | scope CHECK; UNIQUE(scope,scope_key,preference_key) |
| daily_brief_runs | bodies, pr, rs, RC, URLs, WB | review_tier CHECK; research_packet_id/evaluation_run_id links |
| daily_brief_source_refs | (refs only) | — |
| launchd_schedule_previews | WB | mode CHECK = 'dry_run' |
| phase_08a_validation_runs | pr, rs, WB | — |

Tested: every guard-named column declares `CHECK(=0)` (parametrized); a nonzero guard insert raises
IntegrityError; `review_tier=4` rejected / `=2` accepted; research packet defaults Tier 3 /
pending_review / advisory; memory candidate defaults review_required=1; preference UNIQUE enforced;
V1–V25 tables intact; migration idempotent at V26.

## Contracts installed (`src/hb_assistant/resources/json/`)

Loader: `construction/second_brain/contracts.py`. Installed (entities land in V26):
`second_brain_runtime_contract`, `source_reference_contract`, `long_term_memory_contract`,
`memory_update_candidate_contract`, `research_packet_contract`, `evaluation_criteria_contract`,
`operator_feedback_contract`, `operator_preference_profile_contract`, `review_tier_contract`,
`memory_quality_signal_contract`.

### Deferred contracts → owning prompt (NOT installed now)

| Contract | Owning prompt | Reason |
|---|---|---|
| retrieval_policy | 04 | references retrieval runtime not built |
| obsidian_index_manifest | 05 | indexing runtime not built |
| sqlite_query_tool | 06 | query-tool allowlist runtime not built |
| interactive_query | 08 | query CLI not built |
| chat_session_memory | 09 | chat runtime not built |
| daily_brief | 11–12 | brief runtime not built |
| phase_08a_data_quality_gates | 14 | 08A gates not wired |
| phase_08a_validation_matrix | 16 | references `second-brain …` CLI commands not built — installing now would re-create the G-07D-02 "matrix points at unbuilt command" drift remediated in Prompt 01 |

## Review-tier posture proof (Final-Update requirements)

`review_tier_contract.json` (tested in `tests/test_phase_08a_contracts.py`):
- **No Tier 3 item treated as accepted fact:** `tier_3_is_accepted_fact: false`,
  `never_auto_accept_tiers: ["tier_3"]`, `tiers.tier_3.auto_accept_as_fact: false`,
  guardrail `tier_3_never_auto_accepted: true`.
- **Sensitive/high-impact ⇒ mandatory review:** `mandatory_review_for` includes `sensitive_high_impact`
  (+ legal/contractual/claim/personnel/safety/financial/entitlement/schedule_impact/model_only/
  low_confidence/unsupported/stale/conflict); guardrail `sensitive_high_impact_defaults_to_mandatory_review: true`.
- **Tiers + reason codes appear in schema output:** `review_tier` + `review_tier_reason_code` columns on
  all output-bearing V26 tables; every `reason_codes` value maps to a defined tier.
- Memory: `default_review_required: true`, `silent_acceptance_allowed: false`.
- Source references: `forbidden_fields` includes signed_url/download_url/token/secret/raw_body.

## Validation outputs

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed |
| `mypy src` | 0 | no issues in 192 source files (scope partial-by-config) |
| `pytest -m "not live and not integration and not manual"` | 0 | **2285 passed, 1 deselected** (incl. new schema/contract tests; one pre-existing 07D assertion loosened `==25`→`>=25`) |
| `construction-agent validate --json` | 0 | 4/4, **schema_version=26** |
| `construction-agent data-quality table-inventory --json` | 0 | `contract_table_count=141`, 21 V26 tables `operational_empty_expected`, `in_db_not_in_contract=[]` (`operational_empty_expected` 27→48) |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` (unchanged; V26 tables not yet in proof scope — 08A arm deferred to Prompt 15) |

## No-raw self-attestation

No raw email/document/calendar bodies, raw prompts/responses, retrieved context, signed/download URLs,
tokens, secrets, or private payload values appear in the V26 schema, the installed contracts, or this
evidence. Persisted columns are bounded/redacted summaries, hashes, counts, enums, reason codes,
origin IDs, and source refs only. The DB-layer `CHECK(col = 0)` guards enforce this for any future
writer. No external writeback / arbitrary SQL / model API path is introduced.

## Next-prompt readiness

V26 schema + foundational contracts are in place. **08A Prompt 03 (dependency/config + Claude
adapter)** may proceed. Deferred contracts install with their owning prompts (table above).
Coverage warning: reflects local repo state on 2026-06-02; re-verify if the branch moves.
