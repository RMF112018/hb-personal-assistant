# Phase 08A — Prompt 07: Retrieval Orchestrator + Research Packet Agent — Run Proof

Pre-synthesis context-quality gate. The Research Packet Agent (A02) assesses source
coverage, stale/unknowns, conflicts, review-tier density, accepted memory, and open
questions; the Retrieval Orchestrator (A01) requires a packet for complex/daily-brief
paths and gates synthesis so insufficient context degrades or blocks — never overstates.

## Repo-truth preflight

- Baseline `git rev-parse HEAD`: `d9c61d3` (Prompt 06 HEAD).
- Package repo-truth baseline cited by the prompt: `c2656e1c9606662d7e6d86ef80f5715540216912`.
- Schema head **V26** (unchanged); contract table count **141** (unchanged).
- No migration — V26 already ships `second_brain_research_packets` (+
  `second_brain_evaluation_runs`, `research_packet_id` on `retrieval_query_receipts` /
  `daily_brief_runs`).
- The repo `research_packet_contract.json` (Prompt 02) is authoritative: compact,
  V26-column-aligned required_fields; 3-value degradation (`none/graceful_degraded/
  blocked`); `context_quality_classes` (`sufficient/partial/insufficient`).

## Files changed

Created:
- `resources/config/phase_08a_research_packet_policy.seed.yaml`
- `src/hb_assistant/construction/second_brain/research/{__init__,models,policy,packet,orchestrator,store}.py`
- `tests/test_research_packet_policy.py`, `tests/test_research_packet.py`,
  `tests/test_retrieval_orchestrator.py`, `tests/test_second_brain_research_packet_cli.py`
- `docs/architecture/64-phase-08a-retrieval-orchestrator-and-research-packet.md`
- `docs/evidence/.../research-packet-agent-proof.json`, `.../retrieval-orchestrator-proof.json`,
  `.../07-retrieval-orchestrator-and-research-packet-proof.md`

Modified:
- `src/hb_assistant/construction/second_brain/__init__.py` (research re-exports)
- `src/hb_assistant/cli/second_brain.py` (`research-packet build` subgroup)

No contract registration / `test_phase_08a_contracts` change (research_packet_contract
already registered + tested in Prompt 02). No `migrator.py` / `safety.py` change.

## Validation commands + results

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in 220 source files |
| `pytest tests/test_research_packet_policy.py tests/test_research_packet.py tests/test_retrieval_orchestrator.py tests/test_second_brain_research_packet_cli.py` | 0 | 26 new tests passed |
| `pytest -m "not live and not integration and not manual"` | 0 | full suite green |
| `construction-agent validate --json` | 0 | summary 4/4 passed, ok=true |
| `construction-agent data-quality table-inventory --json` | 0 | schema_version=26, contract_table_count=141 |
| `construction-agent data-quality no-writeback-proof --json` | 0 | proof_passed=true (unchanged) |
| `second-brain research-packet build --packet-type interactive_query --json` | 0 | requires=True, ok=True, allowed=True, degr=graceful_degraded, cqc=partial |
| `second-brain research-packet build --packet-type daily_brief --json` | 0 | type=daily_brief, requires=True |
| `second-brain research-packet build --packet-type bogus --json` | 2 | error=invalid_packet_type |

## Evidence proofs

- `research-packet-agent-proof.json` → `proof_passed: true`: seeded packet carries the
  contract required_fields, computes coverage/tier/stale/conflict, surfaces open
  questions + accepted-memory refs; receipt persisted with guard columns 0; empty DB →
  `degradation_mode=blocked`, `context_quality_class=insufficient`, `status=blocked`;
  no raw content.
- `retrieval-orchestrator-proof.json` → `proof_passed: true`: packet built for both
  daily_brief + interactive_query; both paths require a packet; insufficient context →
  `synthesis_allowed=False` + `research_packet_ok=False` + `synthesis_blocked` warning
  (degrade, not overstate); no raw content.

## Guardrail proof points

- **Synthesis requires a packet**: orchestrator builds a packet for required-for paths;
  `synthesis_allowed = research_packet_ok = degradation_mode != "blocked"`.
- **Insufficient context degrades/blocks, never overstates**: empty/incomplete-ref
  context scores `blocked` + `insufficient`; synthesis disallowed with explicit warnings
  (`test_empty_context_blocks_not_overstates`, `test_insufficient_context_blocks_synthesis`).
- **No raw content**: packet + assessment reuse RetrievalItem-derived metadata;
  `accepted_memory_refs` validator rejects forbidden field names; tests scan serialized
  output.
- **Source refs present**: every retrieved item carries `source_family/source_ref`;
  coverage + completeness computed; tier-3 items surfaced as open questions, never concluded.
- **Receipts metadata-only**: `second_brain_research_packets` rows carry counts/classes/
  redacted summary + warning codes; guard CHECK columns all 0; `review_status` pending_review.
- **Dry-run default**: `--no-emit-receipt` (default) writes nothing locally (retrieval
  receipt gated by `emit_receipt` too); `--emit-receipt` persists linked receipts.
- **V25 read-only**: `test_v25_rows_unchanged_after_packet` confirms no writeback.

## Reconciliations / known limitations

- Persisted packet = compact V26 receipt (contract-aligned). Rich assessment (coverage
  detail, open questions, memory refs) is returned, not persisted raw — repo truth over
  the package's fuller proposed SQL. `packet_type` is a model/CLI field, not a V26 column.
- Two degradation vocabularies reconciled: 5-value broker recommendation → 3-value packet
  `degradation_mode`.
- `min_source_coverage` (0.5) is repo-authored (the package seed specifies tier-3/stale
  densities + ref completeness but no numeric coverage floor).
- Output Evaluation Agent (A05) + `second_brain_evaluation_runs` writes, interactive
  query/synthesis (08), daily brief (13), memory curation (10–12) remain deferred.

## Next prompt readiness

The orchestrator emits `research_packet_ok` / `synthesis_allowed` for **Prompt 08**
(interactive query / answer synthesis), which will pass `research_packet_ok` into the
`reasoning.ContextEnvelope` gate and run the Output Evaluation Agent (A05). The
`daily_brief` packet path is ready for **Prompt 13**. Schema stays V26 / 141; no-writeback
proof unchanged; the 08A no-writeback proof arm (now covering research-packet/retrieval/
query-tool tables) remains deferred to its owning prompt (~15).
