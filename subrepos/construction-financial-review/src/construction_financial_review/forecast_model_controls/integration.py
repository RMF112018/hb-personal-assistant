"""Shared entrypoint that the standalone package, forecast_monthly, and forecast_comprehensive import.

Each consumer already knows the canonical universe, per-code actuals/amounts, the model's uncontrolled
final/CTC, the per-code schedule evidence, the project schedule, and the forecast calendar. This helper
assembles the reference + schedule context, runs load -> map -> resolve, and (optionally) fails closed
before generation when a control file is structurally invalid or carries an unsafe mapping / reference /
window / floor / manual / duplicate violation.

The ``override_path`` (``--forecast-model-control-file``) flows through ``prepare`` to every consumer so a
validation/fixture run never silently falls back to the dormant committed config.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from . import apply, load_controls
from . import mapping as cmap


def build_ref_ctx(canonical_keys, amounts_by_key: dict, rec_by_key: dict,
                  prior_final_by_key: dict | None = None, *, context_package_path: str | None = None,
                  intelligence_package_path: str | None = None,
                  prior_comprehensive_package_path: str | None = None,
                  prior_is_current_run: bool = False,
                  projected_budget_distinct_by_key: dict | None = None) -> dict:
    """Assemble the per-key reference context consumed by ``target_sources.resolve_reference``."""
    prior_final_by_key = prior_final_by_key or {}
    projected_budget_distinct_by_key = projected_budget_distinct_by_key or {}
    out = {}
    for key in canonical_keys:
        rec = rec_by_key.get(key) or {}
        out[key] = {
            "budget_code_key": key,
            "amounts": amounts_by_key.get(key) or {},
            "projected_budget_distinct": projected_budget_distinct_by_key.get(key),
            "context_package_path": context_package_path,
            "intelligence_final": {"value": rec.get("recommended_final_cost"),
                                   "source_package_path": intelligence_package_path},
            "prior_comprehensive_final": {"value": prior_final_by_key.get(key),
                                          "source_package_path": prior_comprehensive_package_path,
                                          "is_current_run": bool(prior_is_current_run)},
        }
    return out


def prepare(cfg: dict, subproject_root: Path, canonical_keys, actuals_by_key: dict, ref_ctx_by_key: dict,
            schedule_by_key: dict, project_schedule: dict, calendar_months: list,
            model_final_by_key: dict, model_ctc_by_key: dict, project_key: str,
            stamp_iso: str | None = None, override_path: str | Path | None = None) -> "OrderedDict":
    """Return load_result, mapping_results, and the resolved decision bundle."""
    load_result = load_controls.load(cfg, subproject_root, stamp_iso, override_path)
    cc_index = cmap.cost_code_to_keys(canonical_keys)
    mapping_results = [cmap.map_control(c, canonical_keys, cc_index) for c in load_result["controls"]]
    cfg_fmc = load_controls.model_controls_config(cfg)
    resolved = apply.resolve(load_result, mapping_results, cfg_fmc, actuals_by_key, ref_ctx_by_key,
                             schedule_by_key, project_schedule, calendar_months, model_final_by_key,
                             model_ctc_by_key, project_key)
    return OrderedDict([("load_result", load_result), ("mapping_results", mapping_results),
                        ("resolved", resolved)])


def integration_active(cfg: dict, bundle: dict) -> bool:
    return bool(bundle["load_result"]["enabled"] and bundle["load_result"]["present"])


def has_applied_controls(bundle: dict) -> bool:
    return bool(bundle["resolved"]["by_key"])


def gate_reasons(cfg: dict, bundle: dict) -> list:
    """List of fail-closed reasons (empty when safe to integrate)."""
    cfg_fmc = load_controls.model_controls_config(cfg)
    lr, rv = bundle["load_result"], bundle["resolved"]
    reasons = []
    if not lr["parse_ok"]:
        reasons.append("control file cannot parse")
    if lr["duplicate_control_ids"]:
        reasons.append(f"duplicate control_id(s): {lr['duplicate_control_ids']}")
    if lr["controls_missing_required_fields"]:
        reasons.append("control(s) missing required/conditional/acceptance fields")
    if rv["any_ambiguous_mapping"] and cfg_fmc.get("fail_on_ambiguous_cost_code", True):
        reasons.append("ambiguous cost_code mapping")
    if rv["any_invented"] and cfg_fmc.get("fail_on_unknown_budget_code_key", True):
        reasons.append("unknown (invented) budget_code_key")
    if rv["any_unknown_source"]:
        reasons.append("unknown reference_source")
    if rv["any_missing_reference"] and cfg_fmc.get("fail_on_missing_target_reference", True):
        reasons.append("missing selected reference value")
    if rv["any_ambiguous_reference"]:
        reasons.append("ambiguous projected_budget vs projected_costs reference")
    if rv["any_circular_reference"]:
        reasons.append("circular prior_comprehensive_integrated_final reference")
    if rv["any_floor_conflict"] and cfg_fmc.get("preserve_actuals_floor", True):
        reasons.append("controlled final below actuals floor")
    if rv["any_impossible_window"]:
        reasons.append("resolved forecast window has no active months")
    if rv["any_window_degraded_blocked"]:
        reasons.append("schedule dataset missing and horizon fallback disabled")
    if rv["any_manual_invalid"]:
        reasons.append("manual monthly/total values invalid or do not reconcile")
    if rv["any_constraint_unresolvable"]:
        reasons.append("value constraint could not be resolved")
    if rv["any_duplicate_conflict"] and cfg_fmc.get("fail_on_duplicate_conflicting_controls", True):
        reasons.append("duplicate conflicting accepted model controls for a budget code")
    return reasons


def assert_integration_safe(cfg: dict, bundle: dict) -> None:
    """Fail closed (SystemExit) before monthly/comprehensive generation when controls are unsafe."""
    if not integration_active(cfg, bundle):
        return
    reasons = gate_reasons(cfg, bundle)
    if reasons:
        raise SystemExit(
            "ERROR: forecast model controls failed validation (fail closed): " + "; ".join(reasons))
