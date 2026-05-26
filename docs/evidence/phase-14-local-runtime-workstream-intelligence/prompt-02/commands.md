# Phase 14 Prompt 02 — Commands Executed

## Pre-Edit (per Global Operating Rules)
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short

## New CLI (core acceptance)
.venv/bin/hb-assistant actions --help
.venv/bin/hb-assistant actions extract --help
.venv/bin/hb-assistant actions list --help
.venv/bin/hb-assistant actions extract --dry-run --json   (live, captured)
.venv/bin/hb-assistant actions list --json

## Tests
.venv/bin/python -m pytest tests/test_actions_cli.py -q --tb=line

## Full Validation Suite
.venv/bin/python -m pytest --tb=no -q
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json

## Evidence Capture
All stdout + exit codes + the exact new CLI JSON output saved to validation-outputs/.

**All commands from repo root with phase-0 venv.**
