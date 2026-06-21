"""Deterministic anomaly detection for external-forecast evaluation (Implementation Phase 4).

Flags follow plan section 11.3. Severity uses the CFR-style materiality gate ($25k AND 10%) and
tiers (critical/high/medium/low/informational). All findings are humanized + path-free. Findings
at severity ``medium`` or higher seed the human-review queue. Pure functions over the mapped rows,
the external-by-code map, and the loaded baselines — no I/O, no CFR import.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from hb_assistant.construction.analytics import forecast_external_baselines as bl
from hb_assistant.construction.analytics.forecast_external_metrics import to_decimal

MATERIALITY_ABSOLUTE = Decimal("25000")
MATERIALITY_PERCENT = Decimal("0.10")
HIGH_VALUE_THRESHOLD = Decimal("100000")
MOM_JUMP_RATIO = Decimal("3")

_REVIEW_SEVERITIES = {"critical", "high", "medium"}


def severity_for_gap(gap_abs: Decimal, base_value: Decimal) -> str:
    """Materiality-gated severity for a signed gap vs a baseline value."""
    mag = gap_abs.copy_abs()
    pct = (mag / base_value.copy_abs()) if base_value != 0 else Decimal(0)
    if mag < MATERIALITY_ABSOLUTE or pct < MATERIALITY_PERCENT:
        return "low"
    if mag >= Decimal("250000") and pct >= Decimal("0.25"):
        return "critical"
    if mag >= Decimal("100000") and pct >= Decimal("0.15"):
        return "high"
    return "medium"


def detect(
    mapped_rows: list[dict[str, Any]],
    unmapped_rows: list[dict[str, Any]],
    external_by_code: dict[str, Decimal],
    baselines: dict[str, dict[str, Decimal]],
    source_system: str | None = None,
    period: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []

    actuals = baselines.get(bl.BASELINE_ACTUALS) or {}
    erp = baselines.get(bl.BASELINE_ERP_JTD) or {}
    p50 = baselines.get(bl.BASELINE_MODEL_P50) or {}
    budget = baselines.get(bl.BASELINE_CURRENT_BUDGET) or {}

    # 1. External EAC below actuals-to-date (a forecast can never be below money already spent).
    for code in sorted(external_by_code):
        act = actuals.get(code)
        if act is not None and external_by_code[code] < act:
            findings.append(
                _f("external_below_actuals", "high", code,
                   "External forecast is below the actual cost already incurred.")
            )

    # 2. Negative remaining without an approved credit.
    for row in mapped_rows:
        rem = to_decimal(row.get("remaining"))
        if rem is not None and rem < 0:
            findings.append(
                _f("negative_remaining", "high", str(row.get("budget_code_key") or "") or None,
                   "Remaining cost is negative without an approved credit.")
            )

    # 3. Duplicate cost-code / month.
    pair_counts = Counter(
        (str(r.get("budget_code_key") or ""), str(r.get("month") or ""))
        for r in mapped_rows
        if r.get("budget_code_key")
    )
    for (code, _month), count in sorted(pair_counts.items()):
        if count > 1:
            findings.append(
                _f("duplicate_code_month", "medium", code or None,
                   "The same cost code and month appears more than once.")
            )

    # 4. Unmapped cost code (one per distinct raw label).
    for label in sorted({str(r.get("raw_label") or "") for r in unmapped_rows if r.get("raw_label")}):
        findings.append(
            _f("unmapped_code", "medium", None,
               f"Cost code could not be mapped to a known budget code: {label}.")
        )

    # 5. External materially below ERP job-to-date.
    findings.extend(_material_below(external_by_code, erp, "external_below_erp_jtd",
                                    "External forecast is materially below ERP job-to-date cost."))

    # 6. External materially below backend model P50.
    findings.extend(_material_below(external_by_code, p50, "external_below_model_p50",
                                    "External forecast is materially below the backend model P50."))

    # 7. Missing high-value cost code (a material budgeted code absent from the external forecast).
    for code in sorted(budget):
        if budget[code] >= HIGH_VALUE_THRESHOLD and code not in external_by_code:
            findings.append(
                _f("missing_high_value_code", "high", code,
                   "A high-value budgeted cost code is missing from the external forecast.")
            )

    # 8. Unexplained month-over-month jump (per code with >=3 monthly values).
    findings.extend(_mom_jumps(mapped_rows))

    # 9. Period not specified.
    if not period:
        findings.append(
            _f("period_not_specified", "informational", None,
               "The external forecast period was not specified.")
        )

    # 10. Manual source without a reviewer note.
    if (source_system or "").lower() == "manual" and not any(
        str(r.get("notes") or "").strip() for r in mapped_rows
    ):
        findings.append(
            _f("manual_without_note", "informational", None,
               "Manually-entered forecast has no reviewer note.")
        )

    review_items = [
        {
            "reason_code": f["flag_code"],
            "severity": f["severity"],
            "budget_code_key": f["budget_code_key"],
            "detail": f["message"],
            "status": "open",
        }
        for f in findings
        if f["severity"] in _REVIEW_SEVERITIES
    ]
    return {"anomaly_findings": findings, "review_items": review_items}


def _material_below(
    external: dict[str, Decimal], baseline: dict[str, Decimal], flag_code: str, message: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for code in sorted(set(external) & set(baseline)):
        diff = external[code] - baseline[code]
        if diff < 0:
            sev = severity_for_gap(diff, baseline[code])
            if sev != "low":
                out.append(_f(flag_code, sev, code, message))
    return out


def _mom_jumps(mapped_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code: dict[str, list[Decimal]] = {}
    for row in mapped_rows:
        code = str(row.get("budget_code_key") or "")
        val = to_decimal(row.get("value"))
        if code and val is not None:
            by_code.setdefault(code, []).append(val)
    out: list[dict[str, Any]] = []
    for code in sorted(by_code):
        vals = [v for v in by_code[code] if v > 0]
        if len(vals) >= 3:
            lo, hi = min(vals), max(vals)
            if lo > 0 and hi >= lo * MOM_JUMP_RATIO and (hi - lo) >= MATERIALITY_ABSOLUTE:
                out.append(
                    _f("mom_jump", "medium", code,
                       "An unexplained month-over-month jump was detected.")
                )
    return out


def _f(flag_code: str, severity: str, code: str | None, message: str) -> dict[str, Any]:
    return {
        "flag_code": flag_code,
        "severity": severity,
        "budget_code_key": code,
        "message": message,
    }
