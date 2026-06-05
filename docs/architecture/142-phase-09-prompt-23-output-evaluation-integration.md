# 142 — Phase 09 Prompt 23: Output Evaluation Integration

**Status:** Implementation — semantic retrieval outputs routed through evaluation + unsupported-claim + source-linked checks + receipts; read-only, fail-closed, no answer assembly.
**Schema:** V38 (unchanged; reuses `source_linked_proof_runs` + `unsupported_claim_checks`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `8d711c0`, Prompt 22 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/23-output-evaluation-integration.md` (+ `.json`, `output-evaluation-integration-proof.{json,md}`, `validation-outputs-prompt-23/`).
**Builds on:** records 139–141 (hybrid broker, metadata filter, research-packet integration); reuses the A05 `build_evaluation_preview`, `AdapterResult` / `_review_status_for_tier` / `ContextEnvelope` (reasoning), `build_research_packet_from_envelope` (A02), `build_hybrid_envelope` (retrieval), and `_assert_no_raw`.

---

## 1. Purpose

Complete the semantic-retrieval doctrine boundary: route semantic retrieval **outputs** through the
Output Evaluation (A05) layer, an unsupported-claim check, and a source-linked proof, persisting
metadata-only receipts. Semantic context is evaluated for fitness but never assembles a final answer, and
every retrieved item must be a supported, source-linked claim before the context is usable.

## 2. Design

### Evaluate the context through the real A05 layer (no synthesis)
`build_semantic_output_evaluation` builds the hybrid envelope → research packet → a **non-synthesized
context `AdapterResult`** (`answer=""`, `synthesized=False`, source refs/tier/confidence from
`envelope.to_context_envelope`) → the **real** `build_evaluation_preview`. Because `synthesized=False`,
`no_tier_3_treated_as_accepted_fact` always holds and no answer is assembled — the evaluation runs over
the retrieved context, which is exactly "route semantic retrieval outputs through evaluation." The 5-value
retrieval degradation mode is mapped to the 3-value `AdapterResult` literal.

### Unsupported-claim check + source-linked proof (zero tolerance)
Over `envelope.items`, a retrieved item is a *supported, source-linked claim* iff it carries a
`source_ref` + an allowlisted (non-`EXCLUDED_FAMILIES`) `source_family`. `_source_linked_proof` and
`_unsupported_claim_check` count `checked/source_linked/unlinked` and `claim/unsupported`; any
`unsupported_count`/`unlinked_count` > 0 fails closed (`status='blocked'`/`unlinked_found`). The
`unsupported_claim_performed` guard stays 0 — the layer *detects and blocks* unsupported claims; it never
emits one. `overall_passed = evaluation.passed AND unsupported==0 AND unlinked==0`.

### Metadata-only receipts; read-only by default
`persist_evaluation_receipts` writes one `source_linked_proof_runs` row (`checked/source_linked/unlinked/
status`) + one `unsupported_claim_checks` row (`claim/unsupported/status`, linked by `run_id`), mirroring
the `vector_index` persister pattern (`_schema_ready`/`_open_ro`, guard-clean, metadata-only — all 23
`CHECK(=0)` guards 0). The CLI `run` defaults `emit_receipt=False` (no operator-DB write); persistence is
proven on a temp DB. The raw query is never emitted (only `query_hash`); no answer/excerpt is emitted.

### Fail-closed, no rewiring
Fail-closed on missing policy, stale schema (V38-gated), or an excluded source family. `synthesize_answer`
(A04) is untouched; wiring semantic output evaluation into the default synthesis path is deferred.

## 3. Contract & seed

`phase_09_output_evaluation_integration_contract.json` (+ `.seed.yaml`):
`unsupported_claim_zero_tolerance=true`, `source_linked_required=true`, run/check column allowlists, status
vocab, forbidden-emitted fields (raw query/answer/excerpt/embedding/vector), and global requirements
(preserve review tier/confidence/source refs/freshness/coverage; no semantic bypass; no answer assembly;
fail-closed). Registered as `output_evaluation_integration_contract`.

## 4. CLI

`second-brain retrieval output-eval run "<q>" [--project] [--source a,b] [--max-review-tier]
[--min-confidence] [--mode] | proof`. Unique Typer var / guardrails constant / command names (avoiding the
Prompt-22 collision class). `run` is read-only (no persist; exit 0 iff overall passes); `proof` runs the
offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (291 files) clean; `pytest -m "not live and not integration and not manual"`
= 3166 passed, 0 failed. The integration proof passes (real A05 evaluation score 1.0; 0 unsupported / 0
unlinked; guard-clean metadata-only receipts in both V38 tables; unsupported-claim detection over
synthetic items; no answer; raw query not emitted; excluded family fail-closed). A real `bge-small` smoke
routed 3 advisory semantic + 3 deterministic items through the evaluation without synthesizing. Operator
DB unmutated (both tables 0; schema 38). Full matrix in the evidence bundle.

## 6. Deferred

Default-synthesis (A04) adoption; deeper claim-level NLI / hallucination scoring (Prompts 28-29); the
broader source-linked proof matrix (Prompt 34); `generated_outputs` loader; eval sets / benchmarks /
memory-quality review — later Phase 09 prompts.
