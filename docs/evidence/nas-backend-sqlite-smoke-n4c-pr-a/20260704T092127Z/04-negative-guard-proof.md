# 04 — Negative guard proof (local unit, not production DB)

Run on Mac against PR A code @ `9bcf7e2e`:

```sh
PYTHONPATH=src python -m pytest tests/test_db_storage_guard.py -q
```

**Result:** 8 passed

## Cases covered

| Case | Expected | Result |
|---|---|---|
| `HB_NAS_RUNTIME=1` + production NAS DB path | allow `nas_local` | PASS |
| `HB_NAS_RUNTIME=1` + smoke NAS DB path | allow `nas_local` | PASS |
| `HB_NAS_RUNTIME=1` + `/Volumes/...` | blocked | PASS |
| `HB_NAS_RUNTIME=1` + Mac app-support path | blocked | PASS |
| `HB_NAS_RUNTIME=1` + `HB_DB_STORAGE_GUARD=permissive` + `/tmp/...` | still blocked | PASS |
| `smb://` scheme | blocked | PASS |
| relative path | blocked | PASS |
| dev tmp path without NAS runtime | `dev_permissive` | PASS |

Raw output: `json/negative-guard-tests.txt`
