# Prompt 04: Validation Baseline Green

## Objective

Make the repo’s core validation commands green or explicitly scope them with documented rationale.

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
- Create evidence under `docs/evidence/remediation/prompt-04-*/`.

## Tasks

1. Fix the failing tests shown in prior evidence:
   - `tests/test_auth.py::test_delegated_provider_status_no_token`
   - `tests/test_config.py::test_no_secrets_in_paths_or_config`
2. Fix Ruff failures in source and scripts.
3. Update Ruff config to current `[tool.ruff.lint]` format.
4. Ensure `mypy src` has a captured output file and passes under the agreed scope.
5. Do not mark failures as “pre-existing” unless they are out of scope, documented, isolated, and excluded by an explicit validation standard.
6. Add `docs/evidence/remediation/prompt-04-validation-baseline/validation-summary.md`.

## Validation

```bash
python -m pytest
ruff check .
mypy src
hb-assistant --version
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics automation --json
```

## Required Commit

```text
fix(validation): make tests lint and type checks pass
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
