# 194. Frontend Settings Guided Setup

Date: 2026-06-07

Package: Frontend UI/UX Shell Layout Implementation Package

## Decision

Settings is organized as guided setup panels for account connections, project connections, Daily Brief, preferences, project keywords, data health, and update approval.

The frontend consumes the existing normalized routes already exposed through `frontend/src/lib/api.ts`: onboarding readiness, account summaries, project connection preview/save/list, data health summary/detail, and Daily Brief status/configuration.

## Rationale

Settings is a normal user setup surface, not a debug console. It should present clear actions and safe status summaries while keeping implementation details, generated setup material, and admin-only detail behind explicit disclosures or gated panels.

## Guardrails

- Do not add backend routes for this layout change.
- Do not start live sync from status, preview, save, or approval checks.
- Do not render raw JSON or prompt/debug labels in normal Settings UI.
- Keep Daily Brief advanced setup and diagnostics collapsed by default.
