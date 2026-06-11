# 00 — Repo Truth and Branch Preflight

## Objective

Establish repo truth, branch safety, and current implementation baseline before changing code.

## Steps

1. Enter the repo and capture git state:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git rev-parse origin/main
git show --stat --oneline --decorate 4d8ca0717324955dab539ebf0690b5a93d4db6e0
git log --oneline --decorate --graph -40 --all
```

2. Create or inspect the working branch:

```bash
git checkout main
git pull --ff-only
git checkout -b experiment/phase-10-daily-brief-raw-projection-first-slice
```

If the branch exists, inspect it and continue only if safe. Do not reset or force-push.

3. Check for local-only config:

```bash
git ls-files config/config.yml || true
test -f config/config.yml && ls -l config/config.yml || true
git status --short -- config/config.yml || true
```

4. Capture current relevant files and tests:

```bash
rg -n "LATEST_SCHEMA_VERSION|V46|V47|V48|V49|email_calendar|projection-reprocess|daily_brief_action_candidates|candidate_source_refs|build_calendar_prep_candidates|build_procore_action_digest|gate_model_candidate_context|usefulness|contradiction|data_gaps|project_alias|construction_project_identity" src tests docs > /tmp/first-slice-rg-baseline.txt
```

## Evidence

Create:

- `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/00-repo-state.md`
- `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/01-branch-state.txt`
- `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/02-target-commit-basis.md`

## Acceptance

- Branch is not `main`.
- Dirty state is understood before implementation.
- Target commit/PR basis is documented.
- No code modified yet except evidence files.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
