"""Comprehensive validation gates: clean case passes; floor/cap/coverage failures fail closed."""
from collections import OrderedDict

from construction_financial_review.common.io import write_json, write_jsonl
from construction_financial_review.forecast_comprehensive import validation as v

KEY = "1000.10-01-302.LAB"


def _acc(row):
    row.update([("requires_human_acceptance", True), ("do_not_auto_apply", True),
                ("acceptance_status", "pending"), ("accepted_by", None), ("accepted_at", None),
                ("acceptance_notes", None)])
    return row


def _collections():
    fr = _acc(OrderedDict([("budget_code_key", KEY), ("actual_cost_to_date", "40000.00"),
                           ("accepted_recommended_final_cost", "100000.00"),
                           ("integrated_recommended_final_cost", "109000.00"),
                           ("integrated_minus_accepted_final_cost", "9000.00"),
                           ("floored_at_actuals", False), ("upper_cap_applied", False),
                           ("integrated_direction", "integrated_increase_review"),
                           ("history_consumption_status", "consumed"),
                           ("frequency_consumption_status", "consumed")]))
    return {
        "integrated_evidence_registry_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("source_package_type", "context"),
            ("source_file", "x.jsonl"), ("source_row_id", KEY), ("evidence_family", "actual_cost_truth"),
            ("supports_final_cost", True)])],
        "integrated_forecast_by_budget_code.jsonl": [fr],
        "integrated_final_cost_recommendations.jsonl": [_acc(OrderedDict([("budget_code_key", KEY),
            ("upper_cap_applied", False)]))],
        "integrated_monthly_forecast_by_budget_code.jsonl": [_acc(OrderedDict([("budget_code_key", KEY)]))],
        "integrated_probability_by_budget_code.jsonl": [_acc(OrderedDict([("budget_code_key", KEY),
            ("upper_cap_applied", False)]))],
        "integrated_human_review_queue.jsonl": [_acc(OrderedDict([("budget_code_key", KEY)]))],
    }


def _audit():
    return OrderedDict([
        ("actuals_floor_audit", {"all_floors_respected": True}),
        ("no_upper_cap_audit", {"no_upper_cap_anywhere": True}),
        ("monthly_reconciliation_audit", {"per_code_all_reconciled": True, "project_total_reconciled": True}),
        ("probability_adjustment_audit", {"deterministic_no_monte_carlo": True, "deterministic_seed": 1}),
        ("history_consumption_audit", {"every_code_consumed_or_downgraded": True}),
        ("frequency_consumption_audit", {"disposition": "consumed"}),
        ("source_hashes_before_after", {"unchanged": True}),
    ])


def _discovery():
    return OrderedDict([(t, {"required": req, "present": True})
                        for t, req in (("context", True), ("intelligence", True), ("monthly", True),
                                       ("probability", False), ("cost_frequency", False))])


def _write(out, coll):
    for fn, payload in coll.items():
        write_jsonl(out / fn, payload)
    (out / "README.md").write_text("r", encoding="utf-8")
    (out / "SCHEMA.md").write_text("s", encoding="utf-8")
    write_json(out / "input_inventory.json", {"x": 1})


def _run(out, coll, audit):
    inputs = {"project_key": "tropical", "canonical_keys": {KEY}}
    det = {"diff_result": "pass"}
    safety = {"passed": True}
    meta = {"generated_timestamp_local": "t", "package_stamp": "p"}
    return v.build_validation(out, inputs, coll, audit, det, safety, meta, _discovery(), False, [])


def test_clean_case_passes(tmp_path):
    coll = _collections()
    _write(tmp_path, coll)
    rep = _run(tmp_path, coll, _audit())
    assert rep["passed"] is True, [k for k, val in rep["checks"].items() if not val]


def test_floor_violation_fails_closed(tmp_path):
    coll = _collections()
    _write(tmp_path, coll)
    audit = _audit()
    audit["actuals_floor_audit"]["all_floors_respected"] = False
    rep = _run(tmp_path, coll, audit)
    assert rep["passed"] is False
    assert rep["checks"]["actuals_floor_preserved"] is False


def test_uncovered_code_fails_closed(tmp_path):
    coll = _collections()
    _write(tmp_path, coll)
    inputs_audit = _audit()
    out = tmp_path
    inputs = {"project_key": "tropical", "canonical_keys": {KEY, "OTHER.00-00-000.X"}}
    rep = v.build_validation(out, inputs, coll, inputs_audit, {"diff_result": "pass"}, {"passed": True},
                             {"generated_timestamp_local": "t", "package_stamp": "p"}, _discovery(), False, [])
    assert rep["checks"]["canonical_budget_code_coverage"] is False


def test_monthly_reconciliation_failure_fails_closed(tmp_path):
    coll = _collections()
    _write(tmp_path, coll)
    audit = _audit()
    audit["monthly_reconciliation_audit"]["project_total_reconciled"] = False
    rep = _run(tmp_path, coll, audit)
    assert rep["checks"]["monthly_reconciliation_passed"] is False
