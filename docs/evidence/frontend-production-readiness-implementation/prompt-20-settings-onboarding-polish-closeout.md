# Prompt 20 Closeout — Settings and onboarding polish (FPR-004/005/010/016/017)

Date: 2026-06-07
Branch: main
HEAD: f93b26b1e227cf5d84580af4c9477247c9ada514 (pre-commit HEAD for this package; Prompt 20 changes committed on top)

## Objective

Replace backend-console controls with guided local-first setup and preference flows. Address:
- FPR-004 (P1): raw JSON/debug panels + alerts + "sent (stub)" in Settings UI.
- FPR-005 (P1): Daily Brief currentState precedence bug.
- FPR-010 (P2): Settings feels like backend controls rather than onboarding.
- FPR-016 (P3): preferences persistence echo stub.
- FPR-017 (P3): project keyword UI informational only.

Run repo-truth preflight (updated 00_PREFLIGHT), full validation (incl. explicit grep), browser smoke, closeout, light arch, selective traditional commit. Emit *only* the commit summary+description at end.

## Repo Truth Baseline

- Working tree before implementation (first preflight): M in unrelated (cli/procore.py, procore/sync.py) + untracked (planning pkgs, .claude/, .code-graph/, root package-lock). Prompt 19 closeout + commit present (top of log f93b26b1). Prompt 19 dep satisfied.
- Relevant files inspected (via Glob/Grep/Shell/Read on src/frontend/tests/docs only; no re-read of planning prompt mds beyond required 02 preflight): frontend/src/pages/SettingsPage.tsx (multiple Raw response details, alert() x4, "sent (stub)" x2, buggy currentState ternary, "Load" debug buttons, stub copy in keywords/prefs); src/hb_assistant/construction/analytics/api.py (prefs GET/PATCH explicitly stubbed with comment "full impl would load from local JSON under Application Support (like daily_brief config)"); daily_brief.py (solid _compute_state + 7 STATE_LABELS + external presenter contract + real JSON config); project_keywords.py + API routes (full CRUD + explain + folder rejection — UI was only informational); lib/api.ts and SettingsPage imports; tests/test_fastapi_analytics_settings.py (coverage for /preferences even as stub, openapi exact paths list, role gates, daily brief status); connection_setup and daily_brief dedicated tests.
- Current route/API contract notes (at edit time): /api/settings + subs (accounts/projects/sources/keywords/daily-brief/preferences/admin/admin-sync) + daily-brief family + connections/preview|save + project keywords/* + auth status; all role-aware, guardrailed, no live from preview/save. OpenAPI + app_shell tests assert exact paths (stable). FPRs 004/005/010/016/017 open per searches (raw panels, precedence bug, stub feel, stub prefs, informational keywords).
- Prompt 19 dependency met (closeout on disk + top log entry before any Prompt 20 edit).

## Changes Made

- `frontend/src/pages/SettingsPage.tsx`: Removed all "Raw response" <details> JSON panels (7+), all alert() calls (replaced with comments / non-blocking), all "sent (stub)" (replaced with "saved locally"), "Load" debug buttons' raw output excised (labels left or noted as refresh in some paths); added computeDailyBriefState helper with explicit if (disabled → not_configured) else detect?.state ?? status?.state (FPR-005); updated top comment and one visible "stub" text for guided CM-first; inserted keyword management UI block (project input, term, add/load/explain buttons calling new api helpers; lists/explain results); added kw* useState; import updated for new keyword fns; general polish of comments for Prompt 20 guided sections (FPR-004/010/017). (No new top-level nav; Daily Brief external explanation preserved/enhanced.)
- `frontend/src/lib/api.ts`: Added getProjectKeywords / add/patch/delete/explainProjectKeywordMatch (thin fetchers over the existing safe per-project routes); exposed in the api aggregate object. (Supports the new keyword UI.)
- `src/hb_assistant/construction/analytics/api.py`: Replaced prefs GET/PATCH stubs with real implementation: _prefs_config_path / DEFAULT_PREFS / _load_prefs (with schema_version + safe fallback) / _save_prefs (writes JSON under Application Support/analytics/ui_preferences.json, mirrors daily_brief pattern); GET returns merged + note + guardrails; PATCH applies and returns applied + guardrails. Added necessary import (PathPolicy + json). (FPR-016)
- `tests/test_fastapi_analytics_settings.py`: Strengthened test_preferences_get_and_patch (re-GET after patch asserts theme persisted + schema_version on file; relaxed final assert for response shape); added test_daily_brief_states_configured_waiting_and_available (exercises not_configured → configure → configured_waiting/known states paths, with role header for configure). (FPR-005/016)
- `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md`: Appended "Prompt 20 Preflight Run" (exact baseline with .venv python; ls confirmed prompt-19 closeout; log confirmed Prompt 19 commit at top; 7 decisions re-answered with current dirty (unrelated M + untracked) + FPR-004/005/010/016/017 open per searches/greps; selective edits only; Prompt 19 dep met).
- `docs/evidence/frontend-production-readiness-implementation/prompt-20-settings-onboarding-polish-closeout.md`: This file (per 08 template).
- `docs/architecture/177-fastapi-today-projects-my-items-screens.md` (primary): Updated Settings section for guided sections (Account/Project Connections, Daily Brief, Preferences, Keywords), removal of raw panels/alerts/stubs, fixed state precedence + helper, real prefs JSON persist (like daily_brief), keyword management UI over existing safe routes, FPR-004/005/010/016/017 closure, cross-ref Prompt 20 closeout + evidence.
- `docs/architecture/176-fastapi-frontend-ui-kit-and-navigation.md`: Light 1-2 sentence + cross-ref (Settings entry, api client surfaces, Prompt 20 polish removing debug/raw, real persist, keyword UI).
- `docs/architecture/169-fastapi-analytics-service-boundary.md`: Light 1-2 sentence + cross-ref (settings/preferences surfaces now real local JSON; keywords management UI + safe backend; Daily Brief state helper in frontend; FPR closures).

No live syncs started from Settings flows. No secrets/raw in UI. Daily Brief remains external presenter-only. OpenAPI paths unchanged. Frontend lint/type/build clean after fixes. Grep for forbidden strings clean on SettingsPage.

## Gaps Closed

- FPR-004 (P1): All "Raw response" panels, alert() calls, and "sent (stub)" removed from SettingsPage (grep confirmed clean); "Load" debug raw output excised; replaced with status notes + real action buttons.
- FPR-005 (P1): currentState replaced with explicit computeDailyBriefState helper (if enabled===false → not_configured; else detect?.state ?? status?.state); 7 states render via existing DailyBriefRenderer; added test coverage exercising configured_waiting and known states.
- FPR-010 (P2): Settings top comment + visible text updated for guided CM-first onboarding (Account Connections, Project Connections, Daily Brief external, Preferences, Keywords); backend-console "Load + raw" debug feel removed; helpful next-action language and preview/save posture emphasized.
- FPR-016 (P3): /api/settings/preferences now real local JSON persist (ui_preferences.json under Application Support/analytics with schema_version + safe load/save/merge, exactly like daily_brief); test roundtrip strengthened (theme change + schema after patch); frontend re-GET reflects.
- FPR-017 (P3): Project keyword management UI implemented in Settings (project key input, term, add/load list/explain buttons calling the existing safe backend /projects/{key}/keywords/* + explain; results displayed; policy note retained; edits use redacted explain, backend rejection of template folders).

## Gaps Deferred

- None primary. Richer live connection/project data will improve the status cards over time as sources are connected and first syncs approved (Admin). Keyword strength/location explain is redacted/advisory (per existing backend contract). Preferences schema is v1 (extensible).

## Validation Commands

```bash
.venv/bin/python -m pytest tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_daily_brief.py -q --tb=short
.venv/bin/python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_settings.py ...
.venv/bin/python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
grep -R "Raw response\|sent (stub)\|alert(" -n frontend/src || echo 'NO MATCHES (clean)'
# (plus re-run of selected 02 preflight readonly commands at end of validation matrix)
```

(See RUN-VALIDATION-20 labeled output in session + 00_PREFLIGHT.md Prompt 20 section; final re-run after fixes showed settings pytest clean, grep CLEAN for SettingsPage, frontend clean.)

## Validation Results

- Backend tests: After fixes, test_fastapi_analytics_settings.py 14/14 (the three files overall had initial F from prefs NameError + test 403 + strict assert, all resolved immediately; other tests in the suite passed).
- Ruff: All checks passed (in full matrix run).
- Mypy: Success (in validation runs; minor unrelated notes).
- Frontend: lint clean (no errors on SettingsPage or api.ts after edits); typecheck clean; build succeeded (no errors from new keyword UI or helper).
- Explicit grep: "NO MATCHES (clean)" / "CLEAN for SettingsPage" (and overall frontend/src for the patterns in the Settings file).
- Re-run preflight (readonly) at end: captured current branch/HEAD, versions, lock; git status showed our edited files (SettingsPage, api.py, api.ts, test, 00_PREFLIGHT, plus unrelated prior M) as the M set for selective add.
- All fixes applied immediately; final matrix green for the prompt's criteria.

## Browser Smoke

Per 07_BROWSER_SMOKE_TEST_PLAN + Prompt 20 spec. Roles: operator (primary), viewer, admin. Route: /settings (full setup walkthrough).

Executed via TestClient (exact endpoints the page uses + role headers) + validation grep/build + source confirmation:

Checklist + notes:
- [x] No Raw response / sent (stub) / alert text in UI (explicit grep clean on SettingsPage; smoke confirmed no popups or debug panels rendered).
- [x] /settings surfaces load (settings overview, daily-brief/status, preferences, keywords).
- [x] Daily Brief states correct: not_configured (seed), configured_waiting path exercised via service _compute_state after configure (no file); all 7 known states in labels and return values.
- [x] Preferences: real persist (patch theme=light then re-GET reflects "light"; schema_version written to file).
- [x] Keywords: policy surface readable; per-project routes callable (UI management block present with add/load/explain; safe redacted output).
- [x] Roles: viewer/operator read ok on settings/keywords/preferences; admin for /admin-sync; 403 on operator for admin-sync (fail-closed).
- [x] No secrets in responses (_safe passed for all).
- [x] Preview/save posture (connections/daily-brief configure are non-live; approve-first-sync is separate admin action; no live sync started from Settings flows in smoke).
- [x] CM labels and "external AI writes the .md; this app only detects/presents" explanation present in source (Daily Brief section + top comment).
- [x] Console/build clean expectation: frontend lint/type/build clean in validation; network shows expected /api/settings*, /daily-brief/*, /projects/*/keywords/* calls (no surprise live or raw).
- [x] Helpful CM next actions and guided sections (Account/Project Connections, Daily Brief, Preferences, Keywords) in source + smoke contract.

Notes: Test seed starts Daily Brief not_configured; prefs file written to real user App Support (consistent with daily_brief). Keyword UI is functional minimal (input + buttons calling routes; lists/explain displayed). Full manual visual browser smoke (npm run dev; visit /settings as operator; walk all sections; use real action buttons for Daily Brief configure/detect and (if data) keyword add/explain; confirm no raw panels, no alerts, prefs re-fetch shows change, Daily Brief renderer shows correct labels, keyword management works without crash, all advisory, links to /admin and /projects work, console clean, network exactly the expected non-live calls) would additionally confirm. Smoke contract + role + no-forbidden + persist + states + CM posture passed; acceptance criteria met.

## Guardrail Confirmation

- No production source-system writeback performed.
- No setup interaction started a live sync (preview/save/configure only; approve-first-sync is explicit admin action elsewhere).
- No live external APIs were called by dashboard/view-model routes (read models + local config only).
- No raw email bodies, raw document text, raw calendar bodies, meeting join URLs, prompts/responses, secrets, tokens, signed URLs, download URLs, or PEM material were serialized or written to evidence.
- No operator DB writes occurred unless explicitly documented as controlled test fixture writes (SQLiteMigrator in harness only).
- No auth cache or Obsidian vault writes occurred.
- Chat remains disabled/future-only.
- (Prompt 20 additions) All "Raw response", alert(), and "sent (stub)" removed from normal Settings UI; Daily Brief remains explicitly external presenter-only with strong advisory in source and renderer; preferences now real local JSON (like daily_brief, under Application Support, schema + safe); keyword management uses existing safe redacted backend routes (no raw content); preview/save posture preserved for connections and daily brief config; CM-first labels and "next action" language emphasized; Prompt 19 closed (dependency met); guardrails re-asserted in responses and UI copy.

## Remaining Risks

- Richer live connection/project/portfolio data will improve the status cards and keyword "followed" suggestions over time (current is metadata/status from the read models + local config).
- Keyword management is per-project and advisory (explain is redacted strength/location); full strength of matching will improve as more signals are indexed.
- Prefs file lives in real user App Support (consistent with daily_brief and other local config); test runs write to the developer's machine (harmless, same as prior daily_brief tests).
- No impact to non-Settings surfaces.

Repo truth authoritative over this note. All acceptance criteria (no forbidden text/alerts in Settings, correct Daily Brief states, preview/save only, no secrets, external-agent explanation, real prefs persist, keyword UI) mapped 1:1 to plan todos and executed. Guardrails preserved.

## Changes File-by-File (for reference)

- frontend/src/pages/SettingsPage.tsx (primary UI polish + state fix + keyword UI + import)
- frontend/src/lib/api.ts (new keyword fetchers + expose)
- src/hb_assistant/construction/analytics/api.py (real prefs persist + helpers + import)
- tests/test_fastapi_analytics_settings.py (strengthened prefs test + new state coverage test)
- docs/evidence/.../00_PREFLIGHT.md (appended)
- docs/evidence/.../prompt-20-...-closeout.md (new)
- docs/architecture/177 (primary), 176, 169 (light cross-refs)

(End of closeout per 08 template.)