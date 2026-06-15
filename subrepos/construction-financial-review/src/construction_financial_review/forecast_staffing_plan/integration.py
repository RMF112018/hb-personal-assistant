"""Shared entrypoint that the standalone generator + forecast_cost_frequency / forecast_monthly /
forecast_comprehensive import to consume the staffing plan.

Runs discover -> load override -> resolve mapping -> resolve plan against the caller's canonical
universe, actuals, and accepted recommendations, and (optionally) fails closed before generation when
the source package is unsafe, the override is structurally invalid, or an applied mapping is ambiguous /
invented / below the actuals floor / fails reconciliation.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from . import apply, load_mapping, mapping, package_discovery


def prepare(cfg: dict, subproject_root: Path, data_root: Path, canonical_rows, actuals_by_key: dict,
            rec_by_key: dict, project_key: str, *, stamp_iso: str | None = None,
            monthly_actuals_by_key: dict | None = None, forecast_horizon_end: str | None = None,
            freq_basis_by_key: dict | None = None) -> "OrderedDict":
    """Return discovery, mapping load/result, and the resolved staffing-plan bundle."""
    discovery = package_discovery.discover(cfg, data_root)
    mapping_load = load_mapping.load(cfg, subproject_root, stamp_iso)

    sp = package_discovery.staffing_config(cfg)
    require_acceptance = bool(sp.get("require_mapping_acceptance", True))
    canonical_keys = {r.get("budget_code_key") for r in canonical_rows}
    fam_index = mapping.build_canonical_family_index(canonical_rows)

    overrides_by_cc = {}
    for r in mapping_load["rows"]:
        overrides_by_cc.setdefault(r.get("source_cost_code"), []).append(r)

    cost_codes = (discovery.get("parsed") or {}).get("cost_codes") or []
    mapping_results = [mapping.resolve_cost_code(cc, fam_index, canonical_keys, overrides_by_cc,
                                                 require_acceptance) for cc in cost_codes]

    resolved = apply.resolve(discovery, mapping_results, actuals_by_key, rec_by_key, sp, project_key,
                             monthly_actuals_by_key=monthly_actuals_by_key,
                             forecast_horizon_end=forecast_horizon_end,
                             freq_basis_by_key=freq_basis_by_key)
    return OrderedDict([
        ("discovery", discovery),
        ("mapping_load", mapping_load),
        ("mapping_results", mapping_results),
        ("resolved", resolved),
    ])


def integration_active(cfg: dict, bundle: dict) -> bool:
    """True when the staffing plan is enabled and a source package is present."""
    return bool(package_discovery.staffing_config(cfg).get("enabled") and bundle["discovery"]["present"])


def gate_reasons(cfg: dict, bundle: dict) -> list:
    """List of fail-closed reasons (empty when safe to integrate)."""
    sp = package_discovery.staffing_config(cfg)
    disc, ml, rv = bundle["discovery"], bundle["mapping_load"], bundle["resolved"]
    reasons = []
    if sp.get("enabled") and not disc["present"]:
        reasons.append("staffing package required (enabled) but not found")
    if disc["present"]:
        reasons.extend(package_discovery.gate_reasons(disc))
    if not ml["parse_ok"]:
        reasons.append("mapping override file cannot parse")
    if ml["duplicate_cost_codes"]:
        reasons.append(f"duplicate mapping rows: {ml['duplicate_cost_codes']}")
    if ml["rows_missing_required_fields"]:
        reasons.append("mapping override row(s) missing required fields")
    if ml["over_allocated_cost_codes"]:
        reasons.append(f"allocation_share > 1.0 for: {ml['over_allocated_cost_codes']}")
    if sp.get("fail_on_ambiguous_mapping", True) and rv["any_ambiguous_applied"]:
        reasons.append("ambiguous/invalid mapping applied")
    if rv["any_unmapped_applied"]:
        reasons.append("unmapped cost code applied")
    if rv["any_invented"]:
        reasons.append("override targets a non-canonical budget-code key")
    if rv["any_floor_violation"]:
        reasons.append("staffing-plan implied final below actuals floor")
    if rv["any_reconciliation_failure"]:
        reasons.append("staffing-plan monthly values failed reconciliation")
    return reasons


def assert_integration_safe(cfg: dict, bundle: dict) -> None:
    """Fail closed (SystemExit) before downstream generation when the staffing plan is unsafe."""
    if not integration_active(cfg, bundle):
        # If enabled-but-missing, that is itself a gate reason; surface it.
        if package_discovery.staffing_config(cfg).get("enabled") and not bundle["discovery"]["present"]:
            raise SystemExit("ERROR: staffing plan enabled but source package not found (fail closed)")
        return
    reasons = gate_reasons(cfg, bundle)
    if reasons:
        raise SystemExit("ERROR: staffing plan failed validation (fail closed): " + "; ".join(reasons))
