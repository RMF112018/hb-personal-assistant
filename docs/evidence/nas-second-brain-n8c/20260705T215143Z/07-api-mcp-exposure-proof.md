# 07 — API / MCP Exposure Proof

N8C-4 claims are exposed **read-only on the LOCAL API only**. There is **no remote MCP claim tool** and
**no claim-write surface** anywhere.

## Local API (read-only, GET-only, bounded)
Three closures added to `create_app` (mirroring the N8C-3 `/api/assistant/*` pattern: `del role`,
all-roles, `guardrails`, delegate to `ClaimRepository` over the live DB):
- `GET /api/assistant/claims?limit=&claim_type=&status=&source_id=&note_rel_path=`
- `GET /api/assistant/sources/{source_id}/claims?limit=`
- `GET /api/assistant/cards/claims?note_rel_path=&limit=`

Proof — `tests/test_fastapi_analytics_claims.py` (6 tests): list + filter + by-source + by-card return
`guardrails.read_only=true` and the expected counts; all roles accessible; `_assert_safe` (no
secrets); `test_claim_routes_are_get_only` asserts methods ⊆ {GET}, no POST/PUT/PATCH/DELETE. Evidence
text returned is already bounded (≤ `EVIDENCE_MAX_CHARS` at write) — no unbounded evidence exposure.

## Remote MCP — deliberately unchanged
No `assistant_*` claim tool was added. The N8C-3 remote MCP surface stays exactly **12** `assistant_*`
tools (`tests/test_nas_mcp_assistant_nav.py::test_registration_adds_12_assistant_tools_when_enabled`
passes unmodified; obsidian tool count still 56). Rationale: keep N8C-4 mostly internal and avoid
broadening the internet-facing surface; remote claim exposure is a future, separately-authorized
decision. No `db_allowlist` change; `ai_outputs_card_upsert` remains the only sanctioned remote write;
raw SQL/shell/filesystem stay denied.

## No claim SQL / no arbitrary text
Claim reads go only through the fixed `ClaimRepository` helpers (bounded `limit`, clamped ≤ 200) — no
raw claim SQL is exposed on any surface.
