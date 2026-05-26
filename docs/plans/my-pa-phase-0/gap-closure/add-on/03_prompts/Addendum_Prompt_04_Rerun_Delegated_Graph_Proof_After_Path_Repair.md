# Addendum Prompt 04: Rerun Delegated Graph Proof After Path Repair

## Objective

Re-run and validate the delegated Graph proof after path/DB readiness blockers are resolved.

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

## Prerequisite

Addendum Prompts 01–03 must be committed first.

## Tasks

1. Run:

```bash
hb-assistant auth status --json
```

2. If no delegated token exists, run:

```bash
hb-assistant auth login --json
```

3. Re-run:

```bash
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
```

4. If Microsoft permission gaps remain, classify them as external/manual blockers only if:
   - path readiness is green;
   - token cache is readable/writable;
   - delegated token exists or login completes;
   - proof runner reaches Graph and receives Graph status responses.

5. Update proof evidence and known issues.

## Required Validation

```bash
hb-assistant auth status --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics scan-sensitive --repo . --json
python -m pytest tests/test_graph_proof.py tests/test_auth.py
```

## Expected Result

- Path permission no longer blocks proof.
- Proof either passes or returns a true Microsoft permission/auth blocker with Graph status.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-04/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
test(graph): rerun delegated proof after local path repair
```
