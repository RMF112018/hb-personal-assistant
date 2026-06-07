# Implementation Sequence

Run prompts in order.

## Prompt A — Auth Route Contract and Safe Status Models

Creates normalized backend façade routes and shared state models.

Dependency: none.

## Prompt B — Microsoft Graph Local Auth Flow

Implements verified Graph status, device-flow sessions, polling, silent refresh, and local disconnect.

Dependency: Prompt A.

## Prompt C — Procore Local OAuth Flow

Implements OAuth start/callback/status, state validation, refresh, manual fallback, and local disconnect.

Dependency: Prompt A.

## Prompt D — Get Started and Account Connections UX

Implements `/get-started`, startup readiness routing, Graph/Procore connection cards, stale-auth refresh UX, and no raw JSON panels.

Dependencies: Prompts A, B, C.

## Prompt E — Project Connections Auth-Aware Setup Flow

Implements project/source preview/save UI and typed API helpers.

Dependencies: Prompts A, B, C, D.

## Prompt F — Admin First-Sync Approval Integration

Normalizes approval queue and sync eligibility guardrails across source types.

Dependency: Prompt E.

## Prompt G — Data Quality Readiness/Freshness Surfaces

Implements non-admin sidebar Data Quality indicator and admin Settings diagnostics.

Dependencies: Prompts A, F.

## Prompt H — Auth/Security Regression Tests and Smoke Harness

Adds tests and smoke commands for auth/onboarding/security.

Dependencies: Prompts A-G.

## Prompt I — Documentation and Runbook

Updates docs/runbooks after implementation is complete and validated.

Dependency: Prompt H.

## Stop Criteria

Stop and report before proceeding if:

- a route requires exposing tokens to frontend;
- a test requires real external auth by default;
- implementation would start live sync during setup;
- admin first-sync approval cannot be enforced;
- repo truth contradicts a package assumption materially.
