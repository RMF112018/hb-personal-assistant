# Phase 09 — Prompt 21: Metadata Filter Enforcement (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `d8758fc5066f806df81e55a0f2c2a0bb08899874`
- **Schema:** V38 (unchanged — pure filter layer, no new table; contract table count stays 190)

## Objective

Enforce **project / source / date / review / confidence / source-coverage** filters **before** retrieval
(constrain which allowlisted families/sources are queried; reject excluded families) and **after**
retrieval (drop items outside the requested window / tier / confidence and emit source-coverage
warnings), preserving source-of-truth discipline.

## What changed

- **`retrieval/metadata_filter.py`** (new) — `MetadataFilter` spec, `normalize_filter` (pre),
  `apply_metadata_filter` (post), `build_metadata_filter_proof`, loaders.
- **`retrieval/hybrid_broker.py`** — `build_hybrid_retrieval` gains an optional `metadata_filter` param:
  pre-filter sets the deterministic `families`/`project_key`; post-filter drops merged items before
  `apply_context_budget`; the summary gains `filter_applied` + `filter_summary`.
- **`contracts.py`** — registered `metadata_filter_contract`.
- **`cli/second_brain.py`** — new `retrieval metadata-filter` group: `status`, `apply`, `proof`.
- **Contract/seed** — `phase_09_metadata_filter_contract.json` + `phase_09_metadata_filter.seed.yaml`.
- **No migrator change, no persistence** (read-only filter).

## Filter semantics

- **Pre (`normalize_filter`):** fail-closed (`MetadataFilterError`) when an excluded family is explicitly
  requested; allowlisted-but-unknown families dropped with `requested_family_not_allowlisted`; date
  window / tier bound / confidence validated.
- **Post (`apply_metadata_filter`):** drops by `project_mismatch` / `family_not_selected` /
  `out_of_date_window` / `review_tier_above_max` / `confidence_below_min` (recorded per reason).
  **Date filtering is family-aware** — date-incapable families (`cross_source_relationships`, semantic)
  are kept with `date_filter_not_applicable`, never silently dropped. Review tier / confidence / source
  refs / freshness preserved on kept items.
- Confidence order (best→worst): `deterministic > high > medium > low > unknown`.

## Filter proof — `metadata-filter proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| excluded family rejected pre-filter | true |
| unknown family coverage noted | true |
| allowlisted family kept | true |
| post-filter drop matrix ok | true |
| dropped_by_reason | `{out_of_date_window:1, review_tier_above_max:1, project_mismatch:1, family_not_selected:1}` |
| kept source refs | `[iss-keep]` |
| date-incapable family noted | true |
| hybrid integration ok | true |
| raw query not emitted | true |

## Real HuggingFace filtered hybrid smoke (`BAAI/bge-small-en-v1.5`)

A real `bge-small` hybrid query with `MetadataFilter(max_review_tier=2, min_confidence=medium)` returned
`status='ok'`, `filter_applied=true`, 6 results (**3 tier-1 + 3 tier-2, 0 tier-3** — the tier ceiling is
enforced), `assembles_final_answer=false`. Captured at
`validation-outputs-prompt-21/real-huggingface-filter-smoke.json`. Automated equivalent:
`tests/test_phase_09_metadata_filter.py::test_filtered_hybrid_real_huggingface_smoke` (`integration`).

## Operator DB outcome

`metadata-filter apply` against the operator DB → `status='ok'`, `filter_applied=true`,
`result_count=0`, `dropped_by_reason={review_tier_above_max: 500}` — the operator
`project_issue_history_items` are review-tier 3 and `--max-review-tier 2` drops all 500 (correct
enforcement). **Persists nothing**; `hybrid_query_runs`/`hybrid_query_results` stay **0 rows**; schema 38;
operator DB data unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in **289** source files
- `pytest -m "not live and not integration and not manual"` → **3152 passed, 0 failed, 4 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval metadata-filter status --json` → exit 0
- `second-brain retrieval metadata-filter apply "<q>" --source … --max-review-tier … --min-confidence … --json` → exit 0 (filtered; no persist)
- `second-brain retrieval metadata-filter proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0.

## Deferred

- Wiring the filtered hybrid broker into Research Packet (A02) / Synthesis (A04) — deferred (Prompt 20 carry).
- `generated_outputs` (research-packet) loader still absent. Eval sets / benchmarks / memory-quality — later prompts.
