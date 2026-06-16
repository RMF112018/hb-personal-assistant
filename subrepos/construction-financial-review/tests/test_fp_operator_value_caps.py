"""forecast_probability: accepted operator not_to_exceed value caps (operator-constrained, disclosed).

Synthetic, no data root. Covers the loader (binding / non-binding / manual / actuals-floor), the
simulation override + disclosure, and the split upper-cap validation checks.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from decimal import Decimal

import numpy as np

from construction_financial_review.common.io import read_json, write_json
from construction_financial_review.forecast_probability import (
    generate_probabilistic_validation_package as gen,
    risk_metrics,
    simulate,
    simulation_inputs as si,
)


# --------------------------------------------------------------------------- loader

def _monthly_pkg(tmp_path, applied):
    pkg = tmp_path / "forecast_monthly_package_tropical_20260101_000000"
    (pkg / "audit").mkdir(parents=True)
    write_json(pkg / "audit" / "forecast_model_controls_applied.json",
               OrderedDict([("model_controls_active", True), ("applied_model_controls", applied)]))
    return pkg


REC_BY = {
    "1000.10-01-340.MAT": {"actual_cost_all_source_to_date": "42656.25",
                           "current_projected_cost": "42656.25", "recommended_final_cost": "80389.82"},
    "1000.20-00-001.SUB": {"actual_cost_all_source_to_date": "1000.00",
                           "current_projected_cost": "900.00", "recommended_final_cost": "6000.00"},
    "1000.15-16-110.SUB": {"actual_cost_all_source_to_date": "9554919.18",
                           "current_projected_cost": "12000000.00", "recommended_final_cost": "11832740.65"},
}


def _ctrl(key, policy, cf, rem, changes):
    return OrderedDict([("budget_code_key", key), ("control_id", f"c-{key}"),
                        ("model_type", "front_loaded_s_curve"), ("value_constraint_policy", policy),
                        ("controlled_final_cost", cf), ("controlled_remaining", rem),
                        ("changes_deterministic_final", changes)])


def test_loader_binding_not_to_exceed_cap(tmp_path):
    pkg = _monthly_pkg(tmp_path, [
        _ctrl("1000.10-01-340.MAT", "not_to_exceed_reference", "42656.25", "0.00", True)])
    c = si.load_operator_value_constraints(pkg, REC_BY)["1000.10-01-340.MAT"]
    assert c["operator_constrained"] is True and c["cap_binding"] is True and c["floor_event"] is False
    assert c["controlled_final"] == 42656.25 and c["reference_value"] == 42656.25
    assert c["reference_source"] == "projected_cost" and c["reference_field"] == "projected_costs"
    assert c["uncapped_model_final"] == 80389.82


def test_loader_skips_non_binding_and_manual(tmp_path):
    pkg = _monthly_pkg(tmp_path, [
        _ctrl("1000.10-01-340.MAT", "not_to_exceed_reference", "80389.82", "37733.57", False),  # non-binding
        _ctrl("1000.15-16-110.SUB", "explicit_remaining_value", "12955369.18", "3400450.00", True)])  # manual
    out = si.load_operator_value_constraints(pkg, REC_BY)
    assert out == {}                          # neither a binding cap nor a floor event -> nothing to consume


def test_loader_cap_below_actuals_is_floor_event(tmp_path):
    pkg = _monthly_pkg(tmp_path, [
        _ctrl("1000.20-00-001.SUB", "not_to_exceed_reference", "900.00", "0.00", True)])
    c = si.load_operator_value_constraints(pkg, REC_BY)["1000.20-00-001.SUB"]
    assert c["floor_event"] is True and c["operator_constrained"] is False   # actuals (1000) win over 900


def test_loader_missing_audit_degrades(tmp_path):
    assert si.load_operator_value_constraints(tmp_path / "nope", REC_BY) == {}


# --------------------------------------------------------------------------- simulate override + disclose

def _arrays(keys, actual, mu, sigma, rec_final, worst, proj, near):
    n, nm = len(keys), 2
    return OrderedDict([
        ("n_codes", n), ("n_months", nm), ("months", ["2026-06", "2026-07"]), ("keys", list(keys)),
        ("actual", np.array(actual, dtype=np.float64)),
        ("carried_prior_forecast", np.zeros(n, dtype=np.float64)),
        ("mu", np.array(mu, dtype=np.float64)), ("sigma", np.array(sigma, dtype=np.float64)),
        ("near_complete", np.array(near, dtype=bool)),
        ("recommended_final", np.array(rec_final, dtype=np.float64)),
        ("worst_credible_final", np.array(worst, dtype=np.float64)),
        ("current_projected", np.array(proj, dtype=np.float64)),
        ("revised_budget", np.array(proj, dtype=np.float64)),
        ("committed", np.zeros(n, dtype=np.float64)),
        ("base_weights", np.full((n, nm), 0.5, dtype=np.float64)),
        ("monthly_score", np.full(n, 0.5, dtype=np.float64)),
        ("rho", 0.35), ("kappa0", 40.0),
    ])


CAP = {
    "1000.10-01-340.MAT": {
        "budget_code_key": "1000.10-01-340.MAT", "control_id": "c1",
        "value_constraint_policy": "not_to_exceed_reference", "reference_source": "projected_cost",
        "reference_field": "projected_costs", "reference_value": 42656.25,
        "actual_cost_to_date": 42656.25, "controlled_final": 42656.25, "controlled_remaining": 0.0,
        "uncapped_model_final": 80389.82, "cap_binding": True, "floor_event": False,
        "operator_constrained": True},
}


def _run(arrays, constraints):
    base = simulate.simulate(arrays, runs=400, seed=7, antithetic=True, lhs=False, draw_months=True)
    inputs = {"operator_value_constraints": constraints}
    gen._apply_operator_value_constraints(base, arrays, inputs)
    rows = {r["budget_code_key"]: r for r in risk_metrics.code_rows(base, arrays, constraints)}
    return base, rows


def test_binding_cap_point_mass_and_alignment():
    keys = ["1000.10-01-340.MAT", "1000.20-00-001.SUB"]
    arrays = _arrays(keys, [42656.25, 1000.0], [math.log(37733.57), math.log(5000.0)],
                     [0.25, 0.30], [80389.82, 6000.0], [80389.82, 12000.0],
                     [42656.25, 6000.0], [False, False])
    base, rows = _run(arrays, dict(CAP))
    a = rows["1000.10-01-340.MAT"]
    # p50 == p90 == controlled final; deterministic recommended re-anchored to the cap (alignment holds)
    assert a["simulated_p50"] == a["simulated_p90"] == "42656.25"
    assert a["deterministic_recommended_final_cost"] == "42656.25"
    assert a["probability_treatment"] == "operator_constrained_not_to_exceed"
    assert a["cap_binding"] is True and a["upside_simulated"] is False
    assert a["reason"] == "accepted_not_to_exceed_projected_cost"
    # counterfactual uncapped risk evidence preserved
    assert a["uncapped_model_final"] == "80389.82"
    assert Decimal(a["uncapped_p90"]) > Decimal("42656.25")
    assert Decimal(a["cap_delta_to_uncapped_model"]) > Decimal("0")
    # the uncapped sibling is untouched (still risk-distributed)
    b = rows["1000.20-00-001.SUB"]
    assert "probability_treatment" not in b
    assert Decimal(b["simulated_p90"]) > Decimal(b["simulated_p50"])


def test_floor_event_not_point_massed_but_disclosed():
    keys = ["1000.20-00-001.SUB"]
    arrays = _arrays(keys, [1000.0], [math.log(5000.0)], [0.30], [6000.0], [12000.0], [900.0], [False])
    floor = {"1000.20-00-001.SUB": {**CAP["1000.10-01-340.MAT"],
                                    "budget_code_key": "1000.20-00-001.SUB", "reference_value": 900.0,
                                    "actual_cost_to_date": 1000.0, "controlled_final": 900.0,
                                    "uncapped_model_final": 6000.0, "cap_binding": False,
                                    "floor_event": True, "operator_constrained": False}}
    base, rows = _run(arrays, floor)
    r = rows["1000.20-00-001.SUB"]
    assert r["probability_treatment"] == "actuals_floor_over_reference"
    assert r["cap_binding"] is False
    # actuals floor absolute: distribution NOT collapsed to the sub-actuals reference (900); p10 >= actual
    assert Decimal(r["simulated_p10"]) >= Decimal(r["actual_cost_to_date"])
    assert r["simulated_p50"] != "900.00"


# --------------------------------------------------------------------------- split validation checks

def _audit_row(key, accepted=False, src=None, status="uncapped_ok"):
    return OrderedDict([
        ("budget_code_key", key), ("operator_accepted_cap", accepted),
        ("upper_cap_applied", bool(accepted)),
        ("upper_cap_source", ("accepted_operator_not_to_exceed" if accepted else src)),
        ("reference_values_reported_only", not accepted),
        ("validation_status", "accepted_operator_cap" if accepted else status)])


def _disclosed_row(key, cf):
    r = OrderedDict([("budget_code_key", key), ("near_complete", False),
                     ("simulated_p95", "42656.25"), ("deterministic_worst_credible_final_cost", "80389.82"),
                     ("simulated_p50", risk_metrics.m(cf)), ("simulated_p90", risk_metrics.m(cf))])
    risk_metrics._disclose_operator_constraint(r, CAP["1000.10-01-340.MAT"])
    return r


def test_split_checks_accepted_cap_passes_hidden_fails():
    cap_key = "1000.10-01-340.MAT"
    # one uncapped code with realized upside + one accepted-cap code
    code_rows = [
        OrderedDict([("budget_code_key", "1000.20-00-001.SUB"), ("near_complete", False),
                     ("simulated_p95", "11000.00"), ("deterministic_worst_credible_final_cost", "9000.00")]),
        _disclosed_row(cap_key, 42656.25)]
    no_cap_audit = [_audit_row("1000.20-00-001.SUB"), _audit_row(cap_key, accepted=True)]
    constraints = {cap_key: CAP[cap_key]}
    ok = gen._upper_cap_checks(code_rows, no_cap_audit, constraints, Decimal("50000.00"), "45000.00")
    assert ok["hidden_or_implicit_upper_caps_absent"] is True
    assert ok["accepted_operator_caps_disclosed"] is True
    assert ok["accepted_operator_caps_applied"] is True
    assert ok["no_unaccepted_reference_caps"] is True

    # a hidden reference cap (projected_cost, NOT accepted) must trip the prohibition
    hidden_audit = [_audit_row("1000.20-00-001.SUB", src="projected_cost", status="uncapped_ok"),
                    _audit_row(cap_key, accepted=True)]
    bad = gen._upper_cap_checks(code_rows, hidden_audit, constraints, Decimal("50000.00"), "45000.00")
    assert bad["hidden_or_implicit_upper_caps_absent"] is False
    assert bad["no_unaccepted_reference_caps"] is False


def test_no_upper_cap_audit_tags_accepted_cap():
    cap_key = "1000.10-01-340.MAT"
    collections = {"probabilistic_final_cost_by_budget_code.jsonl": [
        OrderedDict([("budget_code_key", cap_key), ("near_complete", False), ("simulated_p95", "42656.25"),
                     ("current_projected_cost", "42656.25"), ("revised_budget", "42656.25"),
                     ("deterministic_worst_credible_final_cost", "80389.82")]),
        OrderedDict([("budget_code_key", "1000.20-00-001.SUB"), ("near_complete", False),
                     ("simulated_p95", "11000.00"), ("current_projected_cost", "900.00"),
                     ("revised_budget", "900.00"), ("deterministic_worst_credible_final_cost", "9000.00")])]}
    audit = gen._no_upper_cap_audit(collections, {cap_key: CAP[cap_key]})
    by = {a["budget_code_key"]: a for a in audit}
    assert by[cap_key]["operator_accepted_cap"] is True
    assert by[cap_key]["upper_cap_source"] == "accepted_operator_not_to_exceed"
    assert by["1000.20-00-001.SUB"]["operator_accepted_cap"] is False
    assert by["1000.20-00-001.SUB"]["upper_cap_source"] is None
