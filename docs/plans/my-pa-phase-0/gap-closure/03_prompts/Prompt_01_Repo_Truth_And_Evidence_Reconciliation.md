# Prompt 01: Repo Truth And Evidence Reconciliation

## Objective

Reconcile the current local/remote ref, correct overstated closeout documentation, and establish a truthful remediation baseline.

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
- Create evidence under `docs/evidence/remediation/prompt-01-*/`.

## Tasks

1. Verify the current local and remote commit state.
2. Attempt to locate user-stated SHA `63bb05c7163b85ff556f0a599a19cf9bba501280`:
   - `git cat-file -t 63bb05c7163b85ff556f0a599a19cf9bba501280`
   - `git branch --contains 63bb05c7163b85ff556f0a599a19cf9bba501280`
   - `git reflog --all | grep 63bb05c7163b`
   - `git ls-remote --heads --tags origin | grep 63bb05c7163b`
3. Compare local `HEAD` to remote `origin/main`.
4. Create `docs/evidence/remediation/remediation-baseline.md` containing current branch, local HEAD, origin/main, status of `63bb05c7163b85ff556f0a599a19cf9bba501280`, and whether the working tree was clean.
5. Update README if it still claims Phase 1 or points to Prompt 02 as next.
6. Add a remediation status section: “Implemented through v1.3.0 but not accepted until remediation validation is green.”
7. Update or add `docs/architecture/remediation-gap-closure.md`.
8. Do not delete prior evidence. Add a note that prior Phase 13 closeout evidence is superseded pending remediation.

## Validation

```bash
git status --short
grep -n "Current Phase\|v1.3.0\|remediation" README.md || true
test -f docs/evidence/remediation/remediation-baseline.md
```

## Required Commit

```text
chore(audit): reconcile repo truth and closeout evidence
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
