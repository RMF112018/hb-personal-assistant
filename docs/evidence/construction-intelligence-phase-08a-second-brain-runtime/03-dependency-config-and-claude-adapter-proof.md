# Phase 08A · Prompt 03 — Dependency, Config, and Claude Adapter — Proof

Scope: LlamaIndex/Anthropic dependency surface (Anthropic only this prompt) +
second-brain config loader + mock/live Claude adapter boundary + V26 config-receipt
writer + offline-safe `second-brain status --json`. Local-only, additive,
mock-first. No external API calls, no writeback, no raw content, no secrets.

## Repo-truth preflight (before edits)

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `f8c1324a334e22050d1787360d4f04ea2aec4d51` (Prompt 02) |
| `git status --short` | clean except untracked `.claude/`, `.code-graph/` |
| `python -V` | Python 3.14.5 (venv) |
| `hb-assistant --version` | hb-assistant 1.3.0 |
| `construction-agent validate --json` | 4/4 ok, `schema_version=26`, writeback `none` |
| `data-quality table-inventory --json` | `contract_table_count=141`, `in_db_not_in_contract=[]` |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `data-quality phase-07d-gates --json` | `ok=true` |
| `anthropic` installed? | **No** (confirms offline/base posture) |

HEAD differs from the prompt's expected `c2656e1` (Prompt 01) because Prompt 02
landed intentionally; the actual SHA is recorded above and the V26 schema/contracts
are present, so the baseline is sound.

## Files changed

Created:
- `src/hb_assistant/construction/second_brain/config.py` — `SecondBrainConfig` + `load_second_brain_config` (fail-closed mode resolution, presence-only API key).
- `src/hb_assistant/construction/second_brain/reasoning.py` — Claude adapter boundary: `ContextEnvelope`, `AdapterResult`, `ClaudeAdapter` (+ pre-synthesis gate), `MockClaudeAdapter`, `LiveClaudeAdapter` (lazy `anthropic`), `AnthropicUnavailable`, `build_claude_adapter`.
- `src/hb_assistant/construction/second_brain/store.py` — `write_config_receipt` / `read_latest_config_receipt` against V26 `second_brain_runtime_config_receipts`.
- `src/hb_assistant/cli/second_brain.py` — `second-brain status` (offline-safe).
- `tests/test_second_brain_config.py`, `tests/test_claude_adapter.py`, `tests/test_second_brain_cli.py` — 28 deterministic offline tests.
- `docs/architecture/58-phase-08a-dependency-config-claude-adapter.md`.

Modified:
- `pyproject.toml` — added `[project.optional-dependencies] second-brain = ["anthropic>=0.40"]`; added `hb_assistant.construction.second_brain.*` to strict mypy overrides.
- `src/hb_assistant/construction/second_brain/__init__.py` — export config/adapter/store API.
- `src/hb_assistant/cli/main.py` — register the `second-brain` group.

## Validation commands and exit codes

| Command | Result |
| --- | --- |
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | All checks passed! (exit 0) |
| `mypy src` | Success: no issues found in 196 source files (exit 0)* |
| `pytest tests/test_second_brain_config.py tests/test_claude_adapter.py tests/test_second_brain_cli.py` | 28 passed |
| `pytest -m "not live and not integration and not manual"` | 2313 passed, 1 deselected (exit 0) — was 2285 at Prompt 02 (+28 new) |
| `construction-agent validate --json` | 4/4 ok, `schema_version=26` |
| `data-quality table-inventory --json` | `contract_table_count=141`, `in_db_not_in_contract=[]` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain status --json` | exit 0, `mode=disabled` (offline default), receipt written, `runtime_contract_version=phase_08a_second_brain_runtime-v1`, `schema_version=26` |

\* mypy emits a pre-existing benign note about an unused `hb_assistant.retrieval.context`
override section (not introduced by this prompt); no errors.

## Guardrail proof points

- **Mock-first / offline**: `anthropic` not installed; full suite + mock adapter +
  `second-brain status` all run with no cloud-model tooling and no network.
- **Fail-closed live**: `live` requires enabled + `MODE=live` + API key + `external_llm_enabled`
  + `anthropic` installed; any gap degrades to `mock`/`disabled` (proven in `test_live_*`).
- **No secret persistence**: API key value never stored on `SecondBrainConfig`, never in
  the receipt, never emitted by the CLI (proven in `test_api_key_value_never_stored`,
  `test_status_never_emits_api_key`). Only `api_key_configured: bool` is recorded.
- **No model external access / no raw content**: adapter accepts only a `ContextEnvelope`;
  forbidden raw reference fields rejected at the boundary; `LiveClaudeAdapter` sends only
  bounded envelope metadata; `AdapterResult` carries no raw prompt/response/URLs.
- **Tier 3 never auto-accepted**: Tier 3 (and missing research packet / no source refs /
  insufficient context) → blocked, `review_required`, `synthesized=False` (no model call).
- **No-writeback / guard columns**: config receipt leaves all ten `CHECK(col = 0)` guard
  columns at 0 (proven in `test_status_writes_guarded_receipt`).

## Env var names (no values)

`HB_SECOND_BRAIN_ENABLED`, `HB_SECOND_BRAIN_MODE`, `HB_ANTHROPIC_API_KEY` (presence only),
`HB_CLAUDE_MODEL`, `HB_CLAUDE_MAX_INPUT_CHARS`, `HB_CLAUDE_MAX_OUTPUT_TOKENS`.

## Deferred commands (documented, not implemented this prompt)

| Command | Owning prompt |
| --- | --- |
| `second-brain index obsidian` | 05 |
| `second-brain query` / `chat` | 06 / 10 |
| `second-brain memory extract` / `review` | 11–12 |
| `second-brain brief daily` | 13 |
| `second-brain launchd install` | 14 |
| `data-quality phase-08a-no-writeback-proof` | 15 |
| `data-quality phase-08a-gates` | 16 |
| `llama-index-core` dependency | 04 |

The `phase_08a_validation_matrix` must reference only built commands when installed
(Prompt 16) to avoid repeating the G-07D-02 drift.

## Unresolved gaps / next prompt readiness

- V26 second-brain tables (incl. config receipts) are guarded at the DB layer but not
  yet in `build_data_quality_no_writeback_proof` scope — that arm is Prompt 15.
- Ready for Prompt 04 (retrieval policy + context budget; adds `llama-index-core` to the
  `second-brain` extra and the retrieval orchestrator that builds `ContextEnvelope`s).
