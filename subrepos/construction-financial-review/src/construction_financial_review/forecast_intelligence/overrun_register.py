"""Overrun risk register: one row per budget code whose recommended final cost overruns.

Overrun is measured against current projected cost (the headline). Severity scales with the overrun
amount and percentage. The register also surfaces which other references (revised budget, committed
cost, owner SOV value) the recommended final cost breaches.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str

SEV_CRITICAL_ABS = Decimal("250000")
SEV_CRITICAL_PCT = Decimal("0.25")
SEV_HIGH_ABS = Decimal("100000")
SEV_HIGH_PCT = Decimal("0.15")


def _severity(amount: Decimal, pct) -> str:
    if pct is None:
        return "medium"
    if amount >= SEV_CRITICAL_ABS and pct >= SEV_CRITICAL_PCT:
        return "critical"
    if amount >= SEV_HIGH_ABS and pct >= SEV_HIGH_PCT:
        return "high"
    return "medium"


def build_register(recommendations: list, evidence_by_key: dict, confidence_by_key: dict,
                   project_key: str) -> list:
    rows = []
    for rec in recommendations:
        if not rec.get("overrun_projected"):
            continue
        key = rec["budget_code_key"]
        recommended = D(rec.get("recommended_final_cost"))
        projected = dec(rec.get("current_projected_cost"))
        amount = (recommended - projected) if projected is not None else recommended
        pct = (amount / projected) if (projected is not None and projected > 0) else None
        ev = evidence_by_key.get(key, {})
        cf = confidence_by_key.get(key, {})
        rows.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("budget_code_description", ev.get("budget_code_description")),
            ("recommended_final_cost", rec.get("recommended_final_cost")),
            ("worst_credible_final_cost", rec.get("worst_credible_final_cost")),
            ("current_projected_cost", rec.get("current_projected_cost")),
            ("overrun_amount", money_str(amount)),
            ("overrun_percent", str(pct.quantize(Decimal("0.0001"))) if pct is not None else None),
            ("severity", _severity(amount, pct)),
            ("overrun_basis", rec.get("overrun_basis")),
            ("forecast_direction", rec.get("forecast_direction")),
            ("overrun_vs_revised_budget", rec.get("overrun_vs_revised_budget")),
            ("overrun_vs_committed_cost", rec.get("overrun_vs_committed_cost")),
            ("overrun_vs_owner_scope_value", rec.get("overrun_vs_owner_scope_value")),
            ("schedule_association", ev.get("schedule_association")),
            ("trend_signal", ev.get("trend_signal")),
            ("primary_evidence", rec.get("primary_evidence")),
            ("confidence_band", cf.get("confidence_band")),
            ("limiting_data_gaps", rec.get("limiting_data_gaps")),
            ("requires_human_acceptance", True),
        ]))
    rows.sort(key=lambda r: (-D(r["overrun_amount"]), r["budget_code_key"]))
    return rows


def rank_top(register: list, n: int = 25) -> list:
    return register[:n]
