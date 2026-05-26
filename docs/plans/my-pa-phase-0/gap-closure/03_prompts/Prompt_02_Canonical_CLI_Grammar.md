# Prompt 02: Canonical CLI Grammar

## Objective

Refactor the Typer CLI so implemented commands match the package/runbook contract and validation commands.

## Required Starting Checks

Run and capture:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python --version
```

Do not proceed if the working tree contains unrelated uncommitted changes unless you first document them and isolate your patch.

## Agent Rules

- Do not trust prior closeout claims.
- Do not re-read files already in current context unless changed or required by failing tests.
- Do not enable Microsoft 365 writeback.
- Do not log or commit tokens, private keys, PEM bodies, full email bodies, or full file contents.
- Keep the patch tightly scoped to this prompt.
- Create evidence under `docs/evidence/remediation/prompt-02-*/`.

## Required CLI Contract

Implement these as canonical commands:

```bash
hb-assistant auth login --json
hb-assistant auth status --json
hb-assistant auth logout --json
hb-assistant auth clear-cache --json
hb-assistant run morning --dry-run --json
hb-assistant diagnostics env --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics automation --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Tasks

1. Refactor `src/hb_assistant/cli/main.py`:
   - Replace boolean-option `auth` command with an `auth` Typer sub-app.
   - Replace boolean-option `run` command with a `run` Typer sub-app.
2. Move auth command implementation to `src/hb_assistant/cli/auth.py`.
3. Move run command implementation to `src/hb_assistant/cli/run.py`.
4. Keep command functions thin.
5. Preserve compatibility aliases only if simple. Canonical tests must use subcommands.
6. Update docs/runbook references and evidence command lists.
7. Add or update tests:
   - Typer CliRunner test for every canonical command.
   - Test that launchd-relevant commands parse successfully.

## Validation

```bash
hb-assistant auth status --json
hb-assistant run morning --dry-run --json
hb-assistant --help
hb-assistant auth --help
hb-assistant run --help
python -m pytest tests/test_cli*.py tests/test_auth.py tests/test_automation.py
```

## Required Commit

```text
fix(cli): align auth and run command groups with canonical grammar
```

The commit message body must summarize files changed, validation commands run, evidence path, and remaining issues if any.
