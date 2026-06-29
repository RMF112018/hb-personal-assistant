# Evidence — A1.11 PM-Value Source-Card Prioritization & File-Type Policy

**Date:** 2026-06-29
**Branch:** `feat/source-card-pm-priority-policy-20260629T214004Z`
**Base commit:** `9238a28c` (origin/main — A1.8/A1.9/A1.10 merged)

## What this patch does
Makes automatic source-card generation **PM-value aware** instead of first-come-first-drained. Every
source is classified into one disposition; drains prefer high-value construction PM/control artifacts
and suppress placeholders/screenshots/system-test/broad business-record files. **Additive only — no
schema migration, no OCR, no new dependencies, no macro/formula execution, watcher stays off.**

## Dispositions (`source_value.py` — pure, deterministic)
`AUTO_CARD_HIGH` · `AUTO_CARD_NORMAL` · `METADATA_ONLY` · `DEFERRED` · `EXCLUDED` · `UNSUPPORTED`.
`classify_source_value(detail, config)` order: excluded segment (no index) → unsupported ext (no
index) → deferred segment (indexed, no auto-card) → document_type mapping → generic-spreadsheet
metadata gate → path-signal promotions (upgrade only). Returns priority_score, allow_auto_card/summary/
metadata_index, skip_code, reasons.

- **HIGH** = drawings, bid_package, rfi, submittal, meeting_minutes, schedule, specification,
  cost_document, **change_order/PCCO**, **pay_application**, **contract**, **daily_log**, **punchlist**,
  **closeout**, **project_controls**, **staffing_report** (the bold ones are new doc-types).
- **NORMAL** = presentation, marketing, site_map, and unknown-but-real documents (general_pdf/
  general_document still card — just not ahead of recognized PM artifacts).
- **METADATA_ONLY** = generic spreadsheets/CSV (no high-value class); indexed, not auto-carded.
- **DEFERRED** = HB INSURANCE RENEWALS / CERTIFICATES OF INSURANCE / COI / INSURANCE RENEWAL
  (strict segment-equality — `COImaging` is NOT deferred); indexed/searchable; manual generate allowed.
- **UNSUPPORTED** = url/aspx/lnk/webloc/tmp/lock + png/jpg/jpeg/heic/gif/webp; **skipped before
  indexing** (no fragile parsers); never auto-carded.
- **EXCLUDED** = node_modules/.venv/dist/… (unchanged hard hygiene).

## Behavior changes
- **Excel:** high-value classes (pay app, cost report/entries, forecast, budget, staffing/manpower —
  NARROW phrases, never bare `cost`) → HIGH with a dedicated card section (`## Spreadsheet Identity /
  PM Relevance / Detected Workbook Signals / Review·Verification Notes`) and `Card basis: spreadsheet
  metadata + bounded cell sample`. Generic workbooks → METADATA_ONLY. Workbook signals come from the
  already-extracted bounded excerpt (sheet names + ≤50×20 cell sample); **no formulas evaluated, no
  macros executed** (`data_only=True, read_only=True`).
- **Card basis line** on every card: full text / spreadsheet metadata / metadata-only / filename-path.
- **Drain prioritization:** rebuild orders eligible sources by `priority_score` (HIGH before NORMAL,
  ties by rel_path) before the per-drain card cap; overflow re-enqueues only eligible sources.
  Single-file events: metadata-only that indexed cleanly → `skipped`/`metadata_only_no_auto_card`;
  unsupported → `skipped`/`unsupported_file_type` (pre-index); deferred → `skipped`/`deferred_path`;
  excluded → `skipped`/`excluded_path`. **Policy skips are successful, NOT errors.**
- **Status:** `source_value_policy` block, `skipped_count` + `skipped_by_code`, and a bounded coarse
  `queued_by_disposition` diagnostic.
- **Maintenance:** retire now also matches manual/test cards (`source-summary-test`/`manual-test` path
  signals) under `by_policy.test`; dry-run default, apply marks `stale`, file delete only with the
  explicit flag. Insurance retire unchanged.
- **UI:** editable PM source-value policy controls (high/normal signals, metadata-only/unsupported
  types) mirroring the A1.10 deferred control, plus an explanatory note.

## Files changed
- New: `src/hb_assistant/obsidian_mcp/source_value.py`
- `obsidian_mcp/`: `source_analyzers.py`, `source_indexer.py`, `source_notes.py`, `source_search.py`,
  `source_index_repository.py`, `config.py`, `source_maintenance.py`
- `construction/analytics/api.py` (config-patch request fields)
- `frontend/`: `ObsidianMcpPanel.tsx` (+`.test.tsx`), `lib/api.ts`
- Tests: new `test_obsidian_source_value.py`, `test_obsidian_source_pm_priority_drain.py`,
  `test_obsidian_source_spreadsheet_card.py`; extended `test_obsidian_mcp_backend.py`,
  `test_obsidian_source_maintenance.py`

## Schema / migration
**None.** Additive config fields; `skipped` event-status + free-text `error_code` already existed;
retire reuses the legal `stale` status (no new enum value).

## Tests
See `backend-tests.txt` / `frontend-tests.txt`. Frontend: typecheck clean, `ObsidianMcpPanel` 22/22
(20 prior + 2 new). Ruff clean on all changed obsidian_mcp files.

## Manual validation (live; watcher OFF; backlog NOT drained)
See `source-policy-status.json`, `source-policy-config.json`, `maintenance-dry-run.json`
(+ `maintenance-apply.json` if run), `active-card-inventory-before/after.txt`, `backend-log-tail.txt`.

## Known limitations / follow-ups
- **Prioritization is NOT a persistent DB queue-priority model.** It orders (a) the rebuild scan's
  in-memory source list and (b) per-event disposition skips within a claim batch (`created_at ASC`,
  ≤50). There is no events priority column and no enqueue-time reordering — the DB does not globally
  prioritize the backlog.
- `queued_by_disposition` is a coarse path/ext-only sample (document_type is unavailable for
  not-yet-indexed events, so HIGH/NORMAL there is filename-signal-based, approximate).
- Unsupported types are skipped, not indexed (no fragile parsers).
- Spreadsheet cards are metadata/cell-sample based (no formula semantics).
- New doc-types render via the fallback/spreadsheet sections (no bespoke per-type templates).
