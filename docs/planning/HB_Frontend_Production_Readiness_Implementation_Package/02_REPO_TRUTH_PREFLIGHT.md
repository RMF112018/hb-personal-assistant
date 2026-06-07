# 02 Repo Truth Preflight

Run this before Prompt 16 and again before any later prompt if another session or commit has landed.

## Baseline Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30
python -m pip show fastapi || true
python -m pytest --version
python - <<'PYLOCAL'
import tomllib
from pathlib import Path
pyproject = tomllib.loads(Path('pyproject.toml').read_text())
print('project.version=', pyproject.get('project', {}).get('version'))
print('optional-dependencies=', sorted(pyproject.get('project', {}).get('optional-dependencies', {}).keys()))
PYLOCAL

cd frontend
node --version
npm --version
cat package.json
[ -f package-lock.json ] && echo 'package-lock.json present' || echo 'package-lock.json missing'
npm install
```

## Required Preflight Decisions

Document the answers in `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md`:

- Is the working tree clean before implementation?
- Is local `main` at or ahead of audited HEAD `be470af1326c82b4c78be6103969e6a0622067be`?
- Are there new frontend/backend commits after the audit?
- Do any P0/P1 gaps appear already fixed?
- Does `npm install` complete without `--legacy-peer-deps`?
- Does the FastAPI optional dependency group still include the dashboard dependencies?
- Does the frontend lockfile appear current relative to `package.json`?

## If Preflight Fails

- If the working tree is dirty, inventory the dirty files and determine whether they are user changes. Do not overwrite them.
- If dependencies do not install, classify as a Prompt 16 blocker and fix as part of launch hardening.
- If the audit baseline is stale, update evidence but continue against current repo truth.
