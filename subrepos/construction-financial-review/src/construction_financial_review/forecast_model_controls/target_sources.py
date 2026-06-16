"""Resolve a control's selected ``reference_source`` into a concrete reference value.

Each value-constrained control names a ``reference_source`` from the approved vocabulary (section 7).
This module turns that selection into a single ``resolved_reference_value`` (Decimal, a *total* reference
value) plus full lineage (which package/file/field supplied it), and fails closed when the value is
missing, ambiguous, or circular. The value-constraint policy (equal / cap / floor / explicit) is applied
in ``apply.py`` — this module only selects + validates the reference.

It is deliberately agnostic of source-package nesting: the caller assembles a per-key ``key_ctx`` bundle
(extracted amounts + intelligence final + prior-comprehensive final + lineage) and this module only
selects + validates.

Fail-closed rules:
- A missing selected reference value fails closed (``missing = True``).
- ``projected_budget`` is an alias for ``projected_costs``; if a *distinct* literal ``projected_budget``
  field ever appears with a different value, emit ambiguity and fail closed (never silently alias).
- ``prior_comprehensive_integrated_final`` is allowed only when it references a *prior* package — never
  the run currently being generated (circular -> fail closed).
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.money import dec, money_str
from . import control_schema as cs

# Default source field per vocabulary entry (operator may override via reference_field).
DEFAULT_FIELD = {
    cs.RS_ORIGINAL_BUDGET: "original_budget_amount",
    cs.RS_REVISED_BUDGET: "revised_budget",
    cs.RS_PROJECTED_BUDGET: "projected_costs",
    cs.RS_PROJECTED_COST: "projected_costs",
    cs.RS_COMMITTED_COST: "committed_costs",
    cs.RS_ACCEPTED_INTEL_FINAL: "recommended_final_cost",
    cs.RS_PRIOR_COMPREHENSIVE_FINAL: "integrated_recommended_final_cost",
}

_CONTEXT_SOURCES = frozenset({
    cs.RS_ORIGINAL_BUDGET, cs.RS_REVISED_BUDGET, cs.RS_PROJECTED_BUDGET,
    cs.RS_PROJECTED_COST, cs.RS_COMMITTED_COST,
})


def _result(source, field, amount, value, *, missing=False, missing_reason=None, ambiguity=False,
            ambiguity_reason=None, circular=False, alias_used=None, pkg_type=None, pkg_path=None,
            source_file=None, source_row_id=None) -> "OrderedDict":
    return OrderedDict([
        ("reference_source", source),
        ("reference_field", field),
        ("reference_explicit_amount", money_str(amount) if amount is not None else None),
        ("resolved_reference_value", money_str(value) if value is not None else None),
        ("reference_is_total_or_remaining", "total"),
        ("source_present", value is not None and not missing),
        ("missing", bool(missing)),
        ("missing_reason", missing_reason),
        ("ambiguity", bool(ambiguity)),
        ("ambiguity_reason", ambiguity_reason),
        ("circular", bool(circular)),
        ("alias_used", alias_used),
        ("source_package_type", pkg_type),
        ("source_package_path", pkg_path),
        ("source_file", source_file),
        ("source_row_id", source_row_id),
    ])


def resolve_reference(control: dict, key_ctx: dict | None) -> "OrderedDict":
    """Resolve one control's selected reference into a value + lineage (does not mutate)."""
    source = control.get("reference_source")
    field = control.get("reference_field") or DEFAULT_FIELD.get(source)
    key_ctx = key_ctx or {}

    if source not in cs.REFERENCE_SOURCES:
        return _result(source, field, dec(control.get("explicit_value_amount")), None,
                       missing=True, missing_reason=f"unknown reference_source '{source}'")

    if source == cs.RS_EXPLICIT:
        amount = dec(control.get("explicit_value_amount"))
        if amount is None:
            return _result(source, None, None, None, missing=True,
                           missing_reason="explicit_user_amount requires explicit_value_amount")
        return _result(source, None, amount, amount, pkg_type="operator_explicit_amount",
                       source_row_id=control.get("control_id"))

    if source in _CONTEXT_SOURCES:
        amounts = key_ctx.get("amounts") or {}
        value = dec(amounts.get(field))
        if source == cs.RS_PROJECTED_BUDGET:
            distinct = key_ctx.get("projected_budget_distinct")
            if distinct is not None and dec(distinct) != value:
                return _result(source, field, None, None, ambiguity=True,
                               ambiguity_reason="distinct projected_budget and projected_costs differ; "
                                                "operator must disambiguate")
            alias = "projected_budget->projected_costs"
        else:
            alias = None
        if value is None:
            return _result(source, field, None, None, missing=True,
                           missing_reason=f"context amount '{field}' missing for budget code",
                           alias_used=alias, pkg_type="forecast_context",
                           pkg_path=key_ctx.get("context_package_path"),
                           source_file="summaries/budget_code_forecast_context.jsonl")
        return _result(source, field, None, value, alias_used=alias, pkg_type="forecast_context",
                       pkg_path=key_ctx.get("context_package_path"),
                       source_file="summaries/budget_code_forecast_context.jsonl",
                       source_row_id=key_ctx.get("budget_code_key"))

    if source == cs.RS_ACCEPTED_INTEL_FINAL:
        intel = key_ctx.get("intelligence_final") or {}
        value = dec(intel.get("value"))
        if value is None:
            return _result(source, field, None, None, missing=True,
                           missing_reason="accepted intelligence final not available for budget code",
                           pkg_type="forecast_accuracy_next", pkg_path=intel.get("source_package_path"),
                           source_file="forecast_recommendations_by_budget_code.jsonl")
        return _result(source, field, None, value, pkg_type="forecast_accuracy_next",
                       pkg_path=intel.get("source_package_path"),
                       source_file="forecast_recommendations_by_budget_code.jsonl",
                       source_row_id=key_ctx.get("budget_code_key"))

    if source == cs.RS_PRIOR_COMPREHENSIVE_FINAL:
        prior = key_ctx.get("prior_comprehensive_final") or {}
        if prior.get("is_current_run"):
            return _result(source, field, None, None, circular=True, missing=True,
                           missing_reason="prior_comprehensive_integrated_final points at the current run "
                           "being generated (circular); not allowed",
                           pkg_type="forecast_comprehensive", pkg_path=prior.get("source_package_path"))
        value = dec(prior.get("value"))
        if value is None:
            return _result(source, field, None, None, missing=True,
                           missing_reason="prior comprehensive integrated final not available",
                           pkg_type="forecast_comprehensive", pkg_path=prior.get("source_package_path"),
                           source_file="integrated_final_cost_recommendations.jsonl")
        return _result(source, field, None, value, pkg_type="forecast_comprehensive",
                       pkg_path=prior.get("source_package_path"),
                       source_file="integrated_final_cost_recommendations.jsonl",
                       source_row_id=key_ctx.get("budget_code_key"))

    return _result(source, field, None, None, missing=True,
                   missing_reason=f"unhandled reference_source '{source}'")
