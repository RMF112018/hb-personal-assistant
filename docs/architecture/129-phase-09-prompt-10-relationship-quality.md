# 129 — Phase 09 Prompt 10: Cross-Source Relationship Quality Mart (gap G-08)

**Status:** Preflight remediation (Prompt 10 — read-only advisory relationship-quality mart; no schema).
**Schema:** V37 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `e6d7579`, Prompt 09 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/10-relationship-quality-preflight.md` (+ `.json`).
**Builds on:** records 120–128 (Prompts 00–09); the V25 cross-source relationship substrate (Phase 07D).

---

## 1. Purpose

Resolve gap G-08 — the cross-source relationship substrate is **populated** (1,880 candidates / 1,671
promoted / 1,880 evidence trails) but had **no quality mart** (classified at Prompt 02). Build a
read-only quality profile — **link ratios**, **confidence distribution**, and **orphan / duplicate**
counts — so the relationship graph's health is measurable before semantic retrieval consumes it.
Preflight boundary unchanged: no LlamaIndex / embeddings / vector / semantic-retrieval code; **no
schema migration** (V38 stays reserved for the real build).

## 2. Mart signals (read-only, advisory, no determination)

`build_relationship_quality_mart` (read-only `?mode=ro`) over `cross_source_relationship_candidates`,
`cross_source_relationships`, `source_evidence_trails`:
- **Link ratios** — promotion share, review-required share, deterministic / model_proposed share,
  human-promoted share, and the candidates→relationships promotion rate (live: **0.889**).
- **Confidence** — counts per the 7-value `confidence_class` enum + `confidence_score` min/avg/max
  spread (live candidates: deterministic 1,671 / strong_heuristic 51 / weak_heuristic 158).
- **Orphan counts** (within-schema, reachability-honest): a relationship is a true evidence-orphan
  only if it reaches a trail by **neither** its own `evidence_trail_id` **nor** via
  `candidate_id → candidate.evidence_trail_id`; plus promoted edges lacking a candidate parent and
  candidates lacking a trail. Live `orphan_total=0`. The separate
  `relationship_direct_evidence_trail_absent=1,671` is reported as **informational denormalization**
  (the 07D promotion path didn't copy `evidence_trail_id` forward — still traceable via candidate),
  deliberately **not** an orphan or a warning.
- **Duplicate / multi-edge** — one source→target pair under >1 `relationship_type` (exact duplicate
  edges are blocked by the UNIQUE edge constraint). Live: **46** multi-edge pairs (advisory warning).
- **Preserved**: `sensitive_high_impact` + `review_required` counts, a `_risk_category`-based
  high-impact `relationship_type` tally, freshness (stale tallies), and source-coverage warnings.

## 3. Reusable helper + CLI + tests

`construction/second_brain/relationship_quality_mart.py` — `build_relationship_quality_mart` +
`build_relationship_quality_proof` (read-only; guard-column attestation sums the 8 `CHECK(=0)` guard
columns on each table to 0; `_FORBIDDEN` raw scan over the JSON/text columns reports `table.column`
only). Reuses `_risk_category` + `HIGH_IMPACT_CATEGORIES` from the review-load mart / risk digest.

`cli/second_brain.py` — read-only `second-brain data-quality relationship-quality --json [--project]`
(mirrors the `review-load` command + `_emit_08c`; exit 0/3).

`tests/test_phase_09_relationship_quality_mart.py` (5): normal link-ratios / guard-clean; empty
substrate fail-soft; stale-schema graceful; no-raw injection fail-closed (value never echoed, DB
unchanged); orphan + duplicate signals (advisory, do not fail the proof).

## 4. Guardrails & stop conditions

Read-only verifier; metadata-only (counts / ratios / enums); no Graph/Procore/external writeback; no
raw content/prompts/responses/tokens/URLs/PEMs/arbitrary SQL; **no automatic promotion**; no final
financial/legal/contractual/claim/entitlement/payment/schedule/safety determination — orphan,
duplicate, and confidence outputs are advisory quality signals + warnings only. Operator DB verified
unmutated (relationship-table counts before == after). No stop condition triggered.
