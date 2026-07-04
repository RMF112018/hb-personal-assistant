# 08 — Emergency shutdown proof

## Command (default mode)

```sh
sudo sh scripts/emergency-shutdown.sh
```

## Result: PASS

| Check | Result |
|---|---|
| Already stopped | Safe no-op compose down |
| WAL checkpoint | **None** (default; no `--passive-checkpoint`) |
| DB mutation | **None** |
| `container_absent` | **yes** |
| Port 8000 LISTEN | **no** |

Captured: `captured/evidence/emergency-shutdown.txt`

Final agent re-check: **PASS: no LISTEN 8000**; no `hb-personal-assistant` container running.
