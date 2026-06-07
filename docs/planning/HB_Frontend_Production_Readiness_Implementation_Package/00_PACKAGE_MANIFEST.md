# 00 Package Manifest

Generated: 2026-06-07T07:23:55.448328+00:00

## Package Purpose

This is an implementation package for making the current FastAPI / Vite React analytics dashboard production-ready for local-first use. It is based on the audit package generated under `docs/evidence/frontend-production-readiness-audit/` and should be executed only after verifying current repository truth.

## Repository Baseline from Audit

- Repository: `RMF112018/hb-personal-assistant`
- Audited branch: `main`
- Latest visible HEAD during audit: `be470af1326c82b4c78be6103969e6a0622067be`
- Latest relevant FastAPI/frontend commit during audit: `4d902ce0ffb88e4e2e0eb362f7059cba0ff4928a`
- Python package version from audit: `1.3.0`
- Frontend package version from audit: `0.0.0`
- Severity count: P0=1, P1=7, P2=6, P3=4

## Included Files

- `README.md` — package use instructions.
- `00_PACKAGE_MANIFEST.md` — this manifest.
- `01_MASTER_AGENT_INSTRUCTIONS.md` — controlling instructions for the coding agent.
- `02_REPO_TRUTH_PREFLIGHT.md` — required preflight/rebaseline commands.
- `03_PRODUCT_AND_SAFETY_GUARDRAILS.md` — non-negotiable product/safety constraints.
- `04_ROUTE_API_CONTRACT_MATRIX.md` — audit-derived route/API alignment matrix.
- `05_GAP_TO_PROMPT_TRACEABILITY.md` — gap register mapped to implementation prompts.
- `06_VALIDATION_MATRIX.md` — command matrix and per-prompt evidence requirements.
- `07_BROWSER_SMOKE_TEST_PLAN.md` — local browser smoke plan.
- `08_ACCEPTANCE_EVIDENCE_TEMPLATE.md` — closeout template per prompt.
- `09_CLOSEOUT_AND_HANDOFF.md` — final closeout requirements.
- `prompts/PROMPT_16_*.md` through `prompts/PROMPT_25_*.md` — executable coding-agent prompts.
- `data/*.json` — machine-readable gap, route, API, prompt, and validation inventories.
- `source_audit_reference/` — copied audit markdown/json reference files.

## Execution Rule

Use repository truth over this package whenever they conflict. If current repo truth has already fixed a listed gap, verify the fix with tests and evidence, then mark that gap as already resolved rather than reimplementing it.
