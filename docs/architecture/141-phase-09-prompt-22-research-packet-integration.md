# 141 — Phase 09 Prompt 22: Research Packet Integration

**Status:** Implementation — semantic retrieval context routed through Research Packet generation only; read-only, fail-closed, no answer assembly.
**Schema:** V38 (unchanged; reuses `second_brain_research_packets`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `660faa6`, Prompt 21 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/22-research-packet-integration.md` (+ `.json`, `research-packet-integration-proof.{json,md}`, `validation-outputs-prompt-22/`).
**Builds on:** records 139 (hybrid broker) + 140 (metadata filter); reuses the Research Packet Agent (A02) `build_research_packet_from_envelope`, `RetrievalEnvelope`/`RetrievalItem`, and `_assert_no_raw`.

---

## 1. Purpose

Establish the sanctioned (and only) route for semantic (vector) retrieval context to enter answer
generation: build the hybrid broker's merged `RetrievalEnvelope` (deterministic authoritative + advisory
semantic) and route it through `build_research_packet_from_envelope`, producing a metadata-only
`ResearchPacket` (advisory) — never a final answer. Semantic results can never assemble an answer outside
the Research Packet / Evaluation layers.

## 2. Design

### Expose the hybrid envelope (DRY refactor)
`build_hybrid_retrieval` (Prompt 20/21) returned only a metadata-only summary dict; the merged items were
discarded. The deterministic+semantic merge is extracted into a private `_collect_hybrid`; the summary
builder keeps byte-for-byte identical output (Prompt 20/21 tests pass), and a new `build_hybrid_envelope`
returns the merged `RetrievalEnvelope` (+ meta) so the Research Packet layer can consume it. Semantic
items remain advisory (`RetrievalItem` tier-floored at 2, source-linked).

### The route is a bridge that returns a packet, never an answer
`research/semantic_packet.build_semantic_research_packet` builds the hybrid envelope and routes it through
`build_research_packet_from_envelope` (A02). It returns a metadata-only summary with
`route='research_packet_only'`, `synthesis_performed=false`, `assembles_final_answer=false`, plus the
packet's advisory metadata (advisory_classification, context_quality_class, degradation_mode, review tier,
counts, coverage warnings). It **never** calls the synthesis adapter — semantic context becomes research,
not an answer. The module imports `build_hybrid_envelope` (retrieval) + `build_research_packet_from_envelope`
(research) one-directionally (no cycle).

### No bypass; synthesis untouched
`synthesize_answer` (A04) still calls only the deterministic broker — wiring the semantic packet into the
default synthesis path is deferred. The proof asserts the synthesis agent source has **no** reference to
the hybrid broker, so there is no semantic→answer path except through the Research Packet.

### Read-only, fail-closed, metadata-only
The bridge defaults `emit_receipt=False` (persists nothing to the operator DB); receipt persistence
(a metadata-only, guard-clean `second_brain_research_packets` row) is exercised in the proof on a temp DB.
The raw query is never emitted (only `query_hash`); review tier / confidence / source refs / freshness /
coverage warnings are preserved. Fail-closed on missing policy, stale schema (V38-gated via the hybrid
envelope), or an explicitly requested excluded source family.

## 3. Contract & seed

`phase_09_research_packet_integration_contract.json` (+ `.seed.yaml`):
`semantic_context_route='research_packet_only'`, `semantic_advisory_only=true`,
`no_direct_answer_assembly=true`, allowed packet types, forbidden-emitted fields (raw query/excerpt/answer/
embedding/vector), and global requirements (preserve review tier/confidence/source refs/freshness/coverage;
no semantic bypass; fail-closed). Registered as `research_packet_integration_contract`.

## 4. CLI

`second-brain retrieval research-packet build "<q>" [--project] [--source a,b] [--max-review-tier]
[--min-confidence] [--mode] | proof`. Distinct from the existing 08A top-level `second-brain
research-packet` command (no collision — separate Typer + guardrails). `build` is read-only (no persist).

## 5. Validation

`compileall`/`ruff`/`mypy` (290 files) clean; `pytest -m "not live and not integration and not manual"`
= 3159 passed, 0 failed (incl. the pre-existing `research-packet` CLI tests + Prompt 20/21 tests after the
`_collect_hybrid` refactor). The integration proof passes (route-only; semantic context in the packet;
packet advisory; returns a packet not an answer; persisted receipt metadata-only + guard-clean; synthesis
has no semantic path; excluded family fail-closed; raw query not emitted). A real `bge-small`
semantic-packet smoke routed 3 advisory semantic items into a tier-2 advisory packet without synthesizing.
Operator DB unmutated (research_packets unchanged; schema 38). Full matrix in the evidence bundle.

## 6. Deferred

Wiring the semantic research packet into the default `synthesize_answer` (A04) path; the `generated_outputs`
loader; eval sets / benchmarks / memory-quality review — later Phase 09 prompts.
