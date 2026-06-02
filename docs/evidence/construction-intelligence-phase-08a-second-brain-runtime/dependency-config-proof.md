# Phase 08A · Synthesized Prompt 03 — Dependency, Config, Claude Adapter, Model Profiles — Proof

This package-named proof consolidates the Synthesized Prompt 03 surface. Most of it
was already delivered earlier this session; this run is a **surgical gap-fill** of
model-profile contract enforcement, metadata-only model-call receipts, and the three
named evidence artifacts. Repo truth overrides the package's stale `c2656e1`
baseline — actual HEAD at start was `15cdb00` (Prompts 02 / 03 / agent-addendum
landed).

## Already satisfied by repo truth (not re-done)

| Deliverable | Where | Detail |
| --- | --- | --- |
| Optional `anthropic` extra | `pyproject.toml` (`a5b9f2b`) | `[project.optional-dependencies] second-brain`; lazy-imported; llama-index deferred to Prompt 04 |
| Second-brain config (fail-closed) | `construction/second_brain/config.py` | mode disabled/mock/live; presence-only API key; see `03-...-proof.md` |
| Mock/live Claude adapter | `construction/second_brain/reasoning.py` | `MockClaudeAdapter` default, gated `LiveClaudeAdapter` |
| Model-profile contract + seed + loader | `resources/json/phase_08a_model_profile_contract.json`, `resources/config/phase_08a_model_profiles.seed.yaml`, `agents/loader.py::load_model_profiles` (`15cdb00`) | five profiles; router/Haiku/Sonnet/Opus/checklist |
| Mock model tests | `tests/test_claude_adapter.py` | mock-first, fail-closed live |
| No-live-call CI default | config fail-closed + tests mock-only | proven in `test_default_config_ci_path_is_not_live` |

## New this run (gap-fill)

- **Model-profile enforcement** — `agents/policy.py::validate_model_profiles` +
  `build_agent_model_profile_proof` validate the seed against the contract (5
  profiles, intent map, no-raw persistence policy).
- **Metadata-only model-call receipts** — `reasoning.py::ModelCallReceipt` +
  `build_model_call_receipt` (sha256 input/output hashes + token counts; never raw)
  + `build_claude_adapter_mock_proof`.
- **Evidence** — this file + `claude-adapter-mock-proof.json` +
  `agent-model-profile-proof.json`.

## Files changed (this run)

- `src/hb_assistant/construction/second_brain/agents/policy.py` — `validate_model_profiles`, `build_agent_model_profile_proof`.
- `src/hb_assistant/construction/second_brain/reasoning.py` — `ModelCallReceipt`, `build_model_call_receipt`, `build_claude_adapter_mock_proof`.
- `src/hb_assistant/construction/second_brain/agents/__init__.py`, `__init__.py` — re-exports.
- `tests/test_model_profiles.py` (new), `tests/test_claude_adapter.py` (extended).
- `docs/architecture/60-phase-08a-model-profile-enforcement-and-model-call-receipts.md`.
- `docs/evidence/.../dependency-config-proof.md`, `claude-adapter-mock-proof.json`, `agent-model-profile-proof.json`.

## Validation commands and exit codes

| Command | Result |
| --- | --- |
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! (exit 0) |
| `mypy src` | Success: no issues found in 200 source files (exit 0)* |
| `pytest tests/test_model_profiles.py tests/test_claude_adapter.py tests/test_agent_registry.py` | 37 passed |
| `pytest -m "not live and not integration and not manual"` | 2343 passed, 4 skipped, 1 deselected (exit 0) — +8 new tests |
| `construction-agent validate --json` | `schema_version=26` (unchanged) |
| `data-quality table-inventory --json` | `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` (unchanged) |
| `second-brain agents status --json` | exit 0, valid (unchanged) |

\* mypy emits a pre-existing benign note about an unused `hb_assistant.retrieval.context`
override section; no errors.

## Evidence proofs

- `agent-model-profile-proof.json` — `proof_passed: true`; 5 profiles; intent map
  (router=null / fast=haiku / default=sonnet / deep=opus / evaluator=checklist_json);
  `no_raw_persistence: true`; `guardrails.mcp_implemented: false`; no violations.
- `claude-adapter-mock-proof.json` — `proof_passed: true`; `mode: mock`;
  `live_called: false`; `no_raw_content: true`; model-call receipt carries
  sha256 hashes + token counts only (`raw_prompt_persisted`/`raw_response_persisted`
  false).

## Guardrail posture

- No raw prompt/response/URL/token/secret persisted — receipts are hashes + token
  counts only (proven in `test_model_call_receipt_holds_only_hashes`).
- Live credentials not required; live never called in tests/CI (fail-closed config +
  `live_called: false`).
- No external writeback; no new SQLite tables (schema V26, lifecycle 141).

## Known limitations / next prompt readiness

- `ModelCallReceipt` is in-memory only; the `second_brain_agent_model_receipts` table
  is deferred to the V27 agent-runtime prompt (per the prior operator decision).
- `llama-index-core` deferred to Prompt 04 (retrieval/context budget); MCP to 08D.
- Ready for Prompt 04: retrieval orchestrator builds `ContextEnvelope`s; the V27
  agent-runtime prompt persists `AgentRunReceipt`/tool/model receipts and extends the
  no-writeback proof arm to the new tables.
