# 00 — N8C-4 Closeout (Claim Extraction Layer)

**Slice:** N8C-4 — Claim Extraction Layer (first durable memory layer above sources/cards/navigation).
**Branch:** `ops/nas-second-brain-n8c-04-claim-extraction-20260705T215143Z`, base **`86701ad8`** (the
local N8C-3 commit). **Not committed, not pushed** — awaiting explicit authorization.

## What shipped
- **Schema (V100, `LATEST_SCHEMA_VERSION` 99→100):** `store/assistant_claim_tables.py` —
  `assistant_claims` + `assistant_claim_events`. Additive, idempotent, empty on create; migration
  wired into `store/migrator.py`. No source/import table touched.
- **Model:** `obsidian_mcp/claim_models.py` — neutral claim types (fact/date/risk/assumption/
  preference/commitment/task_candidate/contradiction_candidate/decision_candidate/unknown), status,
  review_state, confidence, deterministic `compute_claim_id`, bounded evidence.
- **Repository:** `obsidian_mcp/claim_repository.py` — sole reader/writer of the claim tables;
  mandatory source provenance, confidence clamping + enum validation, bounded evidence, idempotent
  upsert, event log, bounded read helpers.
- **Extractor:** `obsidian_mcp/claim_extraction.py` — deterministic rule-based extraction (no LLM) for
  dates/deadlines/preferences/risks/assumptions/commitments/decisions, a validated ingestion seam
  (`rule_based | manual | future_qwen`), and a card-aware orchestrator gated by N8C-2/N8C-3 state.
- **Local read API (only):** `GET /api/assistant/claims`, `/api/assistant/sources/{id}/claims`,
  `/api/assistant/cards/claims`. No remote MCP claim tool; no claim-write surface.

## Verification (see 08)
34 new tests pass (12 repository + 16 extraction + 6 claim API). Full N8C-4 + N8C-3 + N8C-2 + N8C-1
regression sweep: 171 passed, 0 failed. Ruff clean on all new/changed files. Migration idempotent →
100; `source_notes.py`/`source_navigation.py` untouched; obsidian tool count 56; the N8C-3 remote MCP
surface stays exactly 12 `assistant_*` tools (no claim tools added remotely).

## Guarantees
Every claim is source-backed (DB CHECK + repo validation). No raw/import DB mutation. No extraction runs
on startup/import. No remote claim-write surface. N8C-3 navigation + bounded-deep-content policy intact.

## Status
Complete and verified locally. **No commit. No push.** Awaiting authorization.
