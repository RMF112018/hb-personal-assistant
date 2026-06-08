# 212. Phase 10 / 10A — Local Model Readiness + Raw Action Extraction Hardening

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence (repo-truth update)

## Context

The v42 raw email/calendar substrate existed but the controlled local-action workflow had gaps: the
default extraction model was `qwen3:14b`; readiness status recommended pulling Qwen3 models even when
disabled; packet builders did not normalize HTML bodies (HTML-only emails → empty model context); and
`raw-action-candidates` mutated the DB on dry-run (then zeroed the count), ignored `--source`, used the
non-deterministic builtin `hash()` for stable keys, and linked `candidate_source_refs.candidate_id` to
a source-ref string instead of the persisted candidate id. This change makes the substrate usable for
controlled extraction with no external writeback and no raw-content leakage.

## Decision

### Local model readiness (`local_ai/provider.py`)
- The Ollama readiness probe (`GET /api/tags`) now uses stdlib **`urllib.request`** instead of
  `requests`. The second-brain no-writeback scanner forbids `import (requests|httpx|aiohttp)` in these
  modules; `urllib` is allowed. A `_UrllibResponse` shim preserves the `status_code`/`json()` surface,
  and the injectable getter (`requests_get`) is retained for hermetic tests.
- Pull recommendations are emitted **only for active profiles** (`enabled`, or heavy + `heavy_enabled`).
  Disabled/not-explicitly-enabled profiles report `blocked_reason="profile_disabled"` and produce no
  `ollama pull` suggestion. Consequence: **no qwen3 pull suggestion unless explicitly enabled**
  (`heavy_context`=qwen3:30b only surfaces under `--heavy-enabled`).

### Profile seeds + contract
- `default_extract` → **`mistral-nemo:12b`** (required + enabled). Removed `fast_extract` (qwen3:8b),
  disabling qwen3 for structured extraction. Added enabled non-heavy profiles **`high_recall_extract`**
  (`llama3.1:8b`) and **`review_filter`** (`qwen2.5:14b`); both added to `fallbacks → default_extract`.
  `quality_reasoning` (gpt-oss:20b) and `heavy_context` (qwen3:30b, explicit-enable only) unchanged.
- Contract `recommended_profiles` updated; added declarative
  `structured_extraction_disabled_model_prefixes: ["qwen3"]` (a test asserts no enabled non-heavy
  profile uses a disabled prefix).

### HTML-to-text normalization (`local_ai/raw_context.py`)
- New `_normalized_body_text(body_text, body_html, max_chars)` reuses the stdlib
  `procore.normalizers.financial.html_to_text` (tag strip + entity unescape + whitespace collapse).
  Applied at all four packet body-mapping paths (email summary/raw, calendar summary/raw): when
  `body_text` is empty/blank and `body_html` is present, the bounded text is derived from the HTML.
  Raw HTML is never emitted as the text field.

### Raw action extraction (`local_ai/raw_action_intelligence.py` + CLI)
- `extract_action_candidates_from_raw` gains `dry_run: bool = True` (default) and `source: str = "both"`.
  Dry-run performs **zero** writes and reports `would_persist`; persistence runs only on apply, after
  schema + business validation. `_build_raw_excerpts` honors `source` for both the packet and
  store-fallback paths.
- Persistence uses **deterministic SHA-256** keys: `stable_key = raw-{type}:{sha256(sorted(source_refs))[:16]}`,
  `candidate_id = sha256(type|sorted(source_refs))[:24]`, and a deterministic `source_ref_id`. Re-apply
  is idempotent (one candidate row + one source-ref row per source-ref set); within a run the first
  candidate for a (type, refs) set wins. `candidate_source_refs.candidate_id` now equals the persisted
  candidate's `candidate_id`.
- The CLI `phase-10 raw-action-candidates` passes `store` / `dry_run` / `source` through (and gains
  `--db`); the previous post-hoc `persisted=0` zeroing is removed — the extractor is authoritative.

## Tests

- `tests/test_phase_10_local_model_readiness.py` — ready=true with mistral-nemo installed; new model
  set; no qwen3 pull by default; qwen3:30b only when heavy-enabled; contract disabled-prefix parity.
- `tests/test_phase_10a_raw_extraction_hardening.py` — HTML→text (email + calendar), dry-run zero
  writes, apply linkage + clean guards, deterministic dedupe, `--source` filtering.
- `tests/test_phase_10a_raw_action_intelligence.py` — updated to pass `dry_run=False` where persistence
  is asserted (dry-run is now the default).

## Guardrails / non-goals

Local-only; advisory; dry-run default. **Not enabling** email send, calendar mutation, Procore
writeback, cloud-LLM submission, or MCP raw exposure. No raw body/prompt/response/URL/token persistence
(HTML-normalized text is bounded model context, never persisted raw; evidence excerpts ≤400 chars). No
new migration or candidate table. No README/ledger bump (consistent with prior prompts).
