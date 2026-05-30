# 10A — No Mailbox Mutation Proof

Phase 06 Prompt 08A · the mailbox stays strictly read-only; encrypted-body capture adds only a GET

## Read-only body fetch

Body capture uses the new `ReadOnlyMailClient.get_message_body(message_id)` → guarded
`GET /me/messages/{id}` with a body `$select`. The path is already on the read allowlist; the endpoint
guard validates method + path before any HTTP call. No new mutating method, scope, or endpoint was
introduced.

- `graph mail status --no-probe --json` guard self-test: `mutation_endpoints_blocked: true`,
  `no_mail_write_scopes_requested: true`.
- Runtime configured scopes: `User.Read, Mail.Read, Calendars.ReadWrite.Shared, Files.ReadWrite.All,
  offline_access` — **no** `Mail.ReadWrite*` / `Mail.Send*` (asserted live + in `test_mutation_lockout`).

## Static guarantees

- `tests/test_mutation_lockout.py` (graph-tree write-verb + mailbox-action-endpoint scan) → green,
  including the new `get_message_body`.
- `tests/test_email_body_security.py` scans `construction/email/*.py`, `cli/graph.py`,
  `mail_readonly_client.py`, `mail_endpoint_guard.py` for `createReply` / `createForward` / `sendMail` /
  `/reply` / `/forward` / `/move` / `/copy` / `markRead` / `markUnread` and for `.post(` / `.patch(` /
  `.delete(` calls → none present.
- The decrypt path (`graph mail body show`) is **local-only** — it reads the vault + DB and makes **no
  Graph call** at all.

## Schema-level locks (unchanged + extended)

`email_message_body_vault_refs` adds `CHECK(plaintext_persisted = 0)` /
`CHECK(obsidian_body_persisted = 0)` / `CHECK(evidence_body_persisted = 0)` /
`CHECK(log_body_persisted = 0)`; `email_messages.full_body_persisted = 0` and all V10/V11 mailbox-mutation
CHECKs remain. No mailbox-mutation path exists or is reachable.
