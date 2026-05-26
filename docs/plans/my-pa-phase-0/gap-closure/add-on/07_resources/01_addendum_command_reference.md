# Addendum Command Reference

## Static

```bash
source .venv/bin/activate
ruff check .
mypy src
python -m pytest
```

## Path + Auth

```bash
hb-assistant diagnostics paths --json
hb-assistant diagnostics paths --repair-dry-run --json
hb-assistant auth status --json
hb-assistant auth login --json
```

## Graph

```bash
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
```

## Runtime

```bash
hb-assistant files sample --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
hb-assistant diagnostics automation --json
```

## Final

```bash
hb-assistant diagnostics scan-sensitive --repo . --json
git status --short
git log --oneline -10
```
