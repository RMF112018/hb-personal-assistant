# Prompt 05 Remediation Evidence: Current Delegated Graph Proof

## Objective

Refresh delegated Graph proof using current runtime code paths and canonical CLI grammar.

## Starting Checks

- `git status --short` ->
  - `?? .tmp-app-support-remediation/`
  - `?? docs/plans/my-pa-phase-0/gap-closure/`
- `git branch --show-current` -> `main`
- `git rev-parse HEAD` -> `3ce58ec4c93418891820db6f54dc1ebfe4528e64`
- `git log --oneline -5` -> captured during run
- `python --version` -> `zsh:1: command not found: python`

## Runtime/CLI Proof Updates

- `hb-assistant diagnostics proof delegated-graph --json` now executes in-package runtime proof logic.
- Backward-compatible `--delegated-graph` alias remains available.
- Proof no longer returns stale script delegation payloads.
- Output status is explicit (`pass`, `gap`, `blocked_no_token`, `runtime_error`) with sanitized details.

## Validation Commands

- `hb-assistant auth status --json` -> exit `1`
- `hb-assistant diagnostics proof delegated-graph --json` -> exit `1`
- `hb-assistant diagnostics graph --safe --json` -> exit `1`
- `hb-assistant diagnostics scan-sensitive --repo . --json` -> exit `0`
- `.venv/bin/python -m pytest tests/test_graph_proof.py tests/test_cli_canonical.py` -> exit `0` (`17 passed`)

## Truthful Gap Reporting

Current environment cannot resolve Microsoft login authority host, so delegated token acquisition fails.

- Auth/proof/graph diagnostics all capture this as a true runtime gap (`blocked_no_token` / diagnostics error)
- Proof explicitly reports remediation:
  - `Run hb-assistant auth login --json and retry proof.`

No delegated proof success is claimed in this environment.

## Isolation Note

Unrelated untracked paths were preserved and not modified:

- `.tmp-app-support-remediation/`
- `docs/plans/my-pa-phase-0/gap-closure/`
