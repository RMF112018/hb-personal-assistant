# Prompt 00 — Repo Truth Rebaseline and Branch

## Objective

Create the implementation branch, record repo truth, confirm schema/audit context, and prepare evidence scaffolding.

## Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate

git fetch origin
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git branch --contains HEAD
git rev-parse main
git rev-parse origin/main
git log --oneline --decorate --graph -30 --all
git branch --all --sort=-committerdate | head -40
```

## Required Actions

1. If not already on a clean implementation branch, create `fix/daily-brief-usefulness-repair`.
2. Confirm no unexpected dirty files.
3. Create `docs/evidence/daily-brief-usefulness-repair/00-rebaseline/`.
4. Copy safe summaries only from the private audit, not raw DB/private output.
5. Record branch, HEAD, main/origin/main, dirty tree, package manifest, audit basis, current CLI help, and schema/status if safe.

## Acceptance

- Evidence root exists.
- Repo truth captured.
- Branch correct and clean except intended evidence.
- No code changes yet unless required by repo setup.

## Suggested Commit

`docs(second-brain): add daily brief usefulness repair baseline`
