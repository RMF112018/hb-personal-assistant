# 07D Prompt 08 — Risk Digest (Evidence)

Additive over schema **V25** (no migration). Materializes review-controlled risk digests into
`project_risk_digest_items` via a new `construction-agent risk-digest` sub-app.

## Preflight (repo truth)

- `git rev-parse HEAD` → `9e42f88b49fcff9bee80c5db3d1a52494d2bcc0c` (Prompt 07 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`07`; this adds `08`.

## What changed

- **Engine** `construction/risk_digest/risk_digest_builder.py` (+ `__init__.py`):
  `RiskDigestBuilder.build()` (dry-run default / `--apply`) with four classifier passes
  (source_stated / inferred_candidate / review_required / model_proposed), a category keyword map,
  and a read-only `project_risk_digest_status()`.
- **Store** `construction/store/repositories.py`: `list_procore_action_signals` (safe columns only)
  + `upsert/list/count_project_risk_digest_item(s)`.
- **CLI** `cli/construction.py`: `construction-agent risk-digest build/status`.
- **Tests** `tests/test_risk_digest.py` (8).
- Reused unchanged: `relationships/contracts.py`, the V25 table already present, and
  `list_cross_source_relationship_candidates` / `list_project_issue_history_items` / `hash_value`.
  `project_risk_digest_items` was already registered in the table-lifecycle contract (inventory stays 120).

## Classification (risk_source_class) grounded in live sources

- **source_stated** ← open `procore_action_signals` grouped by `signal_type` (deterministic).
- **inferred_candidate** ← risk-bearing `project_issue_history_items` (status overdue/void/rejected/
  out_for_pricing or `age_days ≥ 31` open), grouped into overdue/void/rejected/aging_open indicators
  (strong_heuristic).
- **review_required** ← review-required / weak / `sensitive_high_impact` candidates grouped by
  relationship_type (weak_heuristic).
- **model_proposed** ← `model_proposed=1` candidates (model_proposed; 0 live but code-pathed).
Bounded: one item per `(risk_source_class, risk_indicator_type)` with a count + ≤5 safe sample refs.
`review_required` flag set when the indicator's mapped category ∈ review_required_categories OR class
∈ {review_required, model_proposed} OR an underlying edge/family is review-required.

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **184** source files |
| `pytest -m "not live and not integration and not manual"` | **2190 passed**, 1 deselected (exit 0) |

(Prompt 07 baseline 2182; +8 new risk-digest tests.)

## CLI validation matrix (all exit 0)

`risk-digest build` (dry-run), `risk-digest build --apply`, `risk-digest status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p08/*.json` (ephemeral, not committed).

### Live `risk-digest build` (project `tropical`)

| Run | mode | items_written | review_required |
|---|---|---|---|
| dry-run | dry_run | 0 (planned 44) | — |
| apply | apply | 44 | 30 |

- `by_risk_source_class` = {source_stated: 34, inferred_candidate: 4, review_required: 6}
  (model_proposed 0 — none live).
- `by_confidence_class` = {deterministic: 34, strong_heuristic: 4, weak_heuristic: 6}.
- Indicators: action-signal types (billing_period_due_soon, budget_change_posted, change_event_pending,
  commitment_unexecuted, inspection_has_deficient_items, …), issue patterns (aging_open_issue,
  overdue_issue, …), and review-required relationship types (attachment_filename, …).
- `risk-digest status` → `items=44`, `review_required=30`.

### Safety invariants (after live apply)

- No-raw-content regex over the serialized `build --apply` and `status` payloads → **no match**;
  no title/summary/status payload is pulled through (safe columns only).
- All eight guard `CHECK(… = 0)` columns stay 0 on `project_risk_digest_items` (asserted in tests).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.

## Test-path coverage (new file)

source_stated from action signals (financial→review, non-category→not); inferred_candidate from
issue history (overdue / aged-open, non-risk excluded); review_required + model_proposed relationships
(always review, never promoted); empty substrate → 0 items; no-raw-content (no title payload);
idempotent apply; dry-run writes nothing; status coverage.

## Guardrails honored / stop conditions

- No external writeback / write scopes; no mutation beyond the local SQLite risk-digest table; no
  schema change.
- No raw content, raw status/title payload, signed/download URL, token, secret, prompt, or response
  persisted (no-raw test + both no-writeback proofs).
- Weak / model / sensitive risk indicators stay review-required and are never auto-promoted.
- Advisory only — no final legal/contractual/claim/safety/financial determination.
- Readiness not overstated: items reflect only locally-stated/derived signals; no claim of completeness.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `risk_digest` engine + `__init__`, 4 store methods, `risk-digest` CLI sub-app,
  new risk-digest test file, `docs/architecture/51-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** unchanged and honest (`meeting_prep_readiness_claim="ready"`); no new gate.
- **Next prompt allowed to proceed:** yes. Prompt 09 (aging / exposure report) may build on the
  substrate, issue history, and these risk digests; classification and review routing are in place.
