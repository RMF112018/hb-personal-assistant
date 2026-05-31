# Phase 06B — Prompt 09: Cost Exposure Model

**Status:** COMPLETE.
**Run date:** 2026-05-30
**Parent HEAD at start:** `7a61a5b` (`phase-06b prompt-08: overdue & action queue read model`)
**Objective:** Make the V8/V9 financial tables operationally useful via a financial/cost exposure
model — surfaced as `procore live financial exposure --project KEY --json`. Advisory/review aid
only; read-only over local SQLite; no live access; no raw values; no determinations.

---

## 1. What was built

- `src/hb_assistant/store/procore_cost_exposure.py` — `build_cost_exposure(project_key, *, now_utc,
  exposure_type=None, importance=None, max_items=100, db_path=None)`. Deterministic, read-only.
  Reuses `get_procore_action_signals` (`procore_enrichment`) and the Phase 05 read helpers
  `read_financial_amount_facts` / `read_financial_budget_changes` (`procore_financials`).
- CLI `procore live financial exposure --project KEY [--type T] [--importance I] [--max-items N]
  --json` (new verb in the existing `live financial` group; mirrors `live financial risk`).

### Exposure types (the seven the prompt specifies)
| Type | Source signals / rows |
| --- | --- |
| `pending_change` | `change_event_pending`, `change_event_rom_cost_exposure`, `change_event_schedule_impact` |
| `unapproved_change` | `commitment_unexecuted`, `commitment_change_order_unexecuted`, `commitment_change_order_unpaid`, `contract_unexecuted` |
| `budget_movement` | `budget_change_posted`, `budget_modification_posted`, `budget_variance_negative`, `budget_forecast_exceeds_budget`, `budget_actual_exceeds_budget` |
| `invoice_retainage_risk` | `invoice_approved_not_paid`, `invoice_payment_due`, `invoice_retainage_held`, `invoice_pending_approval`, `billing_period_due_soon` |
| `rfq_quote_pending` | `rfq_estimated_cost_exposure`, `rfq_under_review`, `rfq_overdue`, `rfq_no_intent_to_quote`, `rfq_estimated_schedule_impact` |
| `compliance_risk` | `commitment_compliance_document_expiring`, `commitment_non_compliant`, `commitment_insurance_not_compliant` |
| `amount_changed` | `procore_financial_budget_changes` rows with `adjustment_amount` or `from_amount`/`to_amount` |

### Per-item fields
`exposure_type`, `source` (`action_signal` | `budget_change`), `signal_type`, `endpoint_id`,
`record_key`, `importance`, `review_required`, `reason_codes`, `due_at_utc`, `title_redacted`,
`source_url_redacted`, `amounts` (`amount_name` / `amount_value` decimal-safe string /
`currency_iso_code`).

### Inputs
- **classification spine** — open `procore_action_signals` mapped via the explicit
  `_EXPOSURE_SIGNAL_MAP` (only cost/financial types; others skipped).
- **amounts** — `read_financial_amount_facts` joined by `record_key` (values verbatim TEXT).
- **`amount_changed` lens** — `read_financial_budget_changes` from/to/adjustment strings.
- **source link + review flag** — `procore_live_records` joined by `record_key`.

---

## 2. Repo-truth / stop-condition reconciliation

- **Signals already encode the exposure semantics** — the projection layer (Phase 05/06A) emits the
  cost/financial signal vocabulary; Prompt 09 classifies and enriches rather than re-deriving from
  raw payloads. The financial read helpers already return decimal-safe strings.
- **Stop condition honored** — "stop if the model asserts entitlement, liability, or contractual
  determinations." The model emits only counts, type labels, and per-item amounts; it never sums or
  differences money, and a no-determination word scan guards the output. It is advisory/review only.
- **Read-only, no persistence** — consistent with Prompts 06/07/08 and the dry-run-default
  guardrail; no table/migration was added (schema stays V19). Exposure is derived on demand.

---

## 3. Exposure classification & amount safety

- Classification is a literal `signal_type → exposure_type` table (auditable; no keyword guessing).
- **Amounts are never summed, differenced, or float-coerced.** Every `amounts[*].amount_value` is
  the verbatim decimal-safe TEXT string from the store; the distinctive seeded change-event amount
  `250000.00` appears unchanged in the proof. No aggregate/total field is emitted — a summed
  exposure figure would read as a financial determination.
- `review_required` = contributing signal `importance == "high"` OR `exposure_type` ∈
  {`compliance_risk`, `unapproved_change`, `invoice_retainage_risk`} (documented triage label,
  carries reason code `review_required_high_sensitivity`).

---

## 4. Proof (09-cost-exposure-proof.json)

Seeded a temp DB (isolated `HB_PA_CONFIG`) via the projection family functions — an unexecuted
commitment, an approved-unpaid subcontractor invoice with retainage, an open RFQ, an open change
event, and a budget change — and dumped `build_cost_exposure`:

```
summary: total 8, review_required 5,
  by_type { unapproved_change 1, invoice_retainage_risk 3, rfq_quote_pending 2,
            pending_change 1, amount_changed 1, budget_movement 0, compliance_risk 0 },
  by_importance { high 4, medium 4, low 0 }
```

See [`09-cost-exposure-proof.json`](./09-cost-exposure-proof.json).

---

## 5. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_cost_exposure.py` | 0 | 13 passed (classification / amounts-are-strings / filters / review / amount_changed / no-determination / CLI) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+13) |
| `ruff check .` | 0 | no new findings from changed files |
| `mypy src` | 0 | Success: no issues found |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live financial exposure --project tropical --json` | 0 | ok envelope |

---

## 6. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only signal/record metadata, type labels,
  redacted titles, source-link strings, and decimal-safe amount facts. Proof JSON secret/raw-value
  scanned (0 findings).
- **Amounts stay decimal-safe strings** (`amounts_are_strings: true`) — never summed, differenced,
  or float-coerced.
- **No legal/claims/financial/entitlement/liability/contractual determination**
  (`determinations_made: false`) — banned-determination-word scan over the output (0 findings).
