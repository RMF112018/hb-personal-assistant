# 01 — Preflight git and N7 implementation

| Item | Value |
|---|---|
| Branch | `feat/nas-mcp-ssh-launcher-n7-20260704T102041Z` |
| N7 implementation commit | `5dd638ff` |
| N7 apply hotfix commit | `a9ff717e` |
| Ahead of `origin/main` | 17 (after hotfix; evidence commit pending) |
| Untracked (explained) | `deploy/nas/scripts/pr-c-viewer-lifecycle-run.sh` |

Local static checks before apply: `check-mcp-compose.sh` PASS, pytest 10/10 PASS, ruff PASS.

Production DB allowlist in repo: **`schema_version` only** (approved).

Evidence TS: `20260704T103025Z`
