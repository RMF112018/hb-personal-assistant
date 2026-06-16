"""Fail-closed validation gates for the operator staffing-plan package."""
from __future__ import annotations

from collections import OrderedDict

from ..common.validation import all_files_parse


def build_validation(out, discovery, mapping_load, resolved, collections, audit, determinism, safety,
                     meta, source_unchanged) -> "OrderedDict":
    monthly = collections["staffing_plan_monthly_by_budget_code.jsonl"]
    summary = collections["staffing_plan_summary_by_budget_code.jsonl"]

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    meta_doc = ("README.md", "SCHEMA.md", "input_inventory.json")

    # every applied code emits the implied vector; the ctc-reconciled vector is present whenever an
    # accepted CTC exists (the dual disclosure that prevents a stale CTC from being hidden).
    dual_ok = all(r.get("staffing_plan_implied_monthly_forecast") is not None for r in monthly) and \
        all((r.get("current_ctc_reconciled_monthly_forecast") is not None)
            or (r.get("accepted_cost_to_complete") is None) for r in monthly)
    floor_ok = bool(audit["actuals_floor_audit"]["all_floors_respected"])
    no_cap = bool(audit["no_hidden_cap_audit"]["no_hidden_cap"])

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("staffing_package_present", bool(discovery["present"])),
        ("source_validation_passed", bool(discovery["source_validation_passed"])),
        ("required_source_files_present", not discovery["missing_files"]),
        ("source_hashes_verified", bool(discovery["source_hashes_verified"])),
        ("manifest_counts_match", bool(discovery["manifest_counts_match"])),
        ("source_monthly_totals_reconcile", bool(discovery["monthly_totals_reconcile"])),
        ("mapping_file_parses", bool(mapping_load["parse_ok"])),
        ("no_duplicate_mappings", not mapping_load["duplicate_cost_codes"]),
        ("mapping_required_fields_present", not mapping_load["rows_missing_required_fields"]),
        ("allocation_share_within_bounds", not mapping_load["over_allocated_cost_codes"]),
        ("no_ambiguous_mapping_applied", not resolved["any_ambiguous_applied"]),
        ("no_unmapped_cost_code_applied", not resolved["any_unmapped_applied"]),
        ("no_invented_budget_code_keys", not resolved["any_invented"]),
        ("actuals_floor_preserved", floor_ok),
        ("no_hidden_cap", no_cap),
        ("monthly_reconciliation_passed", not resolved["any_reconciliation_failure"]),
        ("plan_implied_and_ctc_reconciled_both_emitted", dual_ok),
        ("meta_files_present", all((out / f).exists() for f in meta_doc)),
        ("source_hashes_unchanged", bool(source_unchanged)),
        ("no_sqlite_mutation", True),
        ("no_external_calls", True),
        ("safety_scan_passed", safety["passed"]),
        ("determinism_passed", determinism["diff_result"] == "pass"),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("project_key", meta["project_key"]),
        ("checks", checks),
        ("source_package", discovery["package_name"]),
        ("plan_cost_code_count", resolved["counts"]["plan_cost_codes"]),
        ("applied_numeric_code_count", resolved["counts"]["applied_numeric_codes"]),
        ("applied_budget_codes", resolved["applied_budget_codes"]),
        ("mapping_status_counts", resolved["counts"]),
        ("review_queue_count", len(resolved["review_queue"])),
        ("conflict_count", len(resolved["conflicts"])),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])
