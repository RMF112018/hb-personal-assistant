# 52 — Phase 07D: Aging and Exposure Reporting

**Status:** Implemented (Phase 07D Prompt 09). Additive over schema **V25** (no migration).
**Scope:** Materialize `aging_exposure_report_items` (shipped empty in Prompt 02) — one classified row
per Procore record across record families, with an aging `threshold_band` and stale/missing-status
flags — via a new `construction-agent aging-exposure build/status` sub-app. Advisory, read-only, no
raw content, no financial amounts, no external writeback, no auto-promotion.

## Problem

The V25 aging table had no producer; the meeting-prep brief's `aging_items` section is an honest
deferred placeholder pointing at it. This prompt turns per-record source timestamps/status into a
banded aging-and-exposure report, recognizing financial-family exposure.

## Design

### Engine — `construction/aging_exposure/aging_exposure_builder.py`

`AgingExposureBuilder(store)` mirrors the Prompt 08 risk-digest builder. It loads
`aging_exposure_report_contract` + `aging_exposure_thresholds` (bands + `record_family_overrides`).
`build(*, dry_run=True, project_filter=None, now_utc=None)` returns `{command, mode, ok,
schema_version, contract_version, policy_version, project_filter, summary{projects, items_planned/
written, review_required, stale, missing_status, unknown_age, by_threshold_band, by_record_family,
financial_exposure{total_financial, stale, critical_review}}, guardrails}`. Dry-run plans and writes
nothing; `--apply` upserts. Projects are enumerated from `procore_live_records`.
`project_aging_exposure_status()` is a read-only coverage report.

**Source = `procore_live_records`** (the most complete per-record aging picture). One row per record
(UNIQUE `project_key, record_family, record_ref`):
- `record_family = endpoint_id`; `record_ref =` reconstructed record_key `project|endpoint|parent|id`
  (matches the substrate); `aging_item_id = hash_value("aging|{project}|{family}|{ref}")` (idempotent).
- `age_days` from `updated_at_utc`; `_band_for(age_days, family)` assigns the seed band
  (current 0–7 / monitor 8–14 / aging 15–30 / stale 31–60 / critical_review 61–∞, honoring
  `record_family_overrides`). No timestamp → `age_days=0`, `threshold_band="unknown"`,
  `confidence_class=NULL` (never overstated); resolved → `confidence_class="deterministic"`.
- `status` via `_normalize_status` (bounded token; Procore dict-strings parsed, never persisted raw);
  `missing_status_flag` when status null/empty/unknown.
- `stale_flag` = band ∈ {stale, critical_review}.
- `evidence_trail_id` from a `{source_record_ref → evidence_trail_id}` map built once from the
  substrate candidates (attached when the record participates; else NULL — `record_ref` is itself the
  source reference).

**Financial boundaries.** `_is_financial(record_family)` matches financial keywords (budget /
commitment / invoice / change-order / change-event / billing / prime / purchase-order / payment /
contract / compliance). A financial-family record in a stale/critical band is flagged
`review_required` and counted in `financial_exposure`. **No raw financial amount is persisted** — the
table has no amount column and amounts stay out of it by design (the boundary).

**`review_required`** = band == `critical_review` OR (financial family AND `stale_flag`) OR the source
record's `review_required` / `sensitive_reason`. Sensitive records stay review-required and are never
auto-promoted.

### Store — `construction/store/repositories.py`

`upsert/list/count_aging_exposure_report_item(s)`, mirroring the Prompt 08 risk-digest methods; the
eight guard `CHECK(… = 0)` columns are never written.

### CLI — `construction-agent aging-exposure`

`build` (`--apply` default dry-run, `--project`, `--json`) and `status` (`--project`, `--json`),
mirroring the `risk-digest` sub-app.

### Not changed

No prerequisite gate / no policy-gated readiness (objective is materialization). The meeting-prep
brief is untouched (`aging_items` stays a deferred placeholder). `aging_exposure_report_items` was
already registered in the table-lifecycle contract (inventory stays 120).

## Guardrails

Local-first, read-only. Rows persist only record_family / record_ref (local record key), bounded
status tokens, band names, and ids — never raw bodies/text/status payloads/financial amounts,
signed/download URLs, tokens, secrets, prompts, or responses (no-raw-content regex test). Advisory
only — no final legal/contractual/claim/safety/financial determination. Sensitive records stay
review-required and are never auto-promoted.

## Validation

ruff / `mypy src` (186 files) / compileall clean; pytest **+10 new tests**. Live
`aging-exposure build --apply` materialized one row per `tropical` record across record families with
banded aging (current/monitor/aging/stale/critical_review/unknown) and a financial-exposure summary;
dry-run wrote nothing; `aging-exposure status` reflects it. Both no-writeback proofs pass;
`table-inventory` 25 / 120; `meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/aging_exposure/__init__.py`, `…/aging_exposure_builder.py` (new).
- `src/hb_assistant/construction/store/repositories.py` (+3 methods).
- `src/hb_assistant/cli/construction.py` (`aging-exposure` sub-app).
- `tests/test_aging_exposure.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/09-aging-and-exposure-reporting.md`.
