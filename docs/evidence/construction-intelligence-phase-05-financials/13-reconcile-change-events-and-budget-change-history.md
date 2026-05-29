# Phase 05 — Reconcile change-events + budget-change-history to their live shapes (2026-05-29)

> The two endpoints held during the live-promotion pass (`12-…`) are reconciled against
> their **observed** live contracts and promoted. Read-only live GET; redaction posture
> preserved; fail-closed-on-residual-divergence retained.

## Observed contract (live diagnostic, redacted — types/lengths only, never raw values)

A live diagnostic fetched a bounded page per endpoint and introspected the real records
(no raw values logged or persisted):

- **change-events** (`/rest/v1.1/change_events`, body = bare `list`): the record is far
  richer than the package sample. Crucially, **`status` is a nested object**
  `{id:int, name:str, mapped_to_status:str}` (also `change_type`, `change_reason`,
  `prime_contract_for_estimates` are objects; `created_by` is `{id, login, name}`). There
  are **no top-level** `estimated_cost`/`estimated_revenue`/`owner_cost_amount` fields —
  cost/revenue live under `change_items[]` / `markup_items[]` (line-item children) and a
  `source_of_revenue_rom` label. The **normalizer succeeded**; the **projection raised**
  because `status` (a dict) was written into a TEXT column.
- **budget-change-history** (`/rest/v2.0/.../budget_change_history`, body = `{data: [...]}`):
  records are `{budget_code, column, created_at, created_by (str), description, old_value,
  new_value, type}` — an append-only change log with **no `id` field** and `created_by` as
  a plain string. The **normalizer succeeded**; each record was **skipped by the
  orchestrator** (`_record_id_of` → None → `missing_record_id`) because there is no id.

## Fixes (match the observed contract — minimal, surgical)

- `store/procore_rfq_change_event_projection.py`: added `_scalar_name()` (dict
  `{name|id}` → scalar; passes strings through) and applied it to `status` + `scope` in
  `_project_change_event` (column write **and** the signal predicate). No dict ever
  reaches a TEXT column; older string-shaped tenants still work.
- `procore/live_sync.py`: `_record_id_of` gains a deterministic **synthetic record-id**
  fallback for id-less change-log endpoints (`_SYNTHETIC_RECORD_ID_FIELDS` →
  `budget-change-history` keyed by `budget_code|column|created_at|old_value|new_value`,
  SHA-256 → `h:<16hex>`). Same change → same id, so latest-state upsert + history + the
  projection's own synthetic key all stay idempotent.

No normalizer changes were needed (both already succeeded on the live records). Redaction
unchanged (amounts decimal-safe; descriptions excerpt-masked; `created_by` string is not a
dict person ref so it is dropped, not stored).

## Re-probe (gated) — both now match

| Endpoint | state | retrieved | normalized | proj_err | projected rows |
|---|---|--:|--:|--:|--:|
| change-events | success | 5 | 5 | 0 | 5 |
| budget-change-history | success | 5 | 5 | 0 | 5 |

## Promotion + full live cadence

`endpoints.py`: both flipped `live_verified=True`
(`verification_reason="phase05_live_smoke_verified_2026-05-29"`). Registry posture
**34 → 36 live-verified / 23 fail-closed / 59 total**.

| Endpoint | smoke | sync (retrieved/upserted/proj_err) | idempotent re-run |
|---|---|---|---|
| change-events | success | 100/100/0 | 100==100 ✅ |
| budget-change-history | success | 100/100/0 | 95==95 ✅ (synthetic id dedups identical change rows) |

No-secret probe over the 295 resulting real rows (`procore_financial_change_events` 100,
`procore_financial_budget_changes` 195) → **zero** Bearer/PEM/`sig=`/email/URL findings;
`raw_body_persisted=0` / `redaction_applied=1` intact.

## Tests

- `tests/test_procore_rfq_change_event_projection.py`: `test_change_event_object_status_projects_name`
  (nested `{id,name}` status → stored scalar `"Open"`, no dict in the TEXT column).
- `tests/test_procore_live_sync_phase05_chain.py`: `test_budget_change_history_synthetic_record_id`
  (id-less record → deterministic `h:` id; distinct change → distinct id; explicit id used verbatim).
- `tests/test_procore_endpoint_registry.py`: `_PHASE05_PROMOTED` now 9 (adds change-events,
  budget-change-history). `tests/test_procore_live_gate.py`: endpoints-list counts 34/25 → **36/23**.

## Verification

- `ruff check .` + `mypy src` clean (115 files); `pytest -m "not integration and not live
  and not manual"` → **1241 passed, 1 skipped, 1 deselected** (+2 new tests).
- Live cadence run with `HB_PROCORE_LIVE=1` via the credential loader; read-only GET,
  SQLite-only, no writeback.

## Residual fail-closed (unchanged)

Child financial endpoints (line-items / responses / quotes / comments / budget-detail-* /
compliance) remain fail-closed pending the deferred N+1 parent→child orchestration;
`budget-details` stays a non-routable sentinel. **Posture: 36 verified / 23 fail-closed.**
