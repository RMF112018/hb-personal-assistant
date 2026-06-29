# Evidence — A1.9 Source Intelligence Hygiene + Bid Package Classification

**Date:** 2026-06-29
**Branch:** `fix/source-intelligence-hygiene-bidpkg-20260629T184227Z`
**Base commit:** `9fb725dc` (origin/main — A1.8 + PR #217)

## Defect 1 — path-exclusion hygiene
Low-value dependency/build trees (node_modules, .venv, dist, build, .next, site-packages,
__pycache__, …) are no longer indexed or carded.
- **Config:** `DEFAULT_EXCLUDED_PATH_PARTS` (15 segments) + `source_index_excluded_path_parts`
  (additive, validated lowercase/dedupe) on `ObsidianMcpConfig` + patch model + api request model.
- **Helper:** `is_excluded_source_path(rel_path, config)` — pure, segment-based (so `node_modules/x`
  and `a/node_modules/x` hit; a file *named* `build.txt` does not).
- **Applied at:** `scan_source_root` + `scan_vault_notes` (skip before index); `drain_queue`
  single-file branch (→ `complete_event "skipped", error_code="excluded_path"`, no index/card);
  `generate_source_card` (raises `ObsidianMcpToolError("source_excluded_path")`); `summarize_source`
  (returns `{summarized: False, reason: "excluded_path"}` before any Ollama call).
- **Status:** `source-index/status.exclusion_policy.excluded_path_parts`.
- **Endpoint hardening:** the source-card generate/summarize endpoints now translate
  `ObsidianMcpToolError` → clean **HTTP 422 {detail: code}** (was an opaque 500 for every guard).
- **Existing rows:** not deleted (guardrail). A maintenance utility to mark existing excluded rows
  inactive is a documented follow-up; future drains/cards are already blocked by the guards.

## Defect 2 — bid_package classification (over RFI)
- **Analyzer:** `bid_package` detected with priority ABOVE rfi via `_bid_package_signal` (path
  `/bid packages/`, filename/text `bid package`, `bid package NN-NN`, `Inclusions:`/`Exclusions:`,
  the "Provide all necessary labor…" boilerplate). **RFI made stricter** (requires
  `request for information` / `RFI #` / `RFI No.` / `RFI Log`, not a bare `rfi` substring).
- **Extraction:** `bid_package_number`, `bid_package_title`, `inclusions`, `exclusions`,
  `procurement_signals`, `trade_scope` (all bounded). `issue_status` detects `BID DOCUMENTS`.
- **Card:** `_render_bid_package_sections` → `## Bid Package Identity / ## Scope Summary /
  ## Inclusions / ## Exclusions / ## Procurement / Estimating Signals / ## PM Coordination Flags`
  + frontmatter `document_type/bid_package_number/bid_package_title`.
- **Typed summary:** `llm.summarize_bid_package` + `_BID_PACKAGE_SYSTEM_PROMPT` + strict schema +
  `_render_bid_package_advisory`; `prompt_version = "source-card-bid-package-v1"`.

## Files changed
- `src/hb_assistant/obsidian_mcp/`: `config.py`, `source_indexer.py`, `source_notes.py`,
  `source_analyzers.py`, `source_search.py`, `llm.py`
- `src/hb_assistant/construction/analytics/api.py` (request field + 2 endpoint 422 wrappers)
- `frontend/src/lib/api.ts`, `frontend/src/components/settings/ObsidianMcpPanel.tsx` (+ `.test.tsx`)
- `tests/test_obsidian_source_exclusions.py` (new), `tests/test_obsidian_source_bid_package_analyzer.py` (new),
  `tests/test_obsidian_mcp_backend.py` (extended)

## Schema / migration
**None.** Additive config field (backward/forward compatible); `'skipped'` event status already
existed in `EVENT_STATUS_VALUES`; no new tables.

## Tests (test-backend.txt / test-frontend.txt)
- New backend: exclusions (6) + bid package (5) + mcp_backend additions = green; combined focused
  run **27 passed**. Full `-k "obsidian or source_index"` regression: **499 passed, 0 failed**.
- Frontend: typecheck clean; `ObsidianMcpPanel` **18/18** (16 prior + 2 new exclusion-control tests).
- `py_compile` of all `src` OK; ruff clean on changed modules.

## Manual validation (manual-validation.txt) — watcher stayed OFF
- bid source `158ac555…` → 200 generated; `sample-bid-package-card.md` shows
  `document_type: "bid_package"`, `bid_package_number: "08-03"`,
  `bid_package_title: "Glass Windows and Doors"` + all PM sections (was `rfi`).
- node_modules source `47e7f4b5…` → **HTTP 422 `source_excluded_path`**, no vault note written.
- `source-index/status` → `watch_enabled:false`, `watcher.running:false`, `processing_count:0`,
  `exclusion_policy.excluded_path_parts` = 15. Backlog NOT drained.
- Live `obsidian_mcp_config.json` backed up and restored byte-identical (sha `dd6aa066…`).

## Known limitations / follow-ups
- Existing indexed excluded rows are not cleaned (no destructive default); a maintenance op is a
  follow-up. Future cards/summaries for them are already blocked.
- `scope_of_work` / `procurement_document` are in `BID_DOCUMENT_TYPES` but only `bid_package` is
  fully implemented (analyzer/card/summary).
- The corrected bid-package card was left in the operator's vault (an improvement over the previous
  misclassified `rfi` card); no other vault writes were made.
