# Run transcripts (captured)

Redactions: tailnet IP shown as `<tailnet-ip>`; `Password:` prompts elided. Commands were run by the
operator from the Mac; the deploy itself ran on the NAS under `sudo`.

## Build + ship (Mac)

```
docker buildx build --platform linux/amd64 --provenance=false --sbom=false \
  -f deploy/nas/Dockerfile -t hb-personal-assistant:nas --load .
# -> BUILD_OK ; image arch=amd64 os=linux id=sha256:0fa5b21749a2… (config 00cab8f1…)
docker save hb-personal-assistant:nas | gzip > hb-nas-bf2f30cc.tar.gz
# -> 108,969,240 bytes ; sha256 f38117b8c61f1d75379bfa3acfc567359f15ca1c738ad45072756fe2ba1642fc

ssh hb-nas 'cat > /tmp/hb-nas-bf2f30cc.tar.gz' < …/hb-nas-bf2f30cc.tar.gz
ssh hb-nas 'cat > /tmp/hb-deploy-v117.sh'      < …/hb-deploy-v117.sh
ssh hb-nas 'sha256sum /tmp/hb-nas-bf2f30cc.tar.gz'
# -> f38117b8c61f1d75379bfa3acfc567359f15ca1c738ad45072756fe2ba1642fc  (match)
```

Image content verified off-NAS: `LATEST_SCHEMA_VERSION = 117`, `tools = 87`, `groups = 14`,
`source-watch` CLI present (bootstrap/run/status/drain/reconcile).

## Deploy — final (idempotent) pass (NAS, `sudo sh /tmp/hb-deploy-v117.sh`)

```
=== 0. Preconditions ===
live_db_bytes=4152483840  backup_fs_avail_bytes=150884962304
preconditions ok

=== 1. Retag current image as :prev (rollback anchor) ===
rollback anchor hb-personal-assistant:prev already exists — preserving it (not overwriting)

=== 2. Load new image from tarball (code deploy) ===
Loaded image: hb-personal-assistant:nas
loaded image id=sha256:00cab8f1557f9dfded2979d5e885beda986d869782305bb13b4eeb980484390c

=== 3. Pre-migration backup + 4. additive migration -> head 117 ===
live DB current schema head = 117
live DB already at head 117 — skipping backup+migrate (idempotent re-run).
existing pre-migration backups:
/volume2/personal-assistant/app-support/db-backups/hb-personal-assistant.pre-v117.20260709T130302Z.sqlite
/volume2/personal-assistant/app-support/db-backups/hb-personal-assistant.pre-v117.20260709T130921Z.sqlite
post-migrate: head=117 quick_check=ok tables=586 views=2 objects=588 v117_tables_present=2/2
note: 5 production table(s) beyond the fresh-migrate baseline (runtime-created, e.g. FTS5 shadow tables) — benign
migration verified

=== 5. Refresh read-only MCP snapshot from migrated live DB ===
snapshot ok: /snap/db/hb-personal-assistant.sqlite 4152483840 bytes in 27.6s
snapshot head/quick_check = 117 ok

=== 6. Restart MCP service on the new image ===
PASS  compose-mcp.yaml static guards
 ✔ Container hb-personal-assistant-mcp  Started
== container ==
hb-personal-assistant-mcp Up 4 seconds 8000/tcp, 127.0.0.1:8765->8765/tcp
== docker port 8765 == 127.0.0.1:8765
--- running image id --- container image=sha256:00cab8f1557f9dfded2979d5e885beda986d869782305bb13b4eeb980484390c
```

(Health/401/tool-count checks in this pass failed as a startup-timing artifact — see `03-…`.)

## Post-restart re-check (~2 min uptime)

```
== container == hb-personal-assistant-mcp Up 2 minutes 8000/tcp, 127.0.0.1:8765->8765/tcp
--- health --- {"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}
--- unauth 401 --- 401
```

## Live surface + roots diagnostic

```
--- tool count (live) ---     tools= 87 groups= 14
--- external sources (redacted) ---
config_path= /volume2/personal-assistant/app-support/analytics/obsidian_mcp_config.json
external_sources= 0
--- config file on host ---
ls: cannot access '/volume2/personal-assistant/app-support/analytics/obsidian_mcp_config.json': No such file or directory
```
