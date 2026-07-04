# 10 — Shutdown proof

## Compose down

From `evidence/compose-down.txt`:

- Container `hb-personal-assistant-backend` stopped, removed
- Network `nas_default` removed

## Post-shutdown port proof (agent re-check)

```text
netstat -an | grep "\.8000 .*LISTEN"
=> PASS: no LISTEN on port 8000
```

No `TIME_WAIT` rows on 8000 at re-check time.

## Container proof

Operator post-smoke: `docker ps -a --filter name=hb-personal-assistant` returned **empty** (no HB container running).

Agent non-interactive re-check could not invoke Docker without sudo; port proof confirms host is not serving 8000.

## Backend left running

**No** — smoke requirement satisfied.
