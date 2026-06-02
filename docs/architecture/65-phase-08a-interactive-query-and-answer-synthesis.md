# 65 — Phase 08A: Interactive Query CLI + Answer Synthesis Agent (A04) (Synthesized Prompt 08)

Status: implemented (Phase 08A Synthesized Prompt 08). Builds on records 57–64.
Deterministic where possible, mock-first synthesis, local-first, read-only, no-writeback,
no new SQLite tables.

## Purpose

Implements source-linked, research-first interactive Q&A through the **Answer Synthesis
Agent (A04)** and a new `second-brain query` CLI. A query retrieves bounded context once,
builds a research packet (the complex-query discipline), maps the context into a
`ContextEnvelope`, runs it through the Claude adapter's pre-synthesis gate (mock by
default, offline), and returns an advisory answer with source refs, claim-strength labels,
review tiers, an evaluation preview, warnings, and advisory-vs-actionable separation.
**High-impact / Tier-3 items are visible but never presented as final conclusions.**

**No new tables / no migration** (schema stays V26 / 141). The answer is never persisted
raw; `--emit-receipt` only persists the orchestrator's packet + retrieval receipts.

## Repo-truth reconciliation

- **The adapter gate is the safety mechanism (reused verbatim).** `reasoning.py::
  ClaudeAdapter.synthesize()` blocks (degraded, no model call: `synthesized=False`,
  `review_status=review_required`, `degradation_mode=blocked`) when `research_packet_ok`
  is False, no source refs, context insufficient, **or `review_tier==3`**. `MockClaudeAdapter`
  is offline-default; live is opt-in and never auto-selected here.
- **`ContextEnvelope.research_packet_ok` was hardcoded `False`.** `RetrievalEnvelope.
  to_context_envelope` gained a `research_packet_ok` parameter (default still False), set
  by the synthesis agent from `packet.degradation_mode != "blocked"` — otherwise nothing
  ever synthesizes.
- **`interactive_query_contract` is now registered** (Prompt 08 owns it): the eight
  `required_output` fields + guardrails. Registered in `second_brain/contracts.py` +
  `test_phase_08a_contracts`.
- **`evaluation_criteria_contract` is repo-authoritative + checklist-based** (10
  `checklist_items`, score 0–1). The evaluation **preview** computes those 10 booleans
  deterministically; it is **not persisted** (the full Output Evaluation Agent A05 +
  `second_brain_evaluation_runs` writes stay deferred). No evaluation seed needed.
- **`build_research_packet_from_envelope`** was extracted from `build_research_packet` so
  the synthesis agent retrieves once and reuses the envelope for both packet + context.
- A04 was already registered; we implement its service. No git push.

## Code

- `synthesis/models.py` — `QueryResult` (the 8 `interactive_query_contract.required_output`
  fields + metadata; validator rejects forbidden raw field names in `source_refs`),
  `EvaluationPreview` (checklist + score; mirrors the evaluation contract shape).
- `synthesis/evaluation.py` — `build_evaluation_preview` (10 deterministic checklist
  booleans incl. `no_tier_3_treated_as_accepted_fact = not (review_tier==3 and
  synthesized)`, `degradation_mode_set_when_insufficient`, `no_raw_content_in_output`).
- `synthesis/agent.py` (A04) — `synthesize_answer` (broker retrieve → packet →
  `to_context_envelope(research_packet_ok=…)` → mock-first adapter → evaluation preview →
  `QueryResult`; claim_strength = strong/qualified/insufficient; advisory disposition,
  empty actionable list), `build_answer_synthesis_agent_proof`.
- `retrieval/models.py` — `to_context_envelope(research_packet_ok=…)`.
- `research/packet.py` — `build_research_packet_from_envelope` (extracted).
- `resources/json/interactive_query_contract.json` — output contract.
- `cli/second_brain.py` — `second-brain query "<question>" [--project-key]
  [--emit-receipt/--no-emit-receipt]` → `synthesize_answer`; prints the 8 required_output
  fields + `synthesized`/`mode`. Exit 0; 3 on error.

## Guardrails

Local-first; external systems read-only; no writeback; **mock-first synthesis (live never
auto-selected; not exercised by tests)**; no raw prompts/responses/bodies/URLs/secrets
emitted or persisted; **research packet required for complex queries; Tier-3 / high-impact
never presented as final conclusions** (adapter gate + `no_tier_3_treated_as_accepted_fact`
checklist); answers not persisted raw; dry-run default.

## Evidence

`interactive-query-preview.md` (a synthesized Tier-1 query + a gated Tier-3 high-impact
query) and `answer-synthesis-agent-proof.md` (`build_answer_synthesis_agent_proof`,
`proof_passed: true`).

## Deferred (later prompts)

Output Evaluation Agent (A05) + `second_brain_evaluation_runs` persistence; chat session
memory (Prompt 10); long-term memory curation (11–12); daily brief (13). The query path
emits the research-packet + evaluation-preview substrate those will reuse.
