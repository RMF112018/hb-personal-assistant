# 126 — Phase 09 Prompt 06: Advisory Financial Data-Completeness Mart (gap G-04)

**Status:** Preflight remediation (Prompt 06 — advisory financial completeness; no determination).
**Schema:** V37 (unchanged — derived read model). **Version:** 1.3.0. **HEAD:** `23e6d87`.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/06-financial-data-completeness.md` (+ `.json`).
**Builds on:** records 120–125 (Prompts 00–05).

---

## 1. Purpose

Remediate gap G-04 (currency 100% null, period ~98.7% null, WBS/cost-code orphan risk) **advisorily,
before semantic retrieval over financial outputs**. The guardrails forbid final financial determinations,
so currency fallback / period enrichment / WBS-cost-code reconciliation are delivered as **advisory
recommendations + review labels**, never assignments. Preflight boundary unchanged: no LlamaIndex /
embeddings / vector / semantic-retrieval code.

## 2. Advisory-vs-determination boundary

A read-only derived mart (`construction/second_brain/financial_completeness_advisory.py`) profiles the
financial fact tables and emits:
- **Currency:** per-project advisory recommendation — dominant source currency when present
  (`advisory_use_dominant_source_currency`), else `project_default_currency_required`. **Live finding:** no
  non-null currency exists anywhere → not data-derivable → `project_default_currency_required` (eligibility
  for an evidence-backed default = false). Never assigned.
- **Period:** `period_context_required` (source-context dependent; not derivable).
- **WBS/cost-code:** orphan/missing presence detection (no parent tables exist) →
  `wbs_cost_code_context_required`. Live: 2,887 WBS + 3,510 cost-code orphan-or-missing.

The mart **writes nothing** — no schema, no fact mutation, and **no routing into the append-only review
ledger** (record 122). Money values are never read or echoed (counts / ISO-codes / labels only). The 08C
guard columns (`financial_determination_performed` / `payment_decision_performed` /
`claim_or_entitlement_decision_performed` / `external_writeback_performed` /
`raw_financial_source_payload_persisted` = 0; `advisory_only` = 1) are re-attested clean.

## 3. Design

`build_financial_completeness_advisory(db_path)` + `build_financial_completeness_advisory_proof(db_path)`
(read-only `mode=ro`), exposed via `second-brain financial completeness-advisory --json`
(`financial_app`). 5 tests (gap profiling / dominant-currency advisory / proof advisory-clean / empty /
stale-schema).

## 4. Guardrails & stop conditions

Read-only operator-DB access (verified unmutated); counts/enums/ISO-codes/labels only — no raw amounts,
content, tokens, URLs, PEMs, arbitrary SQL; no external writeback; **no final financial/claim/entitlement/
payment determination** (advisory recommendations + review labels only); money never float/echoed; review
tier / confidence / source refs preserved. No stop condition triggered.
