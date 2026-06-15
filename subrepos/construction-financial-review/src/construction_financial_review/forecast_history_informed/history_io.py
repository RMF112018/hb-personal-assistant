"""Discover + load every input (read-only) and normalize the two historical forecast packages.

No randomness, no mutation. Resolves the two fixed-name historical packages plus the latest accepted
context / intelligence / monthly / probability packages, loads canonical budget codes + per-code
actuals + current-model evidence, and normalizes the heterogeneous historical rows (cash-flow and
GC/GR shapes) into one unified monthly-value record. Also captures pre-run source hashes so the
package can later prove the historical inputs were never mutated.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl
from ..common.money import dec
from ..schedule_analysis import schedule_io
from ..schedule_analysis.schedule_mapping import build_canonical_index

INTELLIGENCE_GLOB = "forecast_accuracy_next_package_tropical_*"
MONTHLY_GLOB = "forecast_monthly_package_tropical_*"
PROBABILITY_GLOB = "forecast_probability_package_tropical_*"

# Normalized classification vocabulary (unified across both historical shapes).
CLASS_ACTUAL = "actual"
CLASS_FORECAST = "forecast"
CLASS_MIXED = "mixed_actual_forecast_range"
CLASS_ORIGINAL = "original"
CLASS_PROJECTED = "projected"
CLASS_VARIANCE = "variance"


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _by_key(path: Path) -> dict:
    if not path.exists():
        return {}
    return {r["budget_code_key"]: r for r in read_jsonl(path) if r.get("budget_code_key")}


def _fhi_cfg(cfg: dict) -> dict:
    return cfg.get("forecast_history_informed") or {}


def _resolve_history_pkg(data_root: Path, name: str):
    if not name:
        return None
    p = data_root / name
    return p if p.is_dir() else None


# --------------------------------------------------------------------------- historical normalization

def normalize_cashflow_row(r: dict) -> OrderedDict:
    """Cash-flow monthly-value row -> unified record. Amounts are raw floats here; we keep Decimal."""
    period_type = r.get("period_type")
    cls = period_type if period_type in (CLASS_ACTUAL, CLASS_FORECAST, CLASS_MIXED) else (period_type or None)
    return OrderedDict([
        ("history_source_package", "cash_flow"),
        ("source_workbook", r.get("source_workbook")),
        ("source_sheet", r.get("source_sheet")),
        ("source_row", r.get("source_row")),
        ("source_ref", r.get("source_column")),
        ("snapshot_month", r.get("forecast_month")),
        ("cost_code", r.get("cost_code")),
        ("description", r.get("description")),
        ("raw_code_description", r.get("raw_code_description")),
        ("period_month", r.get("period_month")),
        ("classification", cls),
        ("row_label_key", None),
        ("amount", dec(r.get("amount"))),
    ])


def normalize_gcgr_row(r: dict) -> OrderedDict:
    """GC/GR monthly-value row -> unified record. amount_type carries the classification."""
    amount_type = r.get("amount_type")
    return OrderedDict([
        ("history_source_package", "gcgr"),
        ("source_workbook", "GcGr-Forecast-History.xlsx"),
        ("source_sheet", r.get("source_sheet")),
        ("source_row", r.get("source_row")),
        ("source_ref", r.get("source_cell")),
        ("snapshot_month", r.get("forecast_month")),
        ("cost_code", r.get("cost_code")),
        ("description", r.get("description")),
        ("raw_code_description", r.get("row_label_raw")),
        ("period_month", r.get("period_month")),
        ("classification", amount_type),
        ("row_label_key", r.get("row_label_key")),
        ("amount", dec(r.get("amount"))),
    ])


def _load_history(cashflow_dir, gcgr_dir) -> list:
    """Unified, deterministically-ordered list of normalized historical monthly-value records."""
    rows = []
    if cashflow_dir:
        p = cashflow_dir / "cash_flow_forecast_history_monthly_values.jsonl"
        if p.exists():
            rows.extend(normalize_cashflow_row(r) for r in read_jsonl(p))
    if gcgr_dir:
        p = gcgr_dir / "gcgr_forecast_history_monthly_values.jsonl"
        if p.exists():
            rows.extend(normalize_gcgr_row(r) for r in read_jsonl(p))
    # deterministic order independent of file read order
    rows.sort(key=lambda r: (r["history_source_package"], str(r["source_sheet"]),
                             r["source_row"] if r["source_row"] is not None else -1,
                             str(r["cost_code"]), str(r["period_month"]), str(r["source_ref"])))
    return rows


def _documented_counts(cashflow_dir, gcgr_dir) -> OrderedDict:
    """Pull the manifest/validation-documented record counts for reconciliation."""
    out = OrderedDict()
    if cashflow_dir:
        man = read_json(cashflow_dir / "manifest.json")
        rc = man.get("record_counts") or {}
        out["cash_flow"] = OrderedDict([
            ("monthly_values_including_zero",
             rc.get("monthly_or_period_value_records_including_zero")),
            ("code_row_records", rc.get("code_row_records")),
            ("summary_value_records", rc.get("summary_value_records")),
        ])
    if gcgr_dir:
        vr = read_json(gcgr_dir / "gcgr_forecast_history_validation_report.json")
        counts = vr.get("record_counts") or vr.get("counts") or {}
        out["gcgr"] = OrderedDict([
            ("monthly_values_including_zero",
             counts.get("monthly_values_including_zero")
             or counts.get("monthly_actual_forecast_records_including_zero")),
            ("all_row_value_records", counts.get("all_row_value_records")),
        ])
    return out


def reconcile_counts(cashflow_dir, gcgr_dir, history_rows) -> OrderedDict:
    """Compare loaded monthly-value counts to the documented counts; flag material mismatch."""
    documented = _documented_counts(cashflow_dir, gcgr_dir)
    observed = OrderedDict()
    for pkg in ("cash_flow", "gcgr"):
        observed[pkg] = sum(1 for r in history_rows if r["history_source_package"] == pkg)
    reconciled = True
    notes = []
    for pkg, doc in documented.items():
        want = doc.get("monthly_values_including_zero")
        got = observed.get(pkg, 0)
        if want is not None and int(want) != got:
            reconciled = False
            notes.append(f"{pkg}: documented {want} monthly-value rows, loaded {got}")
    return OrderedDict([
        ("documented", documented), ("observed_monthly_values", observed),
        ("reconciled", reconciled), ("notes", notes),
    ])


def source_hashes(cashflow_dir, gcgr_dir) -> OrderedDict:
    """SHA-256 of every file in both historical packages (proof-of-no-mutation baseline)."""
    out = OrderedDict()
    for label, d in (("cash_flow", cashflow_dir), ("gcgr", gcgr_dir)):
        if not d:
            continue
        files = OrderedDict()
        for p in sorted(d.rglob("*")):
            if p.is_file():
                files[str(p.relative_to(d))] = sha256_file(p)
        out[label] = files
    return out


# --------------------------------------------------------------------------- top-level loader

def load_inputs(cfg: dict, data_root: Path, project_key: str) -> OrderedDict:
    fhi = _fhi_cfg(cfg)
    cashflow_dir = _resolve_history_pkg(data_root, fhi.get("cash_flow_history_package"))
    gcgr_dir = _resolve_history_pkg(data_root, fhi.get("gcgr_history_package"))
    if not cashflow_dir and not gcgr_dir:
        raise SystemExit("ERROR: no historical forecast package found (check forecast_history_informed cfg)")

    packages = schedule_io.discover_packages(data_root, cfg)
    context_pkg = packages.get("context_package")
    if not context_pkg:
        raise SystemExit("ERROR: forecast context package not found (required for canonical + actuals)")

    intelligence_pkg = _latest_dir(data_root, fhi.get("forecast_intelligence_package_glob") or INTELLIGENCE_GLOB)
    monthly_pkg = _latest_dir(data_root, fhi.get("forecast_monthly_package_glob") or MONTHLY_GLOB)
    probability_pkg = _latest_dir(data_root, fhi.get("forecast_probability_package_glob") or PROBABILITY_GLOB)
    if not intelligence_pkg:
        raise SystemExit("ERROR: forecast intelligence (accuracy-next) package not found")

    # Canonical universe + cost_code indexes (sole mapping authority).
    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    index = build_canonical_index(budget_codes)

    # Per-code context (actuals truth + budget amounts + evidence flags).
    context_by = _by_key(context_pkg / "summaries" / "budget_code_forecast_context.jsonl")

    # Current-model evidence (read-only inputs; never mutated).
    intel = {
        "recommendations": _by_key(intelligence_pkg / "forecast_recommendations_by_budget_code.jsonl"),
        "trend": _by_key(intelligence_pkg / "trend_evidence_by_budget_code.jsonl"),
        "schedule": _by_key(intelligence_pkg / "schedule_forecast_evidence_by_budget_code.jsonl"),
        "remaining_work": _by_key(intelligence_pkg / "remaining_work_evidence_by_budget_code.jsonl"),
        "confidence": _by_key(intelligence_pkg / "forecast_confidence_by_budget_code.jsonl"),
    }
    monthly = {}
    if monthly_pkg:
        monthly = {
            "monthly": _by_key(monthly_pkg / "monthly_forecast_by_budget_code.jsonl"),
            # per-code accepted source-share blend (schedule / cost-entries / invoice / flat weights):
            # the real source_shares evidence the advisory monthly distribution rebalances.
            "confidence": _by_key(monthly_pkg / "monthly_forecast_confidence_by_budget_code.jsonl"),
            "schedule_phasing": _by_key(monthly_pkg / "schedule_monthly_phasing_by_budget_code.jsonl"),
            "cost_entry_trends": _by_key(monthly_pkg / "cost_entry_monthly_trends_by_budget_code.jsonl"),
            "cashflow": read_json(monthly_pkg / "project_monthly_cashflow_summary.json")
            if (monthly_pkg / "project_monthly_cashflow_summary.json").exists() else {},
        }
    probability = {}
    if probability_pkg:
        probability = {
            "final": _by_key(probability_pkg / "probabilistic_final_cost_by_budget_code.jsonl"),
            "sim_inputs": _by_key(probability_pkg / "simulation_inputs_by_budget_code.jsonl"),
            "overrun": _by_key(probability_pkg / "code_overrun_probabilities.jsonl"),
        }

    history_rows = _load_history(cashflow_dir, gcgr_dir)
    counts = reconcile_counts(cashflow_dir, gcgr_dir, history_rows)
    pre_hashes = source_hashes(cashflow_dir, gcgr_dir)

    return OrderedDict([
        ("project_key", project_key),
        ("cashflow_dir", cashflow_dir), ("gcgr_dir", gcgr_dir),
        ("context_pkg", context_pkg), ("intelligence_pkg", intelligence_pkg),
        ("monthly_pkg", monthly_pkg), ("probability_pkg", probability_pkg),
        ("budget_codes", budget_codes), ("index", index),
        ("context_by", context_by), ("intel", intel),
        ("monthly", monthly), ("probability", probability),
        ("history_rows", history_rows), ("count_reconciliation", counts),
        ("source_hashes_before", pre_hashes),
    ])
