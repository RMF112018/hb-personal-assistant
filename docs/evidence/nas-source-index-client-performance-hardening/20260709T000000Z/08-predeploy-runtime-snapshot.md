# 08 — Pre-deploy runtime snapshot

Captured before attempting controlled deploy of branch  
`ops/source-index-client-performance-hardening-20260709` @ `2a61b4fb01d785d0832c60a0247243a6771b4e77`.

## Worktree pre-checks

| Check | Result |
|-------|--------|
| Branch | `ops/source-index-client-performance-hardening-20260709` |
| HEAD | `2a61b4fb01d785d0832c60a0247243a6771b4e77` |
| origin/main | `2e98a03d56f54b25fef86bd3b4c19a89185988cc` |
| main is ancestor | yes |
| status | `## ops/source-index-client-performance-hardening-20260709...origin/main [ahead 12]` |
| 07 live results present | yes |

### Recent log

```
2a61b4fb (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): live authenticated connected-client matrix results
efc95d2c docs(evidence): post-rebase validation onto origin/main
68d77b08 docs(evidence): 05-TIP points to git rev-parse HEAD as authority
ad7821f2 docs(evidence): point 05-TIP.txt at its own commit
fd43c3cd docs(evidence): add 05-TIP.txt with branch tip hash pointer
69c49cc8 docs(evidence): authoritative closeout HEAD inventory and report
```

## Public / authenticated live surface (pre-deploy)

| Probe | Result |
|-------|--------|
| GET `/health` | HTTP 200 — `{"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}` |
| POST `/mcp` no auth | HTTP 401 |
| POST `/mcp` + origin bearer initialize | HTTP 200 serverInfo={'name': 'hb-nas-mcp', 'version': '1.28.1'} |
| tools/list count | **163** total; assistant≈78 |
| structure tools present | none |
| assistant_output_* | 0 |
| hb_mcp_status exposed count | 78 |
| structure enabled flag | None |
| runtime_commit | v1.3.0 |
| POST `/mcp/` trailing slash | HTTP 307 Location=`http://127.0.0.1:8765/mcp` |

## NAS host (SSH `hb-nas`, no docker socket)

```
{"status":"ok","surface":"nas_mcp","nas_readonly":true,"profile":"remote_cloudflare","origin_auth_required":true}
tcp        0      0 127.0.0.1:8765          0.0.0.0:*               LISTEN     
tcp        0      0 127.0.0.1:8765          127.0.0.1:55934         ESTABLISHED
tcp        0      0 127.0.0.1:55924         127.0.0.1:8765          TIME_WAIT  
tcp        0      0 172.27.0.1:56424        172.27.0.2:8765         TIME_WAIT  
tcp        0      0 127.0.0.1:55928         127.0.0.1:8765          TIME_WAIT
```

Container ID / image digest: **not readable** without docker.sock or sudo (see deploy blocker).

## Rollback plan (prepared)

1. Keep prior `hb-personal-assistant:nas` image on NAS (do not `docker rmi` until new build validated).
2. `sudo /volume2/personal-assistant/bin/hb-mcp-runner stop`
3. Retag/load previous known-good image as `hb-personal-assistant:nas` (last deploy closeout retained image `a96f68f5270c` / then `41e664fa2127` — confirm on NAS before overwrite).
4. `sudo /volume2/personal-assistant/bin/hb-mcp-runner start`
5. Re-check `/health` + authenticated tools/list count returns to pre-deploy baseline (~78 assistant tools).

## Known host-side deploy blocker

- `sudo -n` for MCP runner **requires a password** from this agent session.
- Host sudoers path for the MCP runner had drifted relative to the live runner binary location (details redacted).
- `bfetting` cannot open `/var/run/docker.sock` without sudo.

Machine-readable: `08-predeploy-runtime-snapshot.json`.
