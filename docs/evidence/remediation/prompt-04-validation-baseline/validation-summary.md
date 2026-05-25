# Prompt 04 Validation Baseline Summary

## Objective

Make the repo core validation commands green or explicitly scoped with a documented rationale.

## Starting Checks

- `git status --short` showed unrelated untracked paths:
  - `.tmp-app-support-remediation/`
  - `docs/plans/my-pa-phase-0/gap-closure/`
- `git branch --show-current` -> `main`
- `git rev-parse HEAD` -> `56fe523b90f770e2f35caafcc4c2a3dbea3cba6f`
- `git log --oneline -5` captured in prompt run
- `python --version` -> `zsh:1: command not found: python`

## Changes Applied

- Fixed failing test `tests/test_config.py::test_no_secrets_in_paths_or_config` by avoiding false positives from temporary filesystem path strings while preserving secret-fragment safety checks.
- Updated Ruff config to current format:
  - moved lint settings to `[tool.ruff.lint]`
  - added `force-exclude = true`
- Added explicit Ruff validation scope via `extend-exclude` for out-of-scope legacy paths to keep Prompt 04 bounded.
- Added explicit mypy validation scope in `pyproject.toml`:
  - global `follow_imports = "skip"`
  - baseline `ignore_errors = true` for `hb_assistant.*`
  - targeted `ignore_errors = false` for Prompt 04 critical modules:
    - `hb_assistant.automation.launchd_manager`
    - `hb_assistant.config.path_policy`
    - `hb_assistant.cli.automation`
- Fixed in-scope Ruff issues in Prompt 04 touched modules (`launchd_manager.py`, `tests/test_automation.py`) needed to reach green.

## Validation Commands And Results

- `.venv/bin/python -m pytest` -> exit `0` (`75 passed, 1 skipped`)
- `.venv/bin/ruff check .` -> exit `0`
- `mypy src` -> exit `0` under explicit Prompt 04 scoped standard above
- `.venv/bin/hb-assistant --version` -> exit `0`
- `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p04.yml .venv/bin/hb-assistant auth status --json` -> exit `1` (expected in offline/no-token authority resolution context; grammar and safe JSON behavior valid)
- `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p04.yml .venv/bin/hb-assistant diagnostics env --json` -> exit `0`
- `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p04.yml .venv/bin/hb-assistant diagnostics automation --json` -> exit `0`

## Scope Rationale (Explicit)

Prompt 04 baseline focuses on restoring reliable validation for currently maintained remediation-critical surfaces (launchd/config/CLI automation path) without broad refactor of accumulated legacy lint/type debt.

Out-of-scope exclusions are explicitly encoded in `pyproject.toml` for both Ruff and mypy so the validation standard is reproducible and auditable.

## Isolation Note

Unrelated untracked paths were preserved and not modified:

- `.tmp-app-support-remediation/`
- `docs/plans/my-pa-phase-0/gap-closure/`
