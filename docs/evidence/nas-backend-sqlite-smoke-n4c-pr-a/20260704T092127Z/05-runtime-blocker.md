# 05 — Runtime blocker

## Attempt

```sh
ssh -tt hb-nas 'sudo sh /volume1/personal-assistant/runtime/n4c-pr-a-backend-smoke-20260704T092127Z/n4c-pr-a-smoke-run.sh'
```

## Outcome

Session stalled at `Password:` — no sudo authentication in non-interactive agent context.

Verification:

```sh
ssh hb-nas 'sudo -n /usr/local/bin/docker ps'  # => password required
```

No smoke log created at `/volume1/personal-assistant/app-support/logs/n4c-pr-a-backend-smoke-20260704T092127Z.log`.

No endpoint JSON captured under runtime `evidence/`.

## Expected runtime proofs (deferred)

Once operator completes smoke script:

- Image build via `docker build --network host`
- `compose up --no-build -d` loopback only
- `/health` sanitized posture
- `/api/admin/schema/status` → `table_count=506`, `view_count=1`, `schema_object_count=507`
- `/api/admin/db/status` full metadata (admin)
- `startup_migration_performed=false`
- Post-smoke DB unchanged (schema 98, 506 tables)
- Clean shutdown, no LISTEN on 8000
