# 07D Prompt 09 — Aging and Exposure Reporting (Evidence)

Additive over schema **V25** (no migration). Materializes `aging_exposure_report_items` via a new
`construction-agent aging-exposure` sub-app.

## Preflight (repo truth)

- `git rev-parse HEAD` → `08cdbe6698b7d00280d4d9ab864c34aad448e83d` (Prompt 08 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`08`; this adds `09`.

## What changed

- **Engine** `construction/aging_exposure/aging_exposure_builder.py` (+ `__init__.py`):
  `AgingExposureBuilder.build()` (dry-run default / `--apply`), seed-driven band assignment,
  financial-family recognition, status normalization, and a read-only `project_aging_exposure_status()`.
- **Store** `construction/store/repositories.py`: `upsert/list/count_aging_exposure_report_item(s)`.
- **CLI** `cli/construction.py`: `construction-agent aging-exposure build/status`.
- **Tests** `tests/test_aging_exposure.py` (10).
- Reused unchanged: `relationships/contracts.py`, the V25 table already present, and
  `list_procore_live_records` / `list_cross_source_relationship_candidates` / `hash_value`.
  `aging_exposure_report_items` was already registered in the table-lifecycle contract (inventory
  stays 120).

## Design grounded in repo + live-data truth

- **Source = `procore_live_records`** (1780 records / 39 families). One row per record (UNIQUE
  project_key/record_family/record_ref); `record_family = endpoint_id`; `record_ref =`
  `project|endpoint|parent|id`; real `age_days` from `updated_at_utc`.
- **Bands** from the seed (current 0–7 / monitor 8–14 / aging 15–30 / stale 31–60 / critical_review
  61–∞); no timestamp → `threshold_band="unknown"`, `confidence_class=NULL`.
- **Financial boundaries:** financial families recognized (budget/commitment/invoice/change-order/
  billing/prime/purchase-order); financial-family records in stale/critical bands flagged
  review-required and counted in `financial_exposure`. **No raw financial amounts are persisted** (the
  table has no amount column — the boundary).
- **Status normalization:** Procore dict-string statuses parsed to bounded tokens, never persisted raw.

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **186** source files |
| `pytest -m "not live and not integration and not manual"` | **2200 passed**, 1 deselected (exit 0) |

(Prompt 08 baseline 2190; +10 new aging-exposure tests.)

## CLI validation matrix (all exit 0)

`aging-exposure build` (dry-run), `aging-exposure build --apply`, `aging-exposure status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p09/*.json` (ephemeral, not committed).

### Live `aging-exposure build` (project `tropical`)

| Run | mode | items_written | review_required |
|---|---|---|---|
| dry-run | dry_run | 0 (planned 1780) | — |
| apply | apply | 1780 | 1780 |

- `by_threshold_band` = {current 38, monitor 8, aging 41, stale 40, critical_review 1053, unknown 600}
  (600 unknown = the 600 records without `updated_at_utc`; 1180 timestamped records mostly aged > 61d).
- `stale` 1093, `missing_status` 854, `unknown_age` 600; 39 record families.
- `financial_exposure` = {total_financial 875, stale 13, critical_review 437}.
- `aging-exposure status` mirrors the build counts.
- **Readiness honesty note:** `review_required=1780` (100%) is honest, not overstated — every live
  record is in a critical band, financially stale, source-`review_required`, or carries a
  `sensitive_reason` (the upstream Procore enrichment flags most records as sensitive). The guardrail
  requires sensitive records stay review-required; flagging review is the *conservative* direction
  (more review, never less). The discriminating signal is `threshold_band` + `financial_exposure`,
  which are well-distributed.

### Safety invariants (after live apply)

- No-raw-content regex over the serialized `build --apply` and `status` payloads → **no match**;
  no Procore dict-string status payload is persisted; no financial amounts.
- All eight guard `CHECK(… = 0)` columns stay 0 on `aging_exposure_report_items` (asserted in tests).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.

## Test-path coverage (new file)

band assignment (current/aging/stale/critical, deterministic via injected now); financial exposure
(financial family in stale/critical → review-required + financial_exposure counts); missing-status
flag; unknown-age (no timestamp → band unknown, confidence None); review-required from source flag;
empty source → 0 items; no-raw-content + status normalization; idempotent apply; dry-run writes
nothing; status coverage.

## Guardrails honored / stop conditions

- No external writeback / write scopes; no mutation beyond the local SQLite aging table; no schema
  change.
- No raw content, raw status payload, financial amount, signed/download URL, token, or secret
  persisted (no-raw test + both no-writeback proofs).
- Sensitive records stay review-required and are never auto-promoted.
- Advisory only — no final legal/contractual/claim/safety/financial determination.
- Readiness not overstated: missing timestamps → `unknown` band (not assumed current);
  `review_required` errs conservative.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `aging_exposure` engine + `__init__`, 3 store methods, `aging-exposure` CLI
  sub-app, new aging-exposure test file, `docs/architecture/52-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** unchanged and honest (`meeting_prep_readiness_claim="ready"`); no new gate.
- **Next prompt allowed to proceed:** yes. Prompt 10 (correspondence context, per the 07D package)
  may build on the substrate, issue history, risk digest, and aging exposure; the per-record aging
  layer and financial-exposure boundary are in place.
