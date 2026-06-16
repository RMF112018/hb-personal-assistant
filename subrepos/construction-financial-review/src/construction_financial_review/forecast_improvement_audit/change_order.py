"""Priority 7 — change-order exposure evidence from the read-only SQLite DB.

Change orders carry no deterministic budget-code link (confirmed: the CO table has no cost-code column),
so exposure is mapped at the project / contract-family level only, with explicit ``mapping_confidence:
none``. Exposure is advisory evidence: pending CO is never treated as committed or actual; approved CO is
flagged for double-count against current projected cost / commitments (which already reflect approved
COs). Nothing here becomes a cap or an actual cost.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from ..forecast_comprehensive import human_acceptance as ha

ZERO = Decimal("0")


def classify(status, executed) -> str:
    s = (status or "").strip().lower()
    ex = str(executed) in ("1", "True", "true")
    if s == "void":
        return "void_rejected"
    if s == "approved":
        return "approved_executed" if ex else "pending_unsigned"
    if s == "pending":
        return "potential_unapproved"
    if s == "draft":
        return "potential_unapproved"
    return "unknown_status"


def build(inputs: dict, cfg: dict):
    """Return (exposure_rows, project_summary, gaps)."""
    project_key = inputs["project_key"]
    db = inputs["db"]
    gaps = []
    if not db.get("db_present"):
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_7_change_order_exposure"),
            ("gap_type", "sqlite_db_absent"),
            ("detail", "local SQLite DB not present; change-order exposure skipped"),
            ("requires_human_acceptance", True)]))
        return [], OrderedDict([("db_present", False)]), gaps

    rows = []
    by_class = Counter()
    class_totals = {}
    for co in db["change_orders"]:
        cls = classify(co.get("status"), co.get("executed"))
        amt = D(co.get("grand_total"))
        by_class[cls] += 1
        class_totals[cls] = class_totals.get(cls, ZERO) + amt
        # approved/executed exposure is typically already inside current projected cost + commitments
        double_count_risk = cls == "approved_executed"
        row = OrderedDict([
            ("project_key", project_key),
            ("change_order_record_key", co.get("record_key")),
            ("change_order_number", co.get("number")),
            ("change_order_family", co.get("change_order_family")),
            ("contract_record_key", co.get("contract_record_key")),
            ("source_status", co.get("status")),
            ("executed", co.get("executed")),
            ("paid", co.get("paid")),
            ("exposure_class", cls),
            ("grand_total", money_str(amt)),
            ("schedule_impact_amount", money_str(co.get("schedule_impact_amount"))),
            ("mapped_budget_code_key", None),
            ("mapping_confidence", "none"),
            ("exposure_level", "project_or_contract_family"),
            ("mapping_basis", "CO table carries no deterministic cost-code/budget-code link"),
            ("is_actual_cost", False),
            ("is_committed", cls == "approved_executed"),
            ("double_count_risk_vs_current_projected_cost", bool(double_count_risk)),
            ("double_count_basis", "approved+executed COs are already reflected in current projected cost "
                                   "and committed cost; do not add again" if double_count_risk
             else "pending/draft/void exposure is net-new advisory context, not yet committed"),
            ("note", "advisory exposure evidence; never an actual cost; never a cap"),
        ])
        rows.append(ha.stamp(row))
    rows.sort(key=lambda r: (r["exposure_class"], r["change_order_record_key"] or ""))

    summary = OrderedDict([
        ("project_key", project_key), ("db_present", True),
        ("change_order_count", len(rows)),
        ("by_exposure_class", OrderedDict((k, by_class[k]) for k in sorted(by_class))),
        ("amount_by_exposure_class", OrderedDict(
            (k, money_str(class_totals[k])) for k in sorted(class_totals))),
        ("attribution", "project / contract-family level only; no per-budget-code attribution available"),
        ("double_count_note", "approved_executed totals already reflected in current projected cost + "
                              "commitments; pending/potential exposure is net-new advisory context"),
        ("requires_human_acceptance", True),
    ])
    if any(r["exposure_class"] == "unknown_status" for r in rows):
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_7_change_order_exposure"),
            ("gap_type", "unknown_change_order_status"),
            ("detail", "one or more change orders have a status outside {approved,pending,draft,void}"),
            ("requires_human_acceptance", True)]))
    gaps.append(OrderedDict([
        ("project_key", project_key), ("improvement", "priority_7_change_order_exposure"),
        ("gap_type", "no_budget_code_mapping"),
        ("detail", "change orders cannot be deterministically mapped to budget codes from the DB; "
                   "exposure reported at project/family level with mapping_confidence=none"),
        ("requires_human_acceptance", True)]))
    return rows, summary, gaps
