# Repo-Truth Preflight

Run this before any source edits.

```bash
cd /Users/bobbyfetting/hb-personal-assistant

git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -n 30

cat pyproject.toml
cat frontend/package.json
find frontend/src -maxdepth 4 -type f | sort
find frontend/src -iname "*.css" -o -iname "*.tsx" -o -iname "*.ts" | sort

grep -R "sidebar\|nav\|layout\|overflow\|height\|vh\|scroll\|grid\|masonry\|Today\|Projects\|My Items" -n frontend/src || true
grep -R "local dev role\|not production auth\|Prompt 14B\|Prompt 20\|FPR-004\|raw panels\|JSON.stringify\|FastAPI\|uvicorn\|read model\|source/sync/evidence\|Chat (disabled)\|Vite\|HMR" -n frontend/src || true
```

## Baseline expected from audit

- Branch/source audited: `main`
- HEAD audited: `bc59f1c1631c9525c47477e14c137d85ab6d630d`
- Frontend package: `frontend` v`0.0.0`
- Python package: `hb-personal-assistant` v`1.3.0`
- Core frontend stack: React + TypeScript + Vite + Tailwind utility classes
- Known scripts: `lint`, `typecheck`, `build`, `test`

## Required preflight finding categories

Document:

- branch and HEAD actually being edited;
- dirty working tree status;
- current frontend route/page structure;
- current shell/sidebar component structure;
- current CSS root/body/#root height rules;
- current visible forbidden copy hits;
- current test/build script availability;
- any local repo changes after the audit package baseline.
