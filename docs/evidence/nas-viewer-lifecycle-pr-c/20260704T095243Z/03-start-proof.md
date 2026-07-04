# 03 — Start proof

## Command

```sh
sudo sh scripts/start.sh
```

## Result: PASS

| Check | Observed |
|---|---|
| Implicit build | **None** — `compose up --no-build -d` only |
| Image | `hb-personal-assistant:nas` (prebuilt) |
| Publish | `127.0.0.1:8000->8000/tcp` |
| Workers | Disabled by compose |
| Container | `hb-personal-assistant-backend` started |

Captured: `captured/evidence/start.txt`

## Note

Container reported `health: starting` immediately after create — health probes require short startup wait (see `05`).
