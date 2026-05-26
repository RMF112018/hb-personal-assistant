# Validation Matrix

## Required Commands

The final closeout must run and capture these commands from a clean working tree:

```bash
git status --short
git rev-parse HEAD
python --version
python -m pytest
ruff check .
mypy src
hb-assistant --version
hb-assistant --help
hb-assistant auth status --json
hb-assistant diagnostics env --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
```

## Pass/Fail Rules

| Command Type | Pass Rule |
|---|---|
| Git state | Clean except intentional generated evidence before commit. |
| pytest | Exit code 0. No unmarked failures. |
| Ruff | Exit code 0. No unaddressed violations. |
| mypy | Exit code 0 under agreed scope. |
| auth status | Exit code may be nonzero only if no token is expected, but command grammar must succeed and output valid JSON. |
| Graph proof | Must pass delegated proof or clearly identify a manual permission/auth prerequisite. |
| launchd dry-run | Must render valid ProgramArguments and readiness. |
| sensitive scan | Must emit valid JSON and no secret values. Findings must be categorized. |

## Evidence Standard

Every evidence output must include:

- command;
- timestamp;
- exit code;
- pass/fail;
- output file path;
- summary;
- redaction confirmation.

Do not copy raw secrets or full bodies into evidence.
