# 01 — N8B Preflight (from N8A)

**Phase:** N8B — Always-On NAS MCP via Cloudflare Tunnel (foundation)
**Stamp:** `20260705T090033Z` · **Branch:** `ops/nas-cloudflare-access-n8b-foundation-20260705T090033Z` · **Base:** `origin/main` @ `7f22fa9d`

## N8A precondition — PASS
N8A ("Second-Brain Agent / Watchers / Scheduler Gating" live-proof closeout) merged as **PR #280** (merge commit `7f22fa9d`, now the base). Gating intact (default-off workers, host-stamped lease/lock, V99 root-scoped identity); `/volume1`→`/volume2` config drift resolved; dead sudoers rule absent; temp proof runners revoked. No N8A blocker is carried into N8B.

## Current MCP reality (repo truth, `origin/main`)
- **Transport already correct:** the NAS MCP (`nas_mcp/server.py:38`) is FastMCP **Streamable HTTP** (`stateless_http=True`), `/mcp` + `/health`, container binds `0.0.0.0:8765`, Docker publishes loopback-only `127.0.0.1:8765` (`deploy/nas/mcp/compose-mcp.yaml`).
- **NAS-resident, but remote access was Mac-dependent:** the service runs on the NAS; the only remote path today is a Mac SSH tunnel (`mac-tunnel.sh.example`, `-L 18765:127.0.0.1:8765`). N8B's NAS-side `cloudflared` removes the Mac hop.
- **Two security-critical gaps addressed in this foundation:** (1) the exposed surface was write-capable (5 vault-mutation tools + 2 output writers) — now locked by the `remote_cloudflare` profile (`03`, `26`, `29`); (2) the origin has no auth — Cloudflare Access is the edge layer, origin-side OAuth is a required later sub-phase (`19`).

## NAS parameters (repo truth, non-secret)
| Parameter | Value |
|---|---|
| Service root | `/volume2/personal-assistant` |
| App-support | `/volume2/personal-assistant/app-support` |
| DB (RO to MCP) | `.../app-support/db/hb-personal-assistant.sqlite` |
| Vault (RW) | `/volume2/personal-assistant/vault/obsidian` → `/mnt/vault` |
| MCP origin | `http://127.0.0.1:8765/mcp` (loopback publish) + internal `http://hb-personal-assistant-mcp:8765` |
| Health | `http://127.0.0.1:8765/health` |
| Runtime user | `personal-assistant-svc` (1028:100); control `bfetting` (SSH 10021) |
| Public hostname (intended) | `mcp.bobby-fetting.me` (validated previously vs the `:8000` OAuth surface) |

## Operator confirmations (pending)
- Hostname `mcp.bobby-fetting.me` (default assumed).
- `AI Outputs` folder location under the NAS vault (config default `AI Outputs`; `27`).
- Cloudflare dashboard actions are operator-only (agent cannot create tunnels/Access).

## Verdict
**PASS (preflight).** N8A clean; transport already Streamable HTTP; the two exposure risks are addressed by this foundation's lockdown + scaffold; live Cloudflare is HOLD pending operator Cloudflare setup.
