# HB Auth Onboarding Implementation Package

Generated: 2026-06-07

Repository: `/Users/bobbyfetting/hb-personal-assistant`

Audited branch / ref used for planning: `main` / `be470af1326c82b4c78be6103969e6a0622067be`

Python package version observed: `1.3.0`

Frontend package version observed: `0.0.0`

## Purpose

This package directs a local coding agent through implementation of a production-ready, local-first authentication and onboarding path for Microsoft Graph and Procore in the `hb-personal-assistant` repository.

The implementation objective is to resolve the current blocking issue: the app has backend primitives and partial Settings surfaces, but it does not yet provide a usable end-to-end path for a non-engineering user to authenticate Microsoft Graph or Procore, preview/save source connections, request first-sync admin approval, and see data freshness/quality status without exposing sensitive data.

## Hard Constraints

- Repository truth is authoritative.
- Implement in the live repository only after creating a working branch.
- Do not serialize tokens, secrets, signed URLs, download URLs, PEM material, raw prompts/responses, raw email bodies, or raw document text to the frontend.
- No source-system writeback.
- No setup interaction may start live sync automatically.
- Preview does not sync.
- Save does not sync.
- First live sync requires admin approval.
- Outlook and Calendar project-matching-only behavior remains optional and false by default unless repo truth proves otherwise.
- Non-admin users receive only a simple Data Quality indicator, not detailed diagnostics.
- Returning stale-auth users must get silent refresh first; re-auth is prompted only after automated refresh fails.
- Fully unauthenticated first-time users land on a dedicated Get Started screen.

## Files Included

- `00_PACKAGE_MANIFEST.md`
- `01_EXECUTIVE_BRIEF.md`
- `02_PREFLIGHT_REPO_TRUTH.md`
- `03_TARGET_ARCHITECTURE.md`
- `04_BACKEND_ROUTE_CONTRACTS.md`
- `05_FRONTEND_UX_SPEC.md`
- `06_SECURITY_GUARDRAILS.md`
- `07_ONBOARDING_AND_DATA_QUALITY_SPEC.md`
- `08_TEST_AND_VALIDATION_PLAN.md`
- `09_IMPLEMENTATION_SEQUENCE.md`
- `10_ACCEPTANCE_CHECKLIST.md`
- `11_GAP_REGISTER.md`
- `prompts/PROMPT_A_AUTH_ROUTE_CONTRACT_AND_SAFE_STATUS_MODELS.md`
- `prompts/PROMPT_B_MICROSOFT_GRAPH_LOCAL_AUTH_FLOW.md`
- `prompts/PROMPT_C_PROCORE_LOCAL_OAUTH_FLOW.md`
- `prompts/PROMPT_D_GET_STARTED_AND_ACCOUNT_CONNECTIONS_UX.md`
- `prompts/PROMPT_E_PROJECT_CONNECTIONS_AUTH_AWARE_SETUP_FLOW.md`
- `prompts/PROMPT_F_ADMIN_FIRST_SYNC_APPROVAL_INTEGRATION.md`
- `prompts/PROMPT_G_DATA_QUALITY_READINESS_FRESHNESS_SURFACES.md`
- `prompts/PROMPT_H_AUTH_SECURITY_REGRESSION_TESTS_AND_SMOKE_HARNESS.md`
- `prompts/PROMPT_I_DOCUMENTATION_AND_RUNBOOK.md`
- `data/auth_onboarding_gap_register.json`
- `data/auth_route_contracts.json`
- `data/frontend_component_plan.json`

## Recommended Execution Model

Run prompts A through I in order. Each prompt is implementation-ready and includes objective, scope, non-scope, likely files touched, acceptance criteria, validation commands, risk notes, and dependencies.

Do not skip Prompt A. It creates the shared route/status contract that prevents the frontend from binding directly to mixed root-level auth/setup endpoints.
