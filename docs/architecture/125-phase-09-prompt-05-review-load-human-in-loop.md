# 125 — Phase 09 Prompt 05: Review-Load Mart & Human-In-Loop Promotion Gate (gap G-03)

**Status:** Preflight remediation (Prompt 05 — review-load mart; fail-closed promotion gate).
**Schema:** V37 (unchanged — derived read model, no new schema). **Version:** 1.3.0. **HEAD:** `23e6d87`.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/05-review-load-and-human-in-loop.md` (+ `.json`, `review-tier-preservation-proof.json`).
**Builds on:** records 120–124 (Prompts 00–04), and the Prompt 02 append-only-ledger finding (record 122).

---

## 1. Purpose

Resolve gap G-03 — "review queue ~66,466 items while review_not_performed=true." Build a deterministic
**read-only review-load triage mart** that counts review load by **distinct** review item, classify
high-impact blockers, and enforce a **fail-closed review-required promotion gate** that caps unresolved /
high-impact / review-required content from promotion into an approved source manifest. Preflight boundary
unchanged: no LlamaIndex / embeddings / vector / semantic-retrieval code.

## 2. The reframe (distinct vs raw)

`second_brain_financial_review_required_items` is an append-only per-run ledger (record 122). The mart
de-duplicates it by natural key (`project_key, trigger_category, source_ref, amount_ref`): **109,284 raw
rows across 118 routing runs → 804 distinct items**. Across all review-bearing tables the burden is
**2,733 distinct review items** (not ~111k / ~66k): financial 804, relationship-candidates 1,880, email 22,
construction 26, document 1, memory 0. `review_not_performed=true` (0 human-review decisions).

## 3. Design (no new schema)

`construction/second_brain/review_load_mart.py` (read-only over any DB):
- `build_review_load_mart` — per-table distinct counts, append-only-ledger detection, impact
  classification (reuse `risk_digest_builder._risk_category` + 8 `HIGH_IMPACT_CATEGORIES`), `by_review_tier`,
  unresolved, `review_not_performed` posture. Counts/enums/categories only.
- `evaluate_review_promotion_gate` — **fail-closed**: blocked if unresolved / high-impact / review-required
  / unknown; under `review_not_performed` promotable = 0. Mirrors the `cross_source_substrate.promote`
  `if review_required: skip` pattern.
- `build_review_load_proof` — wraps mart + gate + a no-raw scan into a read-only proof.

Exposed via a read-only CLI command `second-brain data-quality review-load --json`
(`data_quality_app`). 5 tests (reframe / fail-closed gate / proof+raw-clean / category set / stale-schema).

## 4. Guardrails & stop conditions

Read-only operator-DB access (`mode=ro`; verified unmutated); counts/enums/categories only — no raw content,
tokens, URLs, PEMs, arbitrary SQL; no external writeback; **advisory only — impact classification is for
review routing, never a final determination**; review tier / confidence / source refs preserved. The
fail-closed gate yields **promotable=0 / unresolved_high_impact_promotable=0** — the stop condition
("unresolved high-impact review items entering an approved source manifest") cannot be hit. No stop
condition triggered.
