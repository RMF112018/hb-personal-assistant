# HB Auth Onboarding Implementation Package — README

## Purpose

This package guides implementation of a production-ready authentication and onboarding path for the `hb-personal-assistant` frontend/backend setup, focused on Microsoft Graph and Procore.

The core problem addressed is that the app currently lacks a complete, user-operable path to:

- connect Microsoft Graph / Microsoft 365;
- connect Procore;
- confirm safe connection status;
- preview and save project/source connections;
- require admin approval before first live sync;
- expose data readiness/freshness without leaking sensitive details.

This package is implementation guidance only. It should be applied by a local coding agent against current repository truth.

---

## Repository Target

```text
/Users/bobbyfetting/hb-personal-assistant
```

Repository truth remains authoritative over this package. The local coding agent must inspect the current repo before making changes.

---

## Package Contents

```text
HB_Auth_Onboarding_Implementation_Package/
  00_PACKAGE_MANIFEST.md
  01_EXECUTIVE_BRIEF.md
  02_PREFLIGHT_REPO_TRUTH.md
  03_TARGET_ARCHITECTURE.md
  04_BACKEND_ROUTE_CONTRACTS.md
  05_FRONTEND_UX_SPEC.md
  06_SECURITY_GUARDRAILS.md
  07_ONBOARDING_AND_DATA_QUALITY_SPEC.md
  08_TEST_AND_VALIDATION_PLAN.md
  09_IMPLEMENTATION_SEQUENCE.md
  10_ACCEPTANCE_CHECKLIST.md
  11_GAP_REGISTER.md

  data/
    auth_onboarding_gap_register.json
    auth_route_contracts.json
    frontend_component_plan.json

  prompts/
    PROMPT_A_AUTH_ROUTE_CONTRACT_AND_SAFE_STATUS_MODELS.md
    PROMPT_B_MICROSOFT_GRAPH_LOCAL_AUTH_FLOW.md
    PROMPT_C_PROCORE_LOCAL_OAUTH_FLOW.md
    PROMPT_D_GET_STARTED_AND_ACCOUNT_CONNECTIONS_UX.md
    PROMPT_E_PROJECT_CONNECTIONS_AUTH_AWARE_SETUP_FLOW.md
    PROMPT_F_ADMIN_FIRST_SYNC_APPROVAL_INTEGRATION.md
    PROMPT_G_DATA_QUALITY_READINESS_FRESHNESS_SURFACES.md
    PROMPT_H_AUTH_SECURITY_REGRESSION_TESTS_AND_SMOKE_HARNESS.md
    PROMPT_I_DOCUMENTATION_AND_RUNBOOK.md
```

---

## Recommended Reading Order

1. `00_PACKAGE_MANIFEST.md`
2. `01_EXECUTIVE_BRIEF.md`
3. `02_PREFLIGHT_REPO_TRUTH.md`
4. `03_TARGET_ARCHITECTURE.md`
5. `04_BACKEND_ROUTE_CONTRACTS.md`
6. `05_FRONTEND_UX_SPEC.md`
7. `06_SECURITY_GUARDRAILS.md`
8. `07_ONBOARDING_AND_DATA_QUALITY_SPEC.md`
9. `08_TEST_AND_VALIDATION_PLAN.md`
10. `09_IMPLEMENTATION_SEQUENCE.md`
11. `10_ACCEPTANCE_CHECKLIST.md`
12. `11_GAP_REGISTER.md`

Use the JSON files in `data/` as structured planning references. Use the prompt files in `prompts/` as the execution sequence for the local coding agent.

---

## Implementation Sequence

Execute the prompts in order unless repo-truth findings require adjustment.

### Prompt A — Auth Route Contract and Safe Status Models

Establish the safe backend route contract and state model for authentication, onboarding readiness, account status, refresh status, and user-safe connection summaries.

### Prompt B — Microsoft Graph Local Auth Flow

Implement Microsoft Graph local authentication using a local-first MSAL-compatible flow, with silent refresh before reauthentication prompts and no token exposure to the frontend.

### Prompt C — Procore Local OAuth Flow

Implement backend-controlled Procore OAuth, including callback/manual fallback where appropriate, token cache handling, refresh behavior, and safe connected-state reporting.

### Prompt D — Get Started and Account Connections UX

Add the dedicated Get Started onboarding surface for fully unauthenticated sessions and account connection cards for Microsoft 365 and Procore.

### Prompt E — Project Connections Auth-Aware Setup Flow

Add auth-aware setup flows for Procore project URLs, SharePoint/OneDrive source locations, and optional Outlook/Calendar project matching.

### Prompt F — Admin First-Sync Approval Integration

Ensure preview/save never starts sync and that first live sync requires admin approval through governed paths.

### Prompt G — Data Quality Readiness/Freshness Surfaces

Implement the non-admin sidebar footer indicator:

```text
Data Quality  ●
```

The indicator should be green/yellow/red, with latest update date/time revealed on hover. Admins may access detailed diagnostics in Settings.

### Prompt H — Auth/Security Regression Tests and Smoke Harness

Add regression coverage for auth onboarding, token non-exposure, no writeback, no setup-triggered sync, route contracts, frontend state handling, and local smoke validation.

### Prompt I — Documentation and Runbook

Update docs/runbooks after implementation is complete and validated.

---

## Key UX Decisions

### First-Time / Fully Unauthenticated Sessions

Fully unauthenticated sessions should land on a dedicated Get Started screen, not the main app shell.

The Get Started screen should guide the user through:

- Microsoft 365 connection;
- Procore connection;
- project/source setup;
- preview/save;
- admin first-sync approval.

It must clearly state that connecting an account, previewing a source, or saving a setup does not start live sync.

### Returning Users With Stale Auth

Returning users who previously authenticated should not be forced through first-time onboarding.

The system should:

1. detect prior setup/auth state;
2. attempt automated refresh of the needed auth;
3. enter the main app if refresh succeeds;
4. prompt source-specific reauthentication only if refresh fails.

### Non-Admin Data Quality Indicator

Non-admin users should see only a simple readiness indicator in the sidebar footer.

The hover state may show:

- data quality status;
- latest successful update date/time;
- short plain-language message.

It must not show:

- raw JSON;
- source payloads;
- token/cache paths;
- auth diagnostics;
- approval queue internals;
- raw email/document content;
- prompts/responses;
- signed URLs or download URLs.

### Admin Diagnostics

Admin users may access detailed sync readiness, source freshness, auth status, approval state, disabled-action reasons, and troubleshooting diagnostics from Settings.

---

## Security Guardrails

Implementation must preserve these constraints:

- no source-system writeback;
- no active in-app chat;
- no tokens, secrets, signed URLs, download URLs, PEM material, raw prompt/response content, raw email bodies, or raw document text serialized to the frontend;
- no live sync during account connection;
- no live sync during preview;
- no live sync during save;
- first live sync requires admin approval;
- Outlook and Calendar project matching remain optional and false by default unless current repo truth explicitly contradicts this;
- auth refresh may update only local auth/token cache state and must not trigger source sync;
- frontend localStorage must not store auth tokens, refresh tokens, secrets, or source payloads.

---

## Validation Commands

Run the backend validation commands from the repository root:

```bash
python -m pytest tests/test_fastapi_analytics_connection_setup.py
python -m pytest tests/test_fastapi_analytics_settings.py
python -m pytest tests/test_fastapi_analytics_app_shell.py
python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py
python -m pytest tests/test_fastapi_analytics_daily_brief.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
python -m mypy src/hb_assistant/construction/analytics
```

Run the frontend validation commands from `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

Add targeted tests as implementation proceeds, especially for:

- first-time onboarding route behavior;
- stale-auth silent refresh;
- reauth-required fallback;
- Microsoft Graph auth route contract;
- Procore OAuth callback/manual fallback;
- no token/secret/frontend leakage;
- no sync on connect/preview/save;
- admin first-sync approval gating;
- non-admin Data Quality indicator behavior;
- admin diagnostics visibility.

---

## Manual Smoke Test Checklist

### First-Time User

1. Start backend.
2. Start frontend.
3. Open app with no prior auth/setup.
4. Confirm app lands on Get Started.
5. Confirm main app shell is not presented as fully ready.
6. Confirm Microsoft 365 and Procore setup actions are available.
7. Confirm copy states that connecting accounts does not start sync.

### Returning User With Valid Auth

1. Start backend and frontend.
2. Open app with valid prior auth/setup.
3. Confirm app enters main shell.
4. Confirm sidebar footer shows Data Quality indicator.
5. Hover over Data Quality.
6. Confirm latest update date/time appears.
7. Confirm no raw diagnostics appear for non-admin users.

### Returning User With Stale Auth

1. Simulate stale Microsoft Graph and/or Procore auth.
2. Open app.
3. Confirm backend attempts automated refresh first.
4. Confirm successful refresh does not prompt user.
5. Confirm failed refresh produces a source-specific reauth prompt.
6. Confirm no sync starts during refresh.

### Project Connection Setup

1. Connect or simulate authenticated account status.
2. Enter a Procore project homepage URL.
3. Preview parsed project information.
4. Save project connection.
5. Confirm first-sync approval is queued or required.
6. Confirm no live sync starts.

### Security

1. Inspect frontend network responses.
2. Confirm no tokens/secrets/cache paths are returned.
3. Confirm no raw email/document bodies are returned.
4. Confirm no signed/download URLs are returned.
5. Confirm no source-system writeback occurs.

---

## Acceptance Criteria

The implementation is not complete until all of the following are true:

- fully unauthenticated sessions land on Get Started;
- returning users with stale auth get automated refresh before reauth prompt;
- Microsoft Graph can be connected from the app;
- Procore can be connected from the app;
- connection status is safe, user-readable, and non-tokenized;
- preview/save flows do not trigger live sync;
- first live sync requires admin approval;
- non-admin users see a simple Data Quality indicator only;
- hover reveals latest update date/time and simple status message;
- admin users can view detailed readiness/freshness diagnostics;
- frontend does not expose raw JSON/debug panels to normal users;
- tests cover auth, onboarding, refresh, approval gating, and no-secret behavior;
- lint/typecheck/build pass;
- no auth cache, operator DB, Obsidian vault, Graph account, Procore account, or external systems are modified except through explicitly intended local auth/setup behavior during implementation testing.

---

## Notes for the Local Coding Agent

- Do not treat this package as repo truth.
- Start each prompt with a fresh repo inspection.
- Do not assume route names are final if current repo truth differs.
- Prefer adapting existing backend primitives over duplicating auth logic.
- Keep route responses safe for frontend serialization.
- Avoid adding broad dependencies unless justified by repo truth.
- Keep implementation local-first and cross-platform.
- Keep sync execution separate from setup, refresh, preview, and save.
- Preserve existing no-writeback and no-raw-content policy posture.
