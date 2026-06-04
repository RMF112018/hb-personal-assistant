# 130 — Phase 09 Prompt 11: Retrieval Corpus Balance & Source Coverage (gap G-10)

**Status:** Preflight remediation (Prompt 11 — read-only corpus-balance gate + source-family coverage proof; no schema).
**Schema:** V37 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `1feb8d1`, Prompt 10 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/11-corpus-balance-preflight.md` (+ `.json`).
**Builds on:** records 120–129 (Prompts 00–10); the Phase 08A Retrieval Broker allowlist (`retrieval/policy.py`, `retrieval/readers.py`).

---

## 1. Purpose

Resolve gap G-10 — Prompt 02 classified the corpus as `confirmed_imbalance` (procore/financial-heavy
at the raw-ingestion level; generated-output / memory families empty). Build a read-only
**corpus-balance gate** + **source-family coverage proof** over the **retrieval corpus** (the families
the Retrieval Broker may actually read), so balance is measurable before semantic retrieval runs.
Preflight boundary unchanged: no LlamaIndex / embeddings / vector / semantic-retrieval code; **no
schema migration** (V38 stays reserved for the real build).

## 2. Key finding — raw-ingestion vs retrieval-corpus balance

The G-10 "procore/financial-heavy" claim was measured on the **raw ingestion** tables (procore_live_
records 30,035 / amount_facts 85,521 / … vs brief/research/mcp/memory = 0). Measured at the
**retrieval-corpus** level — the post-read-model families the broker reads — the picture is more
precise: **5 of 7** reader-backed families are covered and reasonably distributed (evidence-trails
1,880 / aging-exposure 1,780 / relationships 1,671 / issue-history 598 / risk-digest 44; dominant
share **0.31**), and the real gap is the **2 empty families** — `approved_obsidian_generated_outputs`
and `accepted_long_term_memory` (owned by sibling Prompts 09 and 07). The gate therefore reports
**`imbalanced`** (`too_few_covered_families:5<7`), the honest preflight readiness signal, while the
per-family coverage proof gives the exact distribution.

## 3. Mart + gate + proof (read-only, advisory, no determination)

`construction/second_brain/corpus_balance_mart.py`:
- **Source-family universe** reuses `ALLOWLISTED_SOURCE_FAMILIES` + `EXCLUDED_FAMILIES` from
  `retrieval/policy.py` and `READER_REGISTRY` from `retrieval/readers.py` (imported, not re-listed).
  Each family maps to its read-model table; `meeting_prep_brief_sections` +
  `review_controlled_correspondence_context` are deferred-no-reader (coverage-excused → `no_read_model`
  warnings). The corpus draws only from allowlisted families — never an `EXCLUDED_FAMILIES` raw family.
- `build_corpus_balance_mart` — per-family `row_count` + `coverage_status` (covered / empty /
  deferred), per-family share, dominant family + share, covered/empty/deferred lists, and
  source-coverage warnings (`empty_family:{family}`, `no_read_model:{family}`).
- `evaluate_corpus_balance_gate` — fail-closed: `balanced` requires `covered_families >=
  min_covered_families` AND `dominant_share <= max_dominant_family_share` (policy seed
  `resources/config/phase_09_corpus_balance_policy.seed.yaml`: 7 / 0.6). Verdict
  `balanced`/`imbalanced` + blocking reasons.
- `build_corpus_balance_proof` — fail-closed policy load + mart + gate + guard-column attestation
  (the corpus tables' guard `CHECK(=0)` columns sum to 0) + a `_FORBIDDEN` raw scan over the corpus
  text/JSON columns (report `table.column` only). `proof_passed = policy_loaded ∧ schema_ok ∧
  guard_clean ∧ no_raw` — **independent** of the balance verdict (the proof validly measures an
  imbalanced corpus; `corpus_balance_ok` is reported separately, mirroring review-load).

`cli/second_brain.py` — read-only `second-brain data-quality corpus-balance --json [--project]`
(mirrors `review-load` + `_emit_08c`; exit 0/3).

`tests/test_phase_09_corpus_balance_mart.py` (5): balanced corpus passes the gate; missing-policy
fail-closed; stale-schema graceful; no-raw injection fail-closed (value never echoed, DB unchanged);
imbalanced corpus measured-not-failed (gate `imbalanced`, `proof_passed=true`).

## 4. Guardrails & stop conditions

Read-only verifier; metadata-only (counts / shares / enums); no Graph/Procore/external writeback; no
raw content/prompts/responses/tokens/URLs/PEMs/arbitrary SQL; no raw vector search; no final
financial/legal/contractual/claim/entitlement/payment/schedule/safety determination — balance /
coverage outputs are advisory signals + warnings only. Operator DB verified unmutated (corpus-table
counts before == after). No stop condition triggered.
