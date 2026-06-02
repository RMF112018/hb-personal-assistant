# Phase 08A · Prompt 02 Addendum — Agent Runtime Foundation — Proof

Scope: agent registry contract + tool + model-profile contracts, registry +
model-profiles seeds, registry/model-profiles loaders, internal
`AgentResult`/`AgentRunReceipt` structures, agent policy validation, two read-only
CLI commands (`second-brain agents registry|status --json`), and two JSON evidence
proofs. **Foundation only:** no agent executes, no new SQLite tables, MCP not
implemented (Phase 08D). Local-first, no-writeback, no raw content, no secrets.

## Repo-truth preflight (before edits)

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `a5b9f2b80a6dbd85d193a8ac6f593f926af78b43` (Prompt 03) |
| `git status --short` | clean except untracked `.claude/`, `.code-graph/` |
| `construction-agent validate --json` | `schema_version=26` |
| `data-quality table-inventory --json` | `contract_table_count=141` |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |

## Files changed

Created:
- `src/hb_assistant/resources/json/phase_08a_agent_registry_contract.json`, `phase_08a_agent_tool_contract.json`, `phase_08a_model_profile_contract.json` (copied verbatim from package).
- `resources/config/phase_08a_agent_registry.seed.yaml` (9 agents; `output_contract` added per repo-truth reconciliation), `phase_08a_model_profiles.seed.yaml`.
- `src/hb_assistant/construction/second_brain/agents/__init__.py`, `models.py`, `loader.py`, `policy.py`.
- `tests/test_agent_registry.py`, `tests/test_second_brain_agents_cli.py`.
- `docs/architecture/59-phase-08a-agent-runtime-foundation.md`.
- `docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/agent-registry-proof.json`, `agent-tool-policy-proof.json`, `04-agent-runtime-foundation-proof.md`.

Modified:
- `src/hb_assistant/construction/second_brain/contracts.py` — registered 3 agent contracts.
- `src/hb_assistant/construction/second_brain/__init__.py` — re-export agents API.
- `src/hb_assistant/cli/second_brain.py` — `agents` sub-group + `registry`/`status` commands.
- `tests/test_phase_08a_contracts.py` — added required-key maps for the 3 agent contracts.

## Validation commands and exit codes

| Command | Result |
| --- | --- |
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! (exit 0) |
| `mypy src` | Success: no issues found in 200 source files (exit 0)* |
| `pytest tests/test_agent_registry.py tests/test_second_brain_agents_cli.py` | 16 passed |
| `pytest -m "not live and not integration and not manual"` | 2331 passed, 4 skipped, 1 deselected (exit 0); 2335 selected — was 2313 (+22 new) |
| `second-brain agents registry --json` | exit 0, `count=9` |
| `second-brain agents status --json` | exit 0, `registry_valid=true`, `tool_policy_valid=true`, `violations_count=0`, `mcp_implemented=false` |
| `construction-agent validate --json` | `schema_version=26` (unchanged) |
| `data-quality table-inventory --json` | `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` (unchanged) |

\* mypy emits a pre-existing benign note about an unused `hb_assistant.retrieval.context`
override section (not introduced here); no errors.

## Evidence proofs

- `agent-registry-proof.json` — `proof_passed: true`; 9 agents, all enabled, all
  required present, all fields complete, model profiles explicit, receipts required
  for all, Tier 3 handling visible, `guardrails.mcp_implemented: false`, no violations.
- `agent-tool-policy-proof.json` — `proof_passed: true`; per-agent allow/deny
  verdicts (`allowed_valid`, `no_denied_in_allowed`, `no_global_deny_in_allowed`)
  all true; global deny list echoed; no violations.

## Guardrail proof points

- **No agent allows a globally-denied or self-denied tool group** (arbitrary_sql,
  raw_sqlite_file, raw_filesystem, raw_obsidian_vault, direct_graph/procore_api,
  email/calendar/sharepoint/procore mutate, external_writeback) — proven per-agent.
- **Model-call metadata only**: model-profile contract + seed assert
  `persist_raw_prompt`/`persist_raw_response` false; `AgentRunReceipt` carries no
  raw prompt/response.
- **Tier 3 mandatory review visible**: `review_triage_agent` →
  `tier_3_mandatory_review`; no agent auto-accepts Tier 3.
- **No raw content** in proofs or CLI output (tested).
- **No new SQLite tables / no migration**: schema head V26, lifecycle count 141.
- **MCP not implemented**: no `mcp` command; `mcp_implemented: false` everywhere;
  deferred to Phase 08D per overlay.

## Repo-truth reconciliations (documented deviations from package)

1. Package seed omitted the contract-required `output_contract` field → added a
   logical `output_contract` label per agent so the registry validates against its
   own contract.
2. The package architecture doc describes 5 agent SQLite tables; per the prompt's
   explicit "Required Additions" list and operator decision, those are **deferred**
   to the later agent-runtime prompt (V27). `AgentRunReceipt` is an in-memory
   structure this prompt.

## Env var names (no values)

`HB_SECOND_BRAIN_AGENT_REGISTRY`, `HB_SECOND_BRAIN_MODEL_PROFILES`.

## Deferred (documented, not implemented)

5 agent persistence tables (V27); agent execution / model calls / receipt writing;
MCP (08D); `second-brain research/query/brief/memory/review` runtime commands;
`agents validate` command (validity surfaced inside `agents status`);
`phase-08a-gates` / `phase-08a-no-writeback-proof` arms (owning prompts).

## Next prompt readiness

Registry + contracts + structures + policy validation are in place; the
agent-runtime prompt can add the V27 receipt tables, the controller that runs
agents and persists `AgentRunReceipt`/tool/model receipts, and extend the
no-writeback proof arm to cover the new tables.
