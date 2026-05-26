# Prompt 05: Current Delegated Graph Proof

## Objective

Re-run and refresh delegated Microsoft Graph proof from the current repo/runtime using Bobby’s delegated token.

## Required Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python --version
```

Do not proceed if the working tree contains unrelated uncommitted changes unless you first document them and isolate your patch.

## Agent Rules

- Do not trust prior closeout claims.
- Do not re-read files already in current context unless changed or required by failing tests.
- Do not enable Microsoft 365 writeback.
- Do not log or commit tokens, private keys, PEM bodies, full email bodies, or full file contents.
- Keep the patch tightly scoped to this prompt.
- Create evidence under `docs/evidence/remediation/prompt-05-*/`.

## Prerequisites

Bobby may need to run:

```bash
hb-assistant auth login --json
```

The agent must not claim delegated proof if a delegated token is unavailable.

## Proof Scope

Validate current runtime read capability for:

1. `/me`
2. inbox mail metadata
3. sent mail metadata
4. bounded body retrieval for one candidate message
5. calendarView
6. attachment metadata where available
7. drive root / recent file metadata
8. controlled small-file download proof if available and eligible
9. app-only rejection for mail/calendar runtime
10. sensitive scan after proof

## Tasks

1. Update proof runner so it is importable and executable through CLI:
   - `hb-assistant diagnostics proof delegated-graph --json`
2. Ensure proof uses current CLI/auth code, not stale scripts.
3. Capture delegated token classification:
   - delegated = `scp` present and `roles` absent for runtime.
4. Store only sanitized proof records.
5. If a permission fails, document as a true gap with exact Graph status and remediation.

## Validation

```bash
hb-assistant auth status --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Required Commit

```text
test(graph): refresh delegated graph proof for current runtime
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
