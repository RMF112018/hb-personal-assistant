# Phase 09 — Prompt 24: Retrieval Quality Eval Set (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `2e0a783779eb7e0ffa2ce320d884ac34c0df4e49`
- **Schema:** V38 (unchanged — reuses the existing `eval_sets` + `eval_cases` tables; contract table count stays 190)

## Objective

Create **source-linked retrieval evaluation cases from approved outputs** — metadata-only, fail-closed,
read-only by default.

## What changed

- **`retrieval/eval_set.py`** (new) — `build_retrieval_eval_set` (the builder), `_build_cases`,
  `persist_retrieval_eval_set`, `build_retrieval_eval_set_proof`.
- **`contracts.py`** — registered `retrieval_eval_set_contract`.
- **`cli/second_brain.py`** — new `retrieval eval-set` group: `build`, `proof`.
- **Contract/seed** — `phase_09_retrieval_eval_set_contract.json` + `phase_09_retrieval_eval_set.seed.yaml`.
- **No migrator change, no embeddings** (pure metadata enumeration).

## Build

Enumerate the approved outputs corpus (approved Obsidian generated outputs + reviewed/accepted long-term
memory, via `_gather_approved_nodes`) → one **source-linked** eval case per approved node, admitted iff it
carries a `source_ref` + an allowlisted (non-excluded) `source_family`. Each case stores
`expected_source_ref_hash` (hashed — never the raw ref), a `question_hash` (deterministic query *seed*
hash — no raw query text), and `confidence_class`. The eval set carries a hashed `name_hash`, `case_count`,
a `review_tier` summary, and `status` (`built`/`empty`). Executing/scoring the set (`eval_runs`) is a later
prompt.

## Eval-set proof — `eval-set proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| case_count | 3 |
| cases source-linked (hashed ref, no raw ref) | true |
| eval_sets row persisted metadata-only + guard-clean | true |
| eval_cases rows persisted metadata-only + guard-clean | true |
| unsafe/unlinked/excluded-family node excluded | true |
| no raw source ref emitted | true |

## Operator DB outcome

`eval-set build` against the operator DB → `status='empty'`, 0 cases, warning `no_approved_outputs` (the
operator DB has no approved Obsidian/reviewed-memory outputs — honest); `emit_receipt` defaulted False →
**persists nothing**. `eval_sets` / `eval_cases` row counts unchanged (0); schema 38; operator DB data unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in **292** source files
- `pytest -m "not live and not integration and not manual"` → **3173 passed, 0 failed, 6 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval eval-set build --json` → exit 0 (status=empty; no persist)
- `second-brain retrieval eval-set proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0.

## Deferred

- Executing/scoring the eval set against the index (`eval_runs` + pass/fail) — a later prompt.
- `generated_outputs` loader still absent (eval cases derive from Obsidian + reviewed memory).
- Benchmarks / memory-quality review — later prompts.
