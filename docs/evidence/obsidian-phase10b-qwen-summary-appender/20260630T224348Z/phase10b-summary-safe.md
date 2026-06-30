# Phase 10B — Local qwen2.5:14b advisory-summary appender (sanitized, counts only)

Bounded, local-only appender that replaces ONLY the `hb-local-summary` block in existing generated
Work source cards using Ollama-served `qwen2.5:14b`. No broad indexing, no source-file read, no
source-root scan, no queue enqueue/drain, no DB mutation, no runtime-JSON mutation, no cloud model.

- branch: `feat/obsidian-phase10b-qwen-summary-appender-20260630T224348Z`
- base commit: `13bc00b7` (origin/main; Phase 9 + 10A present)
- Phase 10A marker contract confirmed: `card_version=phase10a-v1`, one `hb-local-summary` pending block
  per card, `replace_local_summary_block()` helper present.
- runtime freeze preconditions (ACTUAL runtime config, read-only): pass — watch/auto-card/auto-summary/
  auto-refresh = false; card-generation/writes/vault-markdown = true; runtime JSON not modified.
- pre-run DB: generated 25 / not_generated 67 / stale 0; work generated 25; queue 0/0; summaries rows 7;
  Work md 26; all 25 blocks `status="pending"`.

## Implementation (files changed)
- `construction/classification/client.py`: **additive** `generate_text(*, system, prompt)` (no
  `format:"json"`) + `base_url` property. `generate_json` unchanged.
- `obsidian_mcp/source_notes.py`: `_local_summary_marker`/`replace_local_summary_block` now stamp a
  `generated_at="<ISO>"` attribute on the generated marker (backward-compatible; pending marker
  unchanged).
- `obsidian_mcp/source_local_summary.py` (new): advisory-boundary system prompt; `build_summary_prompt`
  (deterministic card body minus frontmatter/advisory block + bounded stored excerpt; no paths/full
  file/DB dump); `sanitize_advisory_markdown` (strips fences/HTML-comments/markers/YAML-HR/tables/
  absolute-paths/local-file-links + length bound); `generate_advisory` (maps model failures to
  timeout/ollama_unavailable/empty_response/invalid_response; never raises).
- `scripts/obsidian_source_card_append_local_summary.py` (new): bounded CLI; dry-run default (never
  calls Ollama); apply requires exact confirms + clean runtime + Ollama/model probe; per-card block-
  only replacement via SHA-gated `create_note` with local-sensitive backup; DB fingerprint before/after
  to prove no DB mutation.

## Appender behavior
- Selects existing generated Work cards; eligibility = file exists, `card_version=phase10a-v1`, exactly
  one start+end marker, `status="pending"` (unless `--allow-resummarize`), canonical 11 sections, path
  under `Source Notes/Work/`. Refuses if eligible > `--max-cards` or work-generated != expected.
- Dry-run never constructs/calls Ollama. Apply fail-safe: refuses (zero cards touched) if Ollama
  unreachable (`ollama_unavailable`) or model not installed (`model_unavailable`). A per-card model
  failure leaves that card unchanged and is counted as `failed`.

## Dry-run (production)
- selected 25, eligible 25, ineligible 0, ollama_called false.

## Pilot apply (production; Ollama available, qwen2.5:14b installed)
- selected 25, eligible 25, **summarized 25, failed 0**, skipped 0, created 0, deleted 0, queue_delta 0.
- `pilot_full_success = true` (summarized == eligible == 25 and failed == 0).
- DB fingerprint identical before/after (`db_mutation_detected = false`): generated 25 / not_generated
  67 / stale 0, summaries rows 7, queue 0/0, generated-note metadata hash unchanged.
- Byte-level preservation (each card vs its pre-apply backup): 25/25 outside-block byte-preserved,
  25/25 canonical 11-section order preserved, 25/25 exactly one `generated` block, 25/25 marker carries
  model + `generated_at`. Cards changed outside the block: 0.
- post-apply runtime: backend not listening; frozen flags unchanged; generated 25 / not_generated 67 /
  stale 0; work 25; queue 0/0; summaries rows 7; Work md 26; all 25 blocks `status="generated"`.

## Tests / lint
- new `test_obsidian_source_card_local_summary_appender.py`: 27 passed (dry-run no-Ollama; confirm/
  backend/queue/count/marker/version/already-generated refusals; block-only replacement +
  byte-preservation; failed/empty model leaves card unchanged; success flips marker + model/timestamp;
  no source-file read; no index/scan/queue calls; max-cards cap; sanitizer strips unsafe constructs;
  prompt advisory-boundary + path omission; `generate_text` omits `format:json` while `generate_json`
  unchanged; safe summary carries no paths/bodies).
- broader obsidian source-card suites (phase10a/notes/rerender/summaries/pm-grade/auto-generate/value/
  spreadsheet/taxonomy/analyzer/first-indexing/domain-routing/self-index/skip-codes/work-home-seed):
  passed. Slow watch_ownership + mcp_backend: passed (0 failures). `ruff check` (changed files): clean.

## Ollama / model availability (count-only)
- local Ollama reachable; installed model count 5; `qwen2.5:14b` present.

## Confirmations
- no frontier model / no internet (local Ollama only) · no broad indexing · no queue enqueue/drain ·
  no source-root scan · no external source-file read (open()-guard test) · no runtime JSON mutation ·
  no DB row mutation (fingerprint identical) · no card creation/deletion · no deterministic content
  changed outside the `hb-local-summary` block · production advisory card BODIES not committed (vault
  only) · backups/prompts/model outputs/per-card paths kept under local-sensitive/ (untracked) · only
  count-only safe evidence committed.

## Recommended next phase
Phase 10C — review/feedback + safe re-summarization controls, a pending/generated status view, and a
bounded expansion to the next approved card batch.
