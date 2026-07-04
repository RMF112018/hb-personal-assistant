# 01 — Staging and preflight

## Staging

| Item | Value |
|---|---|
| Path | `/volume1/personal-assistant/runtime/pr-c-viewer-lifecycle-20260704T095243Z/repo` |
| Commit staged | `e862cc119290b441a336a49ab43874ce59aaac02` |
| Method | `tar` over SSH |
| Size | ~308 MB |

Excluded: `.git`, `.venv`, caches, `local-sensitive`, raw DB/WAL/SHM, `__MACOSX`, `._*`

## Preflight

| Check | Result |
|---|---|
| Image present | **yes** — `hb-personal-assistant:nas` `d18715bf714c` |
| Port 8000 LISTEN (pre) | **no** |
| `check-runtime-safety.sh` | **PASS** — see `captured/evidence/check-runtime-safety.txt` |

## Docker access

Operator interactive `sudo` used (password not recorded in evidence).

## No implicit build

`start.sh` used existing image only — no `docker build` in start path.
