# 61 — Phase 08A: Retrieval Policy, Context Budget, and Retrieval Broker Agent (Synthesized Prompt 04)

Status: implemented (Phase 08A Synthesized Prompt 04). Builds on records 57–60.
Deterministic, local-first, no-writeback, no new SQLite tables, no embeddings.

## Purpose

Implements the **Retrieval and Source Broker Agent (A03)** — the only path to
model-bound context. The broker reads bounded, redacted, source-linked metadata
from allowlisted local read-models, enforces a deterministic context budget,
propagates review tiers + stale/unknown/conflict warnings, derives V25 relationship
runtime labels **without rewriting V25 records**, denies raw SQL and raw source
access, and persists metadata-only retrieval receipts.

**No LlamaIndex / embeddings / vectors** — Phase 08A retrieval is deterministic
SQLite/metadata access; LlamaIndex/vector work is deferred to Phase 09 (per the
package dependency plan). **No new tables** — V26 already ships
`retrieval_query_receipts` + `retrieval_context_refs`; schema stays V26 / 141.

## Contracts + seeds

- `resources/json/retrieval_policy_contract.json` (`required_fields`, `excluded`)
  and `context_budget_contract.json` (`required_fields`) — installed + registered in
  `second_brain/contracts.py`.
- `resources/config/phase_08a_retrieval_policy.seed.yaml` (approved/excluded source
  families; review_tier_required; research_packet_required_for) — verbatim from package.
- `resources/config/phase_08a_context_budget.seed.yaml` (max_context_chars 24000,
  max_item_chars 1800, tier_priority, deterministic_truncation, truncation_order,
  degradation_behavior). Repo-truth reconciliation: the seed carries the contract's
  exact required-field names (`deterministic_truncation`/`degradation_behavior`)
  rather than the package seed's `truncation`/`degradation_modes` keys.

## Code (`construction/second_brain/retrieval/`, strict-mypy)

- `models.py` — `RetrievalItem` (source_family, source_ref, record_type, record_ref,
  project_key, confidence_class, review_tier 1/2/3, review_status, review_required,
  relationship_state, evidence_ref, stale_unknown_flags, conflict_flags,
  content_excerpt_redacted, allowed_for_model_context) with a forbidden-raw-field
  validator; `RetrievalEnvelope` with `to_context_envelope()` into the adapter's
  `ContextEnvelope` (most-restrictive tier; quality from item count + truncation).
- `policy.py` — `ALLOWLISTED_SOURCE_FAMILIES` / `EXCLUDED_FAMILIES`; contract + seed
  loaders; `validate_retrieval_policy` (allowlist ∩ excluded = ∅; approved families
  covered; budget satisfies its contract); `derive_relationship_state` (8 runtime
  labels from V25 fields, read-only); `apply_context_budget` (deterministic staged
  sort: tier → recency → confidence → source_ref; per-item + total char caps;
  truncated + degradation_mode).
- `readers.py` — allowlisted per-family readers (relationships, evidence trails,
  issue history via `ConstructionStore.list_*`; risk digest, aging exposure,
  accepted long-term memory via fixed bounded SELECTs over hardcoded safe columns).
  A row's `review_required` forces Tier 3 (mandatory review). Families without a read
  model (meeting_prep_brief_sections, review_controlled_correspondence_context,
  approved_obsidian_generated_outputs) yield no items → broker coverage warning
  (graceful, never fabricated).
- `broker.py` — `RetrievalBroker.retrieve()` (deny excluded/unknown families → run
  readers → budget truncation → warnings/tier distribution/degradation → persist
  receipt); `write_retrieval_receipt()` (insert `retrieval_query_receipts` +
  `retrieval_context_refs`, mode `dry_run`, query_hash, counts only, guard cols 0);
  `build_retrieval_broker_agent_proof()` (synthetic tiers 1/2/3, deterministic,
  DB-independent).

## Guardrails

- **No raw source access / no arbitrary SQL** — readers select only hardcoded safe
  columns from allowlisted tables; no `*`, no dynamic/model-generated SQL; the
  envelope's forbidden-field validator rejects raw reference fields.
- **Excluded families denied** — `EXCLUDED_FAMILIES` (raw email/doc/calendar bodies,
  prompts/responses, signed/download URLs, secrets) are refused with a coverage
  warning.
- **Tier 3 visible but not concluded** — review-required items keep
  `review_status="review_required"`; never auto-accepted as fact.
- **V25 not rewritten** — relationship runtime labels are derived read-only; the
  broker issues zero UPDATE/DELETE on V25 tables (proven in tests).
- **Receipts metadata-only** — `retrieval_query_receipts` + `retrieval_context_refs`
  store hashes/counts/enums; all ten `CHECK(col=0)` guard columns stay 0.

## Out of scope (later prompts)
- LlamaIndex / embeddings / vector retrieval → Phase 09.
- `interactive_query` contract + query/chat/brief CLI + orchestrator wiring →
  Prompts 06/10/13. The broker is internal (A03); no standalone CLI this prompt.
- 08A no-writeback proof arm / agent persistence tables (V27) → owning prompts.
