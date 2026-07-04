# 00 — Closeout

**Phase:** N7 — MCP-on-NAS via SSH tunnel + dedicated loopback port  
**Result:** **WARN** (repo implementation complete; NAS apply deferred; production DB allowlist proposal-only)

## Verdict summary

| Area | Result |
|---|---|
| Repo-truth audit | PASS |
| Dedicated MCP server (`nas_mcp`) | PASS |
| Port separation (:8765 vs :8000) | PASS (compose + static checks) |
| Docker bridge + loopback publish | PASS |
| DB allowlist framework | PASS (production tables proposal-only) |
| FS root-key tools | PASS |
| Audit JSONL | PASS |
| Launcher/runner artifacts | PASS (not installed on NAS) |
| Tests (10) | PASS |
| Redaction scan | PASS |
| NAS apply | **Deferred** |

## Architecture

```text
Mac → http://127.0.0.1:18765/mcp
  SSH -L 18765:127.0.0.1:8765 hb-nas
  NAS 127.0.0.1:8765 → hb-personal-assistant-mcp (bridge network)
  Container listens 0.0.0.0:8765; host publish loopback only
```

## MCP command

```bash
hb-assistant mcp serve --nas-readonly --streamable-http --host 0.0.0.0 --port 8765
```

## Non-blocking follow-ups

1. Bobby approval for production DB table allowlist beyond `schema_version` proposal
2. NAS operator apply + tunnel proof addendum
3. Docker image rebuild on NAS with `[mcp]` extra
4. Optional: commit untracked `pr-c-viewer-lifecycle-run.sh` from prior phase (separate)

## Boundaries

No push, no PR, no NAS apply, no backend exposure, no broad sudo.
