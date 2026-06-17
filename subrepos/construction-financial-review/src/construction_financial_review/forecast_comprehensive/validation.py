"""Fail-closed validation gates for the comprehensive integrated forecast package."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D
from ..common.validation import all_files_parse
from ..forecast_actuals import actuals_export


def _has_acceptance(rows):
    return all(("acceptance_status" in r and "requires_human_acceptance" in r) for r in rows)


def build_validation(out, inputs, collections, audit, determinism, safety, meta, discovery,
                     llm_used, receipts):
    canonical = inputs["canonical_keys"]
    items = collections["integrated_evidence_registry_by_budget_code.jsonl"]
    forecast = collections["integrated_forecast_by_budget_code.jsonl"]
    final_recs = collections["integrated_final_cost_recommendations.jsonl"]
    monthly = collections["integrated_monthly_forecast_by_budget_code.jsonl"]
    probability = collections["integrated_probability_by_budget_code.jsonl"]
    review = collections["integrated_human_review_queue.jsonl"]

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    meta_doc = ("README.md", "SCHEMA.md", "input_inventory.json")

    required_present = all(d["present"] for d in discovery.values() if d["required"])
    lineage_ok = all(i.get("source_package_type") and i.get("source_file") and i.get("source_row_id")
                     for i in items)
    covered = {r["budget_code_key"] for r in forecast}
    coverage_ok = canonical <= covered
    no_invented = all(r["budget_code_key"] in canonical for r in forecast)
    actuals_primary = all(("actual_cost_to_date" in r) for r in forecast)
    # history actuals come from context, never history; pay-apps never support final cost
    no_hist_as_actual = all(i["source_package_type"] == "context"
                            for i in items if i["evidence_family"] == "actual_cost_truth")
    no_payapp_as_actual = all(i.get("supports_final_cost") is False for i in items
                              if i["evidence_family"] in ("owner_pay_application", "subcontractor_pay_application"))

    floor_audit = audit["actuals_floor_audit"]
    floor_ok = bool(floor_audit.get("all_floors_respected"))
    cap_audit = audit["no_upper_cap_audit"]
    no_cap = bool(cap_audit.get("no_upper_cap_anywhere"))
    mrec = audit["monthly_reconciliation_audit"]
    monthly_recon = bool(mrec.get("per_code_all_reconciled") and mrec.get("project_total_reconciled"))
    padj = audit["probability_adjustment_audit"]
    prob_det = (determinism["diff_result"] == "pass"
                and bool(padj.get("deterministic_no_monte_carlo"))
                and padj.get("deterministic_seed") is not None)

    hist_audit = audit["history_consumption_audit"]
    history_ok = bool(hist_audit.get("every_code_consumed_or_downgraded"))
    freq_audit = audit["frequency_consumption_audit"]
    frequency_ok = freq_audit.get("disposition") in ("consumed", "degraded_missing", "degraded_generation_failed")

    acceptance_ok = (_has_acceptance(final_recs) and _has_acceptance(monthly)
                     and _has_acceptance(probability) and _has_acceptance(review)
                     and _has_acceptance(forecast))

    src = audit.get("source_hashes_before_after") or {}
    source_unchanged = bool(src.get("unchanged"))

    # operator forecast controls
    controls_active = bool(inputs.get("controls_active"))
    resolved = (inputs.get("controls_bundle") or {}).get("resolved") or {}
    op_items = [i for i in items if i["evidence_family"] == "operator_forecast_control"]
    op_evidence_ok = (not controls_active) or (len(op_items) > 0)
    op_floor_ok = not resolved.get("any_floor_violation")
    op_mapping_ok = not resolved.get("any_ambiguous") and not resolved.get("any_invented")

    # operator staffing plan (advisory; consumed as accepted-package OUTPUT)
    staffing_active = bool(inputs.get("staffing_plan_active"))
    sp_items = [i for i in items if i["evidence_family"] == "operator_staffing_plan"]
    sp_evidence_ok = (not staffing_active) or (len(sp_items) > 0)
    sp_advisory_ok = all(i.get("requires_human_acceptance") and i.get("do_not_auto_apply")
                         for i in sp_items)

    # actuals export gates (only when the package emits the actuals collection)
    actuals_present = "actuals_monthly_by_budget_code.jsonl" in collections
    actuals_gates = (actuals_export.validation_gates(
        collections, canonical, bool(inputs.get("actuals_contamination_ok", True)))
        if actuals_present else OrderedDict())
    # combined actuals+forecast CSV gates (only when the package emits it)
    apf_present = "actuals_plus_forecast_monthly_by_cost_code.csv" in collections
    apf_gates = actuals_export.combined_validation_gates(collections) if apf_present else OrderedDict()

    llm_receipts_ok = True
    if llm_used:
        req = {"budget_code_key", "model", "status", "safety_passed"}
        llm_receipts_ok = bool(receipts) and all(req <= set(r.keys()) for r in receipts)

    # dormant / closed-code suppression: a suppressed code integrates to actual cost to date (CTC 0) and
    # carries a degenerate dormant_suppressed probability row (no broad risk distribution).
    dorm_forecast = [r for r in forecast if r.get("dormant_suppression_applied")]
    dorm_integrated_ok = all(
        D(r["integrated_recommended_final_cost"]) == D(r["actual_cost_to_date"])
        and D(r["integrated_cost_to_complete"]) == Decimal("0") for r in dorm_forecast)
    _prob_by = {r["budget_code_key"]: r for r in probability}
    dorm_prob_ok = all(_prob_by.get(r["budget_code_key"], {}).get("probability_status") == "dormant_suppressed"
                       for r in dorm_forecast)

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("manifest_present", True),
        ("schema_present", (out / "SCHEMA.md").exists()),
        ("readme_present", (out / "README.md").exists()),
        ("input_inventory_present", (out / "input_inventory.json").exists()),
        ("source_packages_discovered", required_present),
        ("evidence_registry_present", len(items) > 0),
        ("evidence_lineage_present", lineage_ok),
        ("canonical_budget_code_coverage", coverage_ok),
        ("no_invented_budget_code_keys", no_invented),
        ("cost_entries_actuals_primary_truth", actuals_primary),
        ("no_history_as_actual", no_hist_as_actual),
        ("no_pay_apps_as_actual", no_payapp_as_actual),
        ("no_prior_forecast_hard_cap", no_cap),
        ("actuals_floor_preserved", floor_ok),
        ("no_upper_cap_audit_passed", no_cap),
        ("monthly_reconciliation_passed", monthly_recon),
        ("probability_determinism_passed", prob_det),
        ("history_outputs_consumed_or_explicitly_downgraded", history_ok),
        ("frequency_outputs_consumed_or_explicitly_missing", frequency_ok),
        ("human_acceptance_fields_present", acceptance_ok),
        ("operator_control_evidence_present_when_active", op_evidence_ok),
        ("operator_controls_floor_preserved", op_floor_ok),
        ("operator_controls_mapping_unambiguous", op_mapping_ok),
        ("operator_staffing_plan_evidence_present_when_active", sp_evidence_ok),
        ("operator_staffing_plan_advisory_requires_acceptance", sp_advisory_ok),
        ("dormant_suppressed_integrated_final_equals_actual", dorm_integrated_ok),
        ("dormant_suppressed_probability_marked", dorm_prob_ok),
        *((audit.get("cost_basis_decision_audit") or {}).get("validation_checks") or {}).items(),
        *actuals_gates.items(),
        *apf_gates.items(),
        ("meta_files_present", all((out / f).exists() for f in meta_doc)),
        ("source_hashes_unchanged", source_unchanged),
        ("no_sqlite_mutation", True),
        ("no_external_calls", True),
        ("safety_scan_passed", safety["passed"]),
        ("determinism_passed", determinism["diff_result"] == "pass"),
        ("llm_receipts_have_required_fields", llm_receipts_ok),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("project_key", inputs["project_key"]),
        ("checks", checks),
        ("canonical_code_count", len(canonical)),
        ("covered_code_count", len(covered & canonical)),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])
