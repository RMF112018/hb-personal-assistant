# 02 — Script safety

## Local static tests

```sh
PYTHONPATH=src python -m pytest tests/test_nas_runtime_scaffold.py -q
```

**Result:** 27 passed

## Verified invariants (lifecycle scripts)

| Invariant | Status |
|---|---|
| No `compose up --build` in start path | PASS |
| Loopback publish required | PASS |
| No `0.0.0.0:8000` in active script content | PASS |
| No Portainer dependency | PASS |
| No `/Volumes/` paths in active script content | PASS |
| `validate-db.sh` uses `mode=ro` | PASS |
| `emergency-shutdown.sh` no default checkpoint | PASS |

## Runtime safety validator

`check-runtime-safety.sh` on NAS config: **PASS** (captured).
