# Preflight Repo-Truth Requirements

Before implementation, the local coding agent must confirm current repo truth.

## Required Baseline Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30
python - <<'PY'
import tomllib
from pathlib import Path
p = tomllib.loads(Path('pyproject.toml').read_text())
print('project version:', p.get('project', {}).get('version'))
PY
cat frontend/package.json
find src/hb_assistant -iname '*graph*' -o -iname '*procore*' -o -iname '*oauth*' -o -iname '*auth*'
find tests -iname '*graph*' -o -iname '*procore*' -o -iname '*oauth*' -o -iname '*auth*' -o -iname '*connection*'
```

## Expected Baseline Based on Prior Audit

- Branch: likely `main` unless local worktree differs.
- HEAD used to generate this package: `be470af1326c82b4c78be6103969e6a0622067be`.
- Python package version: `1.3.0`.
- Frontend package version: `0.0.0`.
- Microsoft auth library: `msal` is declared.
- Procore auth: custom OAuth/client/token-provider utilities exist; no dedicated Procore SDK was observed.
- FastAPI and frontend dependencies exist through optional backend extras and frontend package scripts.

## Required Preflight Decisions

If repo truth differs from this package, the coding agent must:

1. Prefer repo truth over this package.
2. Document the difference in the implementation summary.
3. Adapt file paths and route names without weakening the hard constraints.
4. Avoid deleting existing tests or guardrails unless replacing them with stronger equivalents.

## Working Branch

Create a branch before implementation:

```bash
git checkout -b frontend-auth-onboarding-production-ready
```

## No External Side Effects During Tests Unless Explicitly Opted In

Default tests must use mocks/fakes. Do not initiate real Graph or Procore auth during automated validation.
