# N8C-21 — NAS redeploy operator commands (DOCUMENTED, not performed)

These are commands the OPERATOR runs on the NAS. This phase performs none of them — no restart, no migration,
no prod-DB mutation, no tunnel/exposure change, no credential rotation, no deploy, no push. STOP-and-report if
any must be performed here.

```sh
# 1. Refresh the read-only DB SNAPSHOT the MCP reads (never the live 4GB DB directly)
deploy/nas/scripts/snapshot-mcp-db.sh

# 2. Read-only DB posture check (schema 111 / 548 tables / 550 objects; PRAGMA quick_check)
deploy/nas/scripts/validate-db.sh

# 3. Redeploy the MCP container via runner verbs
deploy/nas/mcp/hb-mcp-runner stop
deploy/nas/mcp/hb-mcp-runner start
deploy/nas/mcp/hb-mcp-runner status
deploy/nas/mcp/hb-mcp-runner health

# 4. Prove the OAuth origin end-to-end against LOOPBACK before touching the edge
deploy/nas/scripts/probe-oauth-origin.sh
```

Runbooks: `deploy/nas/mcp/README.md`, `deploy/nas/mcp/N8B-oauth-stage-b-runbook.md`. The Cloudflare edge /
tunnel and any credential/token stay UNCHANGED unless separately authorized. Data-plane invariant: the
internet-facing MCP reads only the checkpointed read-only snapshot, never the live production DB.
