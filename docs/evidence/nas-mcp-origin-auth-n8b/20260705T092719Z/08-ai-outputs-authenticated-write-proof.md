# 08 — AI Outputs Authenticated Write Proof

The single sanctioned remote write (`ai_outputs_card_upsert`, tier 3) works **only** for a
valid authenticated client and **only** inside the `AI Outputs` folder.

## Proof (`test_valid_token_can_call_ai_outputs_but_not_outside_folder`)
With an `AuthContext(client=claude, client_label="Claude Desktop", actor=bfetting)` set:
- `ai_outputs_card_upsert(title="Note One", mode="create")` → `ok: True`; card written under the `AI Outputs` folder; a mutation receipt + backup are produced by the reused `obsidian_mcp/mutations` engine (foundation behavior, unchanged).
- A traversal-y `title="../../escape"` does **not** escape — the folder-lock slugs traversal characters away; a filesystem sweep confirms **no `.md` file exists outside `AI Outputs`**.

## Unauthenticated
Without a bearer, `ai_outputs_card_upsert` is unreachable — the request is rejected at the
`OriginAuthMiddleware` (`05`) before the tool is ever dispatched.

## Attribution
The write's audit event carries the authenticated `actor` / `client_label` / `client` and
the card's `source_client` — so remote AI-Outputs writes are attributable per client (`12`).

Folder-lock, Markdown-only, SHA-gated update, backup-before-overwrite, and receipting are
the foundation contract (evidence `27`/`28` of the foundation bundle); this phase adds the
authenticated-caller requirement in front of them.
