# Phase 14 Prompt 01 — Commands Executed

## Pre-Edit (per Global Operating Rules)
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short

## Targeted Grep (stale language discovery + final validation)
grep -r --include="*.md" -n "DNS" . | grep -iE "(blocker|sole|active|remaining|is the)"
grep -r --include="*.md" -n "CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_BLOCKER" .
grep -n -i "DNS\|blocker\|CONDITIONALLY_ACCEPTED" README.md

## Validation Suite (baseline + post-edit)
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json

## Supporting (for completeness, per 04_ taxonomy plan)
.venv/bin/hb-assistant auth status --json
.venv/bin/hb-assistant diagnostics graph --safe --json
.venv/bin/hb-assistant diagnostics env --json

## Evidence Capture
- All stdout/stderr + exit codes saved to validation-outputs/
- Grep results for DNS blocker language (pre and post) saved
- Sensitive scan JSON captured and confirmed clean

**All commands executed from repo root with the phase-0 venv.**
