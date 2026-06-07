# HB Local Production Launcher + Desktop Shortcut Implementation Package

Generated: 2026-06-07T07:51:05.617603+00:00

## Purpose

This package is a follow-on implementation package to be executed **after** completion and validation of the previously generated `HB_Frontend_Production_Readiness_Implementation_Package`.

Its purpose is to direct a local coding agent to add a stable, local-first production launcher and desktop shortcut workflow for the FastAPI + frontend analytics dashboard.

## Scope

This package covers:

- A single-command production launcher for the local dashboard.
- Static frontend serving from the local backend where appropriate.
- Browser auto-open behavior.
- Port/process conflict handling.
- Log and PID file conventions.
- macOS `.command` shortcut support.
- Optional macOS Automator/Shortcuts app wrapper guidance.
- Optional Windows shortcut guidance for future portability.
- Validation and smoke-test scripts.
- Documentation/runbook updates.

## Non-Scope

This package does **not** cover:

- Additional dashboard feature development.
- API route contract fixes from Prompt 16–25.
- New auth providers.
- Electron/Tauri/desktop executable packaging.
- Cloud deployment.
- Source-system writeback.
- Live external sync behavior changes.

## Required Execution Position

Execute this package only after the previous frontend production-readiness implementation package has been completed and closed out.

Minimum expected preconditions:

- Frontend route/API contract alignment is complete.
- `npm run build` succeeds.
- Backend FastAPI app starts cleanly.
- The local browser smoke test passes.
- Settings, Today, Projects, My Items, and Admin/Data Confidence are locally usable.
- Any production static serving decisions from Prompt 24 are resolved or available for this package to finalize.

## Package Contents

| File | Purpose |
|---|---|
| `00_PACKAGE_MANIFEST.md` | Package inventory and execution scope |
| `01_EXECUTION_BRIEF.md` | High-level implementation brief |
| `02_PRODUCT_AND_ARCHITECTURE_DECISION.md` | Decision record: local web app first, executable wrapper later |
| `03_LAUNCHER_REQUIREMENTS.md` | Functional/non-functional requirements |
| `04_PROMPT_26_SINGLE_COMMAND_LOCAL_PRODUCTION_LAUNCHER.md` | Main implementation prompt |
| `05_PROMPT_27_DESKTOP_SHORTCUTS_AND_RUNBOOK.md` | Shortcut/runbook prompt |
| `06_VALIDATION_MATRIX.md` | Validation commands and expected results |
| `07_SMOKE_TEST_PLAN.md` | Manual local smoke test plan |
| `08_RISK_REGISTER.md` | Launcher-specific risk register |
| `09_ACCEPTANCE_EVIDENCE_TEMPLATE.md` | Required closeout evidence template |
| `10_NEXT_PHASE_OPTIONS.md` | Future executable packaging options |
| `launcher_gap_register.json` | Machine-readable gap register |
| `launcher_prompt_sequence.json` | Machine-readable prompt sequence |
| `shortcut_support_matrix.json` | Machine-readable shortcut support matrix |

## Guardrail Statement

The implementation agent must not create a desktop executable runtime in this package. The intended target is a reliable local-first web application launched by a single command and optionally started from a desktop shortcut.
