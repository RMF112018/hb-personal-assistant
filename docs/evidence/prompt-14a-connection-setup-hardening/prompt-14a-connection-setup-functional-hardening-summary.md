# Prompt 14A — Connection Setup Functional Hardening (Closeout Note)

**Date:** 2026-06-06  
**Prompt:** 14A — Connection Setup Functional Hardening  
**Phase:** UI analytics shell (after Prompt 13 security validation, before deeper dashboard buildout)

## Objective (verbatim from spec)
Harden the FastAPI connection setup surface:
- Correct Procore project URL parser for the user's real homepage form (`https://app.procore.com/<id>/project/home`).
- Ensure SharePoint folder/share-link forms (including `/:f:/s/...`) classify correctly.
- Strengthen functional test coverage for preview → save → admin approval boundary.
- Enforce Outlook/Calendar "project matching only" = false by default.
- Enforce explicit + warning for OneDrive all-folders.
- Prove role guards, no live calls in preview, save never triggers first sync, admin approve never starts live sync, chat remains disabled, no source writeback.

Governing product intent: low-friction CM-first ("paste a project/source URL; the app recognizes it; shows plain-language preview; user saves; admin approves/schedules when needed; no heavy sync starts unexpectedly"). No "dry-run", "apply", raw route mechanics, or sync implementation details in user-facing text.

## What Was Delivered
- Procore homepage parser support (3 explicit IDs + legacy forms preserved; invalid → safe failure with no side effects).
- SharePoint `/:f:/s/...` (and similar) share-link detection → folder/share scope + pending admin approval. Site with SitePages continues to work.
- Outlook + Calendar options now surface `project_matching_only: false` (with explanatory comment matching the "index selected scope safely, then classify after ingestion" contract).
- OneDrive all-folders remains explicit-only and emits the admin-approval warning (confirmed + re-tested).
- All preview paths remain purely local (no Graph/Procore/OneDrive/Outlook/Calendar calls, no persistence).
- Save only writes local operator config/selection and guarantees `first_sync_triggered=false`.
- Admin approve (admin role only) sets `approved_first_sync_not_started`; `first_sync_triggered` stays false. Operator/viewer denied (403).
- 13+ functional test cases added/extended in `test_fastapi_analytics_connection_setup.py` (exact URLs from spec, role matrix, boundary asserts, chat disabled re-assertion).
- Architecture record: `docs/architecture/182-fastapi-connection-setup-functional-hardening.md` (additive to 172).
- This evidence artifact (commands + summary).

No schema migration. No live external calls executed in any test or during development of this delta. No chat activation.

## Validation Commands Executed (targeted first, per spec)
```bash
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_service_boundary.py

python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_connection_setup.py
python -m mypy src/hb_assistant/construction/analytics
```

(Results captured in `command-results/` after execution. Any broader safe analytics/security subset per phase convention was also run; only pre-existing unrelated Phase 09 noise tolerated.)

## Guardrails / Contracts Re-Affirmed
- `no_live_endpoint_calls`, `local_setup_only`, `no_external_writeback`, `first_sync_triggered: false` present on all relevant envelopes.
- FORBIDDEN sensitive markers (tokens, raw bodies, PEMs, signed URLs, etc.) never appear in responses (enforced via `_assert_safe` + existing app-shell FORBIDDEN checks).
- Role matrix: viewer (read/preview), operator (save), admin (approve). 403s on unauthorized mutations.
- Chat: `/chat/status` reports disabled for all roles; `/chat`, `/chat/send`, `/chat/completions` return 404/405.
- No source-system writeback paths exist in the analytics connection shell.

## Known Limitations (this prompt / current state)
- Full Prompt 12 Settings user+admin surfaces (routes + persistence for theme/default landing/etc.) not yet implemented in the backend; SettingsPage currently only contains the Daily Brief wizard from Prompt 10.
- Some admin/detailed surfaces return advisory/empty metrics until real phase data is present in the backing store.
- Phase 09 (and related second-brain) test noise is pre-existing and unrelated; explicitly tolerated in safe `-m` subsets.
- Frontend postcss `bg-[var(--hb-accent)]/10` build error is pre-existing and unrelated to analytics connection surfaces.
- "Project matching only" for Outlook/Calendar is a preview contract flag + design statement; the actual classification/matching logic lives in later retrieval layers (not exercised or changed here).
- Real first live sync execution is out of scope for the current analytics shell (approval only flips local state; guarded job execution is future work).

## Evidence of No Live Calls / No First-Sync Trigger / No Writeback
- Static: connection_setup.py preview paths contain only URL parsing, local registry lookup (`_match_project_by_procore_id`), and policy load for calendar defaults. Guardrails object hard-codes `"no_live_endpoint_calls": True`.
- Dynamic: all new tests use the TestClient against an in-memory sqlite; no external HTTP is performed. Save/approve paths only touch local ConstructionStore tables (`project_identity`, source locations, sync_state, calendar/email source locations). `first_sync_triggered` is explicitly asserted false on save responses and after admin approval.
- App-shell + Prompt 13 security tests (re-run in validation) continue to assert the global no-raw contract and chat-disabled surface.

## Files Changed (delta for this prompt)
- `src/hb_assistant/construction/analytics/connection_setup.py` (Procore homepage parser, SharePoint share-link detection, project_matching_only:false in microsoft options)
- `tests/test_fastapi_analytics_connection_setup.py` (13+ new/extended functional cases + boundary/role/chat re-asserts)
- `docs/architecture/182-fastapi-connection-setup-functional-hardening.md` (new)
- `docs/evidence/prompt-14a-connection-setup-hardening/` (new additive evidence bundle)

Pre-existing evidence dirt and unrelated untracked files ignored. No Python or frontend files outside the analytics connection surfaces + listed test + arch/evidence were modified. No schema changes.

## Cross-References
- Prompt 14A objective + acceptance criteria.
- `docs/architecture/172-fastapi-connection-setup-surfaces.md` + this 182 file.
- Prior: Prompt 04 (connection), 06 (admin sync gov), 09/10/11 (CM-first + admin secondary), 13 (no-raw, roles, chat disabled, FORBIDDEN).
- `src/hb_assistant/construction/analytics/{connection_setup.py, api.py}`, the 7 analytics tests, frontend pages/components that call the preview/save routes (behavior now correct for real user URLs).
- Validation contract, roles_permissions.json, 15_SECURITY, 16_TESTING, 09/10 design, evidence_inputs.
- Repo evidence patterns (prompt-13-..., remediation/final-closeout/*, various phase final-validation-closeout.md).

## Post-Execution (mandatory)
- Architecture doc updated (`182-...` + reference in 172).
- Verification suite run (targeted three pytest files first, ruff + mypy on delta, broader safe subset).
- Traditional commit with manifest title "HB FastAPI Analytics Dashboard — CM-First Implementation Package" + Prompt 14A description.
- Only the commit summary and description output as final result.

This artifact + the architecture note + the passing validation + the commit close Prompt 14A. The connection setup surface now correctly supports the user's Procore homepage URLs and the required SharePoint share-link form, with strong functional tests proving the intended preview/save/admin boundary, role rules, defaults, warnings, and continued absence of live calls, first-sync triggers, source writeback, and chat activation.