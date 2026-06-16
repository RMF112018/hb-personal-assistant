"""Improvement-by-improvement support decisions + data inventory + SQLite inventory assembly.

Each decision classifies one of the seven priorities and links it to the available data evidence. The
decision is repo-truth + data-truth grounded: Priority 1 (FHI) is already implemented_and_validated
(verified in code + tests), so it is audit-only here; the rest are newly implemented in this package
where the data supports them.
"""
from __future__ import annotations

from collections import OrderedDict

DECISION_ENUM = (
    "implemented_and_validated", "implemented_with_patch", "newly_implemented",
    "partially_supported_diagnostic_only", "unsupported_data_gap", "not_applicable",
)


def build_decisions(inputs: dict, counts: dict) -> list:
    db_present = inputs["db"].get("db_present")
    discovery = inputs["discovery"]

    def present(ptype):
        return discovery.get(ptype, {}).get("present")

    decisions = [
        OrderedDict([
            ("improvement_id", "priority_1"),
            ("title", "Forecast history-informed advisory prior-evidence layer"),
            ("decision", "implemented_and_validated"),
            ("evidence", ["forecast_history_informed/ modules", "tests/test_fhi_*.py",
                          "forecast_history_informed package on data root"]),
            ("data_fields_relied_on", ["monthly source_shares", "CostEntries actuals",
                                       "actual_inactivity_months_for_zero_support"]),
            ("limitations", "verified in repo (4 hardening items present in code + tests); this package "
                            "adds an audit confirmation only, no patch"),
            ("validation_tests_added", ["audit confirmation in improvement_coverage_audit"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["audit/improvement_coverage_audit.json"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_2"),
            ("title", "Formal Basis of Estimate documentation"),
            ("decision", "newly_implemented"),
            ("evidence", ["package manifests/READMEs/SCHEMAs across discovered packages"]),
            ("data_fields_relied_on", ["package doc artifacts", "source hashes", "discovery"]),
            ("limitations", "BOE generated for THIS package only; existing packages get a coverage score "
                            "+ follow-up (no accepted package mutated)"),
            ("validation_tests_added", ["test_fia_boe (required sections)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["BASIS_OF_ESTIMATE.md", "basis_of_estimate_coverage.json"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_3"),
            ("title", "Backtesting and calibration reporting"),
            ("decision", "partially_supported_diagnostic_only" if present("intelligence")
             else "unsupported_data_gap"),
            ("evidence", ["forecast_accuracy_next model_backtest_results.json",
                          "model_calibration_summary.json", "probability backtest"]),
            ("data_fields_relied_on", ["summary_by_method (n, mape, mean_bias)",
                                       "cohort_breakdown_by_family/division", "before_after_by_method"]),
            ("limitations", "upstream exposes MAPE + bias only (small cohort); WAPE/MAE not invented; "
                            "metrics flagged insufficient_sample where n is low"),
            ("validation_tests_added", ["test_fia_calibration (denominator/sample-size/bias)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["calibration_enhancements.jsonl"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_4"),
            ("title", "Actual-cost lag diagnostics"),
            ("decision", "newly_implemented"),
            ("evidence", ["context monthly_actuals + amounts", "trend_evidence", "latest_subcontractor_invoice",
                          "schedule_forecast_evidence"]),
            ("data_fields_relied_on", ["costentries_total_amount", "recency_gap_months",
                                       "late_cost_emergence", "latest_work_completed_this_period",
                                       "open_activity_count"]),
            ("limitations", "lag-risk flags only; no actual cost inferred from invoice/pay-app/schedule"),
            ("validation_tests_added", ["test_fia_lag (lag/no-lag/insufficient)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["actual_cost_lag_diagnostics.jsonl"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_5"),
            ("title", "Schedule cost-loading readiness audit"),
            ("decision", "newly_implemented" if inputs["schedule_activities"] else "unsupported_data_gap"),
            ("evidence", ["project_schedule_json_package/schedule_activities.jsonl"]),
            ("data_fields_relied_on", ["budget_code_mapping_confidence", "candidate_budget_code_keys",
                                       "progress.activity_percent_complete", "raw_xml_fields cost loading"]),
            ("limitations", "schedule→budget-code mapping sparse (mostly 'none'); posture limited "
                            "accordingly; schedule never overrides actuals"),
            ("validation_tests_added", ["test_fia_schedule (mapped/unmapped/no-cost-loading)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["schedule_cost_loading_readiness_audit.json"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_6"),
            ("title", "GC/GR behavior + fee projected-budget cap"),
            ("decision", "newly_implemented"),
            ("evidence", ["context budget_codes amounts", "trend_evidence", "accuracy_next recommended_final_cost",
                          "gcgr_forecast_history line summary"]),
            ("data_fields_relied_on", ["projected_budget (fee cap source)", "costentries_total_amount",
                                       "recommended_final_cost", "forecast_to_complete", "cost_volatility_cov"]),
            ("limitations", "fee cap proven in this audit's own logic only; no upstream generator enforces "
                            "it (required follow-up); GC/GR classes are advisory, do not change final cost"),
            ("validation_tests_added", ["test_fia_gcgr_fee (5 fee-cap cases + non-fee uncapped)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["gcgr_behavior_diagnostics.jsonl", "fee_cap_diagnostics.jsonl"]),
        ]),
        OrderedDict([
            ("improvement_id", "priority_7"),
            ("title", "Change-order exposure integration"),
            ("decision", "newly_implemented" if db_present else "unsupported_data_gap"),
            ("evidence", ["SQLite procore_financial_change_orders (read-only)",
                          "procore_financial_contracts"]),
            ("data_fields_relied_on", ["status", "executed", "grand_total", "change_order_family",
                                       "contract_record_key"]),
            ("limitations", "no per-budget-code link in DB → project/family-level exposure with "
                            "mapping_confidence none; pending never treated as committed/actual; "
                            "double-count risk flagged vs current projected cost"),
            ("validation_tests_added", ["test_fia_change_order (mapping/pending/approved/void/double-count)"]),
            ("changes_output_contract", False), ("advisory_only", True),
            ("output_artifacts", ["change_order_exposure_evidence.jsonl"]),
        ]),
    ]
    # attach live counts where available
    for d in decisions:
        d["evidence_row_counts"] = counts.get(d["improvement_id"], {})
    return decisions


def data_inventory(inputs: dict) -> OrderedDict:
    discovery = inputs["discovery"]
    packages = []
    for ptype, d in discovery.items():
        packages.append(OrderedDict([
            ("package_type", ptype), ("present", d.get("present")),
            ("package_name", d.get("package_name")),
            ("required", d.get("required")),
            ("manifest_present", d.get("manifest_present")),
        ]))
    return OrderedDict([
        ("project_key", inputs["project_key"]),
        ("data_root", inputs["data_root"]),
        ("packages", packages),
        ("budget_code_count", len(inputs["budget_by_key"])),
        ("monthly_actuals_rows", len(inputs["monthly_actuals"])),
        ("schedule_activity_count", len(inputs["schedule_activities"])),
        ("gcgr_history_lines", len(inputs["gcgr_line_summary"])),
        ("cash_flow_history_rows", len(inputs["cf_code_rows"])),
    ])


def sqlite_inventory(inputs: dict) -> OrderedDict:
    db = inputs["db"]
    inv2 = OrderedDict(inputs["db_schema_inventory"])
    inv2["read_only_mode"] = "file:...?mode=ro"
    inv2["change_orders_read"] = len(db.get("change_orders", []))
    inv2["contracts_read"] = len(db.get("contracts", []))
    inv2["mutation_performed"] = False
    return inv2
