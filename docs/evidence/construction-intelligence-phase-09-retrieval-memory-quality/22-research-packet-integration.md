# Phase 09 — Prompt 22: Research Packet Integration (Evidence)

- **Package version:** 1.4.0-phase-09
- **Repo SHA at build:** `660faa62ae769cc1313b87c99248a5be79374327`
- **Schema:** V38 (unchanged — reuses `second_brain_research_packets`; contract table count stays 190)

## Objective

Route semantic (vector) retrieval context through **Research Packet generation only** — semantic context
may enter answer generation solely via the Research Packet, never assembling a final answer outside the
Research Packet / Evaluation layers.

## What changed

- **`retrieval/hybrid_broker.py`** — extracted the deterministic+semantic merge into `_collect_hybrid`
  (shared); `build_hybrid_retrieval` output is unchanged (Prompt 20/21 tests pass); added
  `build_hybrid_envelope(...) -> (RetrievalEnvelope, meta)` exposing the merged envelope.
- **`research/semantic_packet.py`** (new) — `build_semantic_research_packet` (the sanctioned route) +
  `build_semantic_research_packet_proof`. It builds the hybrid envelope and routes it through
  `build_research_packet_from_envelope` (A02), returning a packet — never an answer.
- **`contracts.py`** — registered `research_packet_integration_contract`.
- **`cli/second_brain.py`** — new `retrieval research-packet` group: `build`, `proof` (distinct from the
  existing 08A top-level `second-brain research-packet`).
- **Contract/seed** — `phase_09_research_packet_integration_contract.json` +
  `phase_09_research_packet_integration.seed.yaml`.
- **No migrator change, no synthesis rewiring.**

## Route discipline

| property | value |
|---|---|
| route | `research_packet_only` |
| synthesis_performed | **false** |
| assembles_final_answer | **false** |
| packet advisory_classification | `advisory` |
| semantic posture | advisory, tier-floored at 2, source-linked |
| no semantic→answer bypass | synthesis agent has no hybrid-broker reference |

## Integration proof — `research-packet proof` (exit 0, proof_passed=true)

| check | result |
|---|---|
| route is research_packet_only | true |
| semantic context in packet | true (semantic_count=3) |
| packet advisory | true |
| returns packet, not answer | true |
| packet receipt persisted metadata-only + guard-clean | true |
| synthesis has no semantic path (no bypass) | true |
| excluded family fail-closed | true |
| raw query not emitted | true |

## Real HuggingFace semantic-packet smoke (`BAAI/bge-small-en-v1.5`)

A real `bge-small` hybrid retrieval routed **3 advisory semantic items** (+ 3 deterministic) into a
**tier-2 advisory** research packet with `synthesis_performed=false` and `assembles_final_answer=false`.
Captured at `validation-outputs-prompt-22/real-huggingface-research-packet-smoke.json`. Automated
equivalent: `tests/test_phase_09_research_packet_integration.py::test_semantic_packet_real_huggingface_smoke`
(`integration`).

## Operator DB outcome

`research-packet build` against the operator DB → `status='ok'`, `route='research_packet_only'`,
`synthesis_performed=false`, 408 deterministic / 0 semantic (no applied vector index → semantic skipped,
honest); `emit_receipt` defaulted False → **persists nothing**. `second_brain_research_packets` row count
unchanged; schema 38; operator DB data unmutated.

## Validation matrix

- `python -m compileall src tests` → exit 0
- `ruff check .` → All checks passed!
- `mypy src` → Success: no issues found in **290** source files
- `pytest -m "not live and not integration and not manual"` → **3159 passed, 0 failed, 5 deselected**
- `construction-agent validate --json` → exit 0 (schema 38)
- `construction-agent data-quality table-inventory --json` → exit 0 (contract_table_count=190, 0 unmapped)
- `construction-agent data-quality no-writeback-proof --json` → exit 0
- `second-brain data-quality phase-08a-gates --json` → exit 0
- `second-brain data-quality phase-08b-gates --json` → exit 0
- `second-brain data-quality phase-08c-gates` → **SKIPPED** (mutates operator DB: ~1,299 ledger rows/call)
- `second-brain data-quality phase-08d-gates --json` → exit 0
- `second-brain mcp no-raw-access --json` → exit 0
- `second-brain mcp no-writeback --json` → exit 0
- `second-brain retrieval research-packet build "<q>" --json` → exit 0 (route-only; no synthesis; no persist)
- `second-brain retrieval research-packet build "<q>" --mode deterministic-only --json` → exit 0
- `second-brain retrieval research-packet proof --json` → exit 0 (`proof_passed=true`)
- post-CLI guard re-run (`test_repo_sensitive_scan` + `test_second_brain_no_writeback_proof`) → pass

> The prompt's exact-command list used stale MCP paths (`mcp data-quality …`); the real commands are
> `second-brain data-quality phase-08d-gates`, `second-brain mcp no-raw-access`, `second-brain mcp
> no-writeback` — all run, all exit 0. The new `second-brain retrieval research-packet` surface is
> distinct from the existing 08A `second-brain research-packet` command (both verified, no collision).

## Deferred

- Wiring the semantic research packet into the default `synthesize_answer` (A04) path — behavior change, later prompt.
- `generated_outputs` (research-packet) loader still absent. Eval sets / benchmarks / memory-quality — later prompts.
