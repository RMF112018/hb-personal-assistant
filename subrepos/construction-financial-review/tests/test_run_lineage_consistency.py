"""Full-fresh-run lineage: shared context resolver + comprehensive full_run_lineage_consistent gate."""
import json
from pathlib import Path

import pytest

from construction_financial_review.common import lineage
from construction_financial_review.forecast_comprehensive import (
    generate_comprehensive_forecast_package as cgen,
)

PROJECT = "tropical"


def _ctx(root: Path, stamp: str) -> Path:
    pkg = root / f"forecast_context_package_{PROJECT}_{stamp}"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps(
        {"package_name": pkg.name, "generated_stamp": stamp,
         "generated_timestamp_local": "2026-06-17T04:34:13"}))
    return pkg


def _downstream(root: Path, ptype_dir: str, consumed_stamp, has_meta=True) -> Path:
    pkg = root / ptype_dir
    pkg.mkdir(parents=True)
    inv = {"generation": {}}
    if has_meta:
        inv["context_lineage"] = lineage.context_lineage(
            root / f"forecast_context_package_{PROJECT}_{consumed_stamp}", "latest_glob")
    (pkg / "input_inventory.json").write_text(json.dumps(inv))
    return pkg


def _discovery(root, present):
    out = {}
    for pt, path in present.items():
        out[pt] = {"package_type": pt, "present": path is not None,
                   "path": str(path) if path else None}
    for pt in ("context", "intelligence", "staffing_plan", "monthly", "cost_frequency", "probability"):
        out.setdefault(pt, {"package_type": pt, "present": False, "path": None})
    return out


# default latest-glob resolution
def test_resolver_latest_glob(tmp_path):
    _ctx(tmp_path, "20260101_000000")
    newest = _ctx(tmp_path, "20260617_043410")
    pkg, meta = lineage.resolve_context_package(tmp_path, {}, PROJECT)
    assert pkg == newest
    assert meta["consumed_context_stamp"] == "20260617_043410"
    assert meta["lineage_source"] == "latest_glob"


# pinned stamp resolves the exact package
def test_resolver_pinned_exact(tmp_path):
    _ctx(tmp_path, "20260617_043410")
    pinned = _ctx(tmp_path, "20260614_084510")
    pkg, meta = lineage.resolve_context_package(tmp_path, {}, PROJECT, context_stamp="20260614_084510")
    assert pkg == pinned and meta["lineage_source"] == "pinned"
    assert meta["consumed_context_stamp"] == "20260614_084510"


# pinned stamp missing fails closed
def test_resolver_pinned_missing_fails_closed(tmp_path):
    _ctx(tmp_path, "20260617_043410")
    with pytest.raises(SystemExit):
        lineage.resolve_context_package(tmp_path, {}, PROJECT,
                                        context_stamp="20990101_000000", strict_pin=True)


# pin_context_into_cfg injects the resolved name so downstream discovery is uniform
def test_pin_injects_into_cfg(tmp_path):
    _ctx(tmp_path, "20260617_043410")
    cfg = {"forecast_context_package": "forecast_context_package_tropical_20260614_084510"}  # stale
    new_cfg, pkg, meta = lineage.pin_context_into_cfg(cfg, tmp_path, PROJECT)
    assert new_cfg["forecast_context_package"] == "forecast_context_package_tropical_20260617_043410"
    assert meta["lineage_source"] == "latest_glob"


# gate: all present packages consumed the same context -> consistent
def test_gate_consistent(tmp_path):
    own = "20260617_043410"
    _ctx(tmp_path, own)
    present = {"context": tmp_path / f"forecast_context_package_{PROJECT}_{own}"}
    for pt in ("intelligence", "staffing_plan", "monthly"):
        present[pt] = _downstream(tmp_path, f"{pt}_pkg", own)
    audit = cgen._run_lineage_audit(PROJECT, _discovery(tmp_path, present),
                                    lineage.context_lineage(present["context"], "pinned"))
    assert audit["full_run_lineage_consistent"] is True


# gate: staffing/monthly consumed a stale context -> inconsistent -> fail
def test_gate_inconsistent_fails(tmp_path):
    own = "20260617_043410"
    _ctx(tmp_path, own)
    _ctx(tmp_path, "20260614_084510")
    present = {"context": tmp_path / f"forecast_context_package_{PROJECT}_{own}",
               "intelligence": _downstream(tmp_path, "intelligence_pkg", own),
               "staffing_plan": _downstream(tmp_path, "staffing_pkg", "20260614_084510"),
               "monthly": _downstream(tmp_path, "monthly_pkg", "20260614_084510")}
    audit = cgen._run_lineage_audit(PROJECT, _discovery(tmp_path, present),
                                    lineage.context_lineage(present["context"], "pinned"))
    assert audit["full_run_lineage_consistent"] is False
    statuses = {r["package_type"]: r["status"] for r in audit["packages"]}
    assert statuses["staffing_plan"] == "inconsistent"


# gate: missing metadata fails closed only under a pinned (strict) run
def test_gate_missing_metadata_strict_vs_legacy(tmp_path):
    own = "20260617_043410"
    _ctx(tmp_path, own)
    present = {"context": tmp_path / f"forecast_context_package_{PROJECT}_{own}",
               "monthly": _downstream(tmp_path, "monthly_pkg", own, has_meta=False)}
    disc = _discovery(tmp_path, present)
    strict = cgen._run_lineage_audit(PROJECT, disc,
                                     lineage.context_lineage(present["context"], "pinned"))
    legacy = cgen._run_lineage_audit(PROJECT, disc,
                                     lineage.context_lineage(present["context"], "latest_glob"))
    assert strict["full_run_lineage_consistent"] is False      # strict fresh run fails closed
    assert strict["missing_context_lineage_metadata"] is True
    assert legacy["full_run_lineage_consistent"] is True       # legacy/ad-hoc tolerated
