# N2C-T · 02 — SSH Tunnel Setup

Backgrounded SSH local-forward from Mac through the NAS to the router + DSM (no passwords):
```
ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes \
  -L 18080:10.0.0.1:80 -L 18443:10.0.0.1:443 \
  -L 15000:127.0.0.1:5000 -L 15001:127.0.0.1:5001 \
  -p 10021 personal-assistant-svc@100.66.28.14
```
- Tunnel PID recorded in scratchpad; **closed at end of phase** (see `00`).
- NAS sshd **allows TCP forwarding** (tunnel came up).

## Endpoint verification (headers only; no cookies/tokens)
| Local | Target | Result |
|---|---|---|
| `http://127.0.0.1:18080` | router 10.0.0.1:80 | 500 with default Host; **200 with `Host: 10.0.0.1`** (Host-header artifact of tunneling) |
| `https://127.0.0.1:18443` | router 10.0.0.1:443 | same |
| `http://127.0.0.1:15000` | DSM :5000 | **200 (nginx)** |
| `https://127.0.0.1:15001` | DSM :5001 | **200** — title "TheLakeHouseNAS - Synology NAS" |

Router identified as **NETGEAR Orbi**; DSM confirmed. Note: the Mac is also **on-LAN (10.0.0.79)**, so
the router/DSM are directly reachable at 10.0.0.1 / 10.0.0.89 too — used for UPnP (below).
