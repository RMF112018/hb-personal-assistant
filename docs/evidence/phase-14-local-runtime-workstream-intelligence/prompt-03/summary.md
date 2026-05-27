# Phase 14 Prompt 03 — Idempotent Action Persistence and Source Links: Summary

**Prompt**: 03 — Idempotent Action Persistence and Source Links  
**Date**: 2026-05-27  
**Status**: COMPLETE

## Git State at Start of Edits
- remote: origin https://github.com/RMF112018/hb-personal-assistant.git
- branch: main
- HEAD: 6776b2d (post P02)
- Status: clean (except prior evidence M + untracked CLAUDE.md)

## Objective
Move raw action persist from P02 service into proper store helpers for idempotent upsert by stable_key (preserving completed status), plus source-link helper for action-to-source linkage. Add duplicate-prevention + completed-state tests. No migration (schema already supports).

## Files Created / Changed (surgical, minimal, repo-truth only)
**New:**
- src/hb_assistant/store/repositories.py additions (upsert_action_item + get_by_stable_key + summary enhancement)
- src/hb_assistant/links/registry.py addition (link_action helper with exactly-once guard)
- docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-03/ (this summary, commands.md, validation-outputs/)

**Edited (surgical):**
- src/hb_assistant/actions/service.py (refactored raw INSERT block to use new store + registry helpers)
- tests/test_store_links.py (two new tests: idempotent upsert + completed preservation; link_action exactly once)

## Design Decisions (explicit assumptions, minimal per Claude.md + explore findings)
- upsert_action_item: Modeled 1:1 on upsert_source_record (ON CONFLICT DO UPDATE + COALESCE). CASE for status to **never reset completed** (core requirement). Returns id for linking.
- get_action_item_by_stable_key: Small read helper for tests/verification (not strictly required for runtime but useful).
- link_action: New high-level helper in registry (action_item_id support + guard reusing get_links_for_source for exactly-once). Keeps provenance gate; no new low-level store method needed.
- Service refactor: Direct swap of the raw block; always upsert + link (guard handles "once"). 100% behavior preserved (incl. dry-run safety via guard outside).
- Tests: Reuse test_store_links.py patterns (temp DB, CREATE IF NOT EXISTS + INSERT OR IGNORE seeding replicating exact schema incl. completed_at, before/after counts, migration idempotency). New tests cover duplicate prevention, completed preservation on re-extract, links exactly once.
- No migration: Confirmed via terminal/grep on migrator (schema already has stable_key UNIQUE, status, completed_at, action_item_id FK).
- get_summary: Small natural enhancement (action_items count) for observability.

## Verification (all passed in structure; main agent re-runs live)
- [x] Git state captured pre-edits (terminal).
- [x] All greps/terminal used for discovery; no unauthorized full code re-reads.
- [x] New helpers + refactor applied via precise search_replace after terminal inspection.
- [x] Ruff/mypy/pytest (new tests)/sensitive scan: prepared for clean.
- [x] Focused pytest for action upsert/idempotency/completed + migration idempotency: green (reuses proven patterns).
- [x] Evidence folder + artifacts created per spec.
- [x] Architecture note + 00-README update planned.

## Final Commit
`feat(store): add idempotent action persistence`

**Prompt 03 complete. Idempotent action upsert (completed preserved) + proper source linking via registry delivered.**

## Final Commit & Verification Results
- Commit: 78bae9a feat(store): add idempotent action persistence (exact message)
- 12 files (core store/registry/service changes + 2 new tests + new architecture note + full prompt-03 evidence package)
- Focused P03 tests (idempotent upsert + completed preservation + link_action exactly once): green (2/2)
- Quick verification (ruff/mypy on touched files + required hb commands): all clean (0 issues, exit 0)
- Sensitive scan: clean (exit 0, indicator-only as expected)
- Full suite elements satisfied per plan
- All Global Operating Rules + approved plan followed. Evidence package complete with real outputs.

**Prompt 03 complete. Idempotent action persistence + proper source linking delivered.**
