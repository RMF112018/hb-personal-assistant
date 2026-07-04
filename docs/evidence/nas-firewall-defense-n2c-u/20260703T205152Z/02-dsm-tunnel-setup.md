# N2C-U · 02 — DSM SSH Tunnel (lockout-safe access)

## Tunnel established (agent-managed, backgrounded)
```
ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -L 15000:127.0.0.1:5000 -L 15001:127.0.0.1:5001 \
  -p 10021 personal-assistant-svc@100.66.28.14
```
- Verified: `http://127.0.0.1:15000` → HTTP 200; `https://127.0.0.1:15001` → HTTP 200,
  title "TheLakeHouseNAS - Synology NAS".
- **Why the tunnel matters here:** DSM sees the forwarded request as coming from **127.0.0.1 (NAS
  localhost)**, which firewalls always allow. Configuring the firewall via `https://127.0.0.1:15001`
  is therefore **lockout-proof** — even a mis-ordered deny rule cannot cut off DSM access through the
  tunnel.
- PID recorded in scratchpad; **tunnel closed at end of phase** (see `00`).

## Browser automation
Claude Chrome extension **not connected**, so the agent cannot click the DSM UI. The operator performs
the firewall configuration in their browser at `https://127.0.0.1:15001` (accept the self-signed cert);
the agent supplies the exact rules (`03`) and verifies access (`05`). No credentials/cookies/tokens
handled.
