# Final Validation Summary

## Outcome

- Final closeout status: **NOT_ACCEPTED**
- Evidence root: `docs/evidence/remediation/final-closeout/`
- Matrix source: `docs/plans/my-pa-phase-0/gap-closure/04_validation/01_validation_matrix.md`

## Command Results

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest` | 0 | PASS |
| `ruff check .` | 1 | FAIL |
| `mypy src` | 0 | PASS |
| `hb-assistant --version` | 0 | PASS |
| `hb-assistant auth status --json` | 1 | FAIL (runtime permission blocker) |
| `hb-assistant diagnostics env --json` | 0 | PASS |
| `hb-assistant diagnostics graph --safe --json` | 1 | FAIL (runtime permission blocker) |
| `hb-assistant diagnostics proof delegated-graph --json` | 1 | FAIL (manual/runtime blocker) |
| `hb-assistant diagnostics automation --json` | 0 | PASS |
| `hb-assistant diagnostics scan-sensitive --repo . --json` | 0 | PASS |
| `hb-assistant files ingest --dry-run --json` | 1 | FAIL (database path runtime blocker) |
| `hb-assistant run morning --dry-run --json` | 1 | FAIL (database path runtime blocker) |

## Blockers

1. Ruff lint violations in current tree (`src/hb_assistant/security/__init__.py`, `src/hb_assistant/security/sensitive_scan.py`).
2. Application Support permission errors blocking delegated auth and graph proof runtime commands.
3. Database file open errors blocking `files ingest --dry-run` and `run morning --dry-run`.

## Redaction Confirmation

All evidence outputs are sanitized and include no token values, private keys, PEM bodies, full email bodies, or full file contents.
