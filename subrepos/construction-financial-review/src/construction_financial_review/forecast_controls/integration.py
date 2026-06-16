"""Shared entrypoint that forecast_monthly and forecast_comprehensive import to consume controls.

Both integrations already know the canonical budget-code universe and per-code actual cost to date, so
this helper just runs load -> map -> resolve against those and (optionally) fails closed before
generation when a control file is structurally invalid or carries an unsafe mapping / floor violation.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from . import apply, load_controls
from . import mapping as cmap


def prepare(cfg: dict, subproject_root: Path, canonical_keys, actuals_by_key: dict,
            project_key: str, stamp_iso: str | None = None) -> "OrderedDict":
    """Return load_result, mapping_results, and the resolved decision bundle."""
    load_result = load_controls.load(cfg, subproject_root, stamp_iso)
    cc_index = cmap.cost_code_to_keys(canonical_keys)
    mapping_results = [cmap.map_control(c, canonical_keys, cc_index) for c in load_result["controls"]]
    cfg_fctl = load_controls.controls_config(cfg)
    resolved = apply.resolve(load_result, mapping_results, cfg_fctl, actuals_by_key, project_key)
    return OrderedDict([
        ("load_result", load_result),
        ("mapping_results", mapping_results),
        ("resolved", resolved),
    ])


def integration_active(cfg: dict, bundle: dict) -> bool:
    """True when controls are enabled and a control file is present."""
    return bool(bundle["load_result"]["enabled"] and bundle["load_result"]["present"])


def gate_reasons(bundle: dict) -> list:
    """List of fail-closed reasons (empty when safe to integrate)."""
    lr, rv = bundle["load_result"], bundle["resolved"]
    reasons = []
    if not lr["parse_ok"]:
        reasons.append("control file cannot parse")
    if lr["duplicate_control_ids"]:
        reasons.append(f"duplicate control_id(s): {lr['duplicate_control_ids']}")
    if lr["controls_missing_required_fields"]:
        reasons.append("control(s) missing required human-acceptance/identity fields")
    if rv["any_ambiguous"]:
        reasons.append("ambiguous cost_code mapping")
    if rv["any_invented"]:
        reasons.append("invented budget_code_key")
    if rv["any_floor_violation"]:
        reasons.append("accepted dollar control below actuals floor")
    return reasons


def assert_integration_safe(cfg: dict, bundle: dict) -> None:
    """Fail closed (SystemExit) before monthly/comprehensive generation when controls are unsafe."""
    if not integration_active(cfg, bundle):
        return
    reasons = gate_reasons(bundle)
    if reasons:
        raise SystemExit("ERROR: forecast controls failed validation (fail closed): " + "; ".join(reasons))
