# 60 — Phase 08A: Model-Profile Enforcement + Model-Call Receipts (Synthesized Prompt 03)

Status: implemented (Phase 08A Synthesized Prompt 03 — gap-fill). Builds on records
58 (dependency/config/Claude adapter) and 59 (agent runtime foundation). Local-first,
no-writeback, no raw content, no new SQLite tables.

## Purpose

The Synthesized Package's Prompt 03 ("Dependency, Configuration, Claude Adapter, and
Model Profiles") restates objectives already satisfied by records 58/59 (the
`anthropic` extra, second-brain config, mock/live Claude adapter, model-profile
contract + seed + loader). This record covers the three genuine gaps it added:

1. **Model-profile contract enforcement** — validate the model-profiles seed against
   `phase_08a_model_profile_contract.json`, not just the agent registry's profile
   references.
2. **Metadata-only model-call receipts** — an in-memory `ModelCallReceipt`.
3. The three exact-named evidence artifacts.

## Model-profile enforcement (`construction/second_brain/agents/policy.py`)

- `validate_model_profiles(seed, contract)` — confirms all five contract profiles
  exist in the seed and that the **intent map** holds:
  - `deterministic_router` → no default model (provider `none_by_default`)
  - `fast_summary` → `claude-haiku-4-5`
  - `default_reasoning` → `claude-sonnet-4-6`
  - `deep_reasoning` → `claude-opus-4-8`
  - `evaluator` → `output_mode: checklist_json`

  It also enforces the no-raw persistence posture: contract
  `persistence_policy.persist_raw_prompt`/`persist_raw_response` are false and every
  seed profile sets `raw_prompt_persisted`/`raw_response_persisted: false`.
- `build_agent_model_profile_proof()` → `agent-model-profile-proof.json`
  (`proof_passed`, `profile_count`, `intent_map`, `no_raw_persistence`, guardrails
  with `mcp_implemented: false`, violations).

## Metadata-only model-call receipts (`construction/second_brain/reasoning.py`)

- `ModelCallReceipt` (Pydantic, extra=forbid) — `model_receipt_id`, `agent_run_id?`,
  `model_profile_id`, `model_id?` (None for the deterministic router),
  `input_context_hash`, `output_hash`, `input_token_count`, `output_token_count`,
  `temperature?`, `effort?`, `created_utc`. **No raw fields.** In-memory only;
  mirrors the future `second_brain_agent_model_receipts` row (deferred to V27).
- `build_model_call_receipt(...)` — sha256-hashes the input context and output text
  (never storing them), approximates token counts offline (~4 chars/token), stamps a
  `uuid4` id and UTC timestamp.
- `build_claude_adapter_mock_proof()` → `claude-adapter-mock-proof.json` — runs a
  representative envelope through `MockClaudeAdapter`, attaches a metadata-only
  receipt, and asserts `live_called: false` and no raw content.

## Guardrail posture

- No raw prompts/responses/URLs/secrets persisted — receipts carry sha256 hashes and
  token counts only (proven in tests + both JSON proofs).
- Live Anthropic is never called in tests/CI: config is fail-closed (record 58) and
  the mock proof asserts `live_called: false`.
- No new SQLite tables / no migration: schema head stays V26, lifecycle contract 141.
  The `second_brain_agent_model_receipts` table remains deferred to the V27
  agent-runtime prompt; `llama-index-core` remains deferred to Prompt 04; MCP to 08D.
