# 01 Master Agent Instructions

You are working on the `RMF112018/hb-personal-assistant` repository at `/Users/bobbyfetting/hb-personal-assistant`.

## Objective

Implement the frontend production-readiness plan for the FastAPI / Vite React analytics dashboard. The end state is a construction-management-first, local-first command center with the top-level navigation:

```text
Today
Projects
My Items
Admin / Data Confidence
Settings
```

The application should not feel like a CLI wrapper, backend console, engineering telemetry dashboard, or placeholder demo.

## Controlling Scope

Execute the implementation prompts in numeric order:

1. Prompt 16 — Route/API contract hardening and launch blockers.
2. Prompt 17 — Today dashboard UX/content completion.
3. Prompt 18 — Projects portfolio and project dashboards.
4. Prompt 19 — My Items dashboard.
5. Prompt 20 — Settings and onboarding polish.
6. Prompt 21 — Admin / Data Confidence polish.
7. Prompt 22 — UI kit, accessibility, responsiveness consolidation.
8. Prompt 23 — End-to-end local smoke harness.
9. Prompt 24 — Local-first production hardening.
10. Prompt 25 — Documentation and runbook packaging.

Do not skip Prompt 16. It addresses the only P0 gap and the highest-risk route/API mismatches.

## Repo Truth Rule

Before modifying code, run the preflight in `02_REPO_TRUTH_PREFLIGHT.md`. If the current branch/HEAD differs from the audit baseline, update the implementation plan notes and continue against current repo truth.

## Safety and Product Rules

- No active or accessible in-app chat route.
- `/chat/status` may exist only as disabled/future status.
- No source-system writeback.
- No setup interaction starts a live sync.
- Admin-only first live sync approval/scheduling remains admin-only.
- No raw email bodies, calendar bodies, document text, prompts/responses, secrets, tokens, signed URLs, download URLs, PEM material, or auth cache content in UI, logs, tests, or evidence.
- Dashboard/view-model routes should not make live external calls.
- Daily Brief remains an external-agent Markdown workflow. The app detects, parses, presents, and preserves the original file.
- Local dev role selector remains clearly labeled as local-only and not production auth. Default local role remains `operator` unless current repo truth intentionally changed that with evidence.

## Implementation Style

- Prefer small, typed adapters over broad backend rewrites when fixing frontend/backend shape mismatches.
- Keep data confidence visible but secondary.
- Use construction-facing labels.
- Keep top-level navigation narrow.
- Avoid introducing domain-specific top-level routes for Meetings, Field Operations, Cost & Time, Documents, Correspondence, Vendors, Billing/Cash, Closeout, RFIs, Submittals, Daily Logs, Observations, Punch List, Startup, or Schedule. Those must remain contextual under Today, Projects, or My Items.
- Do not use `--legacy-peer-deps` as a silent permanent fix. If unavoidable for temporary diagnosis, document it as technical debt and preserve a normal install path as the target.

## Evidence Required After Each Prompt

Create or update evidence under:

```text
docs/evidence/frontend-production-readiness-implementation/
```

Each prompt closeout must include:

- branch and HEAD;
- files changed;
- gaps closed or deferred;
- commands run and results;
- browser smoke results where applicable;
- explicit guardrail statement covering no writeback, no live external calls unless explicitly scoped, no raw/secrets evidence, no operator DB/auth cache/Obsidian modifications unless explicitly required and controlled.
