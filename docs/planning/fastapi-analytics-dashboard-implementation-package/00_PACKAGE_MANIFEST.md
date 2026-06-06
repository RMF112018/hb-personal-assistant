# HB FastAPI Analytics Dashboard — CM-First Implementation Package

Generated: `2026-06-06T09:59:17.223062+00:00`

## Purpose

Direct a local coding agent to implement a FastAPI-backed, construction-management-first, low-friction analytics and time-management UI over the existing local-first HB Personal Assistant repository.

This package supersedes the earlier FastAPI dashboard package by incorporating the latest product clarifications:

- The UI is for construction management users first.
- Admin / Data Confidence is a supporting trust and configuration layer.
- The app must feel like it is doing the work for the user, not exposing CLI controls.
- Users should authenticate Graph and Procore during first setup; tokens remain local.
- Data connections are managed by pasting user-friendly URLs.
- Only Admin users may schedule/trigger the first live sync for a project.
- Project keyword training must not use standard/template folder names.
- Outlook and Calendar project-matching-only scope is optional and not default.
- In-app chat is future/stub-only and disabled.
- Daily Brief is generated externally as Markdown by a desktop AI platform/agent and polished/presented by the app.

## Metrics Baseline

- Total metrics: `135`
- Construction Operations: `90`
- Admin / Data Confidence: `35`
- Hybrid: `10`

## Package Files

1. `01_OBJECTIVE_AND_BOUNDARIES.md`
2. `02_PRODUCT_PRINCIPLES_CM_FIRST.md`
3. `03_USER_ROLES_AND_PERMISSIONS.md`
4. `04_ONBOARDING_AUTH_AND_CONNECTIONS.md`
5. `05_DATA_SOURCE_SETUP_AND_SCOPE.md`
6. `06_PROJECT_MATCHING_KEYWORDS.md`
7. `07_AUTOMATED_SYNC_AND_FRESHNESS.md`
8. `08_DAILY_BRIEF_EXTERNAL_AGENT_WORKFLOW.md`
9. `09_FASTAPI_BACKEND_DESIGN.md`
10. `10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md`
11. `11_FRONTEND_UI_STRUCTURE.md`
12. `12_UI_KIT_THEME_AND_COMPONENTS.md`
13. `13_SETTINGS_AND_CONFIGURATION.md`
14. `14_ADMIN_DATA_CONFIDENCE.md`
15. `15_SECURITY_GUARDRAILS_AND_PRIVACY.md`
16. `16_TESTING_VALIDATION_ACCEPTANCE.md`
17. `17_IMPLEMENTATION_SEQUENCE.md`
18. `18_EXECUTION_PROMPTS_INDEX.md`
19. `prompts/Prompt_00` through `Prompt_14`
20. `resources/json/*`
21. `evidence_inputs/*`

## Hard Non-Goals

- No active in-app chat UI.
- No user-facing dry-run/apply/execute terminology in primary construction workflows.
- No source-system writeback.
- No raw email body, raw document text, raw prompt/response, token, signed URL, or secret exposure.
- No ordinary Construction Management User first-sync trigger for newly added/existing projects.
- No rigid bespoke design system; use modular UI elements and free/off-the-shelf packages wherever practical.
