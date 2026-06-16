"""Comprehensive package assembly: completeness matrix, inventory, rollups, summary."""
from __future__ import annotations

from collections import Counter, OrderedDict

from ..common.money import D, money_str

# packages consumed indirectly (their signals already flow through intelligence/monthly)
_PARTIAL = {"crosswalk_v2", "schedule_integrated"}


def completeness_matrix(project_key, discovery, frequency_disposition, history_enabled) -> OrderedDict:
    rows = []
    for ptype, d in discovery.items():
        if not d["present"]:
            status = "missing"
        elif ptype == "cost_frequency":
            status = {"consumed": "consumed", "degraded_missing": "missing",
                      "degraded_generation_failed": "blocked_by_validation"}.get(frequency_disposition,
                                                                                  "downgraded")
        elif ptype == "history_informed":
            status = "consumed" if history_enabled else "intentionally_excluded"
        elif ptype in _PARTIAL:
            status = "partially_consumed"
        else:
            status = "consumed"
        rows.append(OrderedDict([
            ("package_type", ptype), ("present", d["present"]), ("package_name", d["package_name"]),
            ("manifest_present", d["manifest_present"]), ("consumption_status", status),
        ]))
    return OrderedDict([("project_key", project_key), ("packages", rows)])


def model_package_inventory(project_key, discovery) -> OrderedDict:
    return OrderedDict([("project_key", project_key),
                        ("packages", list(discovery.values()))])


def _f(x):
    return float(D(x))


def tops(forecast_rows, probability_rows, conflict_rows, review_rows):
    overruns = sorted(forecast_rows, key=lambda r: -_f(r["integrated_minus_accepted_final_cost"]))[:25]
    confidence = sorted([r for r in probability_rows if r["integrated_uncertainty_direction"] == "tighten"],
                        key=lambda r: r["integrated_sigma_multiplier"])[:25]
    conflicts = Counter(c["conflict_class"] for c in conflict_rows)
    top_conflicts = [OrderedDict([("conflict_class", k), ("count", v)]) for k, v in conflicts.most_common()]
    top_review = sorted(review_rows, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r["review_priority"], 3))[:25]
    pick = lambda r: OrderedDict([(k, r.get(k)) for k in  # noqa: E731
                                  ("budget_code_key", "cost_code", "integrated_recommended_final_cost",
                                   "integrated_minus_accepted_final_cost", "integrated_direction")])
    return ([pick(r) for r in overruns],
            [OrderedDict([(k, r.get(k)) for k in ("budget_code_key", "cost_code",
                          "integrated_sigma_multiplier", "integrated_uncertainty_direction")])
             for r in confidence],
            top_conflicts,
            top_review)


def summary(project_key, discovery, forecast_rows, monthly_rows, probability_rows, review_rows,
            conflict_rows, frequency_disposition, totals) -> OrderedDict:
    consumed = [t for t, d in discovery.items() if d["present"]]
    missing = [t for t, d in discovery.items() if not d["present"]]
    return OrderedDict([
        ("project_key", project_key),
        ("packages_consumed", consumed),
        ("packages_missing", missing),
        ("frequency_disposition", frequency_disposition),
        ("canonical_codes_covered", len(forecast_rows)),
        ("integrated_final_cost_recommendations", len(forecast_rows)),
        ("integrated_monthly_rows", len(monthly_rows)),
        ("integrated_probability_rows", len(probability_rows)),
        ("human_review_items", len(review_rows)),
        ("evidence_conflicts", len(conflict_rows)),
        ("evidence_conflicts_by_class", dict(Counter(c["conflict_class"] for c in conflict_rows))),
        ("totals", OrderedDict([
            ("accepted_recommended_final_cost_total", money_str(totals["accepted_final"])),
            ("integrated_recommended_final_cost_total", money_str(totals["integrated_final"])),
            ("integrated_cost_to_complete_total", money_str(totals["integrated_ctc"])),
            ("actual_cost_to_date_total", money_str(totals["actual"])),
            ("integrated_minus_accepted_final_cost_total",
             money_str(totals["integrated_final"] - totals["accepted_final"])),
        ])),
        ("probability_method", "accepted_distribution_deterministic_adjustment"),
        ("posture", "Accepted intelligence is the base final cost. Advisory evidence (history-informed, "
                    "cost-frequency) is consumed at bounded, contradiction-collapsed weights with explicit "
                    "lineage. CostEntries are accounting truth; actual cost to date is the only floor; no "
                    "evidence is a cap. Cadence shapes monthly TIMING only. Probability is a deterministic "
                    "transform of the accepted distribution, not a fresh Monte Carlo. Every recommendation "
                    "is advisory and requires human acceptance (status=pending)."),
        ("requires_human_acceptance", True),
    ])
