# Run transcripts — operator deploy 2026-07-10

Operator ran from Mac:

```bash
ssh -t hb-nas 'sudo sh /tmp/hb-deploy-v119.sh' | tee ~/hb-deploy-v119-transcript.txt
```

Password prompt elided.

## Key results

| Step | Result |
| --- | --- |
| Preconditions | `live_db_bytes=4388917248` `backup_fs_avail_bytes=146247147520` ok |
| Compose patch | `HB_RUNTIME_COMMIT: "14dfc3a0e007475543e19f1d8efd999b23f3e28b"` |
| Compose backup | `compose-mcp.yaml.bak-20260710T123637Z` |
| Image load | `sha256:21ed87ad0fbcc5021d59fdd6558aa0d40c5a8a804c31b114f318af7a6c07c5a3` |
| Migration | `117 -> 119` backup `hb-personal-assistant.pre-v119.20260710T123637Z.sqlite` `quick_check=ok` |
| Post-migrate | `tables=587 views=2 v117=2/2 v119=1 v118_cols=2 manifest_rows=0` |
| Snapshot | `4388986880 bytes` head `119 ok` |
| Container | `f90650bfa075…` Up ~1min `127.0.0.1:8765` |
| Health | `{"status":"ok","surface":"nas_mcp",...}` |
| Unauth /mcp | HTTP 401 |
| Runtime identity (phase 7) | No stdout captured; script continued → assert passed |
| Tool count (phase 9) | No stdout captured (non-fatal step) |
| source-watch status | Traceback in `get_bootstrap_state` / `borrow_connection` |
| bootstrap dry-run | `ok: true` `root_count: 4` all `root_found: false` |

## Health timing

`host_listen=missing` in runner status is the known false negative (v117 closeout); `curl 127.0.0.1:8765/health` ok is definitive.