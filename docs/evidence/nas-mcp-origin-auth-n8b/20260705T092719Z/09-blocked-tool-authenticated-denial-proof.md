# 09 — Blocked-Tool Authenticated-Denial Proof

Confirms the FAIL condition "valid auth bypasses capability tiers" does **not** occur.

## With a valid bearer / `AuthContext`, still denied
- **Broad vault-write tools** (`create_note`, `patch_note`, `vault_update_frontmatter`,
  `vault_create_note_from_template`, `vault_append_to_daily_note`) — not registered in
  `remote_cloudflare`, and a direct `broker.dispatch` returns
  `write_tool_blocked_by_profile:<tool>` with an audited deny.
  (`test_valid_token_cannot_call_blocked_or_scratch_writes`)
- **Scratch output writers** (`hb_output_write_file`, `hb_output_create_dir`) — same.
- **Hard-denied verbs** (`raw_sql`, `sql`, `shell`, `exec`, `read_file_absolute`,
  `hb_output_delete`) — `action_denied_by_policy` (foundation behavior, unaffected by auth).
- **Per-token narrowing** — a token scoped to `allowed_tools=["hb_mcp_status"]` is denied
  `hb_root_list` with `tool_not_in_token_scope:hb_root_list`
  (`test_allowed_tools_narrowing`).

## Without a bearer, denied earlier
Any protected call without a valid token never reaches dispatch — `401` at the middleware
(`05`). So blocked tools are unreachable both by unauthenticated callers (edge) and by
authenticated-but-over-reaching callers (capability layer).

## Audit
Every denial writes a 0600 audit event with `decision=deny` + a `deny_reason` class and the
authenticated actor/client (when present) — never a token value (`12`, `14`).
