# Phase 09 — Prompt 23: Output Evaluation Integration (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `8d711c03b7c5e6946d6f284372f3475f61906018`
- **Schema:** V38 (unchanged — reuses the existing `source_linked_proof_runs` + `unsupported_claim_checks` tables; contract table count stays 190)

## Objective

Route **semantic retrieval outputs** through **evaluation, unsupported-claim checks, and receipts** —
fail-closed, metadata-only, never assembling a final answer.

## What changed

- **`synthesis/semantic_output_evaluation.py`** (new) — `build_semantic_output_evaluation` (the route),
  `_unsupported_claim_check` / `_source_linked_proof`, `persist_evaluation_receipts`,
  `build_semantic_output_evaluation_proof`.
- **`contracts.py`** — registered `output_evaluation_integration_contract`.
- **`cli/second_brain.py`** — new `retrieval output-eval` group: `run`, `proof`.
- **Contract/seed** — `phase_09_output_evaluation_integration_contract.json` +
  `phase_09_output_evaluation_integration.seed.yaml`.
- **No migrator change, no synthesis rewiring.**

## Route

Build the hybrid envelope (deterministic authoritative + advisory semantic) → research packet (A02) → a
**non-synthesized context `AdapterResult`** (`answer=""`, `synthesized=False`) → the **real**
`build_evaluation_preview` (A05, 10-item checklist) → an unsupported-claim check + source-linked proof
over the retrieved items. The context is evaluated for fitness; **no answer is synthesized**
(`route='evaluation_only'`, `synthesis_performed=false`, `assembles_final_answer=false`). A retrieved item
is a *supported, source-linked claim* iff it carries a `source_ref` + an allowlisted (non-excluded)
`source_family`; any unsupported/unlinked item fails closed. The `unsupported_claim_performed` guard stays
0 (detect-and-block, never emit). `overall_passed = evaluation.passed AND unsupported==0 AND unlinked==0`.

## Integration proof — `output-eval proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| evaluation passed (score) | true (1.0) |
| unsupported_count | 0 |
| unlinked_count | 0 |
| overall_passed | true |
| receipts persisted metadata-only + guard-clean (both V38 tables) | true |
| unsupported claim detected and blocked (synthetic) | true |
| no answer emitted | true |
| raw query not emitted | true |
| excluded family fail-closed | true |

## Real HuggingFace output-evaluation smoke (`BAAI/bge-small-en-v1.5`)

A real `bge-small` hybrid retrieval (3 advisory semantic + 3 deterministic) routed through the real A05
evaluation (score **1.0**) + zero-tolerance unsupported-claim/source-linked checks, with
`synthesis_performed=false`, `overall_passed=true`, 0 unsupported / 0 unlinked. Captured at
`validation-outputs-prompt-23/real-huggingface-output-eval-smoke.json`. Automated equivalent:
`tests/test_phase_09_output_evaluation_integration.py::test_output_eval_real_huggingface_smoke`
(`integration`).

## Operator DB outcome

`output-eval run` against the operator DB → `status='ok'`, `route='evaluation_only'`,
`overall_passed=true` (10/10), 408 deterministic / 0 semantic (no applied index → semantic skipped);
`emit_receipt` defaulted False → **persists nothing**. `source_linked_proof_runs` /
`unsupported_claim_checks` row counts unchanged (0); schema 38; operator DB data unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in **291** source files
- `pytest -m "not live and not integration and not manual"` → **3166 passed, 0 failed, 6 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval output-eval run "<q>" --json` → exit 0 (evaluation_only; overall passed; no persist)
- `second-brain retrieval output-eval run "<q>" --mode deterministic-only --json` → exit 0
- `second-brain retrieval output-eval proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0.

## Deferred

- Wiring semantic output evaluation into the default `synthesize_answer` (A04) path — later prompt.
- Deeper claim-level NLI / hallucination scoring (Prompts 28-29) and the broader source-linked proof
  matrix (Prompt 34) — this prompt introduces the receipts + zero-tolerance source-linkage gate.
