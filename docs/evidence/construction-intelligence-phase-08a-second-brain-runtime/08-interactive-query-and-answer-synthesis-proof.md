# Phase 08A — Prompt 08: Interactive Query CLI + Answer Synthesis Agent — Run Proof

Source-linked, research-first interactive Q&A through the Answer Synthesis Agent (A04) and
a new `second-brain query` CLI. Advisory intelligence is separated from actionable
recommendations, claim strength is labeled, and Tier-3 / high-impact items are never
presented as final conclusions.

## Repo-truth preflight

- Baseline `git rev-parse HEAD`: `feed1d8` (Prompt 07 HEAD).
- Package repo-truth baseline cited by the prompt: `c2656e1c9606662d7e6d86ef80f5715540216912`.
- Schema head **V26** (unchanged); contract table count **141** (unchanged).
- No migration / no new tables. The answer is never persisted raw.

## Files changed

Created:
- `src/hb_assistant/resources/json/interactive_query_contract.json`
- `src/hb_assistant/construction/second_brain/synthesis/{__init__,models,evaluation,agent}.py`
- `tests/test_evaluation_preview.py`, `tests/test_answer_synthesis.py`, `tests/test_second_brain_query_cli.py`
- `docs/architecture/65-phase-08a-interactive-query-and-answer-synthesis.md`
- `docs/evidence/.../interactive-query-preview.md`, `.../answer-synthesis-agent-proof.md`,
  `.../08-interactive-query-and-answer-synthesis-proof.md`

Modified:
- `src/hb_assistant/construction/second_brain/retrieval/models.py` (`to_context_envelope`
  gains `research_packet_ok`)
- `src/hb_assistant/construction/second_brain/research/packet.py` +
  `research/__init__.py` (extract `build_research_packet_from_envelope`)
- `src/hb_assistant/construction/second_brain/contracts.py` (register
  `interactive_query_contract`)
- `src/hb_assistant/construction/second_brain/__init__.py` (synthesis re-exports)
- `src/hb_assistant/cli/second_brain.py` (`second-brain query`)
- `tests/test_phase_08a_contracts.py` (`interactive_query_contract` required keys)

## Validation commands + results

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in 224 source files |
| `pytest tests/test_evaluation_preview.py tests/test_answer_synthesis.py tests/test_second_brain_query_cli.py tests/test_phase_08a_contracts.py` | 0 | new tests passed |
| `pytest -m "not live and not integration and not manual"` | 0 | full suite green |
| `construction-agent validate --json` | 0 | summary 4/4 passed, ok=true |
| `construction-agent data-quality table-inventory --json` | 0 | schema_version=26, contract_table_count=141 |
| `construction-agent data-quality no-writeback-proof --json` | 0 | proof_passed=true (unchanged) |
| `second-brain query "what changed this week?" --json` | 0 | synthesized=true, mode=mock, claim_strength=qualified, tier=1, evaluation passed, all 8 required_output fields present |

## Evidence

- `interactive-query-preview.md` — a synthesized Tier-1 advisory query + a gated Tier-3
  high-impact query (empty answer, `review_required`, `blocked`, warnings).
- `answer-synthesis-agent-proof.md` — `build_answer_synthesis_agent_proof()`,
  `proof_passed: true`.

## Guardrail proof points

- **Source refs + warnings**: every `QueryResult` carries `source_refs` and `warnings`
  (`test_result_carries_all_required_output_fields`, CLI smoke).
- **High-impact not final**: Tier-3 context → adapter gate blocks synthesis
  (`synthesized=False`, empty answer, `review_required`); evaluation checklist
  `no_tier_3_treated_as_accepted_fact` holds (`test_tier3_high_impact_is_not_a_final_conclusion`).
- **Research packet required**: the synthesis agent always builds an interactive_query
  research packet; `research_packet_ok` gates the adapter.
- **Advisory vs actionable**: `disposition=advisory`, `actionable_recommendations=[]`, with
  an explicit advisory note; claim strength labeled (strong/qualified/insufficient).
- **Mock-first / no live**: adapter resolves to `MockClaudeAdapter` offline; live is never
  auto-selected and not exercised by tests.
- **No raw content**: `QueryResult.source_refs` validator + result-blob scans in tests.
- **No persistence of the answer**: dry-run default; `--emit-receipt` only writes the
  packet + retrieval receipts (metadata-only, guard columns 0).

## Reconciliations / known limitations

- Evaluation is a deterministic **preview** over the repo `evaluation_criteria_contract`
  checklist items — not persisted. The full Output Evaluation Agent (A05) +
  `second_brain_evaluation_runs` writes are deferred.
- `ContextEnvelope.research_packet_ok` threading: `to_context_envelope` gained the
  parameter (default False) so a bare envelope never implies an approved packet.
- Mock-first fallback: when the runtime config is `disabled`, the query falls back to the
  offline `MockClaudeAdapter` (safe, no external calls); live requires explicit config.

## Next prompt readiness

The query path emits the research-packet + evaluation-preview substrate for **Prompt 10**
(chat session memory) and **Prompt 13** (daily brief), and the answer-synthesis gate is
ready for the **Output Evaluation Agent (A05)** to wrap. Schema stays V26 / 141; the 08A
no-writeback proof arm remains deferred to its owning prompt (~15).
