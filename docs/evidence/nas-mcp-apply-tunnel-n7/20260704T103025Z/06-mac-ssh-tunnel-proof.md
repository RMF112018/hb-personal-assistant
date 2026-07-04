# 06 — Mac SSH tunnel proof

## Command

```bash
ssh -N -L 18765:127.0.0.1:8765 -p 10021 hb-nas
```

## Mac listener

```text
ssh ... TCP 127.0.0.1:18765 (LISTEN)
```

## Health through tunnel

`curl http://127.0.0.1:18765/health` — **200**, metadata only (see `captured/mac-tunnel-health.json`).

Tunnel stopped at cleanup: `mac_tunnel_closed=yes`

No direct NAS IP used from Mac client evidence.
