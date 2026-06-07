# P00 — Preflight and Branch Discipline

## Objective

Reconfirm current repo truth, create a safe implementation branch if needed, and capture baseline evidence before any source edits.

## Scope

- Git status, branch, HEAD, recent commit chain.
- Frontend package scripts and dependency reality.
- Python package version.
- Current frontend file inventory.
- Current visible forbidden-copy hits.
- Current shell/layout files.

## Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30
cat pyproject.toml
cat frontend/package.json
find frontend/src -maxdepth 4 -type f | sort

grep -R "local dev role\|not production auth\|Prompt 14B\|Prompt 20\|FPR-004\|raw panels\|JSON.stringify\|FastAPI\|uvicorn\|read model\|source/sync/evidence\|Chat (disabled)\|Vite\|HMR" -n frontend/src || true
```

## Acceptance criteria

- Branch and HEAD documented.
- Dirty tree state documented.
- Any baseline divergence from `bc59f1c1631c9525c47477e14c137d85ab6d630d` documented.
- Implementation branch created or current branch explicitly accepted by operator.
- No source edits made in this prompt except optional evidence notes.

## Stop condition

Stop and report if unrelated dirty files exist and the operator has not authorized editing around them.
