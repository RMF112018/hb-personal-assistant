# Phase 14 Prompt 04 — Commands Executed

## Pre-Edit (per Global Operating Rules)
git remote -v
git branch --show-current
git rev-parse HEAD
git log --oneline -20
git status --short

## Targeted Discovery (terminal/grep only, no read_file on context)
grep -n "bobby_mention|possible_action_or_waiting|body_mention_detected|parser_outputs|calendar_events|file_review|pending_ingest|retrieval|WorkstreamContext|extract_candidates" src/hb_assistant --include="*.py"
sed -n '30,60p' src/hb_assistant/actions/service.py
grep -n "def extract_candidates|signal|classification|bobby|waiting|mention|calendar|parser|file|retrieval|confidence" src/hb_assistant/actions/extractor.py

## New Test + CLI (core acceptance)
.venv/bin/python -m pytest tests/test_actions_cli.py::test_actions_extract_signal_integration_from_bounded_store_signals -q --tb=line
.venv/bin/hb-assistant actions extract --dry-run --json   (live, captured on seeded or current DB)

## Full Validation Suite (per prompt + plan)
.venv/bin/python -m pytest -q --tb=short -k "signal_integration or action" tests/test_actions_cli.py -rA
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
.venv/bin/hb-assistant run morning --dry-run --json

## Evidence Capture
All stdout/stderr + exit codes + the exact new CLI JSON output + focused test results saved to validation-outputs/.

**All commands executed from repo root with the phase-0 venv.**
