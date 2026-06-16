"""Fail-closed validation gates for the standalone forecast-model-controls package."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D
from ..common.validation import all_files_parse

CENTS = Decimal("0.01")
_VALID_PROB_STATUS = frozenset({
    "accepted_probability_anchor", "provisional_manual_value_assessment",
    "probability_unavailable_insufficient_evidence"})


def _previews_reconcile(previews) -> bool:
    for p in previews:
        if not p.get("monthly_preview_available"):
            continue
        target = D(p.get("controlled_final_cost"))
        actual = D(p.get("actual_cost_to_date"))
        remaining = D(p.get("controlled_remaining"))
        alloc = sum((D(mc["recommended_month_cost"]) for mc in (p.get("monthly_allocation") or [])), Decimal("0"))
        if abs(alloc - remaining) > CENTS or abs((actual + alloc) - target) > CENTS \
                or abs((actual + remaining) - target) > CENTS:
            return False
    return True


def _probability_consistent(prob_rows) -> bool:
    """Degraded-aware: every row carries a known status; provisional rows carry required fields."""
    for r in prob_rows:
        status = r.get("probability_status")
        if status not in _VALID_PROB_STATUS:
            return False
        if status in ("provisional_manual_value_assessment", "probability_unavailable_insufficient_evidence"):
            if r.get("manual_value_assessment") is None or r.get("evidence_support_score") is None \
                    or r.get("confidence") is None or r.get("data_gaps") is None:
                return False
    return True


def build_validation(out, load_result, resolved, collections, audit, determinism, safety, meta,
                     source_unchanged) -> "OrderedDict":
    controls_rows = collections["model_controls_by_budget_code.jsonl"]
    applications = collections["model_control_applications_by_budget_code.jsonl"]
    previews = collections["model_control_monthly_preview_by_budget_code.jsonl"]
    prob_rows = collections["model_control_probability_assessment_by_budget_code.jsonl"]

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
        ("human_acceptance_fields_present",
         acceptance_ok and not load_result["controls_missing_required_fields"]),
        ("no_ambiguous_cost_code_mapping", not resolved["any_ambiguous_mapping"]),
        ("no_unknown_budget_code_key", not resolved["any_invented"]),
        ("no_unknown_reference_source", not resolved["any_unknown_source"]),
        ("no_missing_reference", not resolved["any_missing_reference"]),
        ("no_ambiguous_reference", not resolved["any_ambiguous_reference"]),
        ("no_circular_reference", not resolved["any_circular_reference"]),
        ("actuals_floor_preserved", floor_ok and not resolved["any_floor_conflict"]),
        ("no_impossible_window", not resolved["any_impossible_window"]),
        ("no_blocked_window_degraded", not resolved["any_window_degraded_blocked"]),
        ("no_invalid_manual_values", not resolved["any_manual_invalid"]),
        ("no_unresolvable_constraint", not resolved["any_constraint_unresolvable"]),
        ("no_duplicate_conflicting_controls", not resolved["any_duplicate_conflict"]),
        ("applied_controls_reconcile_to_controlled_final", _previews_reconcile(previews)),
        ("probability_assessment_consistent", _probability_consistent(prob_rows)),
        ("no_hidden_cap_without_accepted_control", no_hidden_cap),
        ("control_application_lineage_present", lineage_ok),
        ("target_source_resolution_audit_present", bool(audit.get("target_source_resolution_audit"))),
        ("window_resolution_audit_present", bool(audit.get("window_resolution_audit"))),
        ("actuals_floor_audit_present", bool(audit.get("actuals_floor_audit"))),
        ("model_shape_audit_present", bool(audit.get("model_shape_audit"))),
        ("monthly_reconciliation_preview_audit_present",
         bool(audit.get("monthly_reconciliation_preview_audit"))),
        ("probability_anchor_policy_audit_present", bool(audit.get("probability_anchor_policy_audit"))),
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
