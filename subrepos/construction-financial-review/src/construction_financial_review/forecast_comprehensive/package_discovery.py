"""Discover the latest of each accepted evidence package and verify manifest integrity (read-only)."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from ..common.io import read_json

# (config key, package_type, required) — globs resolved from cfg["forecast_comprehensive"] with defaults
PACKAGE_SPECS = (
    ("forecast_context_package_glob", "context", True, "forecast_context_package_tropical_*"),
    ("forecast_intelligence_package_glob", "intelligence", True, "forecast_accuracy_next_package_tropical_*"),
    ("forecast_monthly_package_glob", "monthly", True, "forecast_monthly_package_tropical_*"),
    ("forecast_probability_package_glob", "probability", False, "forecast_probability_package_tropical_*"),
    ("forecast_history_informed_package_glob", "history_informed", False,
     "forecast_history_informed_package_tropical_*"),
    ("forecast_cost_frequency_package_glob", "cost_frequency", False,
     "forecast_cost_frequency_package_tropical_*"),
    ("forecast_crosswalk_v2_package_glob", "crosswalk_v2", False,
     "forecast_analysis_package_tropical_crosswalk_v2_*"),
    ("schedule_integrated_package_glob", "schedule_integrated", False,
     "schedule_integrated_forecast_package_tropical_*"),
    ("forecast_staffing_plan_package_glob", "staffing_plan", False,
     "forecast_staffing_plan_package_tropical_*"),
)


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _manifest_ok(pkg: Path) -> tuple[bool, dict]:
    mp = pkg / "manifest.json"
    if not mp.exists():
        return False, {}
    try:
        return True, read_json(mp)
    except Exception:
        return False, {}


def discover(cfg: dict, data_root: Path) -> OrderedDict:
    """Return an ordered discovery registry keyed by package_type."""
    fc = cfg.get("forecast_comprehensive") or {}
    out = OrderedDict()
    for cfg_key, ptype, required, default_glob in PACKAGE_SPECS:
        glob = fc.get(cfg_key) or default_glob
        pkg = _latest_dir(data_root, glob)
        man_ok, manifest = (_manifest_ok(pkg) if pkg else (False, {}))
        out[ptype] = OrderedDict([
            ("package_type", ptype),
            ("required", required),
            ("glob", glob),
            ("present", pkg is not None),
            ("path", str(pkg) if pkg else None),
            ("package_name", pkg.name if pkg else None),
            ("manifest_present", man_ok),
            ("manifest_version", manifest.get("manifest_version")),
            ("contract_version", manifest.get("contract_version")),
        ])
    return out


def missing_required(discovery: OrderedDict) -> list:
    return [d["package_type"] for d in discovery.values() if d["required"] and not d["present"]]
