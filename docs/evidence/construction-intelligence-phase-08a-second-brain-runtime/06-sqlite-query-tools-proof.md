# Phase 08A — Prompt 06: SQLite Query Tools — Run Proof

Allowlisted, read-only, named SQLite query tools over approved second-brain
read-models. No arbitrary/model-generated SQL, read-only transaction posture,
bounded results, mandatory source refs + review tiers, metadata-only receipts.

## Repo-truth preflight

- Baseline `git rev-parse HEAD`: `17dfdf38764bab8202f68a7b3e09840ac8a9a38d` (Prompt 05 HEAD).
- Package repo-truth baseline cited by the prompt: `c2656e1c9606662d7e6d86ef80f5715540216912`.
- Schema head: **V26** (unchanged). `construction-agent` contract table count: **141** (unchanged).
- No migration required — V26 already ships `query_tool_receipts`.
- `anthropic` not installed (offline posture) — irrelevant to query tools (no model).

## Files changed

Created:
- `src/hb_assistant/resources/json/sqlite_query_tool_contract.json`
- `resources/config/phase_08a_sqlite_query_tool_allowlist.seed.yaml`
- `src/hb_assistant/construction/second_brain/query_tools/{__init__,models,policy,tools,store}.py`
- `tests/test_query_tool_policy.py`, `tests/test_query_tools.py`, `tests/test_second_brain_query_tools_cli.py`
- `docs/architecture/63-phase-08a-sqlite-query-tools.md`
- `docs/evidence/.../sqlite-query-tool-proof.json`, `.../06-sqlite-query-tools-proof.md`

Modified:
- `src/hb_assistant/construction/second_brain/contracts.py` (register `sqlite_query_tool`)
- `src/hb_assistant/construction/second_brain/__init__.py` (query_tools re-exports)
- `src/hb_assistant/cli/second_brain.py` (`query-tools list` / `run` subgroup)
- `src/hb_assistant/construction/second_brain/retrieval/readers.py` (one backward-compatible
  optional `conn` param on `_read_bounded` + the three `_read_bounded`-backed readers, so
  their bounded SELECT runs under the read-only connection)
- `tests/test_phase_08a_contracts.py` (`_REQUIRED_KEYS["sqlite_query_tool"]`)

## Validation commands + results

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in 214 source files |
| `pytest tests/test_query_tool_policy.py tests/test_query_tools.py tests/test_second_brain_query_tools_cli.py` | 0 | 24 new tests passed |
| `pytest tests/test_phase_08a_contracts.py` | 0 | green (sqlite_query_tool contract registered) |
| `pytest -m "not live and not integration and not manual"` | 0 | full suite green |
| `construction-agent validate --json` | 0 | summary 4/4 passed, ok=true |
| `construction-agent data-quality table-inventory --json` | 0 | schema_version=26, contract_table_count=141 |
| `construction-agent data-quality no-writeback-proof --json` | 0 | proof_passed=true (unchanged) |
| `second-brain query-tools list --json` | 0 | count=13, backed_count=7, policy_valid=true |
| `second-brain query-tools run project_context --json` | 0 | status=no_read_model, rows=0 |
| `second-brain query-tools run "DROP TABLE x" --json` | 3 | error=tool_not_allowlisted |

## Evidence proof

`sqlite-query-tool-proof.json` (`build_sqlite_query_tool_proof`) → `proof_passed: true`:
arbitrary/unknown tool names rejected; read-only connection blocks writes
(`PRAGMA query_only`); no raw content; source refs present + Tier-3 visible-not-concluded;
`no_read_model` tools degrade gracefully; relationship split disjoint; policy valid.
7 backed tools, 6 no_read_model.

## Guardrail proof points

- **No arbitrary SQL**: `run_query_tool` accepts only allowlisted *names*; any other
  string raises `QueryToolError` before DB access. No SQL-string parameter exists.
- **Read-only**: bounded reads run under `read_only_connection` (`PRAGMA query_only = ON`);
  a write/DDL raises `sqlite3.OperationalError` (test `test_read_only_connection_blocks_writes`).
  ConstructionStore-backed readers are SELECT-only.
- **No raw content**: results reuse `RetrievalItem` (rejects forbidden raw field names);
  `QueryToolResult` validator rejects forbidden field names in `source_refs`;
  `test_no_raw_fields_in_result` scans the serialized result.
- **Source refs + review tier**: every row emits `source_family/source_ref/review_tier/
  review_status`; per-tier summary; Tier-3 items are `review_required` (never concluded).
- **Bounded**: `max_rows` cap sets `truncated`.
- **Receipts metadata-only**: `query_tool_receipts` rows carry counts/status/tool_name only;
  guard CHECK columns `arbitrary_sql_allowed`/`external_writeback_performed` = 0.
- **V25 read-only**: `test_v25_rows_unchanged_after_query` confirms no writeback.

## Reconciliations / known limitations

- Full 13-tool allowlist honored; 6 tools (`project_context`, `source_coverage`,
  `meeting_prep_briefs`, `review_queue_status`, `research_packet_status`,
  `evaluation_status`) have no Prompt-04 read-model and resolve to `no_read_model`
  (graceful), deferred to their owning prompts (07/08).
- `relationship_candidates` and `accepted_relationships` share the single relationship
  reader and split on derived V25 state. The relationship table holds *promoted*
  relationships, so the candidate filter typically yields none on real data (the
  candidate store has no Prompt-04 reader).
- Contract enriched beyond the package's minimal `version`+`constraints` (added
  `allowlisted_tools`/`result_required_fields`/`item_required_fields`/`forbidden_fields`)
  so it is self-describing + testable — repo-truth authoritative.

## Env var names (no values)

- `HB_SECOND_BRAIN_QUERY_TOOLS` — optional override path for the query-tool allowlist seed.

## Next prompt readiness

Query tools provide bounded, source-linked, tier-labeled facts for the **Prompt 07**
retrieval orchestrator / research-packet agent (which decides inclusion, degradation,
and warnings) and the **Prompt 08** interactive query / answer-synthesis surface.
Schema stays V26 / 141; no-writeback proof unchanged. The 08A no-writeback proof arm
(scanning second_brain/retrieval/query-tool tables) remains deferred to its owning
prompt (~15).
