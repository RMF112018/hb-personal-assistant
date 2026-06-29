# Ollama-assisted summarize_source — Final Report

Branch `feat/obsidian-mcp-ollama-summaries`, **stacked on PR #201** (source cards, open).
**Uncommitted**, pending authorization.

## Why
The card lifecycle (generate → stale → refresh) is proven, giving Ollama a safe enrichment target.
This adds **model-assisted advisory narrative** without inventing new lifecycle mechanics, kept in a
separate failure domain from search/indexing and from embeddings.

## Scope delivered
`summarize_source` (write/operator MCP tool + operator API route). Reuses `llm.py`'s Ollama seam
with guaranteed fallback. V94 receipt table. Deferred: embeddings, Settings UI.

## Behaviour
- `summarize_source(source_id)` — one call: ensures the deterministic base card exists, then (only
  when a **real model** produced output, `mode=="llm"`) writes a bounded, clearly-labelled
  `## AI Summary (advisory — model-generated, not authoritative)` section in place, preserving the
  deterministic frontmatter and adding `summary_advisory: true` + model fields. Upserts the V94
  receipt. Ollama unavailable / sensitive / link source → `{"summarized": false, "reason": ...}` with
  the deterministic base intact (no fake summary). Bounded model input (`source_summary_max_input_chars`)
  + bounded advisory lists.
- **Clean contract:** deterministic tools never emit model content. `generate_source_card` /
  `refresh_stale_source_notes` strip any advisory section and **delete the receipt**. A summary is
  "stale" when its `source_sha256 != metadata.content_sha256` — surfaced as `stale_summary_count` in
  `source_index_status`.

## V94 schema (additive, 93→94)
`source_intelligence_summaries`: source_id PK, model_provider, model_name, prompt_version,
prompt_sha256, summary_sha256, source_sha256, `advisory INTEGER CHECK(advisory = 1)`, generated_at.
**No raw prompt or model response stored** — hashes + model identity + advisory marker only; the
bounded summary text lives only in the card.

## Guardrails
Advisory (labelled in body + frontmatter); never in the search path; never blocks indexing; Ollama
unavailable degrades to `summarized:false` (no fake summary, no exception); bounded input + advisory
sections; no raw prompt/response persisted; cards via `create_note` only; strict-JSON; timeout guard +
OAuth + deterministic-card + index core untouched. Tool registry + health 44→45; config schema_version 4→5.

## Validation
- `tests/test_obsidian_source_summaries.py` (8, injected fake backend via `llm._resolve_backend`):
  advisory enrich + receipt (no prompt/response in DB); Ollama-unavailable keeps base, no advisory, no
  receipt; deterministic generate strips advisory + deletes receipt; source change → stale_summary_count
  1; link/sensitive → `no_summarizable_text`; advisory lists bounded ≤10; source_not_found.
- `tests/test_migrator_v94_source_summaries.py` (4): additive, `CHECK(advisory = 1)`, idempotent.
- **70 passed** across summaries/migrator/notes/backend/oauth/repo/index; 45-tool timeout sweep
  separate. ruff + mypy clean (api.py pre-existing only).
- Runtime (real app lifespan + `/mcp` + API, injected backend): API summarize 403 viewer / 200 operator
  → `summarized:true mode:llm`, advisory section + frontmatter; MCP `summarize_source` works; status
  `summarized_count=1`. Zero tracebacks/timeouts.

## Files
NEW: `tests/test_obsidian_source_summaries.py`, `tests/test_migrator_v94_source_summaries.py`.
MODIFIED: `store/{migrator,source_intelligence_tables}.py` (V94), `obsidian_mcp/source_notes.py`
(advisory render + summarize_source + receipt-delete on deterministic write),
`source_index_repository.py` (summary receipt methods + counts), `config.py` (source_summary_* ;
schema_version 4→5), `service.py` (facade + health 44→45), `tools.py` (registry +1), `mcp_app.py`
(scope + closure), `api.py` (request model + operator route), backend + timeout test expectations.

## Commit
Single commit `feat(obsidian-mcp): add ollama-assisted source summaries`, stacked PR on #201, no
attribution. UNCOMMITTED pending authorization.
