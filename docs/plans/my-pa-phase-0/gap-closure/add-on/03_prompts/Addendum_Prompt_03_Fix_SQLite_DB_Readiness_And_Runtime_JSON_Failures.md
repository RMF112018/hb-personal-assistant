# Addendum Prompt 03: Fix SQLite DB Readiness And Runtime JSON Failures

## Objective

Resolve `unable to open database file` failures and ensure file ingestion and morning runs fail gracefully when data is unavailable.

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

## Problem Context

`files ingest --dry-run` and `run morning --dry-run` fail because SQLite cannot open the DB path.

## Tasks

### 1. Add explicit DB readiness

Implement a helper such as:

```python
PathPolicy.ensure_db_ready(return_report: bool = False)
```

or:

```python
Store.check_readiness()
```

It must verify:

- app support exists;
- DB parent exists;
- DB parent is a directory;
- DB parent is writable;
- SQLite can open DB or returns a structured reason;
- WAL sidecar creation is possible or gracefully degrades if appropriate.

### 2. Harden `get_connection()`

Before `sqlite3.connect()`:

- ensure DB parent exists;
- check writability;
- raise a custom error with path and repair guidance rather than raw `OperationalError`.

### 3. Harden CLI outputs

`hb-assistant files ingest --dry-run --json` should return valid JSON for:

- no DB available;
- no provenance candidates;
- candidate discovery error.

`hb-assistant run morning --dry-run --json` should return valid JSON for:

- DB unavailable;
- path unavailable;
- orchestrator skipped stages.

### 4. Prefer structured skip over crash

For dry-run only, if DB is unavailable, return a clear `status: "blocked_db_unavailable"` result.

Do not hide real failure; make it actionable.

## Required Validation

```bash
hb-assistant diagnostics paths --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
python -m pytest tests/test_store.py tests/test_files_cli.py tests/test_automation.py tests/test_cli_canonical.py
```

## Expected Result

- No raw traceback.
- JSON outputs are valid.
- If no candidates exist, `files ingest` reports `no_provenance_candidates`.
- If DB is writable, migrations initialize successfully.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-03/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
fix(store): add db readiness checks and structured runtime errors
```
