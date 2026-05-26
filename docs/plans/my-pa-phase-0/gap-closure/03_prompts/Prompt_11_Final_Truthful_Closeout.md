# Prompt 11: Final Truthful Closeout

## Objective

Regenerate the final closeout evidence only after all remediation validation passes.

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
- Create evidence under `docs/evidence/remediation/prompt-11-*/`.

## Tasks

1. Run the full validation matrix from `04_validation/01_validation_matrix.md`.
2. Create `docs/evidence/remediation/final-closeout/`.
3. Generate:
   - `final-closeout-proof.json`
   - `final-validation-summary.md`
   - `command-results/`
   - `known-issues.md`
4. Update README, architecture remediation closeout doc, validation result register, and prompt execution log.
5. The proof must not claim “clean” unless:
   - pytest passes;
   - ruff passes;
   - mypy passes;
   - canonical CLI commands pass;
   - delegated Graph proof current-state passes or explicitly identifies manual permission blocker;
   - sensitive scan passes.
6. If anything is not complete, mark status as `NOT_ACCEPTED` and list remaining blockers.

## Validation

```bash
python -m pytest
ruff check .
mypy src
hb-assistant --version
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
```

## Required Commit

```text
chore(closeout): regenerate truthful final remediation evidence
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
