"""Validation gates: clean case passes; a simulated upper-cap or mutated source fails closed."""
from collections import OrderedDict

from construction_financial_review.common.io import write_json, write_jsonl
from construction_financial_review.forecast_history_informed import validation as fhi_validation

KEY = "1000.20-18-110.OVH"


def _collections():
    return {
        "historical_forecast_signal_by_budget_code.jsonl": [OrderedDict([
            ("historical_source_package", "cash_flow"), ("source_row_count", 1),
            ("budget_code_key", KEY), ("cost_code", "20-18-110"),
            ("mapping_status", "cost_code_unique_budget_match"),
            ("duplicate_cost_code_warning", False), ("historical_pattern_class", "stable_nonzero")])],
        "historical_vs_actual_validation_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("cost_code", "20-18-110"),
            ("validation_class", "validated_aligned"),
            ("historical_forecasted_remaining_in_window", "200.00"),
            ("cost_entries_actual_cost_in_window", "100.00"),
            ("actual_trend_override_score", "0.2000")])],
        "history_informed_forecast_adjustment_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("upper_cap_applied", False),
            ("history_informed_adjusted_final_cost", "500.00"), ("actual_cost_to_date", "100.00")])],
        "historical_forecast_data_quality_warnings.jsonl": [],
    }


def _write_pkg(out, collections):
    for fn, payload in collections.items():
        write_jsonl(out / fn, payload)
    (out / "README.md").write_text("r", encoding="utf-8")
    (out / "SCHEMA.md").write_text("s", encoding="utf-8")
    write_json(out / "input_inventory.json", {"x": 1})


def _ctx():
    inputs = {"count_reconciliation": {"reconciled": True}, "project_key": "tropical",
              "index": {"keys": {KEY}}}
    audit = {"history_mapping_audit": {"x": 1}, "gcgr_proportionality_audit": {"x": 1},
             "source_hashes_before_after": {"unchanged": True}}
    determinism = {"diff_result": "pass"}
    safety = {"passed": True}
    meta = {"generated_timestamp_local": "t", "package_stamp": "p"}
    return inputs, audit, determinism, safety, meta


def test_clean_case_passes(tmp_path):
    coll = _collections()
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]


def test_upper_cap_fails_closed(tmp_path):
    coll = _collections()
    coll["history_informed_forecast_adjustment_by_budget_code.jsonl"][0]["upper_cap_applied"] = True
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is False
    assert rep["checks"]["no_prior_forecast_hard_cap"] is False


def test_mutated_source_fails_closed(tmp_path):
    coll = _collections()
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    audit["source_hashes_before_after"]["unchanged"] = False
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is False
    assert rep["checks"]["source_hashes_unchanged"] is False


def test_count_mismatch_fails_closed(tmp_path):
    coll = _collections()
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    inputs["count_reconciliation"]["reconciled"] = False
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["checks"]["historical_package_counts_reconciled"] is False


def test_divergence_reported_passes_when_classified(tmp_path):
    """A surfaced divergence (classified row with both reality-check fields) passes the gate."""
    coll = _collections()
    coll["historical_vs_actual_validation_by_budget_code.jsonl"][0].update({
        "validation_class": "contradicted_escalation", "actual_trend_override_score": "0.9500"})
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["checks"]["history_vs_actual_divergence_reported"] is True


def test_unclassified_validation_fails_divergence_gate(tmp_path):
    """A validation row missing its class is not surfaced -> gate fails closed (no more `or True`)."""
    coll = _collections()
    coll["historical_vs_actual_validation_by_budget_code.jsonl"][0]["validation_class"] = ""
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is False
    assert rep["checks"]["history_vs_actual_divergence_reported"] is False


def test_missing_reality_check_field_fails_divergence_gate(tmp_path):
    """A row missing a reality-check field can't evidence divergence -> gate fails closed."""
    coll = _collections()
    del coll["historical_vs_actual_validation_by_budget_code.jsonl"][0][
        "cost_entries_actual_cost_in_window"]
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fhi_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["checks"]["history_vs_actual_divergence_reported"] is False
