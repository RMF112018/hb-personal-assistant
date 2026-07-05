# 08 — Operator Override Design

Lets the operator intentionally RAISE a specific limit briefly — without ever letting a remote
LLM relax limits.

## Local-only, no remote self-approval
Overrides are created solely by `python -m hb_assistant.nas_mcp.override_cli` on the NAS host.
**No MCP tool mints or approves an override** — the broker has no such dispatch path (proven by
`test_no_mcp_tool_can_create_override`). Only the override *status* (counts + redacted summary)
is remotely readable, via `hb_capability_mode`.

## Store (`overrides.py`)
JSON at `0600`, atomic write, at `HB_MCP_OVERRIDE_STORE` / `<app_support>/origin-auth/overrides.json`.
Record: `override_id`, `scope`, `max_value`, `client_label`, `actor`, `tool_name?`, `reason`,
`created_by`, `created_ts`, `expires_at`/`expires_ts`, `revoked`, `audit_receipt_id`. Records
carry no secret — an id is a handle, not a credential.

## Invariants (enforced)
- **raise-only** — `effective_limit` uses an override only if it exceeds the base.
- **always expiring** — `expires_minutes > 0` required (no indefinite override).
- **reason required**; scope ∈ {response_size, file_excerpt, search_results, rows, card_size,
  write_count, timeout, specific_tool}; `specific_tool` requires `--tool`.
- narrow: matches by scope + client (`any` or exact) + tool (for specific_tool).
- revocable (`revoke`), auditable (create writes an audit receipt).

CLI: `create --scope --max-value --client --expires-minutes --reason [--tool]`, `list`, `revoke`.
