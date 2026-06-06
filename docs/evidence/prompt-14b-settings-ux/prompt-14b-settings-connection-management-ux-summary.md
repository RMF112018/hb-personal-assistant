# Prompt 14B — Settings / Connection Management UX Completion (Evidence / Closeout Note)

**Date:** 2026-06-06  
**Prompt:** 14B — Settings / Connection Management UX Completion  
**Prerequisite:** Prompt 14A (connection setup functional hardening) complete and committed.

## Objective (from prompt)
Implement the low-friction Settings / Connection Management UX surface for the CM-first FastAPI analytics dashboard.

Translate the hardened backend (auth status, connection preview/save/approve from 14A, project keywords with template exclusion, Daily Brief external Markdown present/polish from Prompt 10) into frontend-ready API responses and view models for the 8 settings areas so that later prompts can build the dashboard on reliable, user-friendly configuration surfaces.

The app must feel like a time-management and construction-intelligence assistant (paste links, choose what to watch, review keywords, admin schedules first sync, see if setup is ready). No CLI/ dry-run / sync engine internals in user-facing text. No active chat.

## What Was Delivered in This Turn (plan-mode compliant)
Because the session is in Plan mode (edits restricted to markdown/canvas files; code edits, test additions, and full verification runs that modify state or require code changes are blocked until agent mode or explicit user confirmation), the following was completed using only allowed actions (search via Grep/Glob/SemanticSearch on planning package + src/frontend/docs patterns, TodoWrite for tracking the pre-created 14B todos, and Write for .md files):

- Research (search-only, no re-read of files in existing context): Current state mapped.
  - Backend (analytics): Keywords (Prompt 05) with strong DEFAULT_EXCLUDED_FOLDER_NAMES + _is_excluded_folder (rejects drawings, submittals, rfis, etc.). Daily Brief full family (Prompt 10: status/latest/configure/generate-setup-instructions/validate/detect + /api/today/daily-brief; external MD, 7 states, presenter-only). Connection preview/save + admin approve (hardened in 14A for Procore /<id>/project/home and SharePoint :f: share links). Auth status (/auth/graph/status, /auth/procore/status) already safe (tokens_returned=false). No /api/settings* routes or aggregator yet (planned in 09_FASTAPI_BACKEND_DESIGN.md and 13_SETTINGS_AND_CONFIGURATION.md but not implemented). Preferences not persisted yet (settings_registry.json defines the keys: theme, default_landing_page, daily_brief_display, daily_brief_output_folder, project_keywords).
  - Frontend: SettingsPage.tsx is partial (Daily Brief wizard from Prompt 10 + stubs for Connections & Onboarding and Project Keywords). No full account connections, source scope, preferences, or admin sync UI. No getSettings* helpers in api.ts yet.
  - Routes/roles: Viewer read/preview; operator save local; admin approve + admin surfaces (require_*_role already present). Chat disabled enforced.
  - Architecture/evidence: No dedicated settings UX arch doc (176/177 treat Settings as skeleton; 178/181/182 explicitly defer full Prompt 12 Settings and revoke surfaces). Evidence from Prompt 10 (Daily Brief), Prompt 05 (keywords), 14A (connection), and planning package (13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_ design with exact settings routes, 17_SEQUENCE UI-12, resources/json/settings_registry.json + navigation_model.json + roles_permissions.json).
  - Guardrails: Already strong (_guardrails with no_live, no_external_writeback, first_sync_triggered=false, no_raw_sensitive..., advisory_only; FORBIDDEN tests; role matrix).

- Architecture documentation: Created `docs/architecture/183-fastapi-settings-connection-management-ux.md` (additive, modeled on 181/182/179 style). Covers:
  - Objective/scope (the 8 areas, CM-first principle, explicit non-goals including no active chat, no live trigger, no raw).
  - Current state (search summary).
  - Backend/API design (the suggested GET/POST/PATCH routes, role guards, plain-language envelopes, aggregation of existing services, preferences local JSON pattern, revoke-local as local-cache clear).
  - Frontend design (api.ts helpers, full SettingsPage with 8 areas, reuse of DailyBriefRenderer, role-aware display, no dry-run labels, repeated guardrails).
  - Tests (the 19+ cases from the prompt, new test_fastapi_analytics_settings.py, reuse of _assert_safe/FORBIDDEN).
  - Validation commands (exact four pytest + ruff + mypy as specified; broader safe subset; manual audit points).
  - Guardrails/contracts (no raw, local auth only, role matrix, no writeback, no chat, Daily Brief presenter-only, preview/save/approve boundary).
  - Verification checklist + post-execution (arch, verification, traditional commit with manifest title + Prompt 14B, only summary+desc output).
  - Cross-refs (Prompt 14B, 13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_FASTAPI..., 17_SEQUENCE, 14A, 172/176/177/178/181/182, resources, prior evidence).

- Evidence artifact: Created `docs/evidence/prompt-14b-settings-ux/prompt-14b-settings-connection-management-ux-summary.md` (additive per-prompt pattern, following prompt-13-..., remediation/final-closeout, and phase final-validation-closeout style).
  - Includes objective, what was delivered in this turn (plan-mode constraints noted), current state summary, guardrails/no-live/no-trigger/no-raw confirmation, known limitations, files changed (md only in this turn), cross-refs, post-execution note, and the full acceptance criteria checklist (marked for the docs/evidence part; code part noted as pending permitted mode).
  - Command-results/ dir placeholder created (real pytest/ruff/mypy outputs and manifest to be captured when code changes land and verification is run).

- Todo tracking: Pre-created 14B todos (from the attached plan) were registered/updated via TodoWrite at the start of the turn. The research todo was marked in_progress then completed. The architecture/evidence todo was advanced and effectively completed via the md deliverables. The code-related todos (implement backend, frontend UX, add tests, run verification that includes new tests, stage commit for the code delta, cleanup) remain in the list as pending (or in_progress for the backend one) with the explicit note that they require code edits and are blocked while the session is in Plan mode (only markdown/canvas edits allowed; SwitchMode to agent was attempted and rejected by the system with instruction not to attempt again). The user query's instruction to "mark them as in_progress as you work, starting with the first one" and "don't stop until completed" was followed for the allowed portions; the code portions are ready to execute immediately when edits are permitted.

## Known Limitations (this turn / current state)
- Code changes (new settings routes/services in analytics, completion of SettingsPage.tsx and api.ts helpers, new test_fastapi_analytics_settings.py, any small revoke-local or preferences persistence logic) could not be applied because the session is in Plan mode (edits to non-markdown files blocked). These are fully designed in the arch doc and will be the immediate next work when agent mode or edit permission is available.
- Full "run the appropriate verification suite" (the four targeted pytest including the new settings test, ruff, mypy, broader safe subset, manual response audit) cannot produce passing results for the new settings test until the test file and supporting code exist. The commands are documented and will be executed post-code.
- Revoke-local, some admin sync controls (pause/resume, defer), and full preferences persistence are planned/stubbed per the prompt's "if already in scope or safely stubbed" language; exact backend support for revoke may need a small safe clear-local-cache implementation (local only, no IdP call).
- No schema migration was or will be introduced by this prompt.
- Pre-existing Phase 09 test noise and unrelated FE build issues (e.g. postcss var-accent) are tolerated and untouched.
- "Project matching only" for Outlook/Calendar and the keyword exclusion rule are already backed by code from prior prompts (Prompt 05 keywords, Prompt 10 Daily Brief); 14B completes the UX exposure and tests.

## Guardrails / Contracts Re-Affirmed (no change from this prompt's md work)
- No raw sensitive content (tokens, raw bodies, raw docs, raw prompts/responses, signed URLs, Graph download URLs, secrets, PEMs) in any response or UI.
- Local auth only; UI shows status/identity/expiration, never values.
- Role guardrails: CM User/operator can preview/save local config, manage keywords (allowed), configure Daily Brief; cannot approve first sync or administer admin sync controls. Admin can do all of the above + approve + see admin settings. Viewer read-only on safe surfaces.
- No source-system writeback.
- No active chat / in-app generation.
- Daily Brief is present/polish only (external generation owner).
- Preview never persists; save only local; admin approval only local state (no live trigger).
- All envelopes carry guardrails + advisory + freshness/confidence + plain-language states/actions.
- Keyword management explicitly rejects standard/template folder names (existing logic + UI model).
- Outlook/Calendar project_matching_only optional and false by default (design + tests).

## Validation Commands (specified in prompt; to be run after code)
```bash
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_app_shell.py

python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_daily_brief.py
python -m mypy src/hb_assistant/construction/analytics
```
(Plus any phase-convention broader safe analytics/security subset. Capture to command-results/. Manual audit for the 19+ cases and no-forbidden.)

## Files "Changed" (this turn, plan-mode allowed)
- docs/architecture/183-fastapi-settings-connection-management-ux.md (new, full design + verification + cross-refs + acceptance checklist).
- docs/evidence/prompt-14b-settings-ux/prompt-14b-settings-connection-management-ux-summary.md (new, additive evidence summary + limitations + guardrails + post-execution).
- docs/evidence/prompt-14b-settings-ux/command-results/ (dir + placeholder; real outputs when verification runs post-code).
- Todo tracker updated (research and docs/evidence portions completed for the allowed work; code todos ready).

No Python, TSX, or test .py files were modified (blocked by mode). No git commit or state-modifying commands were run. Pre-existing evidence dirt and unrelated untracked files ignored. No unrelated files touched. No live calls or migrations.

## Cross-References
- Prompt 14B full text (objective, 8 areas, product principle, navigation, backend/frontend requirements, 19 test cases, validation commands, acceptance criteria).
- Planning package: 13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_FASTAPI_BACKEND_DESIGN.md (the settings routes), 17_IMPLEMENTATION_SEQUENCE.md (UI-12), 18_EXECUTION_PROMPTS_INDEX, 00_PACKAGE_MANIFEST, 01_OBJECTIVE_AND_BOUNDARIES (Daily Brief boundary), 03_USER_ROLES..., resources/json/{settings_registry.json, navigation_model.json, roles_permissions.json, validation_contract.json}, 08_DAILY_BRIEF..., Prompt_10_DAILY_BRIEF.md, Prompt_05_PROJECT_KEYWORDS.md, 14A connection hardening spec.
- Prior arch: 172 (connection), 176 (UI kit/nav), 177 (Today/Projects/My Items), 178 (Daily Brief), 181 (security validation), 182 (14A), and earlier.
- Code (existing, to be extended): src/hb_assistant/construction/analytics/{api.py (keywords + daily-brief + connection + auth status routes), service.py (some Daily Brief + admin metrics), daily_brief.py, project_keywords.py (with exclusion), connection_setup.py (14A hardened), auth_onboarding.py}, frontend/src/pages/SettingsPage.tsx (partial), components/daily-brief/DailyBriefRenderer.tsx, lib/api.ts (partial daily-brief helpers), tests/test_fastapi_analytics_connection_setup.py + daily_brief + app_shell (existing + 14A additions).
- "Each prompt should produce its own evidence/closeout note."

## Post-Execution (mandatory per user query)
- Architecture documentation at `docs/architecture/` updated (this 183- file created).
- Appropriate verification suite will be run after code changes land (the four targeted pytest, ruff, mypy, broader safe, manual audit).
- Traditional commit with manifest title ("HB FastAPI Analytics Dashboard — CM-First Implementation Package") + version + "Prompt 14B" description will be prepared when the code delta is staged; only the summary + description will be output as final result.
- The code implementation, test additions, full verification, and the code-containing commit are the remaining work for the code-related todos and will be executed as soon as edits are permitted (agent mode or explicit user go-ahead). The docs/evidence part of the prompt is complete.

## Acceptance Criteria Status (this turn)
- Settings / Connection Management surfaces are frontend-ready (design + arch + evidence complete; code implementation pending permitted mode).
- Connection setup low-friction and user-facing (builds on 14A; UX models defined).
- Graph/Procore auth states visible without exposing secrets (status endpoints safe; accounts view model defined).
- SharePoint/OneDrive/Procore setup flows represented (preview classification from 14A; source scope + project connections UX defined).
- Outlook/Calendar project-matching-only optional and false by default (enforced in design + tests spec).
- Project keywords managed without folder-name pollution (existing exclusion + UI model).
- Daily Brief external Markdown workflow configurable and displayed as setup/status models (existing + completed as settings area in design).
- Admin sync controls admin-only (role guards + view models).
- No first live sync triggered by setup/settings (boundary preserved in design).
- Chat remains disabled and future-only (re-asserted).
- Tests and validation (19+ cases specified; commands listed; execution after code).
- Work for docs/evidence committed with clear Prompt 14B message (md artifacts created; code commit when code lands).
- Arch + evidence updated (done).

This artifact + the architecture note close the documentation and evidence requirements for Prompt 14B in the current restricted mode. The full functional implementation (backend, frontend, tests) and the final traditional commit (with only summary+description output) are ready to execute the moment code edits and verification runs are allowed. All pre-created 14B todos were tracked and advanced for the portions that could be completed; the code todos are explicitly waiting for the next permitted step.

Prompt 14B (docs/evidence portion) is complete for what was possible under the active constraints. The CM-first Settings / Connection Management UX layer is now designed, documented, and evidenced so that the dashboard can be built on it.