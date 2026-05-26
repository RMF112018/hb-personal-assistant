# Command Reference for Agent

## Ref Reconciliation

```bash
git remote -v
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
git log --oneline -10
git cat-file -t 63bb05c7163b85ff556f0a599a19cf9bba501280 || true
git branch --contains 63bb05c7163b85ff556f0a599a19cf9bba501280 || true
git reflog --all | grep 63bb05c7163b || true
git ls-remote --heads --tags origin | grep 63bb05c7163b || true
```

## Core Validation

```bash
python -m pytest
ruff check .
mypy src
```

## Canonical Runtime

```bash
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics automation --json
hb-assistant run morning --dry-run --json
```

## Security

```bash
hb-assistant diagnostics scan-sensitive --repo . --json
find . -maxdepth 5 -type f | grep -Ei 'token|secret|cert|pem|pfx|key|cache|sqlite|db' || true
git status --short
```
