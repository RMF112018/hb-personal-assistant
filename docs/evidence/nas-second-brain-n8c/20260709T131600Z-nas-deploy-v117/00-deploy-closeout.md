# NAS Deploy Closeout — V117 (merged main `bf2f30cc`)

**Date:** 2026-07-09
**Operator:** Bobby (interactive `sudo` over `ssh -t`)
**Authoring/verification:** agent authored every command and verified every result; agent has no
production access — all `sudo`/remote steps were operator-run.
**Scope (authorized, gate id=u84c2g):** deploy code only + additive schema migration to head 117 +
service restart + read-only validation. **No** watcher enable, **no** `bootstrap ... apply`, **no**
scheduled jobs.

## Result: SUCCESS (for the authorized scope)

| Item | Value |
| --- | --- |
| Source | branch `ops/source-index-watcher-automated-refresh-20260709` → merged `main` **`bf2f30cc`** (PR #289) |
| Image | `hb-personal-assistant:nas` · linux/amd64 · id `sha256:00cab8f1…` · tarball sha256 `f38117b8…` |
| Build host | Mac (Apple Silicon) → `docker buildx --platform linux/amd64`; shipped to NAS `/tmp` via cat-over-SSH |
| Live DB migration | **116 → 117**, additive-only; `quick_check = ok`; both v117 tables present (2/2) |
| Schema objects (prod) | 586 tables / 2 views (the +5 vs the 581-table fresh baseline are benign runtime/FTS shadow tables) |
| RO snapshot | refreshed to head 117 (`quick_check = ok`) |
| Service | `hb-personal-assistant-mcp` restarted on new image; `Up`; `127.0.0.1:8765` (loopback only, port 8000 absent) |
| Health | `/health` → `{"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}` |
| Origin auth | unauth `POST /mcp` → **401** (no leak) |
| MCP tool surface | **87 tools / 14 groups** — unchanged (image-verified + live-verified) |
| `source-watch status` | ok, redacted, `roots: []` |
| `bootstrap --dry-run --all-roots` | ok, `root_count: 0` (no `external_sources` configured — see `04-…`) |
| Watcher | NOT enabled |

## Migration safety (verified before running against production)

- v115 / v116 / v117 are all `CREATE ... IF NOT EXISTS` — zero `DROP` / `DELETE` / `ALTER-DROP`.
- Off-NAS pre-flight: fresh `SQLiteMigrator.apply()` lands at head 117, idempotent on re-apply,
  `quick_check = ok`, both v117 tables created.
- On-NAS: FULL byte-for-byte DB backup taken and integrity-verified **before** the migration.

## Backups / rollback anchors

Pre-migration backups (head 116) — either is a valid DB rollback:

```
/volume2/personal-assistant/app-support/db-backups/hb-personal-assistant.pre-v117.20260709T130302Z.sqlite
/volume2/personal-assistant/app-support/db-backups/hb-personal-assistant.pre-v117.20260709T130921Z.sqlite
```

Image rollback anchor: `hb-personal-assistant:prev` (the prior image, retagged before load).

```
# rollback (if ever needed):
/usr/local/bin/docker tag hb-personal-assistant:prev hb-personal-assistant:nas \
  && sudo /volume2/personal-assistant/bin/hb-mcp-runner stop \
  && sudo /volume2/personal-assistant/bin/hb-mcp-runner start
# and restore DB from one of the pre-v117 backups above.
```

> The deploy script's SUMMARY footer printed a `…131626Z` backup path on the final (idempotent)
> re-run; that file was never created (the re-run skipped backup because the DB was already at 117).
> Use only the two backups listed above.

## Deploy iterations (why three passes)

1. **Pass 1** — aborted at backup `quick_check`: the WAL-mode production DB could not be opened
   read-only on a `:ro` mount without `immutable=1`. Fixed in the script. *No migration ran.*
2. **Pass 2** — backup verified, **migration 116→117 succeeded and verified**, then aborted on an
   over-strict exact object-count assert (586 ≠ 581 fresh baseline). Fixed the assert to check the
   real success criteria (head + integrity + both v117 tables + count ≥ baseline). *DB left at 117.*
3. **Pass 3** — idempotent: skipped backup/migrate (already 117), refreshed snapshot, restarted the
   service, ran read-only validation + `source-watch` dry-run. **Complete.**

Health checks in Pass 3 initially failed as a **startup-timing artifact** (checks ran at 4s uptime,
before the app bound); a re-check at 2 min showed `/health` ok and `POST /mcp` → 401.

## Explicitly NOT done (each needs separate authorization)

1. `source-watch bootstrap --all-roots` **apply** — blocked; a no-op until `external_sources` exist.
2. Watcher enable (`source-watch run --start`).
3. Scheduled snapshot cron / launchd.

## Next gate (separate task)

Configure `external_sources` (see `05-external-sources-config-draft.*`), re-run the dry-run in a
dedicated operator container that mounts the real host roots, review the mapping, THEN authorize apply.

## Artifacts in this bundle

- `01-deploy-script.sh` — the final deploy+migration script (self-contained; backup-first; aborts on error)
- `02-run-transcripts.md` — captured console transcripts (tailnet IP redacted)
- `03-postdeploy-validation.md` — health / tool-count / origin-auth / source-watch outputs
- `04-source-watch-roots-finding.md` — the 0-roots diagnosis (config file absent)
- `05-external-sources-config-draft.md` / `.json` — proposed roots config for review (NOT applied)
