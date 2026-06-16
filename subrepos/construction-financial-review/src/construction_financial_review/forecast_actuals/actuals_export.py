"""Build the shared monthly-actuals export collections from CostEntries (accounting truth).

Outputs (the same seven files in every package that consumes this):
  actuals_monthly_by_budget_code.jsonl     dense: one row per (canonical key, month) on the actuals axis
  actuals_monthly_by_cost_code.jsonl       dense: one row per (cost_code, month)
  actuals_monthly_project_total.jsonl      one row per month (project total)
  actuals_to_forecast_bridge_by_budget_code.jsonl   one row per canonical key (actuals<->forecast bridge)
  actuals_monthly_by_budget_code.csv       matrix: one row per code, one column per month (zero-filled)
  actuals_monthly_by_cost_code.csv         matrix: one row per cost code, one column per month
  audit/actuals_monthly_reconciliation_audit.json

Money is Decimal-string (2dp); never float. Rows + month columns are deterministically ordered.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal

from ..common.io import read_jsonl, write_csv, write_json, write_jsonl
from ..common.money import D, money_str
from ..forecast_cost_frequency.weekday_calendar import add_months, months_between

ZERO = Decimal("0")
CENTS = Decimal("0.01")
ACTUAL_SOURCE = "CostEntries"
ACTUAL_SOURCE_ROLE = "accounting_truth"

ACTUALS_DATA_FILES = (
    "actuals_monthly_by_budget_code.jsonl",
    "actuals_monthly_by_cost_code.jsonl",
    "actuals_monthly_project_total.jsonl",
    "actuals_to_forecast_bridge_by_budget_code.jsonl",
    "actuals_monthly_by_budget_code.csv",
    "actuals_monthly_by_cost_code.csv",
)
ACTUALS_AUDIT_FILE = "audit/actuals_monthly_reconciliation_audit.json"
ACTUALS_FILES = ACTUALS_DATA_FILES + (ACTUALS_AUDIT_FILE,)


# --------------------------------------------------------------------------- load (CostEntries only)

def load_costentries_monthly(context_pkg) -> "OrderedDict":
    """Read context canonical monthly actuals (CostEntries only). Returns a fail-closed result with
    ``by_key`` = {budget_code_key: {month: {amount: Decimal, count: int, first: str|None, last: str|None}}}
    and a ``contamination_ok`` flag (False if any row's source != CostEntries)."""
    from pathlib import Path
    path = Path(context_pkg) / "canonical" / "monthly_actuals_by_budget_code.jsonl"
    by_key: "OrderedDict[str, OrderedDict]" = OrderedDict()
    contamination_ok = True
    non_costentries = []
    present = path.exists()
    if present:
        for r in read_jsonl(path):
            key = r.get("budget_code_key") or r.get("mapped_budget_code_key")
            month = r.get("month")
            if not key or not month:
                continue
            src = r.get("source")
            if src != ACTUAL_SOURCE:
                contamination_ok = False
                non_costentries.append(OrderedDict([("budget_code_key", key), ("month", month),
                                                    ("source", src)]))
                continue
            cell = by_key.setdefault(key, OrderedDict()).setdefault(
                month, {"amount": ZERO, "count": 0, "first": None, "last": None})
            cell["amount"] += D(r.get("amount_decimal_string") if r.get("amount_decimal_string") is not None
                                else r.get("amount"))
            cell["count"] += int(r.get("entry_count") or 0)
            f, last = r.get("first_accounting_date"), r.get("last_accounting_date")
            if f and (cell["first"] is None or f < cell["first"]):
                cell["first"] = f
            if last and (cell["last"] is None or last > cell["last"]):
                cell["last"] = last
    return OrderedDict([
        ("present", present), ("by_key", by_key),
        ("contamination_ok", contamination_ok), ("non_costentries_rows", non_costentries),
    ])


def _month_axis(by_key: dict) -> list:
    months = sorted({m for cells in by_key.values() for m in cells})
    if not months:
        return []
    return months_between(months[0], months[-1])


def _cost_meta(budget_codes):
    """Return (codes sorted, cost_code -> description, key -> (cost_code, category, description))."""
    codes = sorted(budget_codes, key=lambda r: r.get("budget_code_key") or "")
    cc_desc, key_meta = OrderedDict(), OrderedDict()
    for bc in codes:
        key = bc.get("budget_code_key")
        cc = bc.get("cost_code")
        cat = bc.get("category")
        desc = bc.get("budget_code_description")
        key_meta[key] = (cc, cat, desc)
        if cc and cc not in cc_desc and desc:
            cc_desc[cc] = desc   # first (sorted) description seen for the cost code
    return codes, cc_desc, key_meta


# --------------------------------------------------------------------------- build

def build_collections(project_key, budget_codes, monthly_by_key, to_date_by_key, *,
                      rec_by_key=None, forecast_start_month=None) -> dict:
    """Pure + deterministic. Returns {filename: payload} for the seven actuals files."""
    rec_by_key = rec_by_key or {}
    months = _month_axis(monthly_by_key)
    codes, cc_desc, key_meta = _cost_meta(budget_codes)

    bcode_rows, bridge_rows = [], []
    cc_month = defaultdict(lambda: {"amount": ZERO, "count": 0})       # (cost_code, month)
    proj_month = OrderedDict((m, {"amount": ZERO, "count": 0}) for m in months)
    bcode_csv_rows, cc_seen_total = [], OrderedDict()
    per_key_recon = []

    for bc in codes:
        key = bc.get("budget_code_key")
        cc, cat, desc = key_meta.get(key, (bc.get("cost_code"), bc.get("category"),
                                           bc.get("budget_code_description")))
        cells = monthly_by_key.get(key, {})
        csv_row = OrderedDict([("budget_code_key", key), ("cost_code", cc), ("cost_type", cat),
                               ("budget_code_description", desc)])
        key_total = ZERO
        latest_month = last_nonzero = None
        for m in months:
            cell = cells.get(m, {"amount": ZERO, "count": 0, "first": None, "last": None})
            amt = cell["amount"]
            cnt = int(cell["count"])
            key_total += amt
            if cnt > 0 or amt != ZERO:
                latest_month = m
                last_nonzero = m
            bcode_rows.append(OrderedDict([
                ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
                ("cost_type", cat), ("budget_code_description", desc), ("month", m),
                ("actual_cost", money_str(amt)), ("entry_count", cnt),
                ("first_cost_entry_date", cell["first"]), ("last_cost_entry_date", cell["last"]),
                ("actual_source", ACTUAL_SOURCE), ("actual_source_role", ACTUAL_SOURCE_ROLE),
                ("is_actual", True)]))
            csv_row[m] = money_str(amt)
            cc_month[(cc, m)]["amount"] += amt
            cc_month[(cc, m)]["count"] += cnt
            proj_month[m]["amount"] += amt
            proj_month[m]["count"] += cnt
        bcode_csv_rows.append(csv_row)

        # bridge row (actuals <-> forecast)
        to_date = D(to_date_by_key.get(key)) if to_date_by_key.get(key) is not None else None
        diff = (key_total - to_date) if to_date is not None else None
        reconciles = bool(to_date is not None and abs(diff) <= CENTS)
        rec = rec_by_key.get(key) or {}
        ctc = rec.get("recommended_cost_to_complete")
        bridge_rows.append(OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", cc),
            ("cost_type", cat), ("budget_code_description", desc),
            ("actual_cost_to_date", money_str(to_date) if to_date is not None else None),
            ("exported_monthly_actuals_total", money_str(key_total)),
            ("reconciliation_difference", money_str(diff) if diff is not None else None),
            ("latest_actual_month", latest_month), ("last_nonzero_actual_month", last_nonzero),
            ("forecast_start_month", forecast_start_month),
            ("remaining_forecast_cost_to_complete", money_str(D(ctc)) if ctc is not None else None),
            ("actual_source", ACTUAL_SOURCE),
            ("reconciliation_status", "reconciled" if reconciles else
             ("variance" if to_date is not None else "no_to_date_reference")),
            ("reconciles", reconciles), ("requires_human_acceptance", True)]))
        per_key_recon.append(OrderedDict([
            ("budget_code_key", key), ("exported_monthly_actuals_total", money_str(key_total)),
            ("actual_cost_to_date", money_str(to_date) if to_date is not None else None),
            ("reconciliation_difference", money_str(diff) if diff is not None else None),
            ("reconciles", reconciles)]))

    # cost-code jsonl + csv
    cc_rows, cc_csv_rows = [], []
    cost_codes_sorted = sorted({cc for cc, _ in cc_month} | {key_meta[k][0] for k in key_meta if key_meta[k][0]})
    for cc in cost_codes_sorted:
        csv_row = OrderedDict([("cost_code", cc), ("cost_code_description", cc_desc.get(cc))])
        cc_total = ZERO
        for m in months:
            cell = cc_month.get((cc, m), {"amount": ZERO, "count": 0})
            cc_total += cell["amount"]
            cc_rows.append(OrderedDict([
                ("project_key", project_key), ("cost_code", cc),
                ("cost_code_description", cc_desc.get(cc)), ("month", m),
                ("actual_cost", money_str(cell["amount"])), ("entry_count", int(cell["count"])),
                ("actual_source", ACTUAL_SOURCE), ("actual_source_role", ACTUAL_SOURCE_ROLE),
                ("is_actual", True)]))
            csv_row[m] = money_str(cell["amount"])
        cc_csv_rows.append(csv_row)
        cc_seen_total[cc] = cc_total

    # project total jsonl
    proj_rows = [OrderedDict([
        ("project_key", project_key), ("month", m), ("actual_cost", money_str(proj_month[m]["amount"])),
        ("entry_count", int(proj_month[m]["count"])), ("actual_source", ACTUAL_SOURCE),
        ("actual_source_role", ACTUAL_SOURCE_ROLE), ("is_actual", True)]) for m in months]

    # reconciliation audit
    project_total = sum((proj_month[m]["amount"] for m in months), ZERO)
    bcode_grand = sum((D(r["exported_monthly_actuals_total"]) for r in bridge_rows), ZERO)
    cc_grand = sum(cc_seen_total.values(), ZERO)
    all_to_date_reconcile = all(r["reconciles"] for r in per_key_recon
                                if r["actual_cost_to_date"] is not None)
    audit = OrderedDict([
        ("project_key", project_key),
        ("actual_source", ACTUAL_SOURCE),
        ("month_axis", OrderedDict([("first_month", months[0] if months else None),
                                    ("last_month", months[-1] if months else None),
                                    ("month_count", len(months))])),
        ("canonical_budget_code_count", len(codes)),
        ("budget_code_monthly_total", money_str(bcode_grand)),
        ("cost_code_monthly_total", money_str(cc_grand)),
        ("project_monthly_total", money_str(project_total)),
        ("budget_code_equals_cost_code_total", abs(bcode_grand - cc_grand) <= CENTS),
        ("budget_code_equals_project_total", abs(bcode_grand - project_total) <= CENTS),
        ("all_codes_reconcile_to_actual_cost_to_date", bool(all_to_date_reconcile)),
        ("codes_with_to_date_variance",
         [r["budget_code_key"] for r in per_key_recon
          if r["actual_cost_to_date"] is not None and not r["reconciles"]]),
        ("per_budget_code", per_key_recon),
        ("rule", "monthly actuals are CostEntries/Sage only; Σ months per code == actual cost to date; "
                 "cost-code rollup == Σ its budget keys; project total == Σ all keys == Σ all months"),
    ])

    bcode_month_cols = list(months)
    return {
        "actuals_monthly_by_budget_code.jsonl": bcode_rows,
        "actuals_monthly_by_cost_code.jsonl": cc_rows,
        "actuals_monthly_project_total.jsonl": proj_rows,
        "actuals_to_forecast_bridge_by_budget_code.jsonl": bridge_rows,
        "actuals_monthly_by_budget_code.csv": {
            "fieldnames": ["budget_code_key", "cost_code", "cost_type", "budget_code_description",
                           *bcode_month_cols],
            "rows": bcode_csv_rows},
        "actuals_monthly_by_cost_code.csv": {
            "fieldnames": ["cost_code", "cost_code_description", *bcode_month_cols],
            "rows": cc_csv_rows},
        ACTUALS_AUDIT_FILE: audit,
    }


# --------------------------------------------------------------------------- write + validate + rec fields

def write_collections(out, collections: dict):
    """Write the seven actuals files (jsonl/json/csv) under ``out``."""
    from pathlib import Path
    out = Path(out)
    for fname in ACTUALS_FILES:
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        elif fname.endswith(".csv"):
            write_csv(out / fname, payload["fieldnames"], payload["rows"])
        else:
            write_json(out / fname, payload)


def validation_gates(collections, canonical_keys, contamination_ok: bool) -> "OrderedDict":
    """Fail-closed gate booleans for a package that emits the actuals export."""
    bcode = collections.get("actuals_monthly_by_budget_code.jsonl") or []
    audit = collections.get(ACTUALS_AUDIT_FILE) or {}
    csv = collections.get("actuals_monthly_by_budget_code.csv") or {"rows": []}
    keys_in_output = {r["budget_code_key"] for r in bcode}
    canonical = set(canonical_keys)
    return OrderedDict([
        ("actuals_monthly_by_budget_code_jsonl_present", bool(bcode)),
        ("actuals_monthly_by_budget_code_csv_present", bool(csv["rows"])),
        ("all_canonical_keys_in_actuals", canonical <= keys_in_output),
        ("no_non_canonical_keys_in_actuals", keys_in_output <= canonical),
        ("actuals_reconcile_to_actual_cost_to_date",
         bool(audit.get("all_codes_reconcile_to_actual_cost_to_date"))),
        ("actuals_project_total_reconciles",
         bool(audit.get("budget_code_equals_project_total") and audit.get("budget_code_equals_cost_code_total"))),
        ("actuals_source_is_costentries_only", bool(contamination_ok)),
    ])


ACTUALS_PLUS_FORECAST_DATA_FILES = (
    "actuals_plus_forecast_monthly_by_cost_code.csv",
    "actuals_plus_forecast_monthly_by_budget_code.csv",
)
ACTUALS_PLUS_FORECAST_AUDIT_FILE = "audit/actuals_plus_forecast_monthly_by_cost_code_audit.json"
ACTUALS_PLUS_FORECAST_FILES = ACTUALS_PLUS_FORECAST_DATA_FILES + (ACTUALS_PLUS_FORECAST_AUDIT_FILE,)


def build_actuals_plus_forecast(project_key, budget_codes, actuals_cc_rows, actuals_bc_rows,
                                integrated_monthly_rows, controlled=None) -> dict:
    """Combine historical CostEntries actuals (months < current forecast month) with the integrated
    comprehensive monthly forecast (current forecast month forward) into month-by-month matrices,
    collapsed to cost code (+ an optional budget-code traceability matrix). Pure + deterministic.

    Boundary rule: ``current_forecast_month`` = the earliest integrated forecast month; that month and
    all later months use the forecast even if an actual exists (no June-2026 actual leak). Months before
    it use CostEntries actuals only. This is an export/bridge — it changes no recommendation value.
    """
    # forecast months + boundary (package-derived; never the system date)
    fmonths = sorted({mc.get("forecast_month") for r in integrated_monthly_rows
                      for mc in (r.get("monthly_costs") or []) if mc.get("forecast_month")})
    current_forecast_month = fmonths[0] if fmonths else None

    # per-(cost_code, month) actuals (months < boundary) and forecast (months >= boundary)
    actual_cc, actual_bc = {}, {}
    cc_desc, bc_meta = OrderedDict(), OrderedDict()
    for r in actuals_cc_rows:
        actual_cc[(r["cost_code"], r["month"])] = D(r.get("actual_cost"))
        if r["cost_code"] not in cc_desc:
            cc_desc[r["cost_code"]] = r.get("cost_code_description")
    for r in actuals_bc_rows:
        actual_bc[(r["budget_code_key"], r["month"])] = D(r.get("actual_cost"))
        bc_meta[r["budget_code_key"]] = (r.get("cost_code"), r.get("cost_type"),
                                         r.get("budget_code_description"))
    forecast_cc, forecast_bc = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for r in integrated_monthly_rows:
        key, cc = r.get("budget_code_key"), r.get("cost_code")
        bc_meta.setdefault(key, (cc, None, None))
        for mc in (r.get("monthly_costs") or []):
            m, amt = mc.get("forecast_month"), D(mc.get("integrated_month_cost"))
            forecast_cc[(cc, m)] += amt
            forecast_bc[(key, m)] += amt

    # contiguous month axis across all actual + forecast months
    all_months = sorted({m for (_cc, m) in actual_cc} | set(fmonths))
    months = months_between(all_months[0], all_months[-1]) if all_months else []

    def _is_forecast(m):
        return current_forecast_month is not None and m >= current_forecast_month

    def _cc_cell(cc, m):
        return forecast_cc.get((cc, m), ZERO) if _is_forecast(m) else actual_cc.get((cc, m), ZERO)

    controlled = controlled or {}

    def _bc_cell(key, m):
        # Anti-double-count: for an operator-controlled key the current forecast-month combined cell is
        # the current-month actuals-to-date PLUS the current-month remaining forecast (counted once), so
        # the row sums to the controlled final cost without dropping or double counting current-month
        # actuals. All other cells follow the normal boundary rule.
        if key in controlled and current_forecast_month is not None and m == current_forecast_month:
            return actual_bc.get((key, m), ZERO) + forecast_bc.get((key, m), ZERO)
        return forecast_bc.get((key, m), ZERO) if _is_forecast(m) else actual_bc.get((key, m), ZERO)

    cost_codes = sorted({cc for (cc, _m) in actual_cc} | {cc for (cc, _m) in forecast_cc})
    budget_keys = sorted(set(bc_meta))

    cc_csv_rows, actual_total, forecast_total = [], ZERO, ZERO
    for cc in cost_codes:
        row = OrderedDict([("cost_code", cc)])
        for m in months:
            v = _cc_cell(cc, m)
            row[m] = money_str(v)
            if _is_forecast(m):
                forecast_total += v
            else:
                actual_total += v
        cc_csv_rows.append(row)

    bc_csv_rows = []
    for key in budget_keys:
        cc, cat, desc = bc_meta[key]
        row = OrderedDict([("budget_code_key", key), ("cost_code", cc), ("cost_type", cat),
                           ("budget_code_description", desc)])
        for m in months:
            row[m] = money_str(_bc_cell(key, m))
        bc_csv_rows.append(row)

    # reconciliation: actual side vs actuals jsonl (< boundary); forecast side vs integrated (>= boundary)
    actual_recon_src = sum((v for (cc, m), v in actual_cc.items() if not _is_forecast(m)), ZERO)
    forecast_recon_src = sum((v for (k, m), v in forecast_bc.items() if _is_forecast(m)), ZERO)
    actual_ok = abs(actual_total - actual_recon_src) <= CENTS
    forecast_ok = abs(forecast_total - forecast_recon_src) <= CENTS
    combined_total = actual_total + forecast_total
    months_sorted_ok = months == sorted(months)

    # operator-model-controlled target reconciliation: each controlled budget-code row must sum to its
    # controlled final cost, with current-month actuals counted exactly once (anti-double-count).
    controlled_recon = []
    for key in sorted(controlled):
        target = D(controlled[key].get("final"))
        actual_to_date = D(controlled[key].get("actual"))
        hist = sum((actual_bc.get((key, m), ZERO) for m in months if not _is_forecast(m)), ZERO)
        cur_actual = actual_bc.get((key, current_forecast_month), ZERO) if current_forecast_month else ZERO
        cur_remaining = forecast_bc.get((key, current_forecast_month), ZERO) if current_forecast_month else ZERO
        fsum = sum((forecast_bc.get((key, m), ZERO) for m in months if _is_forecast(m)), ZERO)
        row_total = sum((_bc_cell(key, m) for m in months), ZERO)
        reconciles = abs(row_total - target) <= CENTS
        controlled_recon.append(OrderedDict([
            ("budget_code_key", key), ("actual_cost_to_date", money_str(actual_to_date)),
            ("historical_actuals_used_in_combined_csv", money_str(hist)),
            ("current_month_actuals_included", money_str(cur_actual)),
            ("current_month_remaining_forecast", money_str(cur_remaining)),
            ("forecast_sum_used_in_combined_csv", money_str(fsum)),
            ("combined_csv_total", money_str(row_total)), ("target_final_cost", money_str(target)),
            ("current_month_basis", "current_month_actuals_added_to_remaining_forecast"),
            ("reconciles_to_target_final_cost", bool(reconciles))]))
    all_controlled_reconcile = all(r["reconciles_to_target_final_cost"] for r in controlled_recon)
    validation_passed = bool(actual_ok and forecast_ok and months_sorted_ok and all_controlled_reconcile)

    audit = OrderedDict([
        ("project_key", project_key),
        ("current_forecast_month", current_forecast_month),
        ("actual_month_start", months[0] if months else None),
        ("actual_month_end", add_months(current_forecast_month, -1) if current_forecast_month else
         (months[-1] if months else None)),
        ("forecast_month_start", current_forecast_month),
        ("forecast_month_end", fmonths[-1] if fmonths else None),
        ("cost_code_count", len(cost_codes)),
        ("budget_code_count", len(budget_keys)),
        ("month_columns", months),
        ("actual_source", ACTUAL_SOURCE),
        ("forecast_source", "forecast_comprehensive.integrated_monthly_forecast"),
        ("actual_total", money_str(actual_total)),
        ("forecast_total", money_str(forecast_total)),
        ("combined_total", money_str(combined_total)),
        ("actual_months_reconciled", bool(actual_ok)),
        ("forecast_months_reconciled", bool(forecast_ok)),
        ("month_columns_sorted", bool(months_sorted_ok)),
        ("boundary_rule", "months < current_forecast_month use CostEntries actuals; current month and "
                          "later use the integrated forecast (June-2026 actuals are not used). For an "
                          "operator-controlled key the current-month combined cell adds current-month "
                          "actuals-to-date to the current-month remaining forecast (counted once) so the "
                          "row sums to the controlled final cost."),
        ("controlled_target_reconciliation", controlled_recon),
        ("all_controlled_targets_reconcile", bool(all_controlled_reconcile)),
        ("validation_passed", validation_passed),
    ])
    return {
        "actuals_plus_forecast_monthly_by_cost_code.csv": {
            "fieldnames": ["cost_code", *months], "rows": cc_csv_rows},
        "actuals_plus_forecast_monthly_by_budget_code.csv": {
            "fieldnames": ["budget_code_key", "cost_code", "cost_type", "budget_code_description",
                           *months], "rows": bc_csv_rows},
        ACTUALS_PLUS_FORECAST_AUDIT_FILE: audit,
    }


def combined_validation_gates(collections) -> "OrderedDict":
    """Fail-closed gates for the combined actuals+forecast export (used by forecast_comprehensive)."""
    cc_csv = collections.get("actuals_plus_forecast_monthly_by_cost_code.csv") or {"rows": [], "fieldnames": []}
    audit = collections.get(ACTUALS_PLUS_FORECAST_AUDIT_FILE) or {}
    fields = cc_csv.get("fieldnames") or []
    month_cols = fields[1:]
    return OrderedDict([
        ("actuals_plus_forecast_cost_code_csv_present", bool(cc_csv.get("rows"))),
        ("actuals_plus_forecast_budget_code_csv_present",
         bool((collections.get("actuals_plus_forecast_monthly_by_budget_code.csv") or {}).get("rows"))),
        ("actuals_plus_forecast_audit_present", bool(audit)),
        ("actuals_plus_forecast_first_column_is_cost_code", fields[:1] == ["cost_code"]),
        ("actuals_plus_forecast_months_sorted", month_cols == sorted(month_cols)),
        ("actuals_plus_forecast_actual_side_reconciled", bool(audit.get("actual_months_reconciled"))),
        ("actuals_plus_forecast_forecast_side_reconciled", bool(audit.get("forecast_months_reconciled"))),
        ("actuals_plus_forecast_validation_passed", bool(audit.get("validation_passed"))),
    ])


def rec_row_fields(monthly_for_key: dict) -> "OrderedDict":
    """The five additive actuals fields for a forecast recommendation row (values unchanged)."""
    months = sorted(monthly_for_key or {})
    total = sum((monthly_for_key[m]["amount"] for m in months), ZERO)
    nonzero = [m for m in months if monthly_for_key[m]["amount"] != ZERO or monthly_for_key[m]["count"] > 0]
    latest = months[-1] if months else None
    latest_amt = monthly_for_key[latest]["amount"] if latest else ZERO
    return OrderedDict([
        ("actuals_monthly_total_to_date", money_str(total)),
        ("actuals_latest_month", latest),
        ("actuals_latest_month_amount", money_str(latest_amt)),
        ("actuals_month_count_nonzero", len(nonzero)),
        ("actuals_last_nonzero_month", nonzero[-1] if nonzero else None),
    ])
