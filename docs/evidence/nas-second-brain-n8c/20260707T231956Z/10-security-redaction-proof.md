# N8C-21 — security & redaction proof

- `scripts/obsidian_evidence_redaction_check.py <this dir>` → PASS (no secrets/tokens/PEM/absolute-private-path
  in the safe evidence; `local-sensitive/` excluded).
- All captured command output (smoke, git-status) has absolute user-home paths redacted to `<redacted>`.
- No credential, tunnel token, raw prompt, raw MCP payload, source body, or email body is captured anywhere in
  this bundle. The validation is structural (tool names / counts / booleans) only.
- `validate-db.sh` change is constants-only: no write op, migration, service restart, chmod/chown, rsync/scp,
  docker compose up/down, or remote command was added (diff is four constants + a comment).
