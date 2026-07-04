# 02 — Docker CLI Help Proof + Side-Effect Checks

Command form (operator sudo): `sudo /usr/local/bin/docker run --rm --network none hb-personal-assistant:nas <cli...>`
— command overridden (no uvicorn), auto-removed, no ports, no volumes, no network.

## Baseline (pre)
```
db_pre   mtime/size captured
auth_cache_pre=0   (no msal-token-cache.bin present)
```

## CLI help runs
| Command | Exit | Help output |
|---|---|---|
| `hb-assistant --help` | `0` | Usage/Options/Commands printed |
| `hb-assistant auth --help` | `0` | auth subcommands printed |
| `hb-assistant auth login --help` | `0` | login options incl. device-code shown |

All three returned `exit_code=0` and printed genuine Typer help (Usage/Options). The `auth login --help` output
confirms the device-code flow options are wired (consistent with repo truth: device-code is the default).

## Side-effect checks (post)
```
lingering=0            (no --rm leftover containers from the image)
running_hbpa=0         (no hb-personal-assistant backend container running)
db_post mtime/size == db_pre mtime/size   (production DB untouched)
auth_cache_post=0      (== auth_cache_pre; NO MSAL cache created)
```

## Interpretation
- The CLI runs cleanly in the `python:3.12-slim` container and **exits after each command** (`--rm`, `lingering=0`).
- **No backend** started (`running_hbpa=0`; the default uvicorn CMD was overridden every time).
- **No DB access** — the container had no volume mounting the app-support/DB tree, so opening/migrating the DB was
  structurally impossible; the DB mtime/size are unchanged as a belt-and-suspenders confirmation.
- **No token cache** created (`auth_cache_post=0`) — no login was run, and nothing was mounted to write into.

## Redaction
Help text itself is non-sensitive (command/option names only). No tokens, device codes, config values, or paths beyond
the approved image name appear. Host/absolute paths are kept in `local-sensitive/`.
