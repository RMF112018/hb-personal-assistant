# 05 — Loopback port and container proof

## Container

```text
hb-personal-assistant-mcp Up ... 8000/tcp, 127.0.0.1:8765->8765/tcp
```

- Image: `hb-personal-assistant:nas`
- User: `1028:100` (personal-assistant-svc)
- Process listen inside container: `0.0.0.0:8765` (expected for Docker publish)

## Host listeners

```text
tcp 0 0 127.0.0.1:8765 0.0.0.0:* LISTEN
```

- **No** `0.0.0.0:8765` host bind
- **No** port `8000` LISTEN during MCP-only run
- **No** `hb-personal-assistant-backend` container

## DB metadata

| Checkpoint | mtime | size |
|---|---|---|
| preflight | 2026-07-04 08:55:03 UTC | 4151631872 |
| final | 2026-07-04 08:55:03 UTC | 4151631872 |

**Unchanged** — no write/migration during apply.
