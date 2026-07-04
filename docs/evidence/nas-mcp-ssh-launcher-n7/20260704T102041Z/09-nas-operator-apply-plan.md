# 09 — NAS operator apply plan (deferred)

## Preconditions

- Local tests PASS
- Bobby authorizes NAS apply separately

## Steps

1. Copy `deploy/nas/mcp/*` to `/volume1/personal-assistant/deploy/nas/mcp/`
2. Install launcher/runner to `/volume1/personal-assistant/bin/` (mode 755 launcher, 755 runner root-owned)
3. Install `hb-pa-config.mcp.yml` from example (no secrets)
4. `visudo -cf` on sudoers fragment; install to `/etc/sudoers.d/hb-pa-mcp`
5. Rebuild/pull `hb-personal-assistant:nas` image with `[mcp]` extra
6. `hb-mcp-launcher start` → verify `127.0.0.1:8765` LISTEN only
7. Mac: `mac-tunnel.sh.example` → `curl http://127.0.0.1:18765/health`
8. Exercise one allowlisted DB query + one vault excerpt + one deny case
9. `hb-mcp-launcher stop` → verify no lingering container, no `:8000` LISTEN

## Rollback

- `hb-mcp-launcher stop`
- Remove sudoers fragment
- Remove launcher/runner binaries
