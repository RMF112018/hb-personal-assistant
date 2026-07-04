# 07 — Port and exposure proof

## During runtime

| Check | Result |
|---|---|
| Host publish | **`127.0.0.1:8000`** only |
| Docker inspect | `HostIp=127.0.0.1`, `HostPort=8000` |
| Public / tailnet bind | **None** |

Container-internal bind `0.0.0.0:8000` is namespace-local only; host exposure controlled by compose publish to loopback.

## After shutdown

See `10-shutdown-proof.md` — no `LISTEN` on port 8000.
