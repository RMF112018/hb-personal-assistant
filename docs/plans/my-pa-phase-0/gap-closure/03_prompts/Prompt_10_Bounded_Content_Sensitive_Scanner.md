# Prompt 10: Bounded Content Sensitive Scanner

## Objective

Upgrade sensitive scanning from filename/path heuristics to bounded content scanning that still never emits secret values.

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
- Create evidence under `docs/evidence/remediation/prompt-10-*/`.

## Tasks

1. Implement a scanner module under `src/hb_assistant/security/` or equivalent.
2. Scan repo root, Application Support paths, and evidence folders.
3. File handling:
   - skip binary files;
   - skip files over configured max size unless extension is high risk;
   - scan text-like files by line.
4. Detect PEM/private key headers, JWT-like tokens, OAuth token fields, `client_secret`, bearer token strings, MSAL cache files, and `.env` secret assignments.
5. Output category, path, line number, severity, and no matched secret value.
6. Add tests for synthetic token detection, false-positive handling, binary skip, and redacted output.

## Validation

```bash
python -m pytest tests/test_sensitive_scan*.py
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Required Commit

```text
fix(security): implement bounded content sensitive scan
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
