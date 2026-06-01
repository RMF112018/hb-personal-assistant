# 51 — Phase 07D: Risk Digest

**Status:** Implemented (Phase 07D Prompt 08). Additive over schema **V25** (no migration).
**Scope:** Materialize review-controlled risk digests into `project_risk_digest_items` (shipped empty
in Prompt 02), classifying local risk indicators into the four policy `risk_source_class` values, via
a new `construction-agent risk-digest build/status` sub-app. Advisory, read-only, no raw content, no
external writeback, no auto-promotion.

## Problem

The V25 risk-digest table had no producer; the meeting-prep brief's `risk_exposure_watchlist` section
is an honest deferred placeholder pointing at it. This prompt turns the local risk-signal sources into
a bounded, source-linked, review-controlled digest.

## Design

### Engine — `construction/risk_digest/risk_digest_builder.py`

`RiskDigestBuilder(store)` mirrors the Prompt 07 issue-history builder. It loads
`risk_digest_contract` + `risk_digest_policy` (for `review_required_categories`).
`build(*, dry_run=True, project_filter=None)` returns `{command, mode, ok, schema_version,
contract_version, policy_version, project_filter, summary{projects, items_planned/written,
review_required, by_risk_source_class, by_risk_indicator_type, by_confidence_class}, guardrails}`.
Dry-run plans and writes nothing; `--apply` upserts. Projects are enumerated from the substrate
(candidates ∪ issue-history ∪ open action signals). `project_risk_digest_status()` is a read-only
coverage report.

**Bounded digest:** one item per `(risk_source_class, risk_indicator_type)` with a count and ≤5 safe
sample references — not one row per underlying record. `risk_digest_id =
hash_value("risk|{project}|{risk_source_class}|{risk_indicator_type}")` → idempotent.

**Four classifier passes (`risk_source_class`):**

| Class | Source | Indicator | confidence_class |
|---|---|---|---|
| `source_stated` | open `procore_action_signals` grouped by `signal_type` | the signal_type | `deterministic` |
| `inferred_candidate` | risk-bearing `project_issue_history_items` (status ∈ {overdue, void, rejected, out_for_pricing} or `age_days ≥ 31` open) | overdue_issue / void_issue / rejected_issue / aging_open_issue | `strong_heuristic` |
| `review_required` | `cross_source_relationship_candidates` review-required / weak / `sensitive_high_impact`, grouped by `relationship_type` (+ a `sensitive_high_impact_relationship` bucket) | the relationship_type | `weak_heuristic` |
| `model_proposed` | candidates `model_proposed=1`, grouped by `relationship_type` | the relationship_type | `model_proposed` |

No double-count: procore record status risk is already reflected through issue-history, so it is not
re-counted from `procore_live_records`.

**`review_required` flag** = the indicator's mapped category ∈ `review_required_categories`
(financial/cost_impact/schedule_impact/safety/claim/contractual/personnel/legal via `_risk_category`
keyword map) OR `risk_source_class ∈ {review_required, model_proposed}` OR an underlying edge/family
is review_required. Weak / model / sensitive indicators are always review-required and never
auto-promoted.

### Store — `construction/store/repositories.py`

`list_procore_action_signals` (safe identifier/enum columns only — never title/summary/metadata
free-text), plus `upsert/list/count_project_risk_digest_item(s)` mirroring the Prompt 07 issue-history
methods. The eight guard `CHECK(… = 0)` columns are never written.

### CLI — `construction-agent risk-digest`

`build` (`--apply` default dry-run, `--project`, `--json`) and `status` (`--project`, `--json`),
mirroring the `issue-history` sub-app.

### Not changed

No prerequisite gate / no policy-gated readiness (objective is materialization). The meeting-prep
brief is untouched (`risk_exposure_watchlist` stays a deferred placeholder).
`project_risk_digest_items` was already registered in the table-lifecycle contract (inventory stays
120).

## Guardrails

Local-first, read-only. Items persist only counts, enums, category tokens, Procore endpoint names,
and ids/hashes — never raw bodies/text/status payloads/titles, signed/download URLs, tokens, secrets,
prompts, or responses (no-raw-content regex test). Advisory only — no final legal/contractual/claim/
safety/financial determination. Weak/model/sensitive never auto-promoted; review-required flagged.

## Validation

ruff / `mypy src` (184 files) / compileall clean; pytest **+8 new tests**. Live
`risk-digest build --apply` materialized a bounded `tropical` digest across all four classes (mostly
review-required, financial/schedule/contractual categories); dry-run wrote nothing; `risk-digest
status` reflects it. Both no-writeback proofs pass; `table-inventory` 25 / 120;
`meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/risk_digest/__init__.py`, `…/risk_digest_builder.py` (new).
- `src/hb_assistant/construction/store/repositories.py` (+4 methods).
- `src/hb_assistant/cli/construction.py` (`risk-digest` sub-app).
- `tests/test_risk_digest.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/08-risk-digest.md`.
