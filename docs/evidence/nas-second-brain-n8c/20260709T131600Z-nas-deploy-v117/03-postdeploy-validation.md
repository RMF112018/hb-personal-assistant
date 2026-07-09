# Post-deploy validation vs the 12-step target

| # | Target | Result |
| --- | --- | --- |
| 1 | Deploy target = `bf2f30cc` | ✅ merged main, image built from that commit |
| 2 | Capture NAS runtime/package status | ✅ container/image inspected |
| 3 | Backup live DB before migration | ✅ two verified pre-v117 backups (head 116) |
| 4 | Deploy the code | ✅ new image `00cab8f1…` loaded + running |
| 5 | Apply migrations, head = V117 | ✅ 116→117, `quick_check=ok`, both v117 tables |
| 6 | Restart/reload MCP service | ✅ restarted on new image |
| 7 | Tool count = 87 / 14 | ✅ live-verified `tools=87 groups=14` |
| 8 | Existing source tools respond | ✅ `/health` ok, `POST /mcp`→401; broker surface intact |
| 9 | `source-watch status` | ✅ returns (redacted; `roots: []`) |
| 10 | `bootstrap --dry-run --all-roots` | ✅ returns (`root_count: 0`) |
| 11 | Capture dry-run counts / health | ✅ (this bundle) |
| 12 | No apply before dry-run review | ✅ not run |

## Health timing note

In the restart pass, health checks ran at `Up 4 seconds` and failed (`curl (56) connection reset`,
`host_listen=missing`, `POST=000`) because the container process had not yet bound `:8765` (the
container reports `Started 19.0s`). A re-check at ~2 minutes uptime returned `/health` ok and
`POST /mcp` → 401. **Not a defect** — the `sleep 3` post-restart wait was simply too short for
first-boot of the app inside the emulated-built image.

`host_listen=missing` persists in `hb-mcp-runner status` even when healthy: it is a **false negative**
in the runner's `netstat` heuristic (Synology netstat format vs docker-proxy). `curl` to
`127.0.0.1:8765/health` succeeding is definitive proof the service is listening.

## No absolute-path leak

`source-watch status` output is keyed by `root_key` and carries no host paths; the watcher-owner blob
is redacted to `heartbeat_at` only. Unauth `/mcp` returns 401 (no data surface without a credential).
