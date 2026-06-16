"""Cost-frequency validation gates: clean case passes; staffing-not-weekly + partial-basis fail closed."""
from collections import OrderedDict

from construction_financial_review.common.io import write_json, write_jsonl
from construction_financial_review.forecast_cost_frequency import validation as fcf_validation

KEY = "1000.10-01-302.LAB"


def _collections():
    return {
        "cost_frequency_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("cost_code", "10-01-302"),
            ("is_internal_staffing_code", True),
            ("effective_frequency_class", "weekly_internal_staffing")])],
        "internal_staffing_daily_rate_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("latest_complete_month", "2026-05"),
            ("daily_rate", "1000.0000"), ("credit_month_present", False)])],
        "weekday_calendar_by_forecast_month.jsonl": [OrderedDict([
            ("forecast_month", "2026-06"), ("weekday_count", 22)])],
        "frequency_adjusted_monthly_phasing_by_budget_code.jsonl": [OrderedDict([
            ("budget_code_key", KEY), ("do_not_change_accepted_final_cost", True)])],
        "project_cost_frequency_summary.json": OrderedDict([
            ("package_contract", OrderedDict([("contract_version", "1.0.0")]))]),
    }


def _write_pkg(out, collections):
    for fn, payload in collections.items():
        if fn.endswith(".jsonl"):
            write_jsonl(out / fn, payload)
        else:
            write_json(out / fn, payload)
    (out / "README.md").write_text("r", encoding="utf-8")
    (out / "SCHEMA.md").write_text("s", encoding="utf-8")
    write_json(out / "input_inventory.json", {"x": 1})


def _ctx():
    inputs = {"project_key": "tropical", "index": {"keys": {KEY}},
              "window": {"months": ["2026-06"], "latest_complete_month_boundary": "2026-05"}}
    audit = {"staffing_code_policy_audit": {"configured_staffing_codes": [KEY],
                                            "all_configured_present": True,
                                            "missing_from_canonical_budget_details": []},
             "source_hashes_before_after": {"unchanged": True}}
    determinism = {"diff_result": "pass"}
    safety = {"passed": True}
    meta = {"generated_timestamp_local": "t", "package_stamp": "p"}
    return inputs, audit, determinism, safety, meta


def test_clean_case_passes(tmp_path):
    coll = _collections()
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fcf_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is True, [k for k, v in rep["checks"].items() if not v]


def test_staffing_not_weekly_fails_closed(tmp_path):
    coll = _collections()
    coll["cost_frequency_by_budget_code.jsonl"][0]["effective_frequency_class"] = "monthly_observed"
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fcf_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["passed"] is False
    assert rep["checks"]["staffing_codes_effective_weekly"] is False


def test_partial_month_as_rate_basis_fails_closed(tmp_path):
    coll = _collections()
    coll["internal_staffing_daily_rate_by_budget_code.jsonl"][0]["latest_complete_month"] = "2026-06"
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    rep = fcf_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["checks"]["no_partial_month_as_complete_rate_basis"] is False


def test_uncovered_canonical_code_fails_closed(tmp_path):
    coll = _collections()
    _write_pkg(tmp_path, coll)
    inputs, audit, det, safety, meta = _ctx()
    inputs["index"]["keys"] = {KEY, "OTHER.00-00-000.X"}   # a code never covered
    rep = fcf_validation.build_validation(tmp_path, inputs, coll, audit, det, safety, meta, False, [])
    assert rep["checks"]["all_127_canonical_covered_or_skipped"] is False
