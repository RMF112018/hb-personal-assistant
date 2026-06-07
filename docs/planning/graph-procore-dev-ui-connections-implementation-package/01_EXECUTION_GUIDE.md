# Execution Guide

## Operator objective

Repair the Dev UI Microsoft Graph and Procore connection workflows without weakening backend guardrails.

## Execution model

1. Start from `/Users/bobbyfetting/hb-personal-assistant`.
2. Run `P00` and stop if branch, dirty tree, or repo state is unsafe.
3. Implement backend contracts before frontend cards.
4. Add tests in the same prompt that introduces each contract.
5. Keep status routes metadata-only.
6. Run full backend/frontend validation and manual Dev browser validation before closeout.

## Required stop conditions

Stop and report before editing further if:

- unrelated dirty files are present;
- the active branch is not appropriate for this update;
- current repo already has equivalent endpoints but with different names and semantics need review;
- any route would need to expose tokens/secrets/cache paths/raw source data;
- any status endpoint would need to call Microsoft Graph or Procore live APIs;
- a proposed fix bypasses existing live-read gates;
- validation reveals a pre-existing safety regression.

## Execution discipline

- Do not collapse the package into one broad edit.
- Do not duplicate CLI logic if a backend service already exists.
- Do not add migrations unless existing receipt/status infrastructure cannot support the required metadata.
- Prefer thin FastAPI adapters over new integration logic.
- Treat frontend as a consumer of local backend contracts only.
- Keep normal UI copy plain and reserve route names, command names, and config flags for admin details.
