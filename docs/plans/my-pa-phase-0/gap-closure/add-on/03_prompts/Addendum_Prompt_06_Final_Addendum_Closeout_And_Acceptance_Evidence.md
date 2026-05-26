# Addendum Prompt 06: Final Addendum Closeout And Acceptance Evidence

## Objective

Regenerate final evidence after all addendum corrections and determine whether the repo is accepted.

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

1. Run the complete final validation matrix.
2. Create:

```text
docs/evidence/remediation-addendum/final-closeout/
```

3. Generate:
   - `final-addendum-closeout-proof.json`
   - `final-addendum-validation-summary.md`
   - `known-issues.md`
   - `command-results/manifest.json`
   - individual command output files.

4. Update:
   - README closeout status;
   - architecture remediation final note;
   - validation result register;
   - prompt execution log.

5. Status rules:
   - Use `ACCEPTED` only if all required local code/runtime gates are green.
   - Use `NOT_ACCEPTED` if any command fails due code/local path issue.
   - Use `CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_BLOCKER` only if all local code/path gates are green and only Microsoft permission/admin consent or missing delegated login remains.

## Required Final Validation Matrix

```bash
git status --short
git rev-parse HEAD
python -m pytest
ruff check .
mypy src
hb-assistant --version
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics paths --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
hb-assistant files sample --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
```

## Expected Result

A truthful final evidence bundle. No acceptance claim unless supported by command outputs.

## Evidence Required

Create/update:

```text
docs/evidence/remediation-addendum/prompt-06/
```

Include:

- `commands.md`
- command output files
- `summary.md`
- `known-issues.md`

## Required Commit

```text
chore(closeout): regenerate addendum acceptance evidence
```
