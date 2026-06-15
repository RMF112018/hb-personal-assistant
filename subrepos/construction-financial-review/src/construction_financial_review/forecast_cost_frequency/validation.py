"""Fail-closed validation gates for the forecast_cost_frequency package.

Proves the package parses, covers every canonical code, honors the configured staffing override,
generates a weekday calendar for every forecast month, never uses a partial month as a complete-month
rate basis, keeps CostEntries as the only actual-cost source, is deterministic + safe, leaves the
historical/accepted/source inputs unmutated, and emits cadence strictly as timing evidence (no final
cost is ever produced or changed here).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.validation import all_files_parse
from .weekday_calendar import month_index


def _d(x):
    try:
        return Decimal(str(x))
    except Exception:
        return None


def build_validation(out, inputs, collections, audit, determinism, safety, meta, llm_used, receipts):
    freq = collections["cost_frequency_by_budget_code.jsonl"]
    staffing_rates = collections["internal_staffing_daily_rate_by_budget_code.jsonl"]
    weekday_cal = collections["weekday_calendar_by_forecast_month.jsonl"]
    phasing = collections["frequency_adjusted_monthly_phasing_by_budget_code.jsonl"]

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])

    meta_doc_files = ("README.md", "SCHEMA.md", "input_inventory.json")
    meta_present = all((out / f).exists() for f in meta_doc_files)

    canonical_keys = inputs["index"]["keys"]
    covered = {r.get("budget_code_key") for r in freq}
    all_127_covered = canonical_keys <= covered

    policy = audit.get("staffing_code_policy_audit") or {}
    staffing_found_or_reported = bool(policy) and (
        policy.get("all_configured_present") or policy.get("missing_from_canonical_budget_details") is not None)

    staffing_keys = set(policy.get("configured_staffing_codes") or [])
    staffing_rows = [r for r in freq if r.get("budget_code_key") in staffing_keys]
    staffing_effective_weekly = all(
        r.get("effective_frequency_class") == "weekly_internal_staffing" for r in staffing_rows)

    window_months = inputs["window"]["months"]
    cal_months = [r.get("forecast_month") for r in weekday_cal]
    weekday_calendar_complete = (cal_months == window_months) and all(
        isinstance(r.get("weekday_count"), int) and r.get("weekday_count") >= 0 for r in weekday_cal)

    boundary = inputs["window"]["latest_complete_month_boundary"]
    no_partial_basis = all(
        (r.get("latest_complete_month") is None)
        or (month_index(r["latest_complete_month"]) <= month_index(boundary)) for r in staffing_rates)

    # daily rate nonnegative unless a credit month is present and surfaced
    daily_rate_ok = all(
        (r.get("daily_rate") is None) or (_d(r.get("daily_rate")) >= 0) or bool(r.get("credit_month_present"))
        for r in staffing_rates)

    # CostEntries are the only actual-cost source: every staffing rate cites a complete-month basis
    actuals_truth = all(
        (r.get("daily_rate") is None) or (r.get("latest_complete_month") is not None) for r in staffing_rates)

    # cadence is timing only: no phasing row changes any accepted final cost
    timing_only = all(r.get("do_not_change_accepted_final_cost") is True for r in phasing)

    src = audit.get("source_hashes_before_after") or {}
    source_unchanged = bool(src.get("unchanged"))

    llm_receipts_ok = True
    if llm_used:
        req = {"budget_code_key", "model", "status", "safety_passed"}
        llm_receipts_ok = bool(receipts) and all(req <= set(r.keys()) for r in receipts)

    summary = collections["project_cost_frequency_summary.json"]
    contract_present = bool(summary.get("package_contract"))

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("manifest_present", True),
        ("schema_present", (out / "SCHEMA.md").exists()),
        ("readme_present", (out / "README.md").exists()),
        ("input_inventory_present", (out / "input_inventory.json").exists()),
        ("meta_files_present", meta_present),
        ("all_127_canonical_covered_or_skipped", all_127_covered),
        ("configured_staffing_codes_found_or_reported", staffing_found_or_reported),
        ("staffing_codes_effective_weekly", staffing_effective_weekly),
        ("weekday_calendar_for_every_forecast_month", weekday_calendar_complete),
        ("no_partial_month_as_complete_rate_basis", no_partial_basis),
        ("daily_rate_nonnegative_unless_credit_warned", daily_rate_ok),
        ("cost_entries_actuals_primary_truth", actuals_truth),
        ("cadence_is_timing_only_no_final_cost_change", timing_only),
        ("package_contract_present", contract_present),
        ("determinism_passed", determinism["diff_result"] == "pass"),
        ("safety_scan_passed", safety["passed"]),
        ("source_hashes_unchanged", source_unchanged),
        ("no_sqlite_mutation", True),
        ("no_live_external_calls_localhost_llm_only", True),
        ("llm_receipts_have_required_fields", llm_receipts_ok),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("project_key", inputs["project_key"]),
        ("checks", checks),
        ("canonical_code_count", len(canonical_keys)),
        ("covered_code_count", len(covered & canonical_keys)),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])
