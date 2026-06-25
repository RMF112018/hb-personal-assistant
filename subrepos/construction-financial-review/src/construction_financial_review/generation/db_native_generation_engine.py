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

The DB-native financial spine does not carry ``erp_direct_costs`` / ``pending_cost_changes``, so the
projected-cost *formula* cannot reconcile; the cost-basis rules then honestly route committed-cost
codes to ``manual_review_required`` rather than synthesise a reconciled projected basis. This is the
intended conservative behaviour. See ADR 317.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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
        unsupported_outputs=dict(UNSUPPORTED_KIND_CODES),
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        provenance=_provenance(ctx),
    )


def _comprehensive_line(
    row: dict[str, Any], amounts: dict[str, Any], actual: Decimal, has_actuals: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute one budget-code forecast line by reusing the canonical cost-basis decision."""
    key = str(row.get("budget_code_key") or "")
    projected = dec(amounts.get("projected_costs"))
    eac = dec(amounts.get("estimated_cost_at_completion"))
    revised = dec(amounts.get("revised_budget"))

    # Existing-model proxy from the spine, floored to actuals (final must never fall below actual).
    baseline = projected or eac or revised or actual
    inbound_final = baseline if baseline > actual else actual
    inbound_ctc = inbound_final - actual
    if inbound_ctc < ZERO:
        inbound_ctc = ZERO

    # Only the fields the DB-native spine actually carries are handed to the cost-basis rules.
    # erp_direct_costs / pending_cost_changes are absent by design, so the projected-cost formula
    # cannot reconcile and committed-cost codes route to manual_review_required (honest).
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
        "budget_basis": {
            "projected_costs": amounts.get("projected_costs"),
            "estimated_cost_at_completion": amounts.get("estimated_cost_at_completion"),
            "revised_budget": amounts.get("revised_budget"),
            "committed_costs": amounts.get("committed_costs"),
        },
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
        unsupported_outputs={inp.generator_kind: code},
        warnings=(),
        blockers=(code,),
        provenance=_provenance(inp.context),
    )


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
