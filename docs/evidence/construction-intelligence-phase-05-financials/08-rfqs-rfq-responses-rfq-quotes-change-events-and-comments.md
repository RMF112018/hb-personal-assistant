# Phase 05 Prompt 08 — RFQs, RFQ Responses, RFQ Quotes, Change Events & Comments

> **Scope:** the change-management pricing/exposure surface — `rfqs`, `rfq-responses`,
> `rfq-quotes`, `change-events`, `change-event-comments` — linking informal
> pricing/change workflow to formal change records. **No migration** (reuses the V8
> rfqs + change-events tables); responses/quotes/comments project as facts/edges/signals.
> **No live GETs**; all 5 stay `live_verified=False` (fail-closed). Companions:
> [`06-…line-items.md`](./06-change-orders-and-financial-line-items.md),
> [`07-…invoice-items.md`](./07-billing-periods-subcontractor-invoices-and-invoice-items.md).

## 1. No schema change

V8 already carries `procore_financial_rfqs` and `procore_financial_change_events`
(+ `upsert_financial_rfq` / `upsert_financial_change_event`). The package's
authoritative SQL defines **no tables** for rfq-responses, rfq-quotes, or
change-event-comments — so they are **not** given tables (do-not-guess). Migration
stays at **V9**; `apply()` returns 9.

## 2. Normalizers — `procore/normalizers/rfq_change_event.py`

`normalize_rfq`, `normalize_rfq_response`, `normalize_rfq_quote`,
`normalize_change_event`, `normalize_change_event_comment`. Posture: amounts /
schedule-impact verbatim (decimal-safe); WBS/cost-code kept; parties hashed; all free
text (rfq/change-event `title`, rfq/quote `description`, response `comment`,
change-event comment `body`) → `summarize_text` (hash + length + **PII-masked
excerpt**) — raw body never persists.

## 3. Projection — `store/procore_rfq_change_event_projection.py`

`project_rfq_change_event_family(endpoint_id, raw, ...)` + `RFQ_ENDPOINTS`.

| Endpoint | Target | Notes |
|---|---|---|
| rfqs | `procore_financial_rfqs` | facts + edges + 5 signals (below) |
| change-events | `procore_financial_change_events` | facts + creator edge + 3 signals |
| rfq-quotes | amount facts + `quote_of` edge | no table (quote `cost`/`schedule_impact` facts) |
| rfq-responses | `response_of` edge | no table (comment text in live record) |
| change-event-comments | `change_event_comment_added` signal + `comment_of` edge | no table; per-comment record key |

- **Cost/schedule exposure facts:** RFQ — `estimated_amount`, `original_quote`,
  `estimated_schedule_impact`; quote — `cost`, `schedule_impact`; change event —
  `estimated_cost`, `estimated_revenue`, `owner_cost_amount`, `commitment_cost_amount`,
  `schedule_impact_amount` (cost-code id attached to facts when present).
- **Edges:** rfq → commitment (`rfq_of_commitment`), → change event (`rfq_change_event`),
  → PCO/COR/CCO (`rfq_change_order`); quote `quote_of` → rfq; response `response_of` →
  rfq; comment `comment_of` → change event; creator/assignee linked via
  `link_record_entities` (people hashed).
- **PCO/COR/CCO mapping (documented):** prime-family references
  (`potential_change_orders`, `change_order_packages`) → `prime-change-orders`
  record-key namespace; commitment-family (`commitment_potential_change_orders`,
  `commitment_change_order_packages`) → `commitment-change-orders`. dict-or-list tolerant.
- **Signals:** `rfq_overdue` (`_days_until(due_date) < 0`, non-terminal status),
  `rfq_under_review`, `rfq_no_intent_to_quote` (`intent_to_quote` is `False`),
  `rfq_estimated_schedule_impact` (>0), `rfq_estimated_cost_exposure` (`estimated_amount`>0);
  `change_event_pending` (status set + non-terminal), `change_event_rom_cost_exposure`
  (`estimated_cost`>0), `change_event_schedule_impact` (>0); `change_event_comment_added`
  (one per comment, anchored on the comment record key).

## 4. Read views (query support)

`read_financial_rfqs(project_key, status=?)` and
`read_financial_change_events(project_key, status=?)` in `procore_financials.py` —
make the RFQ/change-event workflow queryable.

## 5. Live-sync wiring

5 normalizers registered in `_NORMALIZER_BY_ID`; a guarded `RFQ_ENDPOINTS` block calls
`project_rfq_change_event_family` (after the invoice block). All 5 stay
`live_verified=False` — fail-closed before the normalizer lookup (no transport) until
promotion.

## 6. Tests

- `tests/test_procore_rfq_change_event_normalizers.py` (5): rfq/quote/change-event amounts
  preserved (precision); title/description/comment/body hashed-with-excerpt (no raw PII/contact);
  schedule impact + cost-code preserved.
- `tests/test_procore_rfq_change_event_projection.py` (8): rfq rows + facts + edges
  (commitment/change-event/change-order) + the 5 rfq signals; change-event rows + facts
  (cost-code on facts) + the 3 ce signals + query; quote facts + `quote_of`; response
  `response_of`; comment `change_event_comment_added` + `comment_of`; status query; idempotency;
  raw-body guard.
- `tests/test_procore_endpoint_registry.py`: `_RFQ_IMPLEMENTED` added + OR'd into `_IMPLEMENTED`;
  new `test_phase05_rfq_change_event_endpoints_have_normalizers`.

## 7. Verification run

- `ruff check .` clean; `ruff format` clean on edited source; `mypy src` → no issues in 113 source files.
- `pytest -m "not integration and not live and not manual"` → **1200 passed, 1 skipped, 1 deselected** (was 1186; +14 new tests).
- Fail-closed unchanged: `procore live endpoints list --json` → 27 verified / 32 unverified / 59 total.

## 8. Acceptance criteria status

| Criterion | Status |
|---|---|
| RFQ/change-event workflow is queryable | ✅ rfqs + change-events tables + `read_financial_rfqs`/`read_financial_change_events` (status-filter tests) |
| Cost and schedule exposure facts are preserved | ✅ rfq/quote/change-event amount + schedule-impact facts (precision tested) |
| Text is not stored raw | ✅ all free text → `summarize_text` (hash+len+masked excerpt); parties hashed |
| Edges connect RFQs/change events to related financial records | ✅ rfq→commitment/change-event/change-order, quote/response→rfq, comment→change-event |
| Required signals emitted | ✅ all 9 (`rfq_*`, `change_event_*`), each tested |
| No live GETs; fail-closed preserved | ✅ all 5 `live_verified=False`; 59/27/32 unchanged |
