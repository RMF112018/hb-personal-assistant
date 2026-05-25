# Prompt 11 — Retrieval Embeddings And Workstream Context

## Objective

Execute this phase for `hb-personal-assistant` as part of the HB Personal Assistant + Work Product Intelligence System MVP.

## Required Context

Review the implementation package files relevant to this phase. Do not re-read files still within current context or memory unless needed to verify changed content, inspect unloaded lines, or confirm post-patch behavior.

## Required Work

- Follow the phase sequence in `02_Final_Implementation_Plan.md`.
- Honor `20_Manual_Approval_Gates.md`.
- Preserve read-only Microsoft 365 runtime behavior.
- Add or update tests and evidence for this phase.

## Validation

Run applicable commands:

```bash
python -m pytest
ruff check .
mypy src
hb-assistant diagnostics env --json
hb-assistant auth status --json
hb-assistant diagnostics graph --safe --json
hb-assistant run morning --dry-run --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

## Acceptance Criteria

- Objective complete.
- No broad unrelated refactor.
- No Microsoft 365 write-back.
- No tokens/private keys/full bodies/full file contents logged.
- Evidence created under `docs/evidence/`.
- Prompt execution log updated.
