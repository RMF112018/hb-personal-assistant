# 63 — Phase 08A: Allowlisted Read-Only SQLite Query Tools (Synthesized Prompt 06)

Status: implemented (Phase 08A Synthesized Prompt 06). Builds on records 57–62.
Deterministic, local-first, read-only, no-writeback, no new SQLite tables.

## Purpose

Implements the **named, allowlisted SQLite query-tool layer** that sits below the
future retrieval orchestrator (Prompt 07). Each query tool is an explicit Python
service function — the model never generates or executes SQL. `run_query_tool`
dispatches by allowlisted *name* only; an unknown / model-authored string raises
`QueryToolError` **before any DB access** (the sole "deny arbitrary SQL" path — there
is no SQL-string parameter anywhere in the API). Every result carries source refs +
confidence class + review tier + bounding metadata; tools provide bounded facts only
and never decide final answers.

**No new tables** — V26 already ships `query_tool_receipts`; schema stays V26 / 141.
**No embeddings / vectors / external access.**

## Repo-truth reconciliation (package intent vs repo reality)

The package allowlist defines **13 tools**. Repo truth: **7** map to an existing
Prompt-04 reader (`retrieval/readers.py::READER_REGISTRY`); the other 6 have no
read-model yet. The full 13-tool allowlist is honored (it is the approved surface),
but unbacked tools degrade gracefully (`status="no_read_model"`, empty rows, warning)
— never fabricated — mirroring the broker's graceful-degradation posture.

| Tool | Read-model family | State |
|------|-------------------|-------|
| `relationship_candidates` | `cross_source_relationships` (candidate states) | backed |
| `accepted_relationships` | `cross_source_relationships` (accepted states) | backed |
| `source_evidence_trails` | `phase_07d_source_evidence_trails` | backed |
| `issue_history` | `project_issue_history_items` | backed |
| `risk_digest` | `project_risk_digest_items` | backed |
| `aging_exposure` | `aging_exposure_report_items` | backed |
| `memory_items` | `accepted_long_term_memory` | backed |
| `project_context`, `source_coverage` | composite (orchestrator) | no_read_model |
| `meeting_prep_briefs` | `meeting_prep_brief_sections` (deferred) | no_read_model |
| `review_queue_status` | — | no_read_model |
| `research_packet_status` | Prompt 07 | no_read_model |
| `evaluation_status` | Prompt 07/08 | no_read_model |

Note: `cross_source_relationships` holds *promoted* relationships; on real data the
candidate-state filter typically yields none (the candidates store has no Prompt-04
reader). Both relationship tools share the single relationship reader and split on the
derived (read-only) V25 relationship state.

## Contract + seed

- `resources/json/sqlite_query_tool_contract.json` — package `version`
  (`phase_08a_sqlite_tools-v2`) + `constraints`, enriched (repo-truth authoritative)
  with `allowlisted_tools`, `result_required_fields`, `item_required_fields`,
  `forbidden_fields`, and explicit `arbitrary_sql_allowed`/`mutation_sql_allowed`
  false. Registered in `second_brain/contracts.py` as `sqlite_query_tool` and in
  `tests/test_phase_08a_contracts.py::_REQUIRED_KEYS`.
- `resources/config/phase_08a_sqlite_query_tool_allowlist.seed.yaml` — the 13 tools +
  `arbitrary_sql_allowed: false`, `mutation_sql_allowed: false`,
  `source_refs_required: true`, `review_tier_required: true`.

## Code (`construction/second_brain/query_tools/`, strict-mypy)

- `models.py` — `QueryToolResult` (tool_name, project_key, status, items
  [`RetrievalItem`], source_refs, row_count, char_count, truncated,
  review_tier_summary, warnings) with a validator rejecting forbidden raw field names
  in `source_refs`; `QueryToolReceipt` mirroring V26 `query_tool_receipts`.
- `policy.py` — `ALLOWLISTED_QUERY_TOOLS`, `QUERY_TOOL_FAMILY_MAP`, accepted/candidate
  relationship state sets, `QueryToolError`, `load_query_tool_allowlist_seed`
  (env override `HB_SECOND_BRAIN_QUERY_TOOLS`), `validate_query_tool_policy`.
- `tools.py` — `read_only_connection` (`PRAGMA query_only = ON`; writes raise),
  `run_query_tool` (allowlist gate → reader dispatch → relationship filter → bound →
  source_refs/tier summary → optional receipt), `list_query_tools`,
  `build_sqlite_query_tool_proof`.
- `store.py` — `write_query_tool_receipt` (metadata-only INSERT into V26
  `query_tool_receipts`; guard columns 0 via DB CHECK), `read_latest_query_tool_receipts`.

### Read-only transaction posture

`run_query_tool` reuses the Prompt-04 readers (consistent with the broker). The three
`_read_bounded`-backed readers (risk_digest, aging_exposure, memory_items) accept an
injected connection, so their bounded SELECT runs under the layer-owned
`read_only_connection` (`PRAGMA query_only = ON`) — a write/DDL on it raises
`sqlite3.OperationalError`. The `ConstructionStore`-backed readers
(relationships/evidence/issue) issue only fixed parameterized SELECTs (structural
read-only). `_read_bounded` gained one backward-compatible optional `conn` parameter
to enable this injection.

## CLI

`hb-assistant second-brain query-tools list` (allowlist + backed/unavailable + policy
validity) and `... run <tool> [--project-key] [--emit-receipt/--no-emit-receipt]`
(read-only; exit 0 ok, 3 on a non-allowlisted tool with a JSON error body; dry-run
default — receipts off unless requested).

## Guardrails

Local-first; no external systems; no Microsoft/Procore writeback; no
arbitrary/model-generated SQL code path; read-only transaction posture; bounded
results; mandatory source refs + review tiers; metadata-only receipts (guard CHECK
columns 0); no raw bodies/document text/calendar payloads/prompts/responses/URLs/
secrets emitted or persisted.

## Deferred (owning prompts)

Retrieval orchestrator + research packet (07); interactive query/synthesis (08) —
`project_context`/`source_coverage`/`research_packet_status`/`evaluation_status` stay
no_read_model. New readers for `meeting_prep_brief_sections` /
`review_controlled_correspondence_context` (intentionally deferred). 08A no-writeback
proof arm + V27 agent persistence (later prompts).
