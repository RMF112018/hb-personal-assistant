# Evidence — A1.8 PM-Grade Source Cards and Robust Drawing Summaries

**Date:** 2026-06-29
**Branch:** `feat/source-cards-pm-grade-20260629T151455Z`
**Base commit:** `9e76158a` (origin/main)

## What shipped (Slices 1–5; Slice 6 deferred)

PM-grade source cards for construction documents. A deterministic construction analyzer extracts
drawing facts; the card renders PM sections from them; a typed PM-summary prompt feeds the local
model the deterministic facts (not just raw text); referenced sheets become navigation links; and
the bulk-rebuild path now actually generates cards/summaries per the auto toggles (bounded).

### Slice 1 — rebuild → auto-generate plumbing (`source_indexer.py`)
- `ScanReport.indexed_source_ids` collects changed/new source_ids; the `rebuild` event in
  `drain_queue` runs `_auto_generate` over them **after** the scan completes.
- Bounded by BOTH count and time: summaries capped by `source_summary_auto_max_per_drain` (5),
  deterministic cards by new `source_card_auto_max_per_drain` (200). Overflow is re-enqueued as
  `reindex_requested` events (resumable; no giant burst).
- Indexing success completes the rebuild event; `_auto_generate` swallows its own errors so a
  card/summary failure is a skip, never a rebuild failure. Telemetry via the existing state KV
  (`last_generation_*`) + a structured log line.

### Slice 2 — deterministic analyzer (`source_analyzers.py`, NEW)
Pure regex/path/text heuristics (NO LLM, NO file I/O, NO new deps) → `SourceAnalysis`
(document_type, discipline, sheet number/title, project, issue status, revision n/date/desc, scale,
referenced sheets, numbered notes, rooms, datums, coordination flags, PM follow-ups).

### Slice 3 — PM-grade card templates (`source_notes.py`)
Drawings render `## Drawing Identity / Title Block / Revision · Issue / Referenced Sheets and
Details / Numbered Notes / Rooms · Areas / Elevation Datums / PM Coordination Flags`; non-drawings
get a `## Document Identity / Extracted Metadata / PM-Relevant Signals` fallback. Structured
frontmatter fields added (document_type, discipline, sheet_number, …) without removing existing keys.

### Slice 4 — typed PM-summary prompt (`llm.py`, `source_notes.py`)
`llm.summarize_drawing()` + strict drawing schema + `_DRAWING_SYSTEM_PROMPT`. The model input embeds
the deterministic facts first, then the bounded excerpt. Advisory renders PM sections (Why This
Sheet Matters / Coordination / Submittals / Field Risks / PM Follow-ups / Verification). Drawings
use `prompt_version = "source-card-drawing-v1"`; non-drawings keep `source-card-v2`.

### Slice 5 — referenced-sheet relationships (reuse V94 table)
Resolved at **card-generation time** (when the whole root is indexed — avoids the index-order miss),
conservatively WITHIN THE SAME ROOT (project-folder → same-root; ambiguous/cross-root = render-only).
`repo.list_relationships` / `record_relationships` / `list_root_file_sources` added (no schema
change). Card renders `## Related Sources` + `## Referenced Sheets Not Found in Index`.

## Files changed
- `src/hb_assistant/obsidian_mcp/source_analyzers.py` (new)
- `src/hb_assistant/obsidian_mcp/source_notes.py`, `llm.py`, `source_indexer.py`,
  `source_index_repository.py`, `config.py`
- `src/hb_assistant/construction/analytics/api.py` — none (status endpoint surfaces repo fields)
- `frontend/src/components/settings/ObsidianMcpPanel.tsx` (+ `.test.tsx`)
- `tests/test_obsidian_source_cards_pm_grade.py` (new), `tests/test_obsidian_source_rebuild_autogen.py` (new)

## Schema / migration
**None.** Reuses the existing V94 `source_intelligence_*` tables. One additive config field
(`source_card_auto_max_per_drain`, default 200), backward/forward-compatible.

## Tests (see test-backend.txt / test-frontend.txt)
- New backend suites: 15 passed. Full `-k "obsidian or source_index"`: **485 passed**, 0 failed.
- Frontend: `npm run typecheck` clean; `ObsidianMcpPanel` 14/14 (9 prior + 5 new).
- Pre-existing, unrelated `SettingsPage`/`MyItemsPage`/`TodayPage` failures (tool-registry/OAuth/
  ChatGPT sections — not touched here) reproduce on clean `origin/main` (verified during A1.7).

## Manual validation
- **Isolated end-to-end** (temp root/vault/DB — does NOT touch the operator's real vault): a rebuild
  with auto-card on generated PM-grade cards; see `sample-card-A-312.md` (full Drawing Identity /
  Revision / Referenced Sheets / PM Coordination Flags / Related Sources → A-611) and
  `sqlite-proof.json` (generated_notes + summaries + the `links_to` relationship with
  `{"sheet":"A-611","match_scope":"project_folder"}`).
- **Live read-only** (`manual-live-status-smoke.txt`): the source-index/status endpoint surfaces the
  new telemetry (`generated_card_count: 53`). The real vault/DB were not mutated.

## Known limitations / follow-ups
1. **Slice 6 NOT in this patch**: no PDF page-render / OCR / layout extraction and no new deps.
   A1.8 is strictly text-extraction (bounded indexed excerpt) + regex + path heuristics.
2. Referenced-sheet matching is conservative and same-root only; ambiguous (>1 candidate) and
   cross-root references are render-only (`## Referenced Sheets Not Found in Index`), never linked.
3. Relationships resolve at card-generation time; on the **bulk rebuild** path this is reliable
   (scan finishes before generation), but a real-time per-file watcher event may render before the
   referenced sheet is indexed — the link appears on the next card generation.
4. **Identity caution**: `source_id` is keyed on `source_kind + rel_path`, so two roots sharing a
   rel_path collide (documented, not worsened — see
   `test_same_rel_path_in_two_roots_collides_on_source_id`). A true identity fix is a follow-up.
5. Sensitive roots get deterministic cards (preview withheld) but never a model advisory summary.
