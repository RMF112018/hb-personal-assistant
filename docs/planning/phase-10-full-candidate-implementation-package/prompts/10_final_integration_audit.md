# Prompt 10 — Final Integration Audit and Handoff

## Objective

Conduct a full repo-truth integration audit of all implemented Phase 10 candidates, validate that their final outputs work together, and prepare the final handoff.

Do not add new product scope in this prompt. Fix integration defects only if they are directly caused by the prior nine prompts.

## Required audit

Inspect:

- all commits on `experiment/phase-10-full-candidate-implementation`
- all changed files
- all evidence directories
- all final output artifacts
- all CLI surfaces added/changed
- all schema migrations, if any
- all daily-run/browser/Obsidian/status surfaces
- all safety scan outputs
- all guard-column proofs
- all production DB checksum proofs
- all test/lint/type results

## Required integration validation

Run the strongest practical validation suite.

At minimum:

```bash
git status --short
git log --oneline main..HEAD
python -m compileall src tests
pytest -q tests
```

Run repo-standard lint and typing if available. If broad validation fails due to pre-existing or environmental failures, document exact failures and prove changed files/candidates are locally validated.

## Required final output evidence

Generate in:

```text
docs/evidence/phase-10-full-candidate-implementation/10-final-integration-audit/
```

Required files:

- `README.md`
- `01-final-handoff.md`
- `02-commit-log.txt`
- `03-changed-files.txt`
- `04-evidence-index.md`
- `05-final-output-index.md`
- `06-validation-matrix.md`
- `07-safety-matrix.md`
- `08-schema-migration-summary.md`
- `09-db-mutation-summary.md`
- `10-manual-verification-runbook.md`
- `11-merge-readiness-assessment.md`
- `12-known-limitations.md`
- `13-final-git-status.txt`

## Final handoff requirements

The final handoff must include:

1. Branch and final HEAD.
2. Baseline SHA and current `origin/main`.
3. Commit list.
4. Candidate-by-candidate summary.
5. Candidate-by-candidate final output artifact list.
6. Evidence directory index.
7. Validation matrix.
8. Safety matrix.
9. Schema/migration summary.
10. DB mutation summary.
11. Known limitations.
12. Merge recommendation.
13. Exact commands Bobby can run to verify locally.
14. Exact command to create a PR, if merge-ready.

## Stop conditions

If any of the following are true, do not recommend merge:

- uncommitted tracked changes remain
- broad candidate evidence is missing
- any final-output artifact is missing
- safety scan fails
- external writeback occurred
- cloud LLM fallback occurred
- production DB mutated unexpectedly
- daily brief final surfaces are inconsistent
- generated outputs contain raw/private content
- tests fail due to changes introduced by this branch

## Commit

If final docs/evidence changed, commit:

```text
docs(second-brain): add phase 10 full candidate handoff
```

No 10-minute wait is required after the final prompt.
