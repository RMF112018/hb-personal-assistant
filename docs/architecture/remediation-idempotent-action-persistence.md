# Remediation: Idempotent Action Persistence and Source Links (Phase 14 Prompt 03)

## Summary
Phase 14 Prompt 03 moves raw action persistence (introduced in P02) into proper, reusable Store and Registry helpers for idempotent upsert by stable_key (with strict preservation of completed status/completed_at on re-extract) plus a high-level source-link helper for action-to-source linkage. Duplicate-prevention, completed-state, and migration idempotency tests added. No migration required (schema already supported everything).

## Files Updated
- `src/hb_assistant/store/repositories.py` — new `upsert_action_item` (ON CONFLICT DO UPDATE + CASE/COALESCE to never reset completed), `get_action_item_by_stable_key`, small `get_summary` enhancement.
- `src/hb_assistant/links/registry.py` — new `link_action` helper (action_item_id support + exactly-once guard reusing `get_links_for_source`).
- `src/hb_assistant/actions/service.py` — surgical refactor: raw INSERT block replaced with calls to the new store + registry helpers (behavior 100% preserved, including dry-run safety).
- `tests/test_store_links.py` — two new tests (idempotent duplicate prevention + completed status never reset on re-extract; `link_action` creates exactly once).
- New: `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-03/` (summary, commands, validation outputs with focused pytest for the new tests + migration idempotency).

## Key Changes
- Action upsert is now idempotent by stable_key and lives in the Store (proper place), not scattered in service layer.
- Completed status/completed_at is **never reset** on repeated extraction (core requirement for reliable repeated morning runs).
- Source links for actions now go through the Registry provenance gate (`link_action`).
- Tests reuse and extend the proven `test_store_links.py` patterns (temp DB, exact schema seeding including completed_at, before/after counts, migration idempotency).
- All changes surgical, minimal, 100% repo-truth, following discovered patterns exactly (no new abstractions).

## Validation Performed
- Focused pytest for new action upsert/idempotency/completed + migration idempotency tests: green.
- Full verification suite (pytest, ruff, mypy, hb-assistant diagnostics scan-sensitive --json, run morning --dry-run --json, supporting commands) executed; outputs captured in evidence/.
- Sensitive scan clean.
- Commit: `feat(store): add idempotent action persistence`

## References
- `docs/plans/ph-14-workstream-Intelligence/04_Blocker_Taxonomy_And_Admin_Consent_Closeout_Plan.md` and related (P03 is the immediate follow-on to P02 action foundation).
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-03/summary.md` (complete evidence bundle + SHA).
- `src/hb_assistant/store/repositories.py` and `links/registry.py` (new helpers documented in code).

**Status**: Idempotent action persistence + proper source linking delivered. Ready for Prompt 04+ (signal integration, etc.).
