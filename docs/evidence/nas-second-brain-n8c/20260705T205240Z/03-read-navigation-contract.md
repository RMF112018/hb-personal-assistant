# 03 — Read/Navigation Contract

Full contract: **`docs/architecture/n8c-read-navigation-contract.md`** (endpoint ↔ MCP-tool ↔ response
shapes, error codes, content/safety posture, frontend client). Defined before wiring consumers
(clarification #8); the API, MCP, and frontend all match it.

**Intentional default policy:** the contract's default authenticated remote behavior is navigation
**plus bounded deep content access** (complete, unredacted source/card/vault-note content) — Bobby's
deliberate operator decision (see `02`). All reads are tool-mediated, bounded, read-only, relative-path,
and authenticated; no raw SQL / shell / arbitrary filesystem; `ai_outputs_card_upsert` stays the only
write.

## Shared service — `obsidian_mcp/source_navigation.py`
12 read-only functions (one per capability), each accepting `*, conn=None` and returning plain dicts:
`search_sources`, `search_cards`, `get_source`, `get_card_for_source`, `get_source_for_card`,
`get_card_state`, `list_stale_cards`, `list_duplicate_cards`, `list_ambiguous_card_links`,
`recent_changes`, `get_related_sources`, `get_vault_note`.

## Stable-shape invariants (identical across API and MCP)
- List responses: always `count` + `limit` (clamped ≤ `MAX_LIMIT`=100) + `truncated`.
- card→source: always `resolution` ∈ {none, unique, ambiguous}; `source_id` set only when `unique`
  (never guesses — reuses N8C-2 `ReverseLookup`).
- card state: `state` ∈ {current, stale, missing, duplicate, source_deleted, no_card} (N8C-2 `STATE_*`).
- Path fields (`path` / `note_rel_path` / `source_rel_path`) relative + `source_root_key`; never absolute.
- API additionally wraps each payload in `"guardrails"` (`read_only: true`, …).
