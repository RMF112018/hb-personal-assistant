# 02 — Launcher status bug root cause

## Symptom (N7-APPLY WARN)

`hb-mcp-launcher status` invoked `"$DOCKER" ps` directly as `bfetting`. User lacks Docker socket membership → permission denied.

## Root cause

`deploy/nas/mcp/hb-mcp-launcher` `status` (and `start` post-check) called Docker CLI without sudo. Only `hb-mcp-runner` is granted in sudoers.

## Constraints

- No Docker group for `bfetting`
- No `NOPASSWD: docker`
- Single runner sudoers line preserved
