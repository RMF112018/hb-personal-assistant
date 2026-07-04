# 04 — Status proof

## During runtime

```sh
sudo sh scripts/status.sh
```

| Field | Value |
|---|---|
| `publish_addr` | `127.0.0.1` |
| `container_running` | **yes** |
| Docker inspect | `HostIp=127.0.0.1 HostPort=8000` |
| Loopback-only LISTEN | Container starting; host LISTEN may lag until health ready |

Captured: `captured/evidence/status-during.txt`

## Post-stop

| Field | Value |
|---|---|
| `container_running` | **no** |
| Docker inspect | container not present |

Captured: `captured/evidence/status-post-stop.txt`
