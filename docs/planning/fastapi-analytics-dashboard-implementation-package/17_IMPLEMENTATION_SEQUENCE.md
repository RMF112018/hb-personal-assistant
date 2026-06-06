# Implementation Sequence

## Phase UI-00 — Rebaseline and Package Load

Confirm repo HEAD, schema version, metrics evidence, and no active frontend/FastAPI surface assumptions.

## Phase UI-01 — Service Boundary

Create reusable application services behind the UI. Do not shell out to CLI commands.

## Phase UI-02 — FastAPI Shell

Add FastAPI optional dependency and app shell with health, role dependencies, OpenAPI, `/api/navigation`, and disabled chat status.

## Phase UI-03 — Auth and Onboarding

Add Graph/Procore auth status surfaces and first-run onboarding flow.

## Phase UI-04 — Connection Management

Implement Procore URL parsing, SharePoint URL classification, OneDrive scope selection, Outlook/Calendar scope defaults.

## Phase UI-05 — Project Matching Keywords

Implement project keyword registry, exclusions, no-folder-name generation rule, edit/disable/delete UX.

## Phase UI-06 — Sync Governance

Implement admin-only first sync approval/schedule controls and automated freshness status surfaces.

## Phase UI-07 — Dashboard Read Models

Implement read models/endpoints for the simplified dashboard hierarchy:

1. Today;
2. Projects Portfolio / All Projects;
3. Individual Project Overview;
4. Project Meetings;
5. Project Field Operations;
6. Project Cost & Time;
7. My Items;
8. Admin / Data Confidence.

## Phase UI-08 — Frontend UI Kit and Navigation

Add Vite/React/TypeScript/Tailwind/shadcn-style modular UI shell with dark/system theme and the simplified navigation model:

- Today;
- Projects;
- My Items;
- Admin / Data Confidence;
- Settings.

Do not implement top-level pages for Cost / Change, Documents, Correspondence, Vendors, Billing / Cash, Closeout, or Chat.

## Phase UI-09 — Today, Projects, and My Items Screens

Implement the primary low-friction screens:

- Today dashboard;
- Projects portfolio and selector;
- All Projects aggregated dashboard;
- Project Overview / Meetings / Field Operations / Cost & Time tabs;
- My Items dashboard.

## Phase UI-10 — Daily Brief External Workflow

Implement external platform setup instructions, scheduled prompt generation, Markdown file detection, and polished executive renderer inside Today.

## Phase UI-11 — Admin / Data Confidence

Implement source/sync/job/evidence/guardrail/retrieval/permission dashboards.

## Phase UI-12 — Settings

Implement role-aware settings for theme, default landing, followed projects, Daily Brief setup, keyword preferences, auth reconnect/revoke, and admin-only sync/source controls.

## Phase UI-13 — Validation and Closeout

Run tests, no-raw scans, no-writeback proofs, UI route checks, and closeout evidence.
