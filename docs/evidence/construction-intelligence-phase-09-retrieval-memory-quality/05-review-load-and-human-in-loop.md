# Phase 09 — Prompt 05: Review Load & Human-In-Loop Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/05-review-load-and-human-in-loop.md`
**Machine-readable companions:** `05-review-load-and-human-in-loop.json`, `review-tier-preservation-proof.json`
**Captured outputs:** `validation-outputs-prompt-05/` (incl. `review-load-cli.json`)
**Gap:** G-03 (review queue ~66,466 items while review_not_performed=true)
**Audit date:** 2026-06-04 · **HEAD:** `23e6d87` · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Deterministic **read-only derived mart** over the existing review-bearing tables (**no new schema**) + a **fail-closed review-required promotion gate**, plus a read-only CLI command. Reads the **operator DB read-only** (verified unmutated). **No LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-03 resolution: build a review-triage mart that counts review load by **distinct** review item,
classifies high-impact blockers, surfaces the `review_not_performed` posture, and enforces a fail-closed
promotion gate that **caps unresolved / high-impact / review-required content from promotion** into an
approved source manifest. The mart is a derived read model (06B/07A pattern, no schema), computed
read-only over the operator DB; the impact classifier and the 8 high-impact categories are **reused** from
the risk-digest (`_risk_category` + `review_required_categories`). Impact classification is **advisory**
(for review routing) — never a final determination.

---

## 2. The G-03 reframe — distinct review items, not raw rows

The attached audit's headline ("66,466 review items, review_not_performed=true") conflates raw rows with
distinct items. `second_brain_financial_review_required_items` is an **append-only per-run ledger**
(Prompt 02 finding). The mart de-duplicates it by natural key:

| Review source (table) | Raw rows | Distinct items | Append-only ledger | Unresolved | High-impact |
|---|---|---|---|---|---|
| `second_brain_financial_review_required_items` | 109,284 | **804** (118 runs) | yes | 109,284 | 782 (cost_impact) |
| `cross_source_relationship_candidates` | 1,880 | 1,880 | no | 159 | 460 |
| `email_review_queue` | 22 | 22 | no | 22 | 12 (contractual/claim) |
| `construction_review_queue` | 26 | 26 | no | 26 | 0 |
| `construction_document_intelligence_previews` | 1 | 1 | no | 1 | 0 |
| `memory_update_candidates` | 0 | 0 | no | 0 | 0 |
| **Total** | **111,213** | **2,733** | — | 109,492 | **1,254** |

**The true distinct review burden is 2,733 items (not ~111k / ~66k)** — dominated by 804 distinct
financial items (re-logged across 118 routing runs) + 1,880 relationship candidates. `review_not_performed`
is confirmed (`human_review_decisions = 0`: no `memory_update_reviews`, no resolved construction/email
items).

---

## 3. Fail-closed review-required promotion gate

`evaluate_review_promotion_gate` is **fail-closed**: an item is blocked from promotion (into an approved
source manifest) if it is unresolved, high-impact, review-required, or unknown/missing-policy. Under
`review_not_performed=true`, **promotable = 0** — nothing promotes until a human reviews.

Live result over the operator DB:

```
blocked_from_promotion         = 2733   (all distinct review items)
promotable_review_ready        = 0      (review_not_performed → fail-closed)
unresolved_high_impact_promotable = 0   (the gate never promotes these — stop-condition-clear)
gate_fail_closed_ok            = true
```

This directly satisfies the stop condition ("unresolved high-impact review items entering approved source
manifests"): **zero** such items can promote.

---

## 4. Reusable helper + CLI + tests (committed code)

`src/hb_assistant/construction/second_brain/review_load_mart.py` — `build_review_load_mart`,
`evaluate_review_promotion_gate`, `build_review_load_proof` (read-only, `mode=ro`; counts/enums/categories
only; reuses `risk_digest_builder._risk_category` + the 8 `HIGH_IMPACT_CATEGORIES`). Fully typed; `ruff` +
`mypy src` clean (275 files).

`src/hb_assistant/cli/second_brain.py` — a new read-only command
`hb-assistant second-brain data-quality review-load --json` (emits the mart + gate; exit 0 on pass).

`tests/test_phase_09_review_load_mart.py` (5 tests): distinct-ledger reframe (raw 4 → distinct 2) + claim
high-impact classification; fail-closed gate (promotable 0 under review_not_performed); proof passes +
raw-clean; the 8-category set; stale-schema graceful.

**`review_tier` / impact-category preservation:** `review-tier-preservation-proof.json` records the
per-table `by_review_tier` (e.g. financial `{financial_review, operator_review}`) and `by_impact_category`
breakdowns — review tier, confidence/impact class, and source family are preserved end-to-end (counts/enums
only, no raw content).

---

## 5. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-05/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **275** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3025 + 5 new = **3030 passed**) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a/08b/08c/08d-gates --json` † | 0 | `ok=true` |
| `second-brain mcp no-raw-access / no-writeback --json` † | 0 | `proof_passed=true` |
| **`second-brain data-quality review-load --json`** (new) | 0 | `proof_passed=true`; 2733 distinct; promotable 0 |

† Same CLI-spelling resolutions as Prompts 00–04. Evidence re-stamps from the proof builders were reverted
to keep the commit surgical. **Disclosed:** `phase-08c-gates` (the Prompt-02 append-only ledger) appends a
routing run per call — run once for the matrix; the mart's distinct-item logic is robust to this growth
(distinct 804 regardless of run count). The operator DB review tables were **unmutated** by the mart
(read-only `mode=ro`; before == after).

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — mart emits counts/enums/categories only; no-raw scan clean; no writes |
| External writeback | No — read-only `mode=ro`; operator DB unmutated |
| Missing no-raw / no-writeback proof | No — `build_review_load_proof` + MCP/legacy proofs pass |
| **Unresolved high-impact review items entering an approved source manifest** | **No — the fail-closed gate blocks all (promotable=0); `unresolved_high_impact_promotable=0`** |
| Unapproved Obsidian notes indexed | N/A — no indexing |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no semantic retrieval exists |

No stop condition triggered.

---

## 7. Verdict

G-03 **resolved**: the "66,466 review items" headline is reframed to **2,733 distinct** review items (804
distinct financial across 118 ledger runs + 1,880 relationship candidates + small construction/email/doc),
classified by impact (1,254 high-impact), with `review_not_performed=true`. The fail-closed promotion gate
**blocks all of them** (promotable=0; no unresolved high-impact can promote). A reusable read-only mart +
gate helper, a read-only CLI command, and 5 tests are committed (suite green). No stop condition triggered.
**Proceed to Phase 09 Prompt 06** (financial data completeness preflight).
