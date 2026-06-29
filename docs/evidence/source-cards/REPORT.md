# Deterministic Source Cards — Final Report

Branch `feat/obsidian-mcp-source-cards`, **stacked on PR #200** (`feat/obsidian-mcp-source-intelligence`,
open). **Uncommitted**, pending authorization.

## Why
Natural next layer on the merged source-intelligence index: a curated Obsidian note that *describes
and links back to* an indexed source — proving the generate → stale → refresh lifecycle + source
traceability with **deterministic** templates before any Ollama summaries are layered on.

## Scope delivered
`generate_source_card` + `refresh_stale_source_notes` (MCP write/operator tools) + operator API
routes. Deterministic Markdown only. **No new migration** — reuses the foundation's
`source_intelligence_generated_notes` table + auto-stale-on-reindex hook.
**Deferred:** Ollama summaries, embeddings, Settings UI, the `summarize_source` name.

## Behaviour
- `generate_source_card(source_id, overwrite=False)` — renders a deterministic card via the existing
  `create_note` guardrails (write policy + SHA-gated overwrite + atomic + backup + receipt + pathsafe),
  records `generated_notes` status=generated. Refuses `obsidian_note` kind (already a vault note),
  missing/deleted sources, and respects `source_card_generation_enabled`.
- `refresh_stale_source_notes(max_updates)` — regenerates cards whose source changed
  (`generation_status='stale'`, set automatically on reindex/delete), per-item failures never abort
  the batch.
- **Frontmatter traceability:** note_type, source_id, source_kind, source_path/source_ref,
  source_root_key, source_sha256, source_mtime_ns, indexed_at, generated_at, stale, project_key,
  project_number, tags.
- **Adaptive body:** external_file → Overview (factual fields) + bounded labelled preview
  (`source_card_excerpt_chars`, default 600); sensitive (Text-Vault) → preview withheld; email/procore/
  schedule LINK sources → metadata + Linked Record only (no body, by construction). Always a Source
  Reference section noting the raw file stays outside the vault.

## Guardrails
No raw file dumping (bounded, labelled, capped preview; large-file test proves the cap); **no raw
email body** (link sources have no `_text`; the card never reads `email_messages` bodies); sensitive
text never in the card; cards are `.md` via `create_note` only; operator/write scope; strict-JSON
results; no token/content in logs; timeout guard + OAuth + index core untouched. No schema change.

## Validation
- `tests/test_obsidian_source_notes.py` (9): traceability frontmatter; bounded-preview no-raw-dump;
  obsidian_note → `source_card_not_applicable`; email link → no body, domain ref present; sensitive →
  preview withheld; writes-disabled blocked; exists-requires-overwrite → single `generated_notes` row;
  stale→refresh round-trip; source_not_found.
- Extended backend (44-tool list) + timeout (strict-JSON over the 2 new tools). **58 passed** across
  source-notes/backend/oauth/repo/index; timeout sweep separate. ruff + mypy clean on changed modules
  (api.py pre-existing findings only).
- Runtime (real app lifespan + `/mcp` + API): API generate 403 viewer / 200 operator; card written with
  full frontmatter, no raw dump; MCP `generate_source_card` overwrite → generated; source change →
  reindex → stale → API `refresh-stale` → count 1. Zero tracebacks/timeouts.

## Files
NEW: `obsidian_mcp/source_notes.py`, `tests/test_obsidian_source_notes.py`. MODIFIED:
`source_index_repository.py` (get_source_detail / record_generated_note / list_stale_generated_notes),
`config.py` (source_notes_folder / source_card_generation_enabled / source_card_excerpt_chars;
config schema_version 3→4), `service.py` (facade + health 42→44), `tools.py` (registry +2),
`mcp_app.py` (scopes + 2 closures), `api.py` (2 request models + 2 operator routes),
backend + timeout test expectations.

## Commit
Single commit `feat(obsidian-mcp): generate deterministic source cards`, stacked PR on #200, no
attribution. UNCOMMITTED pending authorization.
