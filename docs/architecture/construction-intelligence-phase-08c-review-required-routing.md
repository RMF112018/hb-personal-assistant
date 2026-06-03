# Phase 08C — Review-Required Financial Signal Routing

Design record for the deterministic routing of sensitive/ambiguous financial signals into
review items. Advisory-only, model-free, local-first. Repo code, tests, and evidence are
authoritative.

## Purpose

Phase 08C normalizes Procore/M365 financial facts and tags readiness, but it must **never**
make financial determinations. When a signal is ambiguous, missing context, inconsistent, or
would otherwise require a determination, the system routes it to a human review tier instead of
resolving it. This component is that router.

## Policy (load + enforce)

Seed: `resources/config/phase_08c_review_required_financial_policy.seed.yaml`.

- `review_tiers`: `none, operator_review, financial_review, executive_review, legal_contract_review`.
- `triggers`: the seven reason codes below.
- `tier_by_trigger` / `confidence_by_trigger`: deterministic, policy-driven maps consumed by
  routing. The seed is authoritative; `resolve_tier_and_confidence()` falls back to module
  defaults only when a map key is absent, and validates the resolved tier against `review_tiers`.

`load_review_policy()` enforces posture before routing: it refuses to run unless
`advisory_only_required` is true and external writeback / financial determination / raw financial
payloads are all disallowed.

## Triggers → reason codes → tier / confidence

| Signal | Trigger (reason code) | Review tier | Confidence | Source |
| --- | --- | --- | --- | --- |
| Parse ambiguity | `amount_parse_ambiguous_or_rejected` | operator_review | low | `amount_facts_normalized.parse_status ∈ {ambiguous, rejected, review_required}` |
| Missing context | `missing_source_field_path` | operator_review | medium | `amount_facts_normalized.source_field_path` empty |
| Inconsistent/missing currency | `missing_or_inconsistent_currency` | financial_review | medium | `amount_facts_normalized.currency_status ∈ {missing, inconsistent, ambiguous}` |
| Missing WBS/cost-code | `missing_wbs_cost_code_or_line_item_type` | operator_review | medium | `procore_financial_*` line-item tables missing wbs/cost/type |
| Relationship ambiguity | `relationship_ambiguity` | financial_review | low | `source_coverage_snapshots.relationship_key_count = 0` |
| Source staleness / fail-closed | `fail_closed_required_source` | financial_review | high | `parse_status = stale` and `coverage_status = fail_closed` |
| Attempted determination | `determination_attempt` | legal_contract_review | high | `parse_status = conflicting` (reconciliation refused) |

`confidence_label` is the advisory quality of the *routing signal* — not certainty of any
financial outcome.

## Persistence (V36)

Review items land in `second_brain_financial_review_required_items` (V35) with a new additive
column added by **V36**: `confidence_label TEXT`. The existing columns already supply the rest of
the required shape — `trigger_category` is the reason code, `source_ref`/`amount_ref` are
metadata-only references, `review_tier` is the tier, and the 14 `*_persisted` / `*_performed`
guard columns (all CHECK-pinned: `advisory_only=1`, determinations/payments/claims/writeback/raw
all `0`) are unchanged.

`route_to_review()` is the single sanctioned insert path; `run_review_required_routing()` opens one
self-contained run (own `run_id` + `second_brain_financial_readiness_agent_runs` receipt), so each
run is isolated and does not duplicate the inline routing performed by `run_financial_completeness`.

## Evidence

`build_financial_review_required_proof()` runs routing, aggregates by trigger/tier/confidence, and
writes `financial-review-required-proof.md` (+ `.json`) under
`docs/evidence/construction-intelligence-phase-08c-financial-readiness/`. Both artifacts pass a
redaction scan (tokens, PEMs, JWTs, URLs, signed-url markers, bare emails) before they are written;
a match is a hard stop. CLI surface: `hb-assistant second-brain financial review-items --json`
(read-only externally; local SQLite + evidence writes only).

## Files

- `src/hb_assistant/store/migrator.py` — `V36_STATEMENTS`, `LATEST_SCHEMA_VERSION = 36`.
- `resources/config/phase_08c_review_required_financial_policy.seed.yaml` — tier/confidence maps.
- `src/hb_assistant/construction/second_brain/financial_review_routing.py` — router + proof.
- `src/hb_assistant/construction/second_brain/financial_completeness.py` — `resolve_tier_and_confidence()`,
  `route_to_review()` confidence persistence.
- `src/hb_assistant/cli/second_brain.py` — `financial review-items` command.
- `tests/test_phase_08c_review_required_routing.py` — schema, all-seven-category routing, guards,
  isolation, redaction-clean proof.
