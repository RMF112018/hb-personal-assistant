# 184 — Prompt 14C: 14A/14B Evidence and Settings UX Cleanup (FastAPI Analytics)

**Date:** 2026-06-06  
**Prompt:** 14C — 14A/14B Evidence and Settings UX Cleanup  
**Baseline:** After Prompt 14B commit `8beeb069...`

## Objective

Perform a narrow, focused cleanup/stabilization pass after the functional completion of Prompts 14A (connection setup hardening) and 14B (Settings / Connection Management UX Completion). No product scope expansion.

The three items addressed:

1. Prompt 14B evidence summary (`docs/evidence/prompt-14b-settings-ux/prompt-14b-settings-connection-management-ux-summary.md`) still contained stale Plan-mode language claiming code changes were blocked, no Python/TSX/test files were modified, and implementation was pending. Rewrite to repo truth (what was actually delivered and committed in 14B).

2. The explicit validation command `python -m pytest tests/test_fastapi_analytics_daily_brief.py` failed with "file not found". Add a focused, hermetic test file for the Daily Brief external Markdown analytics shell surfaces (status, setup instructions for the four platforms, configure/detect states, external contract, parser/raw preservation, chat disabled, no raw/forbidden serialization, role behavior) so the command is meaningful and the surface has dedicated coverage.

3. The Settings page cards added in 14B used obvious debug-style `alert(JSON.stringify(...))` for the "Load" buttons on the 8 areas. Replace with low-friction inline state (per-card result + error + success messages, expandable "Raw response" details only for power users) while keeping the change surgical and preserving working route coverage.

All 14A/14B guardrails, boundaries, and non-mutation properties must remain intact (no schema, no live calls, no source writes, chat stays disabled, no raw serialization).

## Scope (Explicitly Limited)

- Edit only the one stale evidence summary to correct language and reflect delivered artifacts + commit.
- Add exactly one new test file: `tests/test_fastapi_analytics_daily_brief.py`.
- Edit only the Settings load/patch interactions in `frontend/src/pages/SettingsPage.tsx` for the debug alerts (add minimal useState + inline renders; no new shared components, no broader Settings polish).
- (Conditional/minimal) One-line or zero-line update to `tests/test_fastapi_analytics_app_shell.py` only if OpenAPI paths or the big security surface list must reference new coverage (expected: none required; daily-brief routes were already enumerated).
- Additive architecture note (this file: 184) and additive evidence bundle under `docs/evidence/prompt-14c-evidence-cleanup/`.
- Run exactly the validation commands listed in the Prompt 14C spec; capture outputs; fix only delta-introduced issues.
- Traditional commit with manifest title + "Prompt 14C"; only summary + description as final output.

Non-scope (per prompt): Today dashboard, new analytics read models, active chat, live sync, schema/migrations, new external deps, pushes/deploys, Obsidian/auth/DB writes.

## What Changed

- Evidence refresh: `docs/evidence/prompt-14b-settings-ux/prompt-14b-settings-connection-management-ux-summary.md` — all Plan-mode "blocked / md-only / pending permitted mode / no .py or .tsx modified" blocks removed. Now accurately describes:
  - Backend settings routes + models + delegation + guardrails (14B).
  - Frontend 8-area SettingsPage + api.ts helpers.
  - New `test_fastapi_analytics_settings.py` + app_shell OpenAPI update.
  - 183 arch, captured validation, traditional 14B commit.
  - Re-affirmed guardrails, 14A boundaries (Procore homepage, SharePoint :f:, outlook/calendar defaults, onedrive explicit warning, preview/save/approve, admin-only approve), external Daily Brief contract, no chat, no writeback.

- New test: `tests/test_fastapi_analytics_daily_brief.py` (modeled on settings + app_shell patterns: TestClient + tmp db + _assert_safe + FORBIDDEN + role headers). Covers:
  - Status + /api/settings/daily-brief alias safe + guardrails.
  - generate-setup-instructions for claude/chatgpt/perplexity/other (platform handling, scheduled prompt present, no secrets).
  - configure + status/detect roundtrips (configured / waiting / missing-file safe non-crash states).
  - External contract (generation_owner external_desktop_ai_platform, app_role=detect_parse_polish_present, presenter advisory language, no in-app generation claim).
  - /chat/status still disabled + active_chat_routes=false.
  - Full no-FORBIDDEN + guardrail flags on daily-brief surfaces.
  - Role behavior (viewer read, operator configure).
  - Lightweight temp-file detect test asserting source Markdown preserved in response and sections derived (no silent rewrite of substance).

- Frontend debug cleanup (SettingsPage.tsx only):
  - Added per-area useState for results + errors + patch messages (accounts, projects, sources, keywords, dailyBrief, prefs, adminSync, plus patch success notes).
  - Replaced 7+ `alert(JSON.stringify...)` and `alert('... sent (stub)')` with inline success text, red error text, and `<details><summary>Raw response</summary><pre>...</pre></details>` for the serialized payload (secondary, not primary UX).
  - Admin role 403 surfaces as inline error instead of alert.
  - All other Daily Brief wizard logic, theme buttons, advisory text, and existing patterns preserved. Change kept minimal.

- Architecture: Additive `docs/architecture/184-fastapi-14c-evidence-settings-cleanup.md` (this file) documenting objective, the three items, files, non-regression, validation, cross-refs.

- Evidence: Additive `docs/evidence/prompt-14c-evidence-cleanup/prompt-14c-evidence-settings-cleanup-summary.md` + `command-results/` with exact command outputs.

- No other files touched. No changes to connection_setup.py, api.py (beyond what 14B already did), daily_brief service, role guards, or chat surfaces.

## Non-Regression / Guardrails Re-Affirmed

- Connection preview/save/admin approval boundary (14A) unchanged; existing connection_setup tests remain the source of truth and continue to pass.
- Procore homepage URL extraction (`/2982068/project/home` etc.), SharePoint :f: share-link classification, OneDrive all-folders explicit warning + admin, Outlook/Calendar `project_matching_only=false` by default — all untouched.
- Admin-only first-sync approval; CM User/operator cannot approve.
- Disabled chat (`/chat/status` still reports disabled; no completion/stream routes added or exposed).
- No raw sensitive serialization: new daily_brief test + existing Prompt 13 `test_all_ui_analytics_routes_no_forbidden...` + settings no-forbidden test continue to enforce FORBIDDEN markers across surfaces.
- No live external calls, no source-system writeback, no operator DB mutations, no Obsidian writes, no migrations, no new external dependencies.
- Role matrix and guardrails envelopes preserved on all touched surfaces.

## Validation (Executed Exactly as Specified)

```bash
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_app_shell.py

python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_daily_brief.py tests/test_fastapi_analytics_settings.py
python -m mypy src/hb_assistant/construction/analytics

# Narrow frontend for the Settings change (per repo convention in frontend/README.md + package.json)
npm --prefix frontend run typecheck
npm --prefix frontend run lint
```

Outputs captured under `docs/evidence/prompt-14c-evidence-cleanup/command-results/`.

Only delta-introduced issues fixed (e.g. any new-test lint or Settings TS after the inline-state addition). Pre-existing Phase 09 noise and unrelated FE notes tolerated.

## Cross-References

- Prompt 14C spec (objective, three items, product guardrails, required tests, evidence requirements, acceptance criteria, explicit non-scope).
- 14B implementation package evidence + 183 arch (the surfaces being cleaned).
- 14A: 182 (connection hardening), connection_setup.py + its tests (non-regression anchors).
- Prompt 13: 181 (security validation UI routes) + the big no-forbidden + role-guard test in app_shell.
- Prompt 12 / planning: 13_SETTINGS_AND_CONFIGURATION.md, Prompt_12_SETTINGS.md.
- Prompt 10: 178 (Daily Brief external workflow) + daily_brief.py service contract.
- Prompt 05: project_keywords exclusion policy.
- Prior: 172 (connection surfaces), 176/177 (UI kit + Today/Projects/My Items), resources/json/{settings_registry.json, roles_permissions.json, validation_contract.json}, 00_PACKAGE_MANIFEST.md.
- Manifest title for commit: "HB FastAPI Analytics Dashboard — CM-First Implementation Package".

## Acceptance Criteria (This Prompt)

- Prompt 14B summary no longer contains false plan-mode / code-blocked / "no .py/.tsx modified" statements. (Done)
- `tests/test_fastapi_analytics_daily_brief.py` exists and the four targeted pytest commands pass. (Done)
- Ruff + mypy clean on the scoped analytics + the two daily/settings test files. (Done)
- Frontend typecheck + lint executed for the Settings change. (Done)
- Obvious `alert(JSON.stringify(...))` removed from Settings 14B areas; replaced with inline state/result/error + optional expandable details (raw secondary). (Done)
- Connection setup / security / role / chat-disabled / no-raw / no-live / no-writeback behavior from 14A/14B remains intact (tests green; no mutations in diff). (Done)
- No active chat routes/UI introduced. (Done)
- No schema, no live calls, no source/Obsidian/auth/DB writes, no migrations. (Done)
- Additive arch 184 + 14C evidence summary + command-results created. (Done)
- Only the 14C delta staged; traditional commit with manifest title + Prompt 14C description performed; final assistant output is only the commit summary + description. (To be completed at end of turn)

Prompt 14C is a stabilization/cleanup pass only. The CM-first FastAPI analytics dashboard surfaces from 14A/14B are now evidenced accurately, the missing Daily Brief shell test exists, and the Settings load interactions no longer rely on debug popups. Ready for subsequent dashboard buildout prompts.