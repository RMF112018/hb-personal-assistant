# Architecture Documentation

This directory contains living architecture and decision records for the HB Personal Assistant project.

- `01-scaffold-overview.md` — Phase 1 foundation (PathPolicy, Typer CLI, config loader)
- `02-…` through `12-launchd-automation-and-diagnostics.md` — Phase evolution (store, classification, files, retrieval, automation/orchestrator, diagnostics)
- `13-testing-hardening-and-final-closeout.md` — Phase 13 closeout record (`v1.3.0`), preserved as historical evidence
- `remediation-gap-closure.md` — Prompt 01 repo truth reconciliation and remediation acceptance baseline
- `remediation-validation-baseline.md` — Prompt 04 validation baseline and scoped standards (pytest/ruff/mypy reconciliation)
- `docs/decisions/` — Closed technical decisions (D-CLI-001 etc.)

Remediation context: implementation reached `v1.3.0`, but acceptance is gated on remediation validation; prior closeout claims are superseded pending green remediation evidence.

For the full phased plan and research, see `docs/plans/my-pa-phase-0/`.
