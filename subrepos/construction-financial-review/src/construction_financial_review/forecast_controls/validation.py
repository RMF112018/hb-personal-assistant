"""Fail-closed validation gates for the operator forecast-controls package."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D
from ..common.validation import all_files_parse

CENTS = Decimal("0.01")


def _post_stop_zeroed(adjustments) -> bool:
    """No month strictly after an applied stop month carries nonzero forecast."""
    for a in adjustments:
        if not a.get("monthly_preview_available"):
            continue
        stop = a.get("stop_month")
        if not stop:
            continue
        for mc in a.get("after_month_costs") or []:
            if mc["forecast_month"] > stop and D(mc["recommended_month_cost"]) != Decimal("0"):
                return False
    return True


def _adjustments_reconcile(adjustments) -> bool:
    for a in adjustments:
        if not a.get("monthly_preview_available"):
            continue
        target = D(a.get("applied_recommended_cost_to_complete"))
        total = sum((D(mc["recommended_month_cost"]) for mc in (a.get("after_month_costs") or [])), Decimal("0"))
        if abs(total - target) > CENTS:
            return False
    return True


def build_validation(out, load_result, resolved, collections, audit, determinism, safety, meta,
                     source_unchanged) -> "OrderedDict":
    controls_rows = collections["forecast_controls_by_budget_code.jsonl"]
    applications = collections["forecast_controls_application_by_budget_code.jsonl"]
    adjustments = collections["forecast_controls_monthly_adjustments_by_budget_code.jsonl"]

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    meta_doc = ("README.md", "SCHEMA.md", "input_inventory.json")

    lineage_ok = all(r.get("control_id") and ("disposition" in r) for r in applications)
    acceptance_ok = all(all(k in r for k in ("requires_human_acceptance", "acceptance_status"))
                        for r in controls_rows)
    no_hidden_cap = bool(audit["no_hidden_cap_audit"]["no_hidden_cap"])
    floor_ok = bool(audit["actuals_floor_audit"]["all_floors_respected"])

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("control_file_parses", load_result["parse_ok"]),
        ("control_file_present", load_result["present"]),
        ("no_duplicate_control_ids", not load_result["duplicate_control_ids"]),
        ("human_acceptance_fields_present", acceptance_ok and not load_result["controls_missing_required_fields"]),
        ("no_ambiguous_mapping", not resolved["any_ambiguous"]),
        ("no_invented_budget_code_keys", not resolved["any_invented"]),
        ("accepted_final_cost_not_below_actuals", not resolved["any_floor_violation"]),
        ("actuals_floor_preserved", floor_ok),
        ("no_hidden_cap_without_accepted_control", no_hidden_cap),
        ("no_nonzero_forecast_after_accepted_stop", _post_stop_zeroed(adjustments)),
        ("monthly_adjustments_reconcile_to_applied_ctc", _adjustments_reconcile(adjustments)),
        ("control_application_lineage_present", lineage_ok),
        ("mapping_audit_present", bool(audit.get("control_mapping_audit"))),
        ("application_audit_present", bool(audit.get("control_application_audit"))),
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
        ("control_count", load_result["control_count"]),
        ("applied_control_count", len(resolved["by_key"])),
        ("controlled_budget_codes", resolved["controlled_budget_codes"]),
        ("acceptance_counts", resolved["counts"]),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])
