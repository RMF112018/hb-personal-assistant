# 16 — Origin Auth Interaction Proof

The new tools sit behind the origin-auth middleware exactly like every other tool.

`test_freshness_requires_origin_auth` (real wired app via TestClient):
- `POST /mcp tools/call hb_data_freshness` **without** a bearer → `401 {"detail":"unauthorized"}`
  (rejected at the middleware before the tool runs).
- With a valid bearer → `initialize` + `tools/call hb_data_freshness` → `200`.

`test_per_token_allowed_tools_cannot_reach_freshness` — a token whose `allowed_tools` is
`{hb_mcp_status}` is denied `hb_data_freshness` with `tool_not_in_token_scope`. So authentication
is necessary and per-token narrowing still applies to the new tools; a valid token does not
broaden access. Safe mode does not create any unauthenticated path — status/freshness remain
auth-gated even during lockdown.
