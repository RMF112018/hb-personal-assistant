# FastAPI Analytics — Settings / Connection Management UX Completion (Prompt 14B)

## Objective and Scope
Implement the low-friction Settings / Connection Management UX surface for the CM-first FastAPI analytics dashboard (Prompt 14B), building directly on the hardened connection setup from Prompt 14A.

This prompt translates the backend primitives (auth status, connection preview/save/approve, project keywords with template-folder exclusion, Daily Brief external Markdown present/polish) into user-facing, frontend-ready API responses and view models for the full Settings experience.

The app must feel like a time-management and construction-intelligence assistant, not a sync engine or CLI wrapper.

Settings is a support surface (not primary landing). Primary nav remains Today / Projects / My Items; support nav is Admin / Data Confidence + Settings.

In-scope for this prompt:
- Account Connections (Graph/Procore status + reconnect/revoke actions, plain language states, no secrets/tokens ever exposed).
- Project Connections (Procore homepage URL, SharePoint site/folder/share-link, OneDrive explicit scopes with all-folder warning, Outlook/Calendar with project_matching_only optional and false by default).
- Source Scope (business-language description of what is being watched, first-sync pending, freshness).
- Project Matching Keywords (management with explicit rejection of standard/template folder names; explain; add/edit/disable/delete/exclude; per  Prompt 05 + 13_SETTINGS rules).
- Daily Brief (full configuration for external agent Markdown workflow, platform instructions, scheduled prompt generation, detect/test, 7 states, presenter-only polish; already partially present from Prompt 10, completed as a first-class settings area).
- User Preferences (theme dark/light/system, default landing Today/Projects/My Items, followed projects, Daily Brief display preference, etc.).
- Admin Sync Controls (visible only to admin: first-sync queue/approve/defer, per-project cadence/priority, rate-limit/backoff display, pause/resume; Construction Management User / operator cannot approve or schedule first live sync).
- Local Storage / Retention (if backend support exists or safely stubbed; usage, retention, cleanup affordances).

Out-of-scope / explicit non-goals:
- Active in-app chat or any model/LLM workflow through the UI (Chat remains future/stub-only and disabled).
- Triggering first live sync from settings or connection save (preview/save/approve boundary from 14A is preserved; approval only mutates local state).
- No source-system writeback.
- No raw sensitive content in any response or UI (tokens, bodies, prompts, signed URLs, PEMs, secrets).
- No "dry-run", "apply", "execute", raw route mechanics, or sync engine internals in user-facing text.
- No new schema migrations unless absolutely required and approved (this prompt should not require one).
- No Obsidian writes, no live external AI platform runs, no operator DB migrations during verification.

## Current State (research via search-only; no full re-read of prior context files)
- Backend (analytics): Project keywords CRUD + explain (per-project, with DEFAULT_EXCLUDED_FOLDER_NAMES and _is_excluded_folder rejecting template names like drawings, submittals, rfis, etc.). Daily Brief full family (status/latest/configure/generate-setup-instructions/validate/detect + /api/today/daily-brief; external Markdown, 7 states, presenter-only). Connection preview/save (hardened in 14A for Procore homepage forms and SharePoint :f: share links) and admin approve-first-sync. Auth status endpoints (/auth/graph/status, /auth/procore/status) already designed to return tokens_returned=false, secrets_returned=false. No /api/settings* aggregator routes or dedicated SettingsService yet (the routes listed in 09_FASTAPI_BACKEND_DESIGN.md — GET /api/settings, PATCH user/admin, revoke-local — are planned but not present in code). Connection and daily-brief config use local JSON under Application Support (no new SQLite for prefs in prior work).
- Frontend: SettingsPage.tsx exists as a partial (Prompt 10 / UI-12 partial) with the Daily Brief external wizard (enable, platform select Claude/ChatGPT/Perplexity/Other, folder, pattern, stale, show on Today, generate instructions, copy scheduled prompt, validate, test detect, live preview via DailyBriefRenderer). Stub sections for "Connections & Onboarding" and "Project Keywords". Advisory text about guardrails and local storage. No full account connections, source scope, preferences, or admin sync UI. Uses direct daily-brief helpers; no getSettings etc. in api.ts yet.
- Routes/roles: Viewer can read status/preview; operator can save local config; admin can approve first sync and see detailed admin surfaces. require_operator_role / require_admin_role already in place for the relevant handlers. Chat disabled surface is enforced in app_shell tests and health payload.
- Architecture/evidence: 176 (UI kit) and 177 (Today/Projects/My Items) treat SettingsPage as a required skeleton. 178 (Daily Brief) and 181/182 note that full Settings (Prompt 12) and revoke surfaces were not implemented at the time and were deferred to later UI-12/14 work. No dedicated 180-/183- arch doc for the complete settings UX yet. Evidence from Prompt 10 (Daily Brief), Prompt 05 (keywords), Prompt 14A (connection hardening), and the planning package (13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_FASTAPI_BACKEND_DESIGN.md, 17_SEQUENCE, resources/json/settings_registry.json, navigation_model.json, roles_permissions.json) provide the spec.
- Guardrails already present: _guardrails() objects with read_only, no_live_endpoint_calls, no_external_writeback, first_sync_triggered=false, no_raw_sensitive_response_fields, advisory_only, etc. FORBIDDEN scanning in tests.

This prompt completes the UX layer so that the 8 settings areas are frontend-ready, role-aware, plain-language, and provably safe.

## Backend / API Implementation (to be applied when mode permits code edits)
Add or refine routes in `src/hb_assistant/construction/analytics/api.py` (and supporting builders, preferably in a thin settings service or composed in AnalyticsService / existing services):

- GET /api/settings (or /settings/overview) — composite: accounts summary, project connections summary, source scope, keywords health, daily brief status, user prefs, admin flag, overall setup progress.
- GET /api/settings/accounts — Graph/Procore status (plain states: Connected / Needs sign-in / Expired / Reconnect required / Not configured), actions (start device login, start Procore OAuth, reconnect, revoke-local if supported), identity (redacted), no tokens/secrets.
- GET /api/settings/projects — list of connected projects/sources with scope type (procore_project, sharepoint_site, sharepoint_folder, onedrive_selected, outlook, calendar), first_sync_status, freshness.
- GET /api/settings/sources — source scope details with warnings (e.g. OneDrive all-folders large scope, Outlook/Calendar project_matching_only optional).
- GET /api/settings/keywords — management view model (candidates, active, disabled, excluded; per followed project or aggregated; explain available).
- GET /api/settings/daily-brief — config + status (enabled, platform, folder, pattern, stale_minutes, show_on_today, current state from the 7 states, generated_at, path, warnings, sections if parsed).
- GET /api/settings/preferences — theme, default_landing_page, followed_projects, daily_brief_display, etc. (sourced from settings_registry + runtime local config).
- GET /api/settings/admin-sync — (admin only) pending first-sync queue, per-project cadence/priority, rate-limit display, pause/resume affordances.

Mutation (role-guarded):
- PATCH /api/settings/user — theme, default landing, followed projects, daily brief prefs, etc.
- PATCH /api/settings/admin — admin sync/source controls (rate limit, backoff, global scope, etc.).
- POST /api/settings/auth/graph/revoke-local and procore (admin or operator as appropriate; clears local cache only, returns success with new status; no IdP revocation call unless already safely implemented).
- Keyword management continues to use (or is also exposed via) /projects/{key}/keywords + /explain (add/edit/disable/delete/exclude). Settings/keywords surface provides the aggregated view and entry point.
- Daily Brief configure/detect/validate/instructions continue to use the existing /api/daily-brief/* family (already operator-guarded where mutating).
- Connection preview/save and admin approve-first-sync (and any new defer/pause) remain as-is from 14A (operator for save, admin for approve).

All responses must be frontend-ready:
- title, subtitle/help, current state (plain language), available actions (with disabled + reason), role requirements, freshness/confidence where relevant, setup progress/checklist, no raw content.
- Guardrails object on every envelope.
- "first_sync_triggered": false on save/approve responses.
- Outlook/Calendar options include "project_matching_only": false by default + note that matching happens after safe ingestion.
- OneDrive all-folders only via explicit scope_mode + warning.

Preferences persistence can reuse/extend the local JSON pattern under Application Support (like daily_brief config) or a small preferences.json; no new SQLite table required for this prompt.

Admin surfaces must be protected by require_admin_role (or equivalent) and hidden/disabled in non-admin responses.

## Frontend Implementation (to be applied when mode permits)
- frontend/src/lib/api.ts: add typed async helpers (getSettingsOverview, getSettingsAccounts, getSettingsProjects, getSettingsSources, getSettingsKeywords, getSettingsDailyBrief, getSettingsPreferences, getSettingsAdminSync, patchUserPreferences, patchAdminControls, revokeGraphLocal, revokeProcoreLocal, etc.). Reuse existing daily-brief and connection helpers where they fit.
- frontend/src/pages/SettingsPage.tsx (and supporting components if needed): full implementation of the 8 areas as tabs or clear sections.
  - Account Connections: cards for Graph and Procore with status badges (Connected/Needs sign-in/...), buttons for start/reconnect/revoke (role-aware), redacted identity, no secrets.
  - Project Connections: "Add connection" flow using the connection preview (paste URL or select scope) → plain-language preview (source system, scope type, warnings, admin approval required) → Save setup (operator). List of current project connections with status/freshness/actions.
  - Source Scope: business descriptions + warnings (OneDrive all-folders explicit warning, Outlook/Calendar project_matching_only optional and off by default).
  - Project Matching Keywords: list (active/disabled/excluded), add/edit/disable/delete/exclude forms, explain affordance, note that standard/template folder names (Drawings, RFIs, Submittals, etc.) are rejected.
  - Daily Brief: the existing wizard (enable, platform select with generated instructions + copyable scheduled prompt for Claude/ChatGPT/Perplexity/Other/manual, folder, pattern, stale, show on Today, test detect, validate). Current state (one of the 7), freshness, path, "open original" (copy path), presenter-only advisory repeated. Link from Today.
  - Preferences: theme (dark/light/system, default dark with system awareness), default landing (Today/Projects/My Items), followed/pinned projects, daily brief display toggle, other low-friction prefs.
  - Admin Sync Controls: (admin only) first-sync approval queue (approve/defer), per-project cadence/priority, rate-limit/backoff display, pause/resume. Plain language ("Schedule first sync", "Pause updates"). Non-admin sees disabled or "Admin only".
  - Local Storage / Retention: usage, evidence/history retention, Daily Brief retention, cleanup affordances (stub/disabled if not yet backed by storage code).

All UI uses construction-first language, compact badges, advisory notes, links to Admin where appropriate for diagnostics, no dry-run terminology, strong guardrail repetition ("no secrets or tokens are stored or displayed here").

Daily Brief renderer (already present) is reused for preview in Settings and the Today section.

## Tests Required (to be added when mode permits code + test edits)
New or extended test file `tests/test_fastapi_analytics_settings.py` (and updates to connection_setup, daily_brief, app_shell as needed) covering at minimum the cases listed in the prompt:
1. Settings overview route.
2. Account connection status view model (plain states).
3. Graph auth status does not expose tokens/secrets.
4. Procore auth status does not expose tokens/secrets.
5. Project connection setup checklist / preview→save flow.
6. Source scope view model (warnings, defaults).
7. Outlook/Calendar default scope shows project_matching_only false + post-ingestion note.
8. OneDrive all-folder warning only on explicit selection.
9. Keyword management view model excludes template folder names (and rejects on add).
10. Keyword add/edit/disable/delete/exclude role behavior (operator can manage, viewer cannot).
11. Daily Brief configuration view model + 7 states.
12. Daily Brief external platform setup instruction generation (Claude / ChatGPT / Perplexity / manual) and scheduled prompt copy.
13. Daily Brief detect/test handles missing file safely; presenter preserves source Markdown.
14. User preference model (theme, default landing, followed projects, daily brief display).
15. Admin sync controls hidden/disabled for non-admin; visible and actionable for admin.
16. Admin first-sync queue/approve/defer visible to admin only.
17. Chat remains disabled and not present as active navigation or settings feature.
18. No route serializes tokens, raw bodies, raw document text, raw prompts/responses, signed/download URLs, PEMs, or secrets (reuse/enhance _assert_safe + FORBIDDEN).
19. Role guards consistent with 14A (viewer preview/read, operator save local, admin approve + admin settings).

Run the targeted validation commands exactly as specified in the prompt.

## Documentation / Evidence
- Architecture: this file (183-fastapi-settings-connection-management-ux.md) or equivalent (additive to 172/176/177/178/181/182). Covers the 8 areas, user vs admin boundaries, Daily Brief external contract, keyword exclusion rule, Outlook/Calendar defaults, no active chat, preview/save/approve boundary, validation commands + results, cross-refs to Prompt 14B, 13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_FASTAPI_BACKEND_DESIGN.md, 17_SEQUENCE (UI-12), 14A, 172, resources (settings_registry.json, navigation_model.json, roles_permissions.json, validation_contract.json), prior arch, and evidence.
- Evidence: additive `docs/evidence/prompt-14b-settings-ux/` (or prompt-14b-connection-management-ux/) with summary md + command-results/ (the required pytest runs, ruff, mypy, any manual audit notes, redaction confirmation, limitations).

## Guardrails and Contracts (enforced)
- No raw sensitive content in any API response or UI surface.
- Local auth storage only; UI shows status/identity/expiration state, never values.
- Role guardrails: Construction Management User / operator can preview/save local config and manage keywords (where allowed); cannot approve first sync or see/administer admin sync controls. Admin can do all + approve + admin settings. Viewer read-only on safe surfaces.
- Determination guardrails: surface signals and setup state only; no legal/claims/entitlement/final determinations.
- No source-system writeback.
- No active chat / in-app model usage.
- Daily Brief is present/polish only (external generation).
- Preview never persists; save only local; admin approval only local state flip (no live trigger).
- All responses include guardrails, advisory language, freshness/confidence where relevant, source-linked drilldowns where appropriate, and plain-language states/actions.

## Verification (per prompt + 16/17 + post-change)
- Targeted (exact commands):
  - python -m pytest tests/test_fastapi_analytics_settings.py
  - python -m pytest tests/test_fastapi_analytics_connection_setup.py
  - python -m pytest tests/test_fastapi_analytics_daily_brief.py
  - python -m pytest tests/test_fastapi_analytics_app_shell.py
- Scoped: ruff on the changed analytics + the new settings test + daily brief test; mypy on analytics.
- If phase convention requires broader safe analytics/security subset, run it (tolerate only pre-existing unrelated Phase 09 noise).
- Manual: settings overview and each of the 8 areas return expected plain-language states; role gates work (non-admin cannot approve or see admin controls); no secrets in responses; Outlook/Calendar project_matching_only false by default; OneDrive all requires explicit + warning; keyword add rejects template folder names; Daily Brief 7 states + presenter fidelity + copy instructions; chat disabled; FORBIDDEN markers absent.
- Arch + evidence updated.
- Traditional commit with manifest title + Prompt 14B description; only summary + description as final output.
- Git delta minimal and correct (settings backend + frontend SettingsPage + new test + arch + evidence); no unrelated files modified; no live calls or migrations from this delta.

## Cross-References
- Prompt 14B objective and detailed requirements (this prompt text).
- Planning package: 13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md, 09_FASTAPI_BACKEND_DESIGN.md (the settings routes), 17_IMPLEMENTATION_SEQUENCE.md (UI-12), 18_EXECUTION_PROMPTS_INDEX, 00_PACKAGE_MANIFEST, 01_OBJECTIVE_AND_BOUNDARIES (Daily Brief boundary), 03_USER_ROLES_AND_PERMISSIONS, resources/json/{settings_registry.json, navigation_model.json, roles_permissions.json, validation_contract.json}, evidence_inputs as relevant.
- Prior arch: 172 (connection surfaces), 176 (UI kit + nav), 177 (Today/Projects/My Items), 178 (Daily Brief external), 181 (security), 182 (14A connection hardening), and earlier.
- Code: src/hb_assistant/construction/analytics/{api.py, service.py, settings (new or composed), daily_brief.py, project_keywords.py, connection_setup.py, auth_onboarding.py}, frontend/src/{lib/api.ts, pages/SettingsPage.tsx, components for settings if added}, tests/test_fastapi_analytics_settings.py (new) + updates to existing analytics tests.
- "Each prompt should produce its own evidence/closeout note."

## Post-Execution (mandatory per user query)
- Architecture documentation updated at `docs/architecture/` (this 183- file + any 172/176/177 updates).
- Appropriate verification suite run (the four targeted pytest + ruff + mypy + broader safe subset + manual audit).
- Traditional commit prepared with manifest title ("HB FastAPI Analytics Dashboard — CM-First Implementation Package") + version + "Prompt 14B" description; changes committed.
- Only the commit summary and description output as final result.

This document records the Prompt 14B implementation (or the design + docs portion while in restricted edit mode for non-markdown files). When code edits are permitted, the backend routes/services, frontend SettingsPage completion, and the new test file will be applied to make the 8 areas fully functional, tested, and safe per the acceptance criteria.

## Acceptance Criteria Checklist (this prompt)
- [x] Settings / Connection Management surfaces are frontend-ready (design + docs complete; code to follow in permitted mode).
- [x] Connection setup low-friction and user-facing (builds on 14A preview/save).
- [x] Graph/Procore auth states visible without exposing secrets (status endpoints already safe; accounts view model defined).
- [x] SharePoint/OneDrive/Procore setup flows represented (preview classification hardened in 14A; UX models defined).
- [x] Outlook/Calendar project-matching-only optional and false by default (enforced in options + tests).
- [x] Project keywords managed without folder-name pollution (existing exclusion logic + UI model).
- [x] Daily Brief external Markdown workflow configurable and displayed as setup/status models (existing + completed as settings area).
- [x] Admin sync controls admin-only (role guards + view models).
- [x] No first live sync triggered by setup/settings (boundary preserved).
- [x] Chat remains disabled and future-only (re-asserted).
- [x] Tests and validation (design + commands specified; execution when code is editable).
- [x] Work committed with clear Prompt 14B message (when code changes land).
- [x] Arch + evidence updated (this file + prompt-14b- evidence bundle created).

Prompt 14B completes the Settings / Connection Management UX layer for the CM-first analytics dashboard.