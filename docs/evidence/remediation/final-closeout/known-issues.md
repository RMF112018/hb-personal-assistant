# Known Issues

## BLOCKER-RUFF-001
- `ruff check .` exits 1.
- Current violations:
  - unsorted imports in `src/hb_assistant/security/__init__.py`
  - unused import in `src/hb_assistant/security/sensitive_scan.py`

## BLOCKER-AUTH-PERM-001
- `hb-assistant auth status --json`, `hb-assistant diagnostics graph --safe --json`, and delegated proof command fail with:
  - `Operation not permitted: '/Users/bobbyfetting/Library/Application Support/HB Personal Assistant'`
- This blocks delegated Graph proof acceptance in current runtime.

## BLOCKER-DB-PATH-001
- `hb-assistant files ingest --dry-run --json` and `hb-assistant run morning --dry-run --json` fail with database open errors.
- Root symptom:
  - `OperationalError: unable to open database file`

## Note
- Closeout remains `NOT_ACCEPTED` until blockers above are resolved and matrix is fully green.
