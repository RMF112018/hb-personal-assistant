# Prompt 02 Remediation Evidence: Canonical CLI Grammar

## Objective

Align Typer CLI grammar to canonical subcommand contract:

- `hb-assistant auth <subcommand>`
- `hb-assistant run morning ...`

## Starting Checks

- `git status --short` -> `?? docs/plans/my-pa-phase-0/gap-closure/`
- `git branch --show-current` -> `main`
- `git rev-parse HEAD` -> `8e5e687bb981f3861d635d1e899d752d8a45a5bd`
- `git log --oneline -5` -> captured during run
- `python --version` -> `zsh:1: command not found: python`

## Grammar Reconciliation

- Prior mismatch: root `auth` and `run` were boolean-option commands.
- Remediated shape: `auth` and `run` are now Typer sub-apps with canonical subcommands.
- Launchd command contract preserved: ProgramArguments keep `run morning` command shape.

## Canonical Command Set (Validation Target)

- `hb-assistant auth login --json`
- `hb-assistant auth status --json`
- `hb-assistant auth logout --json`
- `hb-assistant auth clear-cache --json`
- `hb-assistant run morning --dry-run --json`
- `hb-assistant diagnostics env --json`
- `hb-assistant diagnostics graph --safe --json`
- `hb-assistant diagnostics automation --json`
- `hb-assistant diagnostics scan-sensitive --repo . --json`

## Validation Results

- `hb-assistant auth status --json` -> exit `1` (grammar success; safe JSON error due offline `login.microsoftonline.com` resolution in this environment)
- `hb-assistant run morning --dry-run --json` -> exit `0`
- `hb-assistant --help` -> exit `0`
- `hb-assistant auth --help` -> exit `0`
- `hb-assistant run --help` -> exit `0`
- `.venv/bin/python -m pytest tests/test_cli*.py tests/test_auth.py tests/test_automation.py` -> exit `0` (`30 passed`)

## Supersession Note

Historical evidence remains preserved. Where prior evidence referenced `run --morning` or root option-based auth grammar, that context is superseded by this remediation baseline and canonical contract.
