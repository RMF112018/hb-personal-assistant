# 14 — Git status

| Item | Value |
|---|---|
| Branch | `feat/nas-mcp-ssh-launcher-n7-20260704T102041Z` |
| N7 implementation commit | `5dd638ff` — `feat(nas): add read-only MCP SSH launcher mode` |
| N7 apply hotfix commit | `a9ff717e` — `fix(nas): align MCP streamable HTTP lifespan and mount` |
| N7-APPLY evidence commit | `docs(nas): add N7 MCP apply and tunnel proof` (this commit) |
| Parent chain | evidence → `a9ff717e` → `5dd638ff` → … |
| Push | **Not authorized** |

Untracked (not in evidence): `deploy/nas/scripts/pr-c-viewer-lifecycle-run.sh`

Excluded from evidence: `local-sensitive/`, secrets, DB/vault files, raw transcripts.

## Post-hotfix working tree (before evidence commit)

```text
?? deploy/nas/scripts/pr-c-viewer-lifecycle-run.sh
?? docs/evidence/nas-mcp-apply-tunnel-n7/
```

No modified tracked files after `a9ff717e`.
