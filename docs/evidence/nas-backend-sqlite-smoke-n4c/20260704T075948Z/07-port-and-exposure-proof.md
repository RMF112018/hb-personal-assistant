# 07 — Port and Exposure Proof

## Before smoke

Port **8000/9000/9443** not listening. No Tailscale Serve/Funnel.

## During smoke

| Check | Result |
|---|---|
| `netstat` | **`127.0.0.1:8000` LISTEN only** |
| `0.0.0.0:8000` | **Absent** (PASS gate) |
| `docker inspect` port bindings | `HostIp=127.0.0.1`, `HostPort=8000` |
| Tailscale Serve/Funnel | None |
| Cloudflare | None |

## After shutdown

| Check | Result |
|---|---|
| `netstat` LISTEN on 8000 | **None** — port 8000 not listening |
| TIME_WAIT rows | Observed transiently; **not** active listeners |

## Exposure verdict

**PASS** — loopback-only publish; no WAN/Tailscale/Cloudflare exposure.
