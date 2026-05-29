# Phase 05 Prompt 09 — Budget Views, Details, Rows & Changes

> **Scope:** the budget surface — `budget-views`, `budget-detail-columns`,
> `budget-detail-rows`, `budget-change-history`, `budget-change-line-items`,
> `budget-modifications` (6 implemented) + `budget-details` (**deferred**, non-routable
> sentinel). **No migration** (reuses the V8 budget tables via the `budget_change_kind`
> discriminator). **No live GETs**; implemented endpoints stay `live_verified=False`
> (fail-closed). Companion: [`08-…change-events.md`](./08-rfqs-rfq-responses-rfq-quotes-change-events-and-comments.md).

## 1. Coverage (per the Coverage Requirement)

Budget response shape varies by view configuration, so coverage is stated explicitly:

| Endpoint | Status | Target / handling |
|---|---|---|
| budget-views | ✅ implemented | `procore_financial_budget_views` (anchor) |
| budget-detail-columns | ✅ implemented | `column_of` edge → parent view (no table; column names kept in live record) |
| budget-detail-rows | ✅ implemented | `procore_financial_budget_rows` + `column_values_json_redacted` + amount facts |
| budget-change-history | ✅ implemented | `procore_financial_budget_changes` (kind `change_history`) |
| budget-change-line-items | ✅ implemented | `procore_financial_budget_changes` (kind `line_item`) |
| budget-modifications | ✅ implemented | `procore_financial_budget_changes` (kind `modification`) |
| **budget-details** | **⛔ DEFERRED** | non-routable sentinel — see §2 |

## 2. budget-details deferral (with reason)

`budget-details` has **no resolved REST path** in the source reference (Prompt 00
§3.2). It was registered as a clearly non-routable sentinel
(`path_template="unresolved:budget-details"`, `live_verified=False`,
`verification_reason="phase05_unresolved_path_fail_closed_prompt00-3.2"`). Per the
acceptance ("implemented **or explicitly deferred with reason**") it is **deferred**:
no normalizer is registered, it is excluded from `BUDGET_ENDPOINTS` and
`_BUDGET_IMPLEMENTED`, and `resolve_normalizer("budget-details")` returns `None`. The
fail-closed invariant test + `test_budget_details_is_non_routable_sentinel` +
`test_phase05_budget_details_remains_unimplemented` enforce this. It must be resolved
(likely merged into `budget-detail-rows`) before any live promotion — do not guess a path.

## 3. No schema change

V8 already carries `procore_financial_budget_views`, `procore_financial_budget_rows`,
and `procore_financial_budget_changes` (with `budget_change_kind`, `parent_change_key`,
`from_amount`/`to_amount`/`adjustment_amount`, WBS/cost columns). Migration stays at
**V9**; `apply()` returns 9. budget-detail-columns and budget-modifications need no new
table.

## 4. Normalizers — `procore/normalizers/budget.py`

6 normalizers (`normalize_budget_view`, `_detail_column`, `_detail_row`,
`_change_history`, `_change_line_item`, `_modification`). Column names / view labels
kept (business metadata, no PII); amounts/quantities verbatim (decimal-safe);
descriptions / forecast notes / unbudgeted reasons / modification notes →
`summarize_text` (hash + length + masked excerpt). Change-history is id-tolerant (uses
`id` if present, else a synthetic key from the change content).

## 5. Projection — `store/procore_budget_projection.py`

`project_budget_family(endpoint_id, raw, ...)` + `BUDGET_ENDPOINTS` (the 6 implemented;
budget-details never reaches here).
- **Variable columns handled safely:** detail-row `column_values_json_redacted` is a
  curated JSON of structured amount/code values only (free text excluded); stored
  verbatim (not hashed) so the structured values are preserved. Amount facts are emitted
  per recognised named amount field with `wbs_code_id` + `cost_code_id` on each fact.
- **Column-name-agnostic signals:** `budget = revised_budget|original_budget_amount`,
  `forecast = budget_forecast.amount`, `actual = first-present(actual_cost|projected_costs|
  committed_costs|direct_costs)`, `variance = projected_over_under|variance|over_under`
  (defensive, gated on presence). On minimal payloads only forecast/variance fire.
- **Edges:** column `column_of` → view; change line item `change_line_item_of` →
  parent change; modification `modifies_budget_row` → from/to budget rows.
- **Signals:** `budget_change_posted` (history; line items with a posted status),
  `budget_modification_posted`, `budget_forecast_exceeds_budget`,
  `budget_actual_exceeds_budget`, `budget_variance_negative`.

## 6. Read views (queryability)

`read_financial_budget_rows(project_key, budget_view_key?, wbs_code_id?, cost_code_id?)`
and `read_financial_budget_changes(project_key, budget_change_kind?, status?)`. Budget
amount facts are queryable **by view/row/column/WBS** via the existing
`read_financial_amount_facts` (amount_name = the budget column; record_key = the row;
facts carry `wbs_code_id`/`cost_code_id`).

## 7. Live-sync wiring

6 normalizers registered in `_NORMALIZER_BY_ID` (budget-details intentionally omitted);
a guarded `BUDGET_ENDPOINTS` block calls `project_budget_family` (after the RFQ block).
All implemented endpoints stay `live_verified=False`.

## 8. Tests

- `tests/test_procore_budget_normalizers.py` (6): view name kept + description hashed;
  column def fields kept; row amounts (precision) + notes/unbudgeted_reason hashed;
  change-history old/new amounts; line-item amount; modification transfer_amount.
- `tests/test_procore_budget_projection.py` (10): view row; column `column_of` edge;
  detail-row structured `column_values_json_redacted` (no free text) + amount facts
  (WBS/cost on facts) + the 3 row signals (rich payload) + under-budget no-signal;
  change-history (kind) + facts + `budget_change_posted`; line-item (kind + parent edge +
  query); modification (kind + from/to edges + `budget_modification_posted`); **query
  tests** (`read_financial_budget_rows` by view/WBS, `read_financial_budget_changes` by
  kind, `read_financial_amount_facts` by column); idempotency.
- `tests/test_procore_endpoint_registry.py`: `_BUDGET_IMPLEMENTED` (6 ids, **budget-details
  excluded**) + OR into `_IMPLEMENTED`; `test_phase05_budget_endpoints_have_normalizers` +
  `test_phase05_budget_details_remains_unimplemented`; existing sentinel/fail-closed tests
  still pass.

## 9. Verification run

- `ruff check .` clean; `ruff format` clean on edited source; `mypy src` → no issues in 114 source files.
- `pytest -m "not integration and not live and not manual"` → **1217 passed, 1 skipped, 1 deselected** (was 1200; +17 new tests).
- Fail-closed unchanged: `procore live endpoints list --json` → 27 verified / 32 unverified / 59 total; `resolve_normalizer("budget-details")` → `None`.

## 10. Acceptance criteria status

| Criterion | Status |
|---|---|
| Budget endpoints implemented or explicitly deferred with reason | ✅ 6 implemented; budget-details deferred (§2) |
| Variable budget columns handled safely | ✅ curated structured `column_values_json_redacted`; column-name-agnostic signals; amount facts per recognised field |
| Budget amount facts queryable by view/row/column/WBS | ✅ `read_financial_budget_rows` + `read_financial_amount_facts` (amount_name=column, record_key=row, wbs/cost on facts) |
| No live GETs; fail-closed preserved | ✅ implemented endpoints `live_verified=False`; 59/27/32 unchanged |
