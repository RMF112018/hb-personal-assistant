# HB Personal Assistant Remediation Addendum — Corrections + Final Gap Closure

**Package date:** 2026-05-25  
**Target repo:** `RMF112018/hb-personal-assistant`  
**Current audited commit:** `aa1cf1b360ab97740913fbf4bbaa70dc693992c3`  
**Purpose:** Add-on package for the prior remediation/gap-closure package. This package instructs the local agent to correct the remaining `NOT_ACCEPTED` items and the underreported bounded-body-mention gap.

## Current State

The remediation sprint improved the repo materially, but final closeout remains `NOT_ACCEPTED`.

Known remaining blockers from the latest audit:

1. `ruff check .` fails due two fixable lint violations in the security scanner.
2. `hb-assistant auth status --json` fails due Application Support permission handling.
3. `hb-assistant diagnostics graph --safe --json` fails due the same Application Support permission blocker.
4. `hb-assistant diagnostics proof delegated-graph --json` fails due the same permission blocker.
5. `hb-assistant files ingest --dry-run --json` fails with `unable to open database file`.
6. `hb-assistant run morning --dry-run --json` fails with `unable to open database file`.
7. Underreported gap: bounded body mention detection still appears preview-only and does not yet satisfy the original MVP requirement.

## Addendum Structure

| Folder | Purpose |
|---|---|
| `00_readme/` | Package entry point. |
| `01_current_assessment/` | Current state and acceptance position. |
| `02_correction_register/` | Corrections required before acceptance. |
| `03_prompts/` | Sequenced add-on prompts for the local code agent. |
| `04_validation/` | Updated validation matrix and final acceptance rules. |
| `05_operations/` | Application Support, DB, launchd, and path repair guidance. |
| `06_security/` | Permission, redaction, and scanner guardrails. |
| `07_resources/` | Command snippets, commit plan, and evidence templates. |

## Execution Instruction

Use this package **after** the original remediation/gap-closure package. Do not re-run the entire original package. Execute only these addendum prompts in sequence.

Do not mark the repo accepted until the final validation matrix is green and the delegated Graph proof either passes or is explicitly blocked by a user/manual Microsoft permission condition unrelated to code or local path readiness.
