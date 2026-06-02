# 58 — Phase 08A: Dependency, Config, and Claude Adapter (Prompt 03)

Status: implemented (Phase 08A Prompt 03). Builds on the V26 schema + contract
loader (record 57). Local-first, additive, mock-first.

## Purpose

Prompt 03 lands the **safety-critical Claude transport boundary** plus the
second-brain runtime config surface — the layer every later 08A feature
(retrieval, interactive query, daily brief, memory synthesis) reaches Claude
through. It is opt-in, offline-by-default, and never calls Anthropic in tests or
default runs.

## Dependency surface

`anthropic` is declared as an **optional extra**, not a hard runtime dependency:

```toml
[project.optional-dependencies]
second-brain = [
  "anthropic>=0.40",
]
```

Rationale: hard runtime deps would make the whole local-first assistant depend on
cloud-model tooling even for purely local workflows. The extra + lazy import keeps
the base install, migrations, full test suite, and mock mode working with no
`anthropic` present. `pip install -e .[second-brain]` enables the live path.
`llama-index-core` is **deferred to Prompt 04** (retrieval/context-budget), where
it is actually exercised; the extra is structured so Prompt 04 appends to it.

The `hb_assistant.construction.second_brain.*` subpackage is opted into **strict
mypy** (`[[tool.mypy.overrides]]`, `ignore_errors = false`).

## Configuration (`construction/second_brain/config.py`)

`load_second_brain_config()` resolves a non-secret `SecondBrainConfig` snapshot
from environment variables and the existing `AppConfig.security.external_llm_enabled`
master switch:

| Env var | Meaning |
| --- | --- |
| `HB_SECOND_BRAIN_ENABLED` | master enable (explicit opt-in: `1/true/yes/on`) |
| `HB_SECOND_BRAIN_MODE` | requested mode (`mock` \| `live`) |
| `HB_ANTHROPIC_API_KEY` | **presence only** — value never stored/logged |
| `HB_CLAUDE_MODEL` | model id (default `claude-opus-4-8`) |
| `HB_CLAUDE_MAX_INPUT_CHARS` | bounded context budget (default 24000) |
| `HB_CLAUDE_MAX_OUTPUT_TOKENS` | output cap (default 2048) |

**Fail-closed mode resolution** — the runtime is `live` only when *all* of:
`HB_SECOND_BRAIN_ENABLED` set **and** `HB_SECOND_BRAIN_MODE=live` **and** an API
key is configured **and** `security.external_llm_enabled` is true **and**
`anthropic` is installed. Anything short of that degrades to `mock` (when enabled)
or `disabled`; the degradation reason is recorded in `notes`. Dependency presence
is probed with `importlib.util.find_spec` (no import, no network). The API key
value is never assigned to a model field — only `api_key_configured: bool`.

## Claude adapter boundary (`construction/second_brain/reasoning.py`)

- **`ContextEnvelope`** — the *only* adapter input: bounded, redacted,
  source-linked. A field validator rejects any source reference carrying a
  forbidden raw field (`signed_url`, `download_url`, `raw_body`,
  `raw_document_text`, `token`, `secret`, …, mirroring
  `source_reference_contract.json`). Carries `review_tier` (1/2/3) + reason code,
  `confidence_class`, `research_packet_ok`, `context_quality`, and warning lists.
- **Pre-synthesis gate** (`ClaudeAdapter.synthesize`) — refuses to call the model
  (returns a `degradation_mode="blocked"`, `review_status="review_required"`
  result) when the research packet has not passed, there are no source
  references, context quality is insufficient, or the item is **Tier 3**
  (mandatory review — never auto-accepted as fact).
- **`MockClaudeAdapter`** — deterministic, offline; the test/default path.
- **`LiveClaudeAdapter`** — lazy-imports the `anthropic` SDK at call time; raises
  `AnthropicUnavailable` (sanitized, no secrets) if the SDK is missing. Reads the
  API key from the environment at call time (never stored on the instance) and
  sends only the bounded envelope — never raw rows, vault notes, or API handles.
- **`build_claude_adapter(config)`** — `disabled → None`, `mock → MockClaudeAdapter`,
  `live → LiveClaudeAdapter`.
- **`AdapterResult`** — structured output only: answer, source references,
  confidence, review tier/reason/status, disposition (advisory vs actionable),
  degradation mode, coverage/stale/conflict warnings. No raw prompt/response.

## Config receipts (`construction/second_brain/store.py`)

`write_config_receipt()` inserts one metadata-only row into the V26
`second_brain_runtime_config_receipts` table (mode, config status, dependency
booleans, runtime-contract policy version), leaving all ten `CHECK(col = 0)`
no-raw / no-writeback guard columns at 0. Reuses the canonical
`get_connection`/`transaction` idiom and runs the migrator to guarantee the table
exists (idempotent).

## CLI (`hb-assistant second-brain status`)

Offline-safe status command reporting mode, config status, synthesis enablement,
dependency availability, schema/contract versions, and guardrails; writes a config
receipt by default (`--no-emit-receipt` to skip) and reports its id. Never emits
the API key value. Composed into the root app as the `second-brain` group.

## Out of scope (later prompts)

`second-brain` query/chat/brief/index/memory/launchd commands; `llama-index-core`
(Prompt 04); the `phase-08a-gates` / `phase-08a-no-writeback-proof` arms (Prompts
15/16). V26 tables remain guarded at the DB layer meanwhile; the existing
`construction-agent data-quality no-writeback-proof` stays green and is not
extended here.
