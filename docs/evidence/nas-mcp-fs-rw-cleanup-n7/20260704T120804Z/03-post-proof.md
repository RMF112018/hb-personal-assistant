# 03 — Post-cleanup proof

**Captured:** after stop + probe removal

## Container / ports

```
== container ==
(empty)
== docker port 8765 ==
8765/tcp: not published
== loopback listener ==
host_listen=missing
== backend port check ==
port_8000=absent
```

| Port | State |
|---|---|
| `127.0.0.1:8765` | **absent** |
| `8000` (any bind) | **absent** |

## DB unchanged

| Field | Before | After |
|---|---|---|
| size | `4151631872` | `4151631872` |
| mtime | `2026-07-04 08:55:03.807899678 +0000` | `2026-07-04 08:55:03.807899678 +0000` |

## Probe artifacts

| Path | After |
|---|---|
| `vault/n7-fs-rw-probe.md` | **missing** |
| `outputs/n7-fs-rw-probe.txt` | **missing** |

## Vault / outputs integrity (top-level only)

| Root | Count before | Count after | Delta |
|---|---|---|---|
| Vault | 17 | 16 | −1 (probe only) |
| Outputs | 1 | 0 | −1 (probe only) |

Vault top-level list after: same as before **minus** `n7-fs-rw-probe.md`.  
Outputs top-level list after: **empty** (directory retained).
