# HB Personal Assistant Remediation + Gap Closure Implementation Package

**Package date:** 2026-05-25  
**Target repo:** `RMF112018/hb-personal-assistant`  
**Accessible audit ref:** `d0cc5516f51f02c5a2d7f2e30379aab2b98abc52`  
**User-stated ref requiring reconciliation:** `63bb05c7163b85ff556f0a599a19cf9bba501280`  
**Package purpose:** Guide the local code agent through the remediation required before the HB Personal Assistant MVP can be accepted as complete, hardened, and automation-ready.

## Executive Position

The repo is architecturally aligned and contains substantial work from the 13 executed prompts, but it is **not accepted as complete** until the remediation work in this package is finished and proven with clean evidence.

The current closeout evidence is internally inconsistent:

- The Phase 13 proof claims complete / clean / no writes.
- Captured pytest evidence shows failures.
- Captured Ruff evidence shows lint failures.
- Captured auth command evidence shows a CLI grammar failure.
- launchd appears to render a command shape that does not match the implemented Typer command shape.
- The delegated Graph proof is not currently proven from the current repo/runtime state.
- The body-mention requirement is only preview-based and does not yet satisfy the original requirement.

## Package Structure

| Folder | Purpose |
|---|---|
| `00_readme/` | Start here; package map and execution instructions. |
| `01_strategy/` | Target state, remediation principles, non-negotiable guardrails. |
| `02_gap_register/` | Detailed blocker/gap register with acceptance criteria. |
| `03_prompts/` | Sequenced local-agent prompts for implementation. |
| `04_validation/` | Validation matrix, evidence standards, closeout checklist. |
| `05_security/` | Read-only M365, redaction, sensitive scan, token/cache protections. |
| `06_operations/` | launchd, runbook, CLI command contract. |
| `07_resources/` | Command snippets, expected CLI grammar, commit plan, issue matrix. |

## Execution Rule

The local agent must execute this as a remediation sprint, not as a new feature wave.

The agent must not mark the MVP complete until:

1. The canonical git ref is reconciled.
2. `pytest`, `ruff`, and `mypy` pass under the agreed scope.
3. Canonical CLI commands run successfully.
4. launchd renders a valid executable and command.
5. delegated Graph proof passes from the current runtime.
6. body mention detection works beyond `bodyPreview`.
7. paging and ingestion provenance are corrected.
8. sensitive scan reads file content safely, not just filenames.
9. final evidence truthfully reflects command outputs.
