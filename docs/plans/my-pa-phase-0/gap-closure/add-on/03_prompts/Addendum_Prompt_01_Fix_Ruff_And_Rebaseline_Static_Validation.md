# Addendum Prompt 01: Fix Ruff And Rebaseline Static Validation

## Objective

Clear the current Ruff failure and establish a clean static validation baseline before touching runtime path code.

## Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
source .venv/bin/activate
python --version
hb-assistant --version
```

## Operating Rules

- Do not re-run broad feature work from the prior remediation package.
- Keep the patch scoped to this addendum prompt.
- Do not enable Microsoft 365 writeback.
- Do not persist full email bodies.
- Do not commit tokens, PEM contents, SQLite DB files, token caches, or private `.env` files.
- Evidence must be truthful. If a command fails, record it as failed.
- Do not claim final acceptance until Addendum Prompt 06 is green.

## Tasks

1. Fix security scanner lint:
   - organize imports in `src/hb_assistant/security/__init__.py`;
   - remove unused `os` import from `src/hb_assistant/security/sensitive_scan.py`.
2. Run Ruff auto-fix if desired, but review the diff.
3. Confirm no functional scanner behavior changed unless required by lint.
4. Capture validation evidence.

## Required Validation

```bash
ruff check .
mypy src
python -m pytest tests/test_sensitive_scan.py tests/test_sensitive_scan_cli.py
```

## Expected Result

All three commands pass.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-01/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
fix(security): clean sensitive scanner lint violations
```
