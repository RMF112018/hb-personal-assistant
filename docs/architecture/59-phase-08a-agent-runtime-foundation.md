# 59 — Phase 08A: Agent Runtime Foundation (Prompt 02 Addendum)

Status: implemented (Phase 08A Prompt 02 Addendum). Builds on records 57 (V26
schema + contracts) and 58 (dependency/config + Claude adapter). Foundation only,
local-first, no-writeback, no new SQLite tables.

## Purpose

The package overlay (`README_OVERLAY.md` + `24_AGENT_ARCHITECTURE_AND_MCP_HANDOFF.md`)
introduces a service-agent architecture: nine internal agents (A01–A09) that are
deterministic or model-assisted **service modules behind controller policy** —
not autonomous actors. This prompt lays the foundation: the agent registry
contract + seed + loader, internal `AgentResult` / `AgentRunReceipt` structures,
agent policy validation, two read-only CLI commands, and two JSON evidence proofs.
No agent executes, nothing is persisted, and **MCP is not implemented** (deferred
to Phase 08D).

## Contracts (`src/hb_assistant/resources/json/`, registered in `second_brain/contracts.py`)

- `phase_08a_agent_registry_contract.json` — `required_agent_fields`,
  `required_phase_08a_agents` (the 9 ids), guardrails.
- `phase_08a_agent_tool_contract.json` — `tool_groups`, global `denied_tool_groups`,
  `mcp_future_exposure_rule` ("Expose workflows only; never expose stores.").
- `phase_08a_model_profile_contract.json` — five model profiles
  (`deterministic_router`, `fast_summary`, `default_reasoning`, `deep_reasoning`,
  `evaluator`) + `persistence_policy` (persist hashes/token-counts only; never raw
  prompt/response).

## Seeds (`resources/config/`, loaded via `PathPolicy.resolve_repo_root()`)

- `phase_08a_agent_registry.seed.yaml` — the nine agents A01–A09, each with
  `agent_id`, `phase_owner`, `enabled`, `purpose`, `allowed_tool_groups`,
  `denied_tool_groups`, `default_model_profile`, `review_policy`,
  `output_contract`, `receipt_required`.
- `phase_08a_model_profiles.seed.yaml` — operative per-profile config (provider/
  model/temperature/output-mode), each asserting
  `raw_prompt_persisted`/`raw_response_persisted: false`.

**Repo-truth reconciliation:** the registry contract lists `output_contract` as a
required agent field but the package seed omitted it; an explicit per-agent
`output_contract` label was added so the registry validates against its own
contract. Labels are logical (the agent's output shape) and need not resolve to an
installed JSON contract this prompt.

## Agents A01–A09 (registered as internal service descriptors)

| Agent | Purpose | Default profile | Review policy |
| --- | --- | --- | --- |
| second_brain_orchestrator_agent | route + enforce research→evaluate→synthesize→capture | deterministic_router | tiered_review_required |
| research_packet_agent | assess context quality before synthesis | fast_summary | advisory_only |
| retrieval_source_broker_agent | bounded source-linked retrieval (no model) | none | source_linked_context_only |
| answer_synthesis_agent | source-linked advisory answers | default_reasoning | no_high_impact_determinations |
| output_evaluation_agent | score outputs before present/apply | evaluator | block_on_policy_failure |
| daily_brief_agent | daily brief + handoff payload | default_reasoning | evaluated_before_apply |
| memory_curator_agent | long-term memory candidates | default_reasoning | source_linked_memory_only |
| operator_preference_agent | reviewed operator preferences | fast_summary | preferences_never_override_safety |
| review_triage_agent | group/explain review load by tier | fast_summary | tier_3_mandatory_review |

## Code (`construction/second_brain/agents/`, strict-mypy)

- `models.py` — `AgentDefinition`, `AgentRegistry` (extra=forbid, no-duplicate-id
  validator); internal `AgentResult` (ok, status, agent_id, receipt_id,
  source_refs, review_tier_summary, warnings, payload) and `AgentRunReceipt`
  (agent_run_id, agent_id, origin_id, request_kind, mode, status,
  review_tier_summary, warnings, source_refs, evaluation_result_id, created_utc) —
  **in-memory only**, no DB.
- `loader.py` — `load_agent_registry()` / `load_model_profiles()` mirroring
  `construction/policy/loader.py` (seed → repo override → explicit → env;
  `HB_SECOND_BRAIN_AGENT_REGISTRY`, `HB_SECOND_BRAIN_MODEL_PROFILES`).
- `policy.py` — `validate_agent_registry()` (required fields present; all 9 agents
  present + enabled; `allowed ⊆ tool_groups`; `allowed ∩ (denied ∪ global_deny) =
  ∅`; default profile known; receipt_required true) + `build_agent_registry_proof()`
  / `build_agent_tool_policy_proof()` (deterministic evidence proofs).

The global `denied_tool_groups` (arbitrary_sql, raw_sqlite_file, raw_filesystem,
raw_obsidian_vault, direct_graph_api, direct_procore_api, email/calendar/
sharepoint/procore mutate, external_writeback) are enforced platform-wide — no
agent may allow any of them. Per-agent `denied_tool_groups` are explicit highlights
(not the full global list).

## CLI (`hb-assistant second-brain agents`)

- `agents registry --json` — list the nine agents (redacted fields) + count.
- `agents status --json` — agent/enabled counts, contract versions,
  `registry_valid`/`tool_policy_valid`, violations count, `tier3_handling_visible`,
  schema version, guardrails (`mcp_implemented: false`). Exit 0 valid / 3 invalid
  (fail-closed). Offline, read-only, no raw content.

## Out of scope (later prompts)

Five agent SQLite persistence tables (V27, agent-runtime prompt); any agent
execution / model calls / receipt writing; MCP (Phase 08D); the `phase-08a-gates`
/ `phase-08a-no-writeback-proof` arms (owning prompts). Schema head stays V26;
lifecycle contract stays 141 tables.
