"""Discover + validate the extracted staffing JSON package (read-only, fail-closed).

Finds the latest ``staffing_json_package_tropical_*`` under the data root (config-overridable), then
verifies: required files present, the source package's own ``validation_report.json`` passed, every
generated file's sha256 matches ``audit/source_hashes.json`` (proving the package was not altered),
manifest counts match the parsed rows, and the parsed monthly totals reconcile to the source package's
project + per-cost-code totals. Nothing in the source package is mutated.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl
from ..common.money import D, money_str

CENTS = Decimal("0.01")

DEFAULT_GLOB = "staffing_json_package_tropical_*"

REQUIRED_FILES = (
    "manifest.json",
    "validation_report.json",
    "staffing_assignments_normalized.jsonl",
    "staffing_monthly_by_cost_code.jsonl",
    "staffing_monthly_project_forecast.jsonl",
    "staffing_summary_by_cost_code.jsonl",
    "staffing_summary_by_person.jsonl",
    "audit/source_hashes.json",
)


def staffing_config(cfg: dict) -> dict:
    return cfg.get("forecast_staffing_plan") or {}


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def discover(cfg: dict, data_root: Path) -> "OrderedDict":
    """Locate + validate the staffing package. Returns a structured, fail-closed result (never raises)."""
    sp = staffing_config(cfg)
    glob = sp.get("package_glob") or DEFAULT_GLOB
    pkg = _latest_dir(Path(data_root), glob)
    present = pkg is not None

    missing_files, hash_mismatches, source_report = [], [], None
    counts_ok = monthly_recon_ok = source_passed = hashes_ok = False
    parsed = OrderedDict()
    recon_detail = OrderedDict()

    if present:
        missing_files = [f for f in REQUIRED_FILES if not (pkg / f).exists()]
        if not missing_files:
            manifest = _safe_json(pkg / "manifest.json")
            source_report = _safe_json(pkg / "validation_report.json")
            source_passed = bool((source_report or {}).get("passed"))

            hash_mismatches = _verify_hashes(pkg)
            hashes_ok = not hash_mismatches

            normalized = list(read_jsonl(pkg / "staffing_assignments_normalized.jsonl"))
            monthly_cc = list(read_jsonl(pkg / "staffing_monthly_by_cost_code.jsonl"))
            project_fc = list(read_jsonl(pkg / "staffing_monthly_project_forecast.jsonl"))
            summary_cc = list(read_jsonl(pkg / "staffing_summary_by_cost_code.jsonl"))
            summary_person = list(read_jsonl(pkg / "staffing_summary_by_person.jsonl"))

            cost_codes = sorted({r.get("cost_code") for r in monthly_cc if r.get("cost_code")})
            counts_ok = (
                manifest.get("data_row_count") == len(normalized)
                and manifest.get("unique_cost_code_count") == len(cost_codes)
            )

            monthly_recon_ok, recon_detail = _reconcile_monthly(monthly_cc, project_fc, manifest)

            parsed = OrderedDict([
                ("manifest", manifest),
                ("normalized", normalized),
                ("monthly_by_cost_code", monthly_cc),
                ("project_forecast", project_fc),
                ("summary_by_cost_code", summary_cc),
                ("summary_by_person", summary_person),
                ("cost_codes", cost_codes),
            ])

    valid = bool(present and not missing_files and source_passed and hashes_ok and counts_ok
                 and monthly_recon_ok)

    return OrderedDict([
        ("enabled", bool(sp.get("enabled"))),
        ("glob", glob),
        ("present", present),
        ("package_path", str(pkg) if pkg else None),
        ("package_name", pkg.name if pkg else None),
        ("missing_files", missing_files),
        ("source_validation_passed", source_passed),
        ("source_hashes_verified", hashes_ok),
        ("hash_mismatches", hash_mismatches),
        ("manifest_counts_match", counts_ok),
        ("monthly_totals_reconcile", monthly_recon_ok),
        ("monthly_reconciliation_detail", recon_detail),
        ("structurally_valid", valid),
        ("parsed", parsed),
    ])


def _safe_json(p: Path) -> dict:
    try:
        return read_json(p)
    except Exception:
        return {}


def _verify_hashes(pkg: Path) -> list:
    """Recompute sha256 of each generated file and compare to audit/source_hashes.json."""
    rec = _safe_json(pkg / "audit" / "source_hashes.json")
    mism = []
    for entry in rec.get("generated_files", []):
        rel = entry.get("path")
        want = entry.get("sha256")
        fp = pkg / rel if rel else None
        if not fp or not fp.exists():
            mism.append(OrderedDict([("path", rel), ("issue", "missing")]))
            continue
        got = sha256_file(fp)
        if got != want:
            mism.append(OrderedDict([("path", rel), ("issue", "sha256_mismatch"),
                                     ("expected", want), ("actual", got)]))
    return mism


def _reconcile_monthly(monthly_cc, project_fc, manifest) -> tuple:
    """Σ per-cost-code monthly == Σ project monthly == manifest allocated total (cent tolerance)."""
    cc_total = Decimal("0")
    for r in monthly_cc:
        cc_total += sum((D(v) for v in (r.get("monthly_forecast") or {}).values()), Decimal("0"))
    proj_total = sum((D(r.get("forecast_amount")) for r in project_fc), Decimal("0"))
    manifest_total = D(manifest.get("allocated_staffing_forecast_total"))
    ok = (abs(cc_total - proj_total) <= CENTS and abs(cc_total - manifest_total) <= CENTS)
    detail = OrderedDict([
        ("per_cost_code_total", money_str(cc_total)),
        ("project_monthly_total", money_str(proj_total)),
        ("manifest_allocated_total", money_str(manifest_total)),
        ("reconciled", bool(ok)),
    ])
    return ok, detail


def gate_reasons(discovery: dict) -> list:
    """Fail-closed reasons (empty when safe to integrate). Only meaningful when the package is present."""
    reasons = []
    if not discovery.get("present"):
        return ["staffing package not found"]
    if discovery.get("missing_files"):
        reasons.append(f"required files missing: {discovery['missing_files']}")
    if not discovery.get("source_validation_passed"):
        reasons.append("source package validation_report did not pass")
    if not discovery.get("source_hashes_verified"):
        reasons.append("source package file hashes do not match the recorded source_hashes")
    if not discovery.get("manifest_counts_match"):
        reasons.append("manifest row/cost-code counts do not match parsed rows")
    if not discovery.get("monthly_totals_reconcile"):
        reasons.append("parsed monthly totals do not reconcile to source package totals")
    return reasons
