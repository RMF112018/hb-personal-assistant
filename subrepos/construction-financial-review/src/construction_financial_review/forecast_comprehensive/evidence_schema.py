"""Canonical evidence-item schema + family / independence-group vocabulary.

Every package row, regardless of origin, is normalized into one evidence item with uniform lineage and
scoring fields. `independence_group` enables no-double-counting: the same underlying signal (e.g.
CostEntries trend, which surfaces in context, intelligence, monthly, and history validation) is grouped
so it stays primary truth but is not weighted multiple times as if independent.
"""
from __future__ import annotations

from collections import OrderedDict

# evidence families (every current model output family)
F_ACTUAL = "actual_cost_truth"
F_BUDGET = "budget_context"
F_PROJECTED = "current_projected_cost"
F_OWNER_SCOPE = "owner_scope_crosswalk"
F_OWNER_PAYAPP = "owner_pay_application"
F_SUB_PAYAPP = "subcontractor_pay_application"
F_COST_TREND = "cost_entry_trend"
F_SCHED_REMAIN = "schedule_remaining_work"
F_SCHED_MONTHLY = "schedule_monthly_phasing"
F_ACCURACY = "forecast_accuracy"
F_INTELLIGENCE = "forecast_intelligence"
F_MONTHLY = "forecast_monthly"
F_PROBABILITY = "forecast_probability"
F_HIST_FINAL = "history_informed_final_cost"
F_HIST_MONTHLY = "history_informed_monthly_shape"
F_HIST_PROB = "history_informed_probability"
F_FREQ_CADENCE = "cost_frequency_cadence"
F_STAFFING_RATE = "internal_staffing_weekday_rate"
F_LLM = "llm_advisory_narrative"

FAMILIES = (
    F_ACTUAL, F_BUDGET, F_PROJECTED, F_OWNER_SCOPE, F_OWNER_PAYAPP, F_SUB_PAYAPP, F_COST_TREND,
    F_SCHED_REMAIN, F_SCHED_MONTHLY, F_ACCURACY, F_INTELLIGENCE, F_MONTHLY, F_PROBABILITY,
    F_HIST_FINAL, F_HIST_MONTHLY, F_HIST_PROB, F_FREQ_CADENCE, F_STAFFING_RATE, F_LLM,
)

# independence groups — items in the same group describe ONE underlying signal (no double-count)
INDEPENDENCE_GROUP = {
    F_ACTUAL: "actuals_truth",
    F_COST_TREND: "cost_entry_trend",
    F_BUDGET: "budget_reference", F_PROJECTED: "budget_reference", F_OWNER_SCOPE: "budget_reference",
    F_OWNER_PAYAPP: "pay_application", F_SUB_PAYAPP: "pay_application",
    F_SCHED_REMAIN: "schedule", F_SCHED_MONTHLY: "schedule",
    F_INTELLIGENCE: "base_model", F_ACCURACY: "base_model", F_MONTHLY: "base_model",
    F_PROBABILITY: "base_model",
    F_HIST_FINAL: "history", F_HIST_MONTHLY: "history", F_HIST_PROB: "history",
    F_FREQ_CADENCE: "frequency", F_STAFFING_RATE: "frequency",
    F_LLM: "narrative",
}


def evidence_item(project_key, budget_code_key, source_package_type, source_package_path, source_file,
                  source_row_id, evidence_family, evidence_signal, evidence_value, *,
                  direction="none", magnitude=None, confidence=None, recency=None,
                  mapping_confidence=None, contradiction_score="0.0000", supports_final_cost=False,
                  supports_monthly_phasing=False, supports_probability=False,
                  requires_human_acceptance=False, do_not_auto_apply=False, reason_codes=None,
                  notes=None) -> OrderedDict:
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("source_package_type", source_package_type),
        ("source_package_path", source_package_path),
        ("source_file", source_file),
        ("source_row_id", source_row_id),
        ("evidence_family", evidence_family),
        ("independence_group", INDEPENDENCE_GROUP.get(evidence_family, "other")),
        ("evidence_signal", evidence_signal),
        ("evidence_value", evidence_value),
        ("direction", direction),
        ("magnitude", magnitude),
        ("confidence", confidence),
        ("recency", recency),
        ("mapping_confidence", mapping_confidence),
        ("contradiction_score", contradiction_score),
        ("supports_final_cost", supports_final_cost),
        ("supports_monthly_phasing", supports_monthly_phasing),
        ("supports_probability", supports_probability),
        ("requires_human_acceptance", requires_human_acceptance),
        ("do_not_auto_apply", do_not_auto_apply),
        ("reason_codes", reason_codes or []),
        ("notes", notes),
    ])
