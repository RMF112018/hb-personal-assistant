# Architecture Documentation

This directory contains living architecture and decision records for the HB Personal Assistant project.

- `01-scaffold-overview.md` — Phase 1 foundation (PathPolicy, Typer CLI, config loader)
- `02-…` through `12-launchd-automation-and-diagnostics.md` — Phase evolution (store, classification, files, retrieval, automation/orchestrator, diagnostics)
- `13-testing-hardening-and-final-closeout.md` — Phase 13 closeout record (`v1.3.0`), preserved as historical evidence
- `remediation-gap-closure.md` — Prompt 01 repo truth reconciliation and remediation acceptance baseline
- `remediation-validation-baseline.md` — Prompt 04 validation baseline and scoped standards (pytest/ruff/mypy reconciliation)
- `remediation-delegated-graph-proof.md` — Prompt 05 runtime delegated Graph proof refresh and truthful gap reporting
- `remediation-bounded-graph-paging.md` — Prompt 07 bounded, deterministic Graph paging across mail/calendar/drive clients
- `remediation-provenance-safe-file-ingestion.md` — Prompt 08 provenance-safe ingest contract (`files sample` vs real `files ingest`)
- `remediation-integrated-daily-brief-content.md` — Prompt 09 Daily Brief sections wired to current context/store sources with explicit empty states
- `remediation-bounded-content-sensitive-scan.md` — Prompt 10 bounded line-level sensitive scanner with redacted findings output
- `remediation-final-truthful-closeout.md` — Prompt 11 final remediation closeout status and acceptance gate evidence
- `remediation-hardened-app-support-permissions.md` — Addendum Prompt 02 path initialization hardening and `diagnostics paths` repair guidance
- `remediation-db-readiness-and-structured-dry-run-blocking.md` — Addendum Prompt 03 DB readiness gate and dry-run JSON blocked status behavior
- `docs/decisions/` — Closed technical decisions (D-CLI-001 etc.)

Remediation context: implementation reached `v1.3.0`, but acceptance is gated on remediation validation; prior closeout claims are superseded pending green remediation evidence.

For the full phased plan and research, see `docs/plans/my-pa-phase-0/`.
