"""Discover + load every input (read-only) and derive the deterministic forecast window.

Loads the canonical budget codes, transaction-level CostEntries (for cadence spacing), per-code monthly
actuals (entry counts), the per-code context summary, and the accepted forecast-intelligence
recommendations (for cost-to-complete used only to scale staffing timing — never to change final cost).
The forecast window is data-derived (the repo period-bucket boundary + the schedule latest finish), so
output is deterministic regardless of wall-clock. Pre-run source hashes prove no input was mutated.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from pathlib import Path

from ..common.dates import JUNE_CUTOFF
from ..common.hashing import sha256_file
from ..common.io import read_jsonl
from ..common.validation import require_fields  # noqa: F401  (available for callers/tests)
from ..schedule_analysis import schedule_io
from ..schedule_analysis.schedule_mapping import build_canonical_index
from .weekday_calendar import add_months, month_index, months_between

ACCEPTED_GLOB = "forecast_accuracy_next_package_tropical_*"


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _by_key(path: Path, key_field: str = "budget_code_key") -> dict:
    if not path.exists():
        return {}
    return {r[key_field]: r for r in read_jsonl(path) if r.get(key_field)}


def _fcf_cfg(cfg: dict) -> dict:
    return cfg.get("forecast_cost_frequency") or {}


def _schedule_latest_finish(schedule_pkg) -> str | None:
    if not schedule_pkg:
        return None
    finishes = []
    for a in schedule_io.iter_activities(schedule_pkg):
        d = a.get("dates") or {}
        for fld in ("finish", "remaining_early_finish", "actual_finish"):
            v = d.get(fld)
            if v and len(str(v)) >= 7:
                finishes.append(str(v)[:10])
    return max(finishes) if finishes else None


def derive_window(latest_finish: str | None) -> OrderedDict:
    """Forecast window: start = repo period-bucket to-date month; end = schedule latest finish month."""
    forecast_start_month = JUNE_CUTOFF[:7]                     # "2026-06" (June-to-date period)
    latest_complete_month = add_months(forecast_start_month, -1)   # "2026-05" (through-May complete)
    end_month = (latest_finish[:7] if latest_finish and len(latest_finish) >= 7 else None)
    fallback = False
    if end_month is None or month_index(end_month) < month_index(forecast_start_month):
        end_month = forecast_start_month
        fallback = True
    months = months_between(forecast_start_month, end_month)
    return OrderedDict([
        ("forecast_start_month", forecast_start_month),
        ("forecast_end_month", end_month),
        ("latest_complete_month_boundary", latest_complete_month),
        ("month_count", len(months)),
        ("months", months),
        ("window_fallback_to_start_month", fallback),
        ("latest_schedule_finish_date", latest_finish),
    ])


def load_inputs(cfg: dict, data_root: Path, project_key: str) -> OrderedDict:
    packages = schedule_io.discover_packages(data_root, cfg)
    context_pkg = packages.get("context_package")
    if not context_pkg:
        raise SystemExit("ERROR: forecast context package not found (required for canonical + actuals)")
    accepted_pkg = _latest_dir(data_root, ACCEPTED_GLOB)
    if not accepted_pkg:
        raise SystemExit("ERROR: accepted forecast-intelligence (accuracy-next) package not found")
    schedule_pkg = packages.get("schedule_package")

    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    index = build_canonical_index(budget_codes)
    context_by = _by_key(context_pkg / "summaries" / "budget_code_forecast_context.jsonl")
    rec_by = _by_key(accepted_pkg / "forecast_recommendations_by_budget_code.jsonl")

    # transaction-level cost entries grouped by mapped canonical key (accounting dates for spacing)
    txn_dates_by = defaultdict(list)
    ce_path = context_pkg / "canonical" / "cost_entries.jsonl"
    transaction_level_available = ce_path.exists()
    if transaction_level_available:
        for r in read_jsonl(ce_path):
            k = r.get("mapped_budget_code_key") or r.get("budget_code_key")
            d = r.get("accounting_date")
            if k and d:
                txn_dates_by[k].append(d[:10])
    for k in txn_dates_by:
        txn_dates_by[k].sort()

    latest_finish = _schedule_latest_finish(schedule_pkg)
    window = derive_window(latest_finish)

    source_files = [
        context_pkg / "canonical" / "budget_codes.jsonl",
        context_pkg / "canonical" / "cost_entries.jsonl",
        context_pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl",
        context_pkg / "summaries" / "budget_code_forecast_context.jsonl",
        accepted_pkg / "forecast_recommendations_by_budget_code.jsonl",
    ]
    pre_hashes = source_hashes(source_files)

    return OrderedDict([
        ("project_key", project_key),
        ("packages", packages),
        ("context_pkg", context_pkg), ("accepted_pkg", accepted_pkg), ("schedule_pkg", schedule_pkg),
        ("budget_codes", budget_codes), ("index", index),
        ("context_by", context_by), ("rec_by", rec_by),
        ("txn_dates_by", dict(txn_dates_by)),
        ("transaction_level_available", transaction_level_available),
        ("window", window),
        ("source_files", source_files),
        ("source_hashes_before", pre_hashes),
    ])


def source_hashes(files: list) -> OrderedDict:
    out = OrderedDict()
    for p in files:
        out[p.name] = sha256_file(p) if Path(p).exists() else None
    return out
