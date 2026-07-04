# 00 — Closeout

**Phase:** N7-FIX — MCP launcher status bug + Obsidian vault tool path audit  
**Result:** **WARN**

## Summary

Fixed `hb-mcp-launcher status` (and `start` post-check) to route Docker inspection through `sudo -n hb-mcp-runner status`. Audited NAS MCP vault pathing — compose/config already target `/volume1/personal-assistant/vault/obsidian` → `/mnt/vault`; hardened tool responses with `path_display`, symlink escape guard, and expanded static/tests.

## WARN reasons

1. NAS re-apply proof **deferred** (not authorized this session) — launcher status fix and vault mapping validated locally only.
2. Functional vault MCP probe not re-run on NAS (MCP stopped after N7-APPLY).

## PASS items

| Check | Result |
|---|---|
| Launcher `status` via runner + sudo | PASS (static) |
| No direct `docker ps` in launcher | PASS |
| Runner fixed verbs only | PASS |
| Sudoers single runner command | PASS |
| Vault host path in compose default | PASS |
| Vault container root `/mnt/vault` | PASS |
| No Mac vault path in NAS MCP code/deploy | PASS |
| Tool output uses logical `path_display` | PASS |
| Traversal/absolute/`.enc`/token denied | PASS |
| Symlink escape denied | PASS |
| Audit on allow/deny | PASS |
| Tests 19/19 | PASS |
| Redaction scan | PASS |
| `server.py` hotfix | Already committed `a9ff717e`; untouched |

## Boundaries

No push, no PR, no N8, no backend `:8000`, no broad sudo, no Docker group grant, no NAS apply.
