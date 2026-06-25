"""Package-free DB-native forecast generation engine (Phase E).

``generate_db_native_forecast(inp)`` consumes a Phase D ``DbNativeForecastContext`` and produces a
typed ``DbNativeForecastResult`` deterministically and in-memory — with NO source/context/analysis
package files, NO run-lineage resolution, NO package workflows, and NO ``hb_assistant`` import.

Supported generator kind:
  * ``comprehensive`` — financial-spine-only forecast. Per budget code it maps the spine's budget
    amounts + actuals into the canonical :mod:`forecast_cost_basis` ``classify``/``apply`` inputs and
    reuses the established rules (actuals floor, asymmetric raise, dormancy suppression, manual-review
    on a non-reconciling formula). Owner / Procore / owner-crosswalk evidence is NOT yet DB-native,
    so it is not used and is disclosed as an explicit ``available=false`` warning.

Unsupported kinds (honest terminal state — never fabricate values):
  * ``monthly``        -> ``db_native_monthly_requires_phasing_signals``
  * ``probability``    -> ``db_native_probability_requires_monte_carlo_inputs``
  * ``model_controls`` -> ``db_native_model_controls_requires_operator_config``

Cost-basis inputs (Phase E2): when the per-code ``cost_basis_inputs`` block is available (DB-native
BudgetDetails formula fields ``committed_costs``/``erp_direct_costs``/``pending_cost_changes``/
``projected_costs`` selected upstream from the structured Procore table), the engine feeds them to the
canonical rules with Procore EAC as the pre-basis model baseline — so a reconciling formula whose
``projected_costs`` exceeds EAC reaches ``budgetdetails_projected_cost_basis`` (the asymmetric raise),
and a non-reconciling formula routes to ``manual_review_required``. When that block is unavailable, the
engine falls back to the v59 spine amounts, which carry no ``erp_direct_costs``/``pending_cost_changes``
— so the formula cannot reconcile and committed-cost codes route to ``manual_review_required`` (the
Phase E behaviour). See ADR 317 (engine) and ADR 318 (BudgetDetails cost-basis inputs).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any

from ..common.money import dec, money_str
from ..context.db_native_context_builder import DbNativeForecastContext
from ..forecast_cost_basis.apply import apply_cost_basis_decision
from ..forecast_cost_basis.classify import (
    STATUS_BUDGETDETAILS_PROJECTED,
    STATUS_MANUAL_REVIEW,
    STATUS_SUPPRESSED_NO_REMAINING,
)

ZERO = Decimal("0")
CENTS = Decimal("0.01")

SCHEMA_VERSION = 1
ENGINE_VERSION = "db_native_generation_engine/1"
GENERATION_SCOPE = "financial_spine_db_native"

# Result statuses (overall).
STATUS_GENERATED = "generated"
STATUS_GENERATED_DEGRADED = "generated_degraded"
STATUS_UNSUPPORTED = "unsupported"
STATUS_INSUFFICIENT_BASIS = "insufficient_basis"

# Result-level codes.
CODE_GENERATED = "db_native_forecast_generated"
CODE_INSUFFICIENT_BASIS = "db_native_insufficient_financial_basis"
CODE_UNKNOWN_KIND = "db_native_unknown_generator_kind"

# Per-kind unsupported codes (curated, specific to the missing input family).
UNSUPPORTED_KIND_CODES = {
    "monthly": "db_native_monthly_requires_phasing_signals",
    "probability": "db_native_probability_requires_monte_carlo_inputs",
    "model_controls": "db_native_model_controls_requires_operator_config",
}

_SUPPORTED_KIND = "comprehensive"

# Monthly phasing (within a comprehensive output): a deterministic even-spread of each budget code's
# forecast_cost_to_complete across the future window (NOT schedule-weighted). When the operator does
# not supply ``forecast_end_date`` — or the window yields no usable future horizon / boundary — the
# monthly output is omitted honestly (no fabricated rows) and the reason is surfaced via
# ``unsupported_outputs["monthly"]`` + a warning. Schedule-weighted phasing is a later patch.
MONTHLY_EVEN_SPREAD_DISCLOSURE = "db_native_monthly_even_spread_not_schedule_weighted"
MONTHLY_NO_SOURCE_ACTUALS_WARNING = "db_native_monthly_no_source_actuals_in_window"
MONTHLY_NO_END_DATE = "db_native_monthly_requires_forecast_end_date"
MONTHLY_NO_FUTURE_HORIZON = "db_native_monthly_no_future_horizon"
MONTHLY_NO_BOUNDARY_ANCHOR = "db_native_monthly_no_boundary_anchor"
MONTHLY_RECONCILIATION_FAILED = "db_native_monthly_reconciliation_failed"

# Kinds that stay unsupported even inside a comprehensive output (monthly is added conditionally).
_COMPREHENSIVE_UNSUPPORTED = {
    "probability": UNSUPPORTED_KIND_CODES["probability"],
    "model_controls": UNSUPPORTED_KIND_CODES["model_controls"],
}

# Per-code row state for a budget code with no usable basis (no budget amounts AND no actuals).
_ROW_STATUS_OK = "ok"
_ROW_STATUS_DEGRADED = "degraded_no_basis"
_ROW_BASIS_INSUFFICIENT = "insufficient_row_basis"

# Spine budget-amount fields surfaced as the disclosed budget basis for each line.
_BUDGET_AMOUNT_FIELDS = (
    "original_budget_amount",
    "revised_budget",
    "approved_cos",
    "pending_budget_changes",
    "projected_budget",
    "projected_costs",
    "committed_costs",
    "estimated_cost_at_completion",
)

# Owner/Procore/crosswalk evidence is not DB-native; comprehensive output is financial-spine-only.
_FINANCIAL_SPINE_ONLY_WARNING = "owner_procore_crosswalk_evidence_unavailable_financial_spine_only"

_MESSAGES = {
    STATUS_GENERATED: "DB-native financial-spine forecast generated.",
    STATUS_GENERATED_DEGRADED: (
        "DB-native financial-spine forecast generated with degraded confidence "
        "(sparse maturity or incomplete per-code basis)."
    ),
    STATUS_INSUFFICIENT_BASIS: (
        "DB-native forecast could not be generated: no usable financial basis for any budget code."
    ),
}
_UNSUPPORTED_MESSAGES = {
    "monthly": (
        "Monthly forecast is not available on the DB-native path: the required phasing/trend "
        "signals are not yet represented as DB-native inputs."
    ),
    "probability": (
        "Probability forecast is not available on the DB-native path: the required Monte-Carlo "
        "simulation inputs are not yet represented as DB-native inputs."
    ),
    "model_controls": (
        "Model-controls forecast is not available on the DB-native path: operator model-control "
        "configuration is not yet represented as DB-native inputs."
    ),
}


@dataclass(frozen=True)
class DbNativeGenerationEngineInput:
    """Path-free engine input: the requested kind + window + the Phase D financial-spine context."""

    project_key: str
    generator_kind: str
    forecast_window: dict[str, Any]
    context: DbNativeForecastContext


@dataclass(frozen=True)
class DbNativeForecastResult:
    """Typed, in-memory, redaction-safe DB-native forecast result. ``public()`` is the contract."""

    project_key: str
    generator_kind: str
    status: str
    result_code: str
    message: str
    generation_scope: str
    forecast_window: dict[str, Any]
    maturity: dict[str, Any]
    confidence: dict[str, Any]
    forecast_lines: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    assumptions: tuple[dict[str, Any], ...]
    risks: tuple[dict[str, Any], ...]
    monthly: tuple[dict[str, Any], ...]
    unsupported_outputs: dict[str, Any]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    provenance: dict[str, Any]

    def public(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "project_key": self.project_key,
            "generator_kind": self.generator_kind,
            "status": self.status,
            "result_code": self.result_code,
            "message": self.message,
            "generation_scope": self.generation_scope,
            "forecast_window": dict(self.forecast_window),
            "maturity": dict(self.maturity),
            "confidence": dict(self.confidence),
            "forecast_lines": [dict(r) for r in self.forecast_lines],
            "summary": dict(self.summary),
            "assumptions": [dict(r) for r in self.assumptions],
            "risks": [dict(r) for r in self.risks],
            "monthly": [dict(r) for r in self.monthly],
            "unsupported_outputs": dict(self.unsupported_outputs),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "provenance": dict(self.provenance),
        }


def generate_db_native_forecast(inp: DbNativeGenerationEngineInput) -> DbNativeForecastResult:
    """Dispatch on ``generator_kind``; only ``comprehensive`` produces financial-spine output."""
    kind = inp.generator_kind
    if kind == _SUPPORTED_KIND:
        return _generate_comprehensive(inp)
    if kind in UNSUPPORTED_KIND_CODES:
        return _unsupported(inp, UNSUPPORTED_KIND_CODES[kind], _UNSUPPORTED_MESSAGES[kind])
    return _unsupported(
        inp,
        CODE_UNKNOWN_KIND,
        f"Unknown generator kind '{kind}' is not supported on the DB-native path.",
    )


def _generate_comprehensive(inp: DbNativeGenerationEngineInput) -> DbNativeForecastResult:
    ctx = inp.context
    readiness = dict(ctx.readiness or {})
    warnings: list[str] = list((ctx.data_quality or {}).get("warnings") or [])
    warnings.append(_FINANCIAL_SPINE_ONLY_WARNING)

    lines: list[dict[str, Any]] = []
    assumptions: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    forecast_ctc_by_key: dict[str, Decimal] = {}
    total_final = ZERO
    total_ctc = ZERO
    total_actual = ZERO
    total_revised = ZERO
    value_line_count = 0
    degraded_count = 0

    # budget_code_context is already deterministically sorted by budget_code_key (Phase D).
    for row in ctx.budget_code_context:
        amounts = dict(row.get("budget_amounts") or {})
        actuals = dict(row.get("actuals") or {})
        actual = dec(actuals.get("actual_cost_to_date")) or ZERO
        entry_count = int(actuals.get("actual_entry_count") or 0)

        has_budget_basis = any(amounts.get(f) is not None for f in _BUDGET_AMOUNT_FIELDS)
        has_actuals = entry_count > 0

        if not has_budget_basis and not has_actuals:
            # Honest coded degraded row — no fabricated forecast value.
            degraded_count += 1
            lines.append(_degraded_line(row, actual))
            continue

        line, decision = _comprehensive_line(row, amounts, actual, has_actuals)
        lines.append(line)
        value_line_count += 1

        new_final = dec(line["forecast_final_cost"]) or ZERO
        new_ctc = dec(line["forecast_cost_to_complete"]) or ZERO
        revised = dec(amounts.get("revised_budget"))
        total_final += new_final
        total_ctc += new_ctc
        forecast_ctc_by_key[line["budget_code_key"]] = new_ctc
        total_actual += actual
        if revised is not None:
            total_revised += revised

        assumptions.append(
            {
                "scope": "budget_code",
                "budget_code_key": line["budget_code_key"],
                "code": decision["cost_basis_status"],
                "reason": list(decision.get("reason") or []),
            }
        )
        risks.extend(_line_risks(line, decision, revised, new_final))

    # Monthly phasing (window-bounded actuals + even-spread forecast). Omitted honestly when no
    # forecast_end_date / no usable horizon — monthly is then disclosed as unsupported for this output.
    monthly_rows, monthly_supported, monthly_reason, monthly_warnings = _build_monthly(
        ctx, dict(inp.forecast_window or {}), forecast_ctc_by_key
    )
    unsupported = dict(_COMPREHENSIVE_UNSUPPORTED)
    if monthly_supported:
        warnings.extend(monthly_warnings)
    else:
        unsupported["monthly"] = monthly_reason
        warnings.append(monthly_reason or MONTHLY_NO_END_DATE)

    warnings = _dedup(warnings)
    blockers: list[str] = []

    if value_line_count == 0:
        status = STATUS_INSUFFICIENT_BASIS
        result_code = CODE_INSUFFICIENT_BASIS
        blockers.append(CODE_INSUFFICIENT_BASIS)
    elif bool(readiness.get("sparse")) or degraded_count > 0:
        status = STATUS_GENERATED_DEGRADED
        result_code = CODE_GENERATED
    else:
        status = STATUS_GENERATED
        result_code = CODE_GENERATED

    summary = {
        "budget_code_count": len(ctx.budget_codes),
        "valued_budget_code_count": value_line_count,
        "degraded_budget_code_count": degraded_count,
        "total_forecast_final_cost": money_str(total_final),
        "total_cost_to_complete": money_str(total_ctc),
        "total_actual_cost_to_date": money_str(total_actual),
        "total_revised_budget": money_str(total_revised),
        "variance_to_budget": money_str(total_final - total_revised),
    }

    return DbNativeForecastResult(
        project_key=ctx.project_key,
        generator_kind=inp.generator_kind,
        status=status,
        result_code=result_code,
        message=_MESSAGES[status],
        generation_scope=GENERATION_SCOPE,
        forecast_window=dict(inp.forecast_window or {}),
        maturity=_maturity_block(readiness),
        confidence=_confidence_block(readiness),
        forecast_lines=tuple(lines),
        summary=summary,
        assumptions=tuple(assumptions),
        risks=tuple(risks),
        monthly=tuple(monthly_rows),
        unsupported_outputs=unsupported,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        provenance=_provenance(ctx),
    )


def _comprehensive_line(
    row: dict[str, Any], amounts: dict[str, Any], actual: Decimal, has_actuals: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute one budget-code forecast line by reusing the canonical cost-basis decision."""
    key = str(row.get("budget_code_key") or "")
    revised = dec(amounts.get("revised_budget"))
    cbi = row.get("cost_basis_inputs") or {}

    if cbi.get("available"):
        # Phase E2: real DB-native BudgetDetails formula inputs drive the canonical decision. The
        # model baseline is Procore EAC (the pre-basis model estimate) so the asymmetric raise can
        # fire when projected_costs (committed + erp_direct + pending_cost_changes) exceeds it.
        eac = dec(cbi.get("estimated_cost_at_completion"))
        baseline = _first_present(
            eac,
            dec(cbi.get("projected_costs")),
            dec(amounts.get("estimated_cost_at_completion")),
            revised,
        )
        evidence = {
            "budget_code_key": key,
            "cost_code": row.get("cost_code"),
            "category": row.get("category"),
            "committed_costs": cbi.get("committed_costs"),
            "erp_direct_costs": cbi.get("erp_direct_costs"),
            "pending_cost_changes": cbi.get("pending_cost_changes"),
            "projected_costs": cbi.get("projected_costs"),
            "commitment_invoiced": cbi.get("commitment_invoiced"),
            "estimated_cost_at_completion": cbi.get("estimated_cost_at_completion"),
            "has_recent_actual_activity": has_actuals,
        }
        budget_basis = {
            "committed_costs": cbi.get("committed_costs"),
            "erp_direct_costs": cbi.get("erp_direct_costs"),
            "pending_cost_changes": cbi.get("pending_cost_changes"),
            "projected_costs": cbi.get("projected_costs"),
            "estimated_cost_at_completion": cbi.get("estimated_cost_at_completion"),
            "commitment_invoiced": cbi.get("commitment_invoiced"),
            "formula_reconciles": cbi.get("formula_reconciles"),
        }
        cost_basis_source = "db_native_budgetdetails"
    else:
        # Phase E fallback: the v59 spine carries no erp_direct_costs / pending_cost_changes, so the
        # projected-cost formula cannot reconcile and committed-cost codes route to manual_review.
        baseline = (
            dec(amounts.get("projected_costs"))
            or dec(amounts.get("estimated_cost_at_completion"))
            or revised
            or actual
        )
        evidence = {
            "budget_code_key": key,
            "cost_code": row.get("cost_code"),
            "category": row.get("category"),
            "committed_costs": amounts.get("committed_costs"),
            "projected_costs": amounts.get("projected_costs"),
            "revised_budget": amounts.get("revised_budget"),
            "estimated_cost_at_completion": amounts.get("estimated_cost_at_completion"),
            "has_recent_actual_activity": has_actuals,
        }
        budget_basis = {
            "projected_costs": amounts.get("projected_costs"),
            "estimated_cost_at_completion": amounts.get("estimated_cost_at_completion"),
            "revised_budget": amounts.get("revised_budget"),
            "committed_costs": amounts.get("committed_costs"),
        }
        cost_basis_source = "spine_budget_amounts"

    if baseline is None:
        baseline = actual
    inbound_final = baseline if baseline > actual else actual
    inbound_ctc = inbound_final - actual
    if inbound_ctc < ZERO:
        inbound_ctc = ZERO

    new_final, new_ctc, decision = apply_cost_basis_decision(
        inbound_final, inbound_ctc, actual, evidence
    )

    # Defensive money safety on the engine boundary (the rules already honour this).
    if new_final < actual:
        new_final = actual
    new_ctc = new_final - actual
    if new_ctc < ZERO:
        new_ctc = ZERO

    status = str(decision["cost_basis_status"])
    line = {
        "budget_code_key": key,
        "cost_code": row.get("cost_code"),
        "category": row.get("category"),
        "actual_cost_to_date": money_str(actual),
        "budget_basis": budget_basis,
        "cost_basis_source": cost_basis_source,
        "cost_basis_classification": status,
        "forecast_final_cost": money_str(new_final),
        "forecast_cost_to_complete": money_str(new_ctc),
        "variance_to_budget": (money_str(new_final - revised) if revised is not None else None),
        "confidence": _line_confidence(status, has_actuals),
        "method_code": status,
        "reason_codes": list(decision.get("reason") or []),
        "row_status": _ROW_STATUS_OK,
    }
    return line, decision


def _degraded_line(row: dict[str, Any], actual: Decimal) -> dict[str, Any]:
    """A coded degraded line for a budget code with no usable basis — no fabricated values."""
    return {
        "budget_code_key": str(row.get("budget_code_key") or ""),
        "cost_code": row.get("cost_code"),
        "category": row.get("category"),
        "actual_cost_to_date": money_str(actual),
        "budget_basis": dict.fromkeys(
            ("projected_costs", "estimated_cost_at_completion", "revised_budget", "committed_costs")
        ),
        "cost_basis_classification": _ROW_BASIS_INSUFFICIENT,
        "forecast_final_cost": None,
        "forecast_cost_to_complete": None,
        "variance_to_budget": None,
        "confidence": "none",
        "method_code": _ROW_BASIS_INSUFFICIENT,
        "reason_codes": ["no_budget_basis_and_no_actuals"],
        "row_status": _ROW_STATUS_DEGRADED,
    }


def _line_risks(
    line: dict[str, Any], decision: dict[str, Any], revised: Decimal | None, new_final: Decimal
) -> list[dict[str, Any]]:
    """Conservative spine-only risk flags: budget overrun exposure and manual-review needs."""
    out: list[dict[str, Any]] = []
    key = line["budget_code_key"]
    if revised is not None and new_final > revised:
        out.append(
            {
                "budget_code_key": key,
                "risk_type": "forecast_exceeds_revised_budget",
                "severity": "warning",
                "variance_to_budget": money_str(new_final - revised),
            }
        )
    if decision.get("cost_basis_status") == STATUS_MANUAL_REVIEW:
        out.append(
            {
                "budget_code_key": key,
                "risk_type": "cost_basis_manual_review_required",
                "severity": "info",
                "reason": list(decision.get("reason") or []),
            }
        )
    return out


def _line_confidence(status: str, has_actuals: bool) -> str:
    """Conservative per-line confidence. Owner/Procore evidence is unavailable, so never 'high'."""
    if status == STATUS_MANUAL_REVIEW:
        return "low"
    if status in (STATUS_SUPPRESSED_NO_REMAINING,):
        return "medium"
    if status == STATUS_BUDGETDETAILS_PROJECTED:
        return "medium"
    # existing_model_basis and other pass-throughs.
    return "medium" if has_actuals else "low"


def _maturity_block(readiness: dict[str, Any]) -> dict[str, Any]:
    """HB-authoritative maturity surfaced from the context readiness (never recomputed here)."""
    return {
        "tier": readiness.get("forecast_maturity"),
        "readiness_status": readiness.get("readiness_status"),
        "initial_forecast": readiness.get("initial_forecast"),
        "prior_forecast_available": readiness.get("prior_forecast_available"),
        "sparse": bool(readiness.get("sparse")),
    }


def _confidence_block(readiness: dict[str, Any]) -> dict[str, Any]:
    """Project-level confidence: the HB-authoritative level, capped to financial-spine scope."""
    return {
        "level": readiness.get("confidence_level"),
        "basis_scope": GENERATION_SCOPE,
        "forecast_basis": readiness.get("forecast_basis"),
        "basis_limitations": list(readiness.get("basis_limitations") or []),
        "note": "owner_procore_evidence_unavailable_confidence_not_elevated",
    }


def _provenance(ctx: DbNativeForecastContext) -> dict[str, Any]:
    prov = dict(ctx.provenance or {})
    prov["engine_version"] = ENGINE_VERSION
    return prov


def _unsupported(
    inp: DbNativeGenerationEngineInput, code: str, message: str
) -> DbNativeForecastResult:
    """An honest unsupported result for a kind whose required inputs are not yet DB-native."""
    readiness = dict(inp.context.readiness or {})
    return DbNativeForecastResult(
        project_key=inp.context.project_key,
        generator_kind=inp.generator_kind,
        status=STATUS_UNSUPPORTED,
        result_code=code,
        message=message,
        generation_scope=GENERATION_SCOPE,
        forecast_window=dict(inp.forecast_window or {}),
        maturity=_maturity_block(readiness),
        confidence=_confidence_block(readiness),
        forecast_lines=(),
        summary={},
        assumptions=(),
        risks=(),
        monthly=(),
        unsupported_outputs={inp.generator_kind: code},
        warnings=(),
        blockers=(code,),
        provenance=_provenance(inp.context),
    )


def _first_present(*values: Decimal | None) -> Decimal | None:
    """First non-None Decimal (so a real ``0.00`` is honoured, unlike ``a or b``)."""
    for value in values:
        if value is not None:
            return value
    return None


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _month(value: Any) -> str | None:
    """Canonical ``YYYY-MM`` from a date/month string (``None``/empty -> None)."""
    text = str(value)[:7] if value else ""
    return text or None


def _next_month(ym: str) -> str:
    """The ``YYYY-MM`` immediately after ``ym`` (zero-padded, so string ordering stays monotonic)."""
    year, month = int(ym[:4]), int(ym[5:7])
    return f"{year + 1:04d}-01" if month == 12 else f"{year:04d}-{month + 1:02d}"


def _months_between(after_exclusive: str, end_inclusive: str) -> list[str]:
    """Contiguous ``YYYY-MM`` months strictly after ``after_exclusive`` through ``end_inclusive``."""
    out: list[str] = []
    cur = _next_month(after_exclusive)
    while cur <= end_inclusive:
        out.append(cur)
        cur = _next_month(cur)
    return out


def _spread(ctc: Decimal, months: list[str]) -> list[tuple[str, Decimal]]:
    """Even-spread ``ctc`` (>= 0) across ``months`` in cents; the rounding residual lands on the
    final month so the per-code sum equals ``ctc`` exactly."""
    n = len(months)
    base = (ctc / n).quantize(CENTS, rounding=ROUND_DOWN)
    out = [(m, base) for m in months]
    residual = ctc - base * n
    last_month, last_value = out[-1]
    out[-1] = (last_month, last_value + residual)
    return out


def _build_monthly(
    ctx: DbNativeForecastContext,
    window: dict[str, Any],
    forecast_ctc_by_key: dict[str, Decimal],
) -> tuple[list[dict[str, Any]], bool, str | None, list[str]]:
    """Window-bounded actual rows + even-spread forecast rows for a comprehensive output.

    Returns ``(rows, supported, degrade_code, warnings)``. When ``supported`` is False the monthly
    output is omitted (no rows) and ``degrade_code`` explains why honestly; the caller surfaces it via
    ``unsupported_outputs["monthly"]``. Each row is ``{budget_code_key, month (YYYY-MM), value
    (canonical money), is_actual (0/1)}``.

    Actual rows are bounded to the requested window ``[actual_lo, actual_hi]`` so a narrower selected
    window never drags in stale source actuals; forecast rows begin strictly after the effective actual
    boundary (the latest *included* actual month, or the cut-off when no actuals are included) and run
    through ``forecast_end_date``.
    """
    end_month = _month(window.get("forecast_end_date"))
    if not end_month:
        return [], False, MONTHLY_NO_END_DATE, []

    start_month = _month(window.get("forecast_start_date"))
    cutoff_month = _month(window.get("forecast_cutoff_date"))

    # Per-code aggregated actuals by month (sum across ``type``), plus the global source span.
    agg: dict[str, dict[str, Decimal]] = {}
    source_months: list[str] = []
    for row in ctx.budget_code_context:
        key = str(row.get("budget_code_key") or "")
        for entry in (dict(row.get("actuals") or {}).get("monthly_actuals") or []):
            month = _month(entry.get("month"))
            amount = dec(entry.get("amount"))
            if month is None or amount is None:
                continue
            source_months.append(month)
            agg.setdefault(key, {})
            agg[key][month] = agg[key].get(month, ZERO) + amount

    actual_lo = start_month or (min(source_months) if source_months else None)
    actual_hi = cutoff_month or (max(source_months) if source_months else None)

    rows: list[dict[str, Any]] = []
    boundary: str | None = None
    if actual_lo is not None and actual_hi is not None and actual_lo <= actual_hi:
        for key in sorted(agg):
            for month in sorted(agg[key]):
                if month < actual_lo or month > actual_hi:
                    continue
                rows.append(
                    {
                        "budget_code_key": key,
                        "month": month,
                        "value": money_str(agg[key][month]),
                        "is_actual": 1,
                    }
                )
                if boundary is None or month > boundary:
                    boundary = month

    had_actuals = bool(rows)
    if boundary is None:
        # No actuals fell inside the window; anchor the forecast start on the cut-off when supplied.
        boundary = cutoff_month
    if boundary is None:
        return [], False, MONTHLY_NO_BOUNDARY_ANCHOR, []

    future_months = _months_between(boundary, end_month)
    if not future_months:
        return [], False, MONTHLY_NO_FUTURE_HORIZON, []

    for key in sorted(forecast_ctc_by_key):
        ctc = forecast_ctc_by_key[key]
        if ctc <= ZERO:
            continue
        spread = _spread(ctc, future_months)
        if sum((value for _, value in spread), ZERO) != ctc:
            return [], False, MONTHLY_RECONCILIATION_FAILED, []
        for month, value in spread:
            rows.append(
                {
                    "budget_code_key": key,
                    "month": month,
                    "value": money_str(value),
                    "is_actual": 0,
                }
            )

    warnings = [] if had_actuals else [MONTHLY_NO_SOURCE_ACTUALS_WARNING]
    warnings.append(MONTHLY_EVEN_SPREAD_DISCLOSURE)
    rows.sort(key=lambda r: (r["budget_code_key"], r["month"], r["is_actual"]))
    return rows, True, None, warnings
