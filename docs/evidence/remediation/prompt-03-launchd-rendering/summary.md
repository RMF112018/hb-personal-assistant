# Prompt 03 Remediation Evidence: Launchd Path And Command Rendering

## Objective

Correct launchd plist rendering so scheduled automation uses a verified executable, valid working directory, and canonical command grammar:

- `hb-assistant run morning`

## Required Starting Checks

- `git status --short` ->
  - `?? .tmp-app-support-remediation/`
  - `?? docs/plans/my-pa-phase-0/gap-closure/`
- `git branch --show-current` -> `main`
- `git rev-parse HEAD` -> `4bcb90bf03bc3ae4ebc2ae3bf3c0c842d4c2cac7`
- `git log --oneline -5` -> captured during run
- `python --version` -> `zsh:1: command not found: python`

## Changes Applied

- Added launchd config block support:
  - `automation.launchd.executable_path`
  - `automation.launchd.working_directory`
  - `automation.launchd.label`
  - `automation.launchd.python_path` (optional)
- Launchd executable resolution now prefers explicit config, then discovered console script, then runtime fallback with verification.
- Working directory resolution now uses explicit config or `PathPolicy.resolve_repo_root()` default.
- ProgramArguments now render exactly as `[hb_assistant_executable, "run", "morning"]`.
- Dry-run preview now includes readiness and blocking diagnostics:
  - executable exists/file/executable,
  - working directory exists/directory,
  - command grammar valid,
  - log directories writable,
  - plist path.
- Install path now blocks if readiness is not met.
- Diagnostics automation output now surfaces launchd readiness/blocking and launchd override config values.

## Validation Results

- `hb-assistant automation install-launchd --dry-run --json` -> exit `0`.
- `hb-assistant diagnostics automation --json` -> exit `0`.
- `.venv/bin/python -m pytest tests/test_automation.py` -> exit `0` (`9 passed`).

Validation executed with `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p03.yml` to ensure writable local state paths and explicit launchd override coverage.

## Isolation And Supersession Note

Unrelated untracked paths were preserved and not modified:

- `.tmp-app-support-remediation/`
- `docs/plans/my-pa-phase-0/gap-closure/`

Historical closeout evidence is preserved; this Prompt 03 evidence supersedes prior launchd executable/path assumptions for remediation acceptance.
