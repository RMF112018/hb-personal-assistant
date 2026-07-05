# 10 — API Endpoint & Role Proof (local)

API-side safety, kept **separate** from the MCP proof (clarification #4). Source:
`tests/test_fastapi_analytics_assistant_nav.py` (8 tests, all pass). The analytics FastAPI shell is the
LOCAL UI backend (vite-proxied to `127.0.0.1`), not the internet-facing surface.

## Endpoints
12 `GET /api/assistant/*` routes added as `create_app` closures, each `role: dict = role_dep` +
`del role` (all-roles, read-only), delegating to `source_navigation.*` over a live-DB
`SourceIndexRepository`, returning the service payload plus `"guardrails": _guardrails()`.

## Proofs
- `test_all_list_endpoints_200_guardrails_safe` — the list endpoints return 200 with
  `guardrails.read_only=true`, `{count,limit,truncated}`, and pass `_assert_safe` (no
  access_token/refresh_token/client_secret/cache_path/Bearer/eyJ/BEGIN PRIVATE KEY/raw_backend).
- `test_source_detail_and_linkage` — `sources/{id}` returns relative `rel_path` + card; the private
  source-root absolute path does not appear; `/card`, `/state`, `/related` all 200 with guardrails.
- `test_card_source_reverse_lookup` — `resolution` ∈ {unique, ambiguous, none}.
- `test_vault_note_complete_content` — full note content, `truncated=False`.
- `test_missing_source_404` — unknown source → 404.
- `test_vault_note_traversal_400` — absolute / `..` / protected-folder paths → 400.
- `test_all_roles_accessible` — viewer/operator/admin all 200 + safe.
- `test_route_shape_get_only_no_writeback` — ≥ 12 routes under `/api/assistant`, methods ⊆ {GET}; no
  POST/PUT/PATCH/DELETE anywhere under `/api/assistant`.

## Result
All pass. Local API is GET-only, all-roles, read-only, guardrailed, and leaks no secrets.
