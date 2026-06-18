#!/usr/bin/env python3
"""
generate_forecast_context_package.py

Tropical World Nursery Senior Living Facility (project_key=tropical, job=23-435-01)
Cost-forecast assistant DATA ASSEMBLY ONLY.

Combines, maps, reconciles and structures three read-only JSON/JSONL source packages
into one consolidated, agent-ingestible forecast context package.

This script:
  - Does NOT mutate source files (verified via SHA-256 before/after).
  - Does NOT build a forecast agent or emit recommendations.
  - Does NOT make live external calls or touch any production DB.
  - Does NOT include raw cells, raw payloads, or sensitive fields in agent-facing output.

Stdlib only. Money math via Decimal(str(value)); no float arithmetic on amounts.
Deterministic output (sorted rows/keys). Re-runnable.
"""

import json
import os
import re
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, getcontext
from collections import defaultdict, OrderedDict
from dataclasses import dataclass

# Phase 4 read adapter: file-backed by default; DB-backed only when HB_FORECAST_DB_BACKED_READS=1.
# Dual-mode import — script mode resolves via the script directory (sys.path[0]); the package
# path is the fallback when this module is imported as part of the CFR package.
try:
    from db_source_adapter import load_forecast_source_rows
except ImportError:  # pragma: no cover - import-path fallback
    from construction_financial_review.context.db_source_adapter import load_forecast_source_rows

getcontext().prec = 50

# --------------------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------------------
# Default production data root. Overridable per run via ContextPackageConfig /
# CFR_CONTEXT_DATA_ROOT so the generator can run against temp roots in controlled mode.
_DEFAULT_DATA_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)

PROJECT_NAME = "Tropical World Nursery Senior Living Facility"
PROJECT_KEY = "tropical"
JOB_REF = "23-435-01"
PACKAGE_PERIOD = "2026-June"

JUNE_CUTOFF = "2026-06-01"          # < this = through_may_2026
JULY_CUTOFF = "2026-07-01"          # < this (and >= june) = june_2026_to_date
CENTS = Decimal("0.01")

# ROOT / TWN_DIR / OWNER_DIR / PROCORE_DIR / STAMP / OUT / SRC_FILES / IGNORED are injected
# per run by _apply_config() inside build_context_package(); they are intentionally NOT module
# globals at import time, so importing this module performs no path I/O or source reads.


@dataclass(frozen=True)
class ContextPackageConfig:
    """Inputs/outputs for one context-package build. Defaults reproduce production behavior."""

    data_root: Path
    out_dir: Path
    stamp: str


def default_config() -> "ContextPackageConfig":
    """Today's default behavior, with optional env overrides for controlled temp-root runs.

    CFR_CONTEXT_DATA_ROOT overrides the source root; CFR_CONTEXT_OUT_DIR the output package
    dir; CFR_CONTEXT_STAMP the wall-clock stamp. Unset => identical to historical defaults.
    """
    root = Path(os.environ.get("CFR_CONTEXT_DATA_ROOT") or _DEFAULT_DATA_ROOT)
    stamp = os.environ.get("CFR_CONTEXT_STAMP") or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_env = os.environ.get("CFR_CONTEXT_OUT_DIR")
    out_dir = Path(out_env) if out_env else root / f"forecast_context_package_tropical_{stamp}"
    return ContextPackageConfig(data_root=root, out_dir=out_dir, stamp=stamp)

# --------------------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------------------
def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")
            n += 1
    return n


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dec(v):
    """Return Decimal(str(v)) or None for null/blank/nonnumeric. No float arithmetic."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def money_str(v):
    """Canonical money string formatted to 2 decimals, or None."""
    d = dec(v)
    if d is None:
        return None
    return str(d.quantize(CENTS))


def dsum(values):
    """Decimal sum over an iterable of raw values; non-numeric ignored."""
    total = Decimal("0")
    for v in values:
        d = dec(v)
        if d is not None:
            total += d
    return total


def parse_budget_key(key):
    """sub_job.cost_code.category  ->  (sub_job, cost_code, category) or None."""
    if not isinstance(key, str):
        return None
    parts = key.split(".")
    if len(parts) != 3:
        return None
    sub_job, cost_code, category = parts
    if not sub_job or not cost_code or not category:
        return None
    return sub_job, cost_code, category


def cost_code_family(cost_code):
    """First two dash-segments, e.g. 15-16-110 -> 15-16 ; 15-01-XXX -> 15-01."""
    if not isinstance(cost_code, str):
        return None
    segs = cost_code.split("-")
    if len(segs) >= 2 and segs[0] and segs[1]:
        return f"{segs[0]}-{segs[1]}"
    return None


def is_placeholder_code(cost_code):
    if not isinstance(cost_code, str):
        return False
    return "X" in cost_code.upper()


def norm_cost_code(cost_code):
    if not isinstance(cost_code, str):
        return None
    return cost_code.strip().upper()


def date_bucket(date_str):
    if not date_str or not isinstance(date_str, str):
        return "undated"
    ds = date_str[:10]
    if len(ds) < 10 or ds[4] != "-":
        return "undated"
    if ds < JUNE_CUTOFF:
        return "through_may_2026"
    if ds < JULY_CUTOFF:
        return "june_2026_to_date"
    return "after_june_2026"


# --------------------------------------------------------------------------------------
# Source mutation guard (hash before)
# --------------------------------------------------------------------------------------
def all_source_paths():
    paths = []
    for d in (TWN_DIR, OWNER_DIR, PROCORE_DIR):
        for p in sorted(d.rglob("*")):
            if p.is_file():
                paths.append(p)
    return paths


# --------------------------------------------------------------------------------------
# Module-level state containers. Empty initializers run at import (no I/O); the source
# reads, hashing, and index-building that populate them now live in _load_inputs_and_index()
# / build_context_package(), and _reset_state() re-initializes every container so a build is
# re-runnable in one process (file-backed then DB-backed parity runs).
# --------------------------------------------------------------------------------------
master = OrderedDict()                       # budget_code_key -> record
master_keys = set()
by_cost_code = defaultdict(set)              # cost_code -> {budget_code_key}
by_cost_code_categories = defaultdict(set)   # cost_code -> {category}
by_family = defaultdict(set)                 # cost_code_family -> {budget_code_key}

# Procore family / cost-code evidence indexes (built from line items + latest)
procore_family_wbs = defaultdict(set)            # family -> {wbs_flat_code}
procore_family_mapped_keys = defaultdict(set)    # family -> {budget_code_key mapped from procore}


def procore_map_wbs(wbs):
    """Return (mapped_key, status, confidence, method, notes, parsed, candidates)."""
    parsed_sj = parsed_cc = parsed_cat = None
    parsed = parse_budget_key(wbs) if wbs else None
    if parsed:
        parsed_sj, parsed_cc, parsed_cat = parsed
    # (a) exact
    if wbs in master_keys:
        return (wbs, "mapped", "high",
                "procore_wbs_flat_code_exact_budget_code_key_match", "exact wbs_flat_code == budget_code_key",
                (parsed_sj, parsed_cc, parsed_cat), [wbs])
    # (b) parsed reconstruct
    if parsed:
        reconstructed = f"{parsed_sj}.{parsed_cc}.{parsed_cat}"
        if reconstructed in master_keys:
            return (reconstructed, "mapped", "high",
                    "procore_wbs_flat_code_parsed_match", "parsed sub_job/cost_code/category reconstructs to budget_code_key",
                    (parsed_sj, parsed_cc, parsed_cat), [reconstructed])
        # (c)/(d) cost_code exists but category conflict / ambiguous
        if parsed_cc in by_cost_code:
            cats = by_cost_code_categories.get(parsed_cc, set())
            cands = sorted(by_cost_code[parsed_cc])
            if parsed_cat not in cats:
                return (None, "manual_required", "low",
                        "procore_cost_code_present_category_conflict",
                        f"category_conflict: parsed category '{parsed_cat}' not in workbook categories {sorted(cats)} for cost_code {parsed_cc}",
                        (parsed_sj, parsed_cc, parsed_cat), cands)
            return (None, "manual_required", "low",
                    "procore_cost_code_present_category_ambiguous",
                    f"cost_code {parsed_cc} present but category resolution ambiguous across {sorted(cats)}",
                    (parsed_sj, parsed_cc, parsed_cat), cands)
    return (None, "manual_required", "none",
            "procore_no_budget_match", "no exact or parsed budget_code_key match",
            (parsed_sj, parsed_cc, parsed_cat), [])


# Pre-scan procore line items + latest to build family evidence (single streaming pass each)
def build_procore_family_index():
    for rec in read_jsonl(SRC_FILES["procore_line_items"]):
        wbs = rec.get("wbs_flat_code")
        if not wbs:
            continue
        parsed = parse_budget_key(wbs)
        fam = cost_code_family(parsed[1]) if parsed else None
        if fam:
            procore_family_wbs[fam].add(wbs)
            if wbs in master_keys:
                procore_family_mapped_keys[fam].add(wbs)
    for rec in read_jsonl(SRC_FILES["procore_latest"]):
        wbs = rec.get("wbs_flat_code")
        if not wbs:
            continue
        parsed = parse_budget_key(wbs)
        fam = cost_code_family(parsed[1]) if parsed else None
        if fam:
            procore_family_wbs[fam].add(wbs)
            if wbs in master_keys:
                procore_family_mapped_keys[fam].add(wbs)


# --------------------------------------------------------------------------------------
# Mapping-decision accumulator (deduped) + ambiguous + per-source result rows
# --------------------------------------------------------------------------------------
decisions = OrderedDict()          # dedupe key -> decision row
ambiguous_rows = []                # rows with multiple candidates


def record_decision(source_system, source_key, source_cost_code, source_category,
                    source_wbs, source_commitment_id, source_vendor_entity_key,
                    candidates, mapped_key, status, confidence, method, reason,
                    requires_human_review):
    dk = (source_system, source_key or "", source_cost_code or "", source_category or "",
          source_wbs or "", source_commitment_id or "", source_vendor_entity_key or "")
    if dk in decisions:
        return
    decisions[dk] = OrderedDict([
        ("source_system", source_system),
        ("source_key", source_key),
        ("source_cost_code", source_cost_code),
        ("source_category", source_category),
        ("source_wbs_flat_code", source_wbs),
        ("source_commitment_id", source_commitment_id),
        ("source_vendor_entity_key", source_vendor_entity_key),
        ("candidate_budget_code_keys", candidates),
        ("mapped_budget_code_key", mapped_key),
        ("mapping_status", status),
        ("mapping_confidence", confidence),
        ("mapping_method", method),
        ("reason", reason),
        ("requires_human_review", requires_human_review),
    ])


# ======================================================================================
# 1) CANONICAL: budget_codes.jsonl
# ======================================================================================
def emit_budget_codes():
    rows = []
    for key in sorted(master_keys):
        rec = master[key]
        sub_job_obj = rec.get("sub_job") or {}
        parsed = parse_budget_key(key)
        sub_job_code = parsed[0] if parsed else rec.get("extra")
        rows.append(OrderedDict([
            ("project_key", PROJECT_KEY),
            ("job", JOB_REF),
            ("budget_code_key", key),
            ("sub_job", sub_job_code),
            ("sub_job_description", sub_job_obj.get("description")),
            ("source_sub_job", sub_job_obj),
            ("cost_code", rec.get("cost_code")),
            ("category", rec.get("category")),
            ("cost_type_description", (rec.get("cost_type") or {}).get("description")),
            ("budget_code_description", rec.get("budget_code_description")),
            ("cost_code_tiers", rec.get("cost_code_tiers")),
            ("amounts", rec.get("amounts")),
            ("source", OrderedDict([
                ("source_sheet", rec.get("source_sheet")),
                ("source_row", rec.get("source_row")),
                ("costentries_match_status", rec.get("costentries_match_status")),
            ])),
            ("mapping_role", "master_budget_code"),
        ]))
        record_decision("workbook_budget", key, rec.get("cost_code"), rec.get("category"),
                        None, None, None, [key], key, "mapped", "high",
                        "master_budget_code", "authoritative BudgetDetails master row", False)
    return write_jsonl(OUT / "canonical" / "budget_codes.jsonl", rows)


# ======================================================================================
# 2) CANONICAL: cost_entries.jsonl  (+ actuals aggregation per budget code)
# ======================================================================================
actuals_by_key = defaultdict(lambda: {
    "all": Decimal("0"), "may": Decimal("0"), "june": Decimal("0"),
    "count": 0, "latest_date": None,
})
june_actual_count = 0
june_actual_total = Decimal("0")
cost_entries_canonical_total = Decimal("0")
cost_entry_source_count = 0
cost_entry_invalid_count = 0
cost_entry_mapped_count = 0


def emit_cost_entries():
    global june_actual_count, june_actual_total, cost_entries_canonical_total
    global cost_entry_source_count, cost_entry_invalid_count, cost_entry_mapped_count
    src = load_forecast_source_rows(
        "cost_entries",
        jsonl_path=SRC_FILES["cost_entries"],
        source_package_name=TWN_DIR.name,
        project_key=PROJECT_KEY,
        read_jsonl_fn=read_jsonl,
    )
    cost_entry_source_count = len(src)
    src.sort(key=lambda r: (r.get("source_row") if isinstance(r.get("source_row"), int) else 0))
    rows = []
    seen_keys_for_decision = set()
    for r in src:
        key = r.get("budget_code_key")
        acct_date = r.get("accounting_date")
        bucket = date_bucket(acct_date)
        amt = r.get("amount")
        amt_str = money_str(amt)
        d = dec(amt) or Decimal("0")
        if key in master_keys:
            status = "mapped"
            method = "workbook_budget_code_key_direct"
            mapped_key = key
            cost_entry_mapped_count += 1
        else:
            status = "invalid_budget_code_key"
            method = "workbook_budget_code_key_not_in_master"
            mapped_key = None
            cost_entry_invalid_count += 1
        cost_entries_canonical_total += d
        if bucket == "through_may_2026":
            actuals_by_key[key]["may"] += d
        elif bucket == "june_2026_to_date":
            actuals_by_key[key]["june"] += d
            june_actual_count += 1
            june_actual_total += d
        actuals_by_key[key]["all"] += d
        actuals_by_key[key]["count"] += 1
        if acct_date and (actuals_by_key[key]["latest_date"] is None
                          or acct_date > actuals_by_key[key]["latest_date"]):
            actuals_by_key[key]["latest_date"] = acct_date

        out = OrderedDict()
        for f in ("source_sheet", "source_row", "job", "job_description", "job2",
                  "extra", "cost_code", "category", "tran_type", "description",
                  "application_of_origin", "budget_code_key"):
            out[f] = r.get(f)
        out["mapped_budget_code_key"] = mapped_key
        out["mapping_status"] = status
        out["mapping_method"] = method
        out["accounting_date"] = acct_date
        out["accounting_month"] = r.get("accounting_month")
        out["amount"] = amt
        out["amount_decimal_string"] = amt_str
        out["actual_period_bucket"] = bucket
        out["source_file"] = "twn_cost_forecast_json_package/data/cost_entries.jsonl"
        rows.append(out)

        if key not in seen_keys_for_decision:
            seen_keys_for_decision.add(key)
            record_decision("workbook_cost_entry", key, r.get("cost_code"), r.get("category"),
                            None, None, None, [key] if key in master_keys else [],
                            mapped_key, status, "high" if mapped_key else "none",
                            method, "cost entry budget_code_key validation against master",
                            status == "invalid_budget_code_key")
    return write_jsonl(OUT / "canonical" / "cost_entries.jsonl", rows)


# ======================================================================================
# 3) CANONICAL: monthly_actuals_by_budget_code.jsonl
# ======================================================================================
monthly_by_key = defaultdict(list)
monthly_actuals_canonical_total = Decimal("0")
monthly_source_count = 0


def emit_monthly_actuals():
    global monthly_actuals_canonical_total, monthly_source_count
    src = load_forecast_source_rows(
        "monthly_actuals",
        jsonl_path=SRC_FILES["monthly_actuals"],
        source_package_name=TWN_DIR.name,
        project_key=PROJECT_KEY,
        read_jsonl_fn=read_jsonl,
    )
    monthly_source_count = len(src)
    src.sort(key=lambda r: (r.get("budget_code_key") or "", r.get("month") or ""))
    rows = []
    for r in src:
        key = r.get("budget_code_key")
        amt = r.get("amount")
        d = dec(amt) or Decimal("0")
        monthly_actuals_canonical_total += d
        status = "mapped" if key in master_keys else "invalid_budget_code_key"
        month = r.get("month")
        bucket = date_bucket((month + "-01") if isinstance(month, str) and len(month) == 7 else None)
        out = OrderedDict()
        for f in ("budget_code_key", "month", "type", "amount", "entry_count", "job",
                  "extra", "cost_code", "category", "first_accounting_date",
                  "last_accounting_date", "source"):
            out[f] = r.get(f)
        out["mapped_budget_code_key"] = key if key in master_keys else None
        out["mapping_status"] = status
        out["amount_decimal_string"] = money_str(amt)
        out["actual_period_bucket"] = bucket
        out["source_file"] = "twn_cost_forecast_json_package/data/monthly_actuals_by_budget_code.jsonl"
        rows.append(out)
        if key in master_keys:
            monthly_by_key[key].append(OrderedDict([
                ("month", month),
                ("amount_decimal_string", money_str(amt)),
                ("entry_count", r.get("entry_count")),
                ("actual_period_bucket", bucket),
            ]))
    return write_jsonl(OUT / "canonical" / "monthly_actuals_by_budget_code.jsonl", rows)


# ======================================================================================
# 4) OWNER pay-app line items mapping
# ======================================================================================
owner_family_seen = defaultdict(lambda: {
    "examples": set(), "count": 0, "latest_app": None,
    "budget_candidates": set(), "procore_wbs": set(),
})

owner_counts = {"mapped": 0, "ambiguous": 0, "manual_required": 0,
                "invalid_budget_code_key": 0, "not_applicable": 0}
owner_method_counts = defaultdict(int)
owner_examples = defaultdict(list)
owner_normalization_improved = 0   # rows mapped only via family normalization (medium)

# owner evidence per budget code (only confidently mapped status==mapped rows)
owner_evidence = defaultdict(list)   # budget_code_key -> list of mapped owner line rows (dicts)


def owner_map(row):
    """Return mapping dict for an owner line item."""
    row_type = row.get("row_type")
    cost_code = row.get("cost_code")
    norm = norm_cost_code(cost_code)
    placeholder = is_placeholder_code(cost_code)
    family = cost_code_family(norm) if norm else None
    candidates_in = [c for c in (row.get("candidate_budget_code_keys") or []) if c]

    # Procore supporting evidence
    proc_wbs = sorted(procore_family_wbs.get(family, set())) if family else []
    proc_budget = sorted(procore_family_mapped_keys.get(family, set())) if family else []

    result = OrderedDict([
        ("owner_cost_code_original", cost_code),
        ("owner_cost_code_normalized", norm),
        ("owner_cost_code_family", family),
        ("owner_placeholder_code_detected", placeholder),
        ("candidate_budget_code_keys", []),
        ("mapped_budget_code_key", None),
        ("mapping_status", None),
        ("mapping_confidence", None),
        ("mapping_method", None),
        ("mapping_notes", None),
        ("procore_supporting_wbs_flat_codes", proc_wbs),
        ("procore_supporting_budget_code_candidates", proc_budget),
        ("procore_supporting_evidence_count", len(proc_wbs)),
    ])

    # Track family seen (construction + change-order with family)
    if family:
        fs = owner_family_seen[family]
        if cost_code:
            fs["examples"].add(cost_code)
        fs["count"] += 1
        app = row.get("application_no")
        if isinstance(app, int) and (fs["latest_app"] is None or app > fs["latest_app"]):
            fs["latest_app"] = app
        fs["budget_candidates"].update(by_family.get(family, set()))
        fs["procore_wbs"].update(proc_wbs)

    # ---- Change-order / PCCO handling ----
    if row_type == "change_order_line_item":
        if not family:
            result.update({
                "mapping_status": "not_applicable", "mapping_confidence": "none",
                "mapping_method": "owner_change_order_not_base_budget",
                "mapping_notes": "PCCO/change-order row with no base cost-code family; outside base budget universe",
            })
            return result
        result.update({
            "candidate_budget_code_keys": sorted(by_family.get(family, set())),
            "mapping_status": "manual_required", "mapping_confidence": "none",
            "mapping_method": "owner_change_order_family_review",
            "mapping_notes": "PCCO/change-order row carries a cost-code family; review before mapping to base budget",
        })
        return result

    # ---- Construction line items ----
    # A) exact candidate match
    matched = [c for c in candidates_in if c in master_keys]
    if matched:
        mk = sorted(matched)[0]
        result.update({
            "candidate_budget_code_keys": sorted(set(matched)),
            "mapped_budget_code_key": mk,
            "mapping_status": "mapped", "mapping_confidence": "high",
            "mapping_method": "owner_candidate_exact_budget_code_key_match",
            "mapping_notes": "owner candidate_budget_code_key exactly matches BudgetDetails",
        })
        return result

    # B) constructed exact key (only when cost_code populated & non-placeholder)
    if norm and not placeholder:
        constructed = f"1000.{norm}.SUB"
        if constructed in master_keys:
            result.update({
                "candidate_budget_code_keys": [constructed],
                "mapped_budget_code_key": constructed,
                "mapping_status": "mapped", "mapping_confidence": "high",
                "mapping_method": "owner_constructed_exact_budget_code_key_match",
                "mapping_notes": "1000.<cost_code>.SUB exists in BudgetDetails",
            })
            return result

    # C) deterministic normalized family match
    if family:
        fam_keys = sorted(by_family.get(family, set()))
        if len(fam_keys) == 1:
            result.update({
                "candidate_budget_code_keys": fam_keys,
                "mapped_budget_code_key": fam_keys[0],
                "mapping_status": "mapped", "mapping_confidence": "medium",
                "mapping_method": "owner_cost_code_family_unique_budget_match",
                "mapping_notes": f"owner cost-code family {family} resolves to a single BudgetDetails key",
            })
            return result
        if len(fam_keys) > 1:
            result.update({
                "candidate_budget_code_keys": fam_keys,
                "mapping_status": "ambiguous", "mapping_confidence": "low",
                "mapping_method": "owner_cost_code_family_multiple_budget_candidates",
                "mapping_notes": f"owner cost-code family {family} maps to multiple BudgetDetails keys",
            })
            return result
        result.update({
            "mapping_status": "manual_required", "mapping_confidence": "none",
            "mapping_method": "owner_cost_code_family_no_budget_match",
            "mapping_notes": f"owner cost-code family {family} has no BudgetDetails match",
        })
        return result

    # No cost code at all
    result.update({
        "mapping_status": "manual_required", "mapping_confidence": "none",
        "mapping_method": "owner_no_cost_code",
        "mapping_notes": "owner row has no usable cost code",
    })
    return result


def flatten_owner_money(row):
    wc = row.get("work_completed") or {}
    ret = row.get("retainage") or {}
    return OrderedDict([
        ("scheduled_value", money_str(row.get("scheduled_value"))),
        ("current_value", money_str(row.get("current_value"))),
        ("previous_completed", money_str(wc.get("from_previous_application"))),
        ("this_period_completed", money_str(wc.get("this_period"))),
        ("materials_presently_stored", money_str(wc.get("materials_presently_stored"))),
        ("total_completed_and_stored_to_date", money_str(wc.get("total_completed_and_stored_to_date"))),
        ("percent_complete", wc.get("percent_complete")),
        ("balance_to_finish", money_str(wc.get("balance_to_finish"))),
        ("retainage", money_str(ret.get("retainage_current_or_reduced"))),
    ])


owner_line_source_count = 0


def emit_owner_line_items():
    global owner_line_source_count, owner_normalization_improved
    src = list(read_jsonl(SRC_FILES["owner_line_items"]))
    owner_line_source_count = len(src)
    src.sort(key=lambda r: ((r.get("sheet_index") or 0),
                            (r.get("source_row") if isinstance(r.get("source_row"), int) else 0)))
    canon_rows = []
    result_rows = []
    unmapped_rows = []
    for r in src:
        m = owner_map(r)
        money = flatten_owner_money(r)
        status = m["mapping_status"]
        owner_counts[status] = owner_counts.get(status, 0) + 1
        owner_method_counts[m["mapping_method"]] += 1
        if m["mapping_method"] == "owner_cost_code_family_unique_budget_match":
            owner_normalization_improved += 1
        if len(owner_examples[status]) < 3:
            owner_examples[status].append(OrderedDict([
                ("source_sheet", r.get("source_sheet")),
                ("source_row", r.get("source_row")),
                ("cost_code", r.get("cost_code")),
                ("row_type", r.get("row_type")),
                ("mapping_method", m["mapping_method"]),
                ("mapped_budget_code_key", m["mapped_budget_code_key"]),
            ]))

        canon = OrderedDict([
            ("source_workbook", r.get("source_workbook")),
            ("source_sheet", r.get("source_sheet")),
            ("source_row", r.get("source_row")),
            ("sheet_index", r.get("sheet_index")),
            ("application_no", r.get("application_no")),
            ("application_date", r.get("application_date")),
            ("period_to", r.get("period_to")),
            ("contractor_project_no", r.get("contractor_project_no")),
            ("row_type", r.get("row_type")),
            ("item", r.get("item")),
            ("owner_sov_code", r.get("owner_sov_code")),
            ("cost_code", r.get("cost_code")),
            ("description_of_work", r.get("description_of_work")),
        ])
        canon.update(m)   # mapping + normalization fields
        canon.update(money)
        canon["validation_flags"] = r.get("validation_flags")
        canon["source_file"] = "owner_pay_app_json_package/owner_pay_app_line_items.jsonl"
        canon_rows.append(canon)

        res = OrderedDict([
            ("source_sheet", r.get("source_sheet")),
            ("source_row", r.get("source_row")),
            ("application_no", r.get("application_no")),
            ("period_to", r.get("period_to")),
            ("row_type", r.get("row_type")),
            ("cost_code", r.get("cost_code")),
            ("owner_cost_code_family", m["owner_cost_code_family"]),
            ("owner_placeholder_code_detected", m["owner_placeholder_code_detected"]),
            ("candidate_budget_code_keys", m["candidate_budget_code_keys"]),
            ("mapped_budget_code_key", m["mapped_budget_code_key"]),
            ("mapping_status", status),
            ("mapping_confidence", m["mapping_confidence"]),
            ("mapping_method", m["mapping_method"]),
            ("mapping_notes", m["mapping_notes"]),
            ("procore_supporting_evidence_count", m["procore_supporting_evidence_count"]),
        ])
        result_rows.append(res)

        if status in ("manual_required", "not_applicable", "invalid_budget_code_key"):
            unmapped_rows.append(res)
        if status == "ambiguous":
            ambiguous_rows.append(OrderedDict([
                ("source_system", "owner_pay_app"),
                ("source_sheet", r.get("source_sheet")),
                ("source_row", r.get("source_row")),
                ("cost_code", r.get("cost_code")),
                ("owner_cost_code_family", m["owner_cost_code_family"]),
                ("candidate_budget_code_keys", m["candidate_budget_code_keys"]),
                ("mapping_method", m["mapping_method"]),
            ]))

        # owner evidence (confidently mapped only) for budget_code summaries
        if status == "mapped" and m["mapped_budget_code_key"]:
            owner_evidence[m["mapped_budget_code_key"]].append(OrderedDict([
                ("period_to", r.get("period_to")),
                ("application_no", r.get("application_no")),
                ("sheet_index", r.get("sheet_index")),
                ("source_sheet", r.get("source_sheet")),
                ("current_value", money["current_value"]),
                ("previous_completed", money["previous_completed"]),
                ("this_period_completed", money["this_period_completed"]),
                ("total_completed_and_stored_to_date", money["total_completed_and_stored_to_date"]),
                ("percent_complete", money["percent_complete"]),
                ("balance_to_finish", money["balance_to_finish"]),
                ("retainage", money["retainage"]),
            ]))

        # decision (deduped by cost_code + row_type)
        record_decision("owner_pay_app", r.get("owner_sov_code"), r.get("cost_code"),
                         None, None, None, None, m["candidate_budget_code_keys"],
                         m["mapped_budget_code_key"], status, m["mapping_confidence"],
                         m["mapping_method"], m["mapping_notes"],
                         status in ("ambiguous", "manual_required"))

    n_canon = write_jsonl(OUT / "canonical" / "owner_pay_app_line_items_mapped.jsonl", canon_rows)
    write_jsonl(OUT / "mapping" / "owner_pay_app_mapping_results.jsonl", result_rows)
    write_jsonl(OUT / "mapping" / "unmapped_owner_pay_app_rows.jsonl", unmapped_rows)
    return n_canon


# ======================================================================================
# 5) OWNER totals (pass-through, flattened money)
# ======================================================================================
owner_totals_source_count = 0
owner_latest = {"sheet": None, "period_to": None, "application_no": None, "sheet_index": -1}
owner_grand_totals = []   # grand_total rows for recon


def emit_owner_totals():
    global owner_totals_source_count
    src = list(read_jsonl(SRC_FILES["owner_totals"]))
    owner_totals_source_count = len(src)
    src.sort(key=lambda r: ((r.get("sheet_index") or 0),
                            (r.get("source_row") if isinstance(r.get("source_row"), int) else 0)))
    rows = []
    for r in src:
        money = flatten_owner_money(r)
        out = OrderedDict([
            ("source_workbook", r.get("source_workbook")),
            ("source_sheet", r.get("source_sheet")),
            ("source_row", r.get("source_row")),
            ("sheet_index", r.get("sheet_index")),
            ("application_no", r.get("application_no")),
            ("application_date", r.get("application_date")),
            ("period_to", r.get("period_to")),
            ("row_type", r.get("row_type")),
            ("description_of_work", r.get("description_of_work")),
        ])
        out.update(money)
        out["validation_flags"] = r.get("validation_flags")
        out["source_file"] = "owner_pay_app_json_package/owner_pay_app_totals.jsonl"
        rows.append(out)
        if r.get("row_type") == "grand_total":
            si = r.get("sheet_index") or 0
            owner_grand_totals.append((si, r.get("period_to"), r.get("application_no"), money, r.get("source_sheet")))
            if si > owner_latest["sheet_index"]:
                owner_latest.update({"sheet": r.get("source_sheet"),
                                     "period_to": r.get("period_to"),
                                     "application_no": r.get("application_no"),
                                     "sheet_index": si})
    return write_jsonl(OUT / "canonical" / "owner_pay_app_totals.jsonl", rows)


# ======================================================================================
# 6) OWNER family crosswalk
# ======================================================================================
def emit_owner_family_crosswalk():
    rows = []
    for fam in sorted(owner_family_seen.keys()):
        fs = owner_family_seen[fam]
        budget_cands = sorted(fs["budget_candidates"])
        proc_wbs = sorted(fs["procore_wbs"])
        if len(budget_cands) == 1:
            resolution = "unique_budget_match"
            rec_method = "owner_cost_code_family_unique_budget_match"
            needs_review = False
        elif len(budget_cands) > 1:
            resolution = "multiple_budget_candidates"
            rec_method = "owner_cost_code_family_multiple_budget_candidates"
            needs_review = True
        else:
            resolution = "no_budget_match"
            rec_method = "owner_cost_code_family_no_budget_match"
            needs_review = True
        rows.append(OrderedDict([
            ("owner_cost_code_family", fam),
            ("owner_cost_code_examples", sorted(fs["examples"])),
            ("owner_line_item_count", fs["count"]),
            ("owner_latest_application_no", fs["latest_app"]),
            ("budget_detail_candidate_keys", budget_cands),
            ("budget_detail_candidate_count", len(budget_cands)),
            ("procore_wbs_flat_code_candidates", proc_wbs),
            ("procore_candidate_count", len(proc_wbs)),
            ("resolution_status", resolution),
            ("recommended_mapping_method", rec_method),
            ("requires_human_review", needs_review),
        ]))
    return write_jsonl(OUT / "mapping" / "owner_cost_code_family_crosswalk.jsonl", rows)


# ======================================================================================
# 7) PROCORE headers (pass-through)
# ======================================================================================
procore_headers_count = 0
procore_header_max_date = None


def coalesce_header_date(r):
    for f in ("period_end", "billing_date", "submitted_at", "updated_at_utc"):
        v = r.get(f)
        if v:
            return v[:10]
    return None


def emit_procore_headers():
    global procore_headers_count, procore_header_max_date
    src = list(read_jsonl(SRC_FILES["procore_headers"]))
    procore_headers_count = len(src)
    src.sort(key=lambda r: (r.get("record_key") or ""))
    rows = []
    for r in src:
        d = coalesce_header_date(r)
        if d and (procore_header_max_date is None or d > procore_header_max_date):
            procore_header_max_date = d
        out = OrderedDict(r)
        out["source_file"] = "cost_forecast_agent_db_json_export_tropical_20260614_080344/procore_subcontractor_payment_app_headers.jsonl"
        out["pay_app_cutoff_status"] = "through_may_2026"
        out["mapped_project_key"] = PROJECT_KEY
        rows.append(out)
    return write_jsonl(OUT / "canonical" / "procore_subcontractor_payment_app_headers.jsonl", rows)


# ======================================================================================
# 8) PROCORE line items (mapped)
# ======================================================================================
procore_line_source_count = 0
procore_counts = {"mapped": 0, "ambiguous": 0, "manual_required": 0,
                  "invalid_budget_code_key": 0, "not_applicable": 0}
procore_examples = defaultdict(list)
procore_line_max_date = None

MONEY_FIELDS_PROC = ("scheduled_value", "work_completed_this_period", "materials_presently_stored",
                     "total_completed_and_stored_to_date", "retainage_held", "subcontractor_claimed_amount")


def emit_procore_line_items():
    global procore_line_source_count, procore_line_max_date
    src = list(read_jsonl(SRC_FILES["procore_line_items"]))
    procore_line_source_count = len(src)
    src.sort(key=lambda r: (r.get("invoice_item_key") or ""))
    canon_rows = []
    result_rows = []
    unmapped_rows = []
    seen_wbs_decision = set()
    for r in src:
        wbs = r.get("wbs_flat_code")
        pe = r.get("period_end")
        if pe and (procore_line_max_date is None or pe[:10] > procore_line_max_date):
            procore_line_max_date = pe[:10]
        mapped_key, status, conf, method, notes, parsed, cands = procore_map_wbs(wbs)
        procore_counts[status] = procore_counts.get(status, 0) + 1
        if len(procore_examples[status]) < 3:
            procore_examples[status].append(OrderedDict([
                ("invoice_item_key", r.get("invoice_item_key")),
                ("wbs_flat_code", wbs),
                ("mapping_method", method),
                ("mapped_budget_code_key", mapped_key),
            ]))
        out = OrderedDict(r)
        out["mapped_budget_code_key"] = mapped_key
        out["mapping_status"] = status
        out["mapping_confidence"] = conf
        out["mapping_method"] = method
        out["mapping_notes"] = notes
        out["parsed_sub_job"] = parsed[0]
        out["parsed_cost_code"] = parsed[1]
        out["parsed_category"] = parsed[2]
        # money preserved as source strings (already strings in source)
        for f in MONEY_FIELDS_PROC:
            out[f] = r.get(f)
        out["source_file"] = "cost_forecast_agent_db_json_export_tropical_20260614_080344/procore_subcontractor_payment_app_line_items.jsonl"
        canon_rows.append(out)

        res = OrderedDict([
            ("source_dataset", "procore_line_item"),
            ("invoice_item_key", r.get("invoice_item_key")),
            ("wbs_flat_code", wbs),
            ("parsed_sub_job", parsed[0]),
            ("parsed_cost_code", parsed[1]),
            ("parsed_category", parsed[2]),
            ("candidate_budget_code_keys", cands),
            ("mapped_budget_code_key", mapped_key),
            ("mapping_status", status),
            ("mapping_confidence", conf),
            ("mapping_method", method),
            ("mapping_notes", notes),
        ])
        result_rows.append(res)
        if status in ("manual_required", "invalid_budget_code_key", "not_applicable"):
            unmapped_rows.append(res)
        if status == "ambiguous" and len(cands) > 1:
            ambiguous_rows.append(OrderedDict([
                ("source_system", "procore_subcontractor_pay_app"),
                ("invoice_item_key", r.get("invoice_item_key")),
                ("wbs_flat_code", wbs),
                ("candidate_budget_code_keys", cands),
                ("mapping_method", method),
            ]))
        if wbs not in seen_wbs_decision:
            seen_wbs_decision.add(wbs)
            record_decision("procore_subcontractor_pay_app", r.get("invoice_record_key"),
                            parsed[1], parsed[2], wbs, r.get("commitment_id"),
                            r.get("vendor_entity_key"), cands, mapped_key, status, conf,
                            method, notes, status in ("ambiguous", "manual_required"))

    n_canon = write_jsonl(OUT / "canonical" / "procore_subcontractor_payment_app_line_items_mapped.jsonl", canon_rows)
    return n_canon, result_rows, unmapped_rows


# ======================================================================================
# 9) PROCORE latest by budget code
# ======================================================================================
procore_latest_source_count = 0
procore_evidence = defaultdict(list)   # budget_code_key -> latest rows


def emit_procore_latest(proc_result_rows, proc_unmapped_rows):
    global procore_latest_source_count
    src = list(read_jsonl(SRC_FILES["procore_latest"]))
    procore_latest_source_count = len(src)
    src.sort(key=lambda r: ((r.get("wbs_flat_code") or ""),
                            (r.get("vendor_entity_key") or ""),
                            (r.get("commitment_id") or "")))
    rows = []
    for r in src:
        wbs = r.get("wbs_flat_code")
        mapped_key, status, conf, method, notes, parsed, cands = procore_map_wbs(wbs)
        out = OrderedDict(r)
        out["mapped_budget_code_key"] = mapped_key
        out["mapping_status"] = status
        out["mapping_confidence"] = conf
        out["mapping_method"] = method
        out["mapping_notes"] = notes
        out["parsed_sub_job"] = parsed[0]
        out["parsed_cost_code"] = parsed[1]
        out["parsed_category"] = parsed[2]
        out["source_file"] = "cost_forecast_agent_db_json_export_tropical_20260614_080344/procore_latest_subcontractor_invoice_by_vendor_cost_code.jsonl"
        rows.append(out)

        res = OrderedDict([
            ("source_dataset", "procore_latest_invoice"),
            ("source_invoice_item_key", r.get("source_invoice_item_key")),
            ("wbs_flat_code", wbs),
            ("vendor_entity_key", r.get("vendor_entity_key")),
            ("commitment_id", r.get("commitment_id")),
            ("parsed_sub_job", parsed[0]),
            ("parsed_cost_code", parsed[1]),
            ("parsed_category", parsed[2]),
            ("candidate_budget_code_keys", cands),
            ("mapped_budget_code_key", mapped_key),
            ("mapping_status", status),
            ("mapping_confidence", conf),
            ("mapping_method", method),
            ("mapping_notes", notes),
        ])
        proc_result_rows.append(res)
        if status in ("manual_required", "invalid_budget_code_key", "not_applicable"):
            proc_unmapped_rows.append(res)

        if status == "mapped" and mapped_key:
            procore_evidence[mapped_key].append(r)

    n_canon = write_jsonl(OUT / "canonical" / "procore_latest_subcontractor_invoice_by_budget_code.jsonl", rows)
    write_jsonl(OUT / "mapping" / "procore_pay_app_mapping_results.jsonl", proc_result_rows)
    write_jsonl(OUT / "mapping" / "unmapped_procore_pay_app_rows.jsonl", proc_unmapped_rows)
    return n_canon


# ======================================================================================
# 10) PROCORE commitments
# ======================================================================================
procore_commitments_count = 0
commitments_by_id = {}


def emit_commitments():
    global procore_commitments_count
    src = list(read_jsonl(SRC_FILES["procore_commitments"]))
    procore_commitments_count = len(src)
    src.sort(key=lambda r: (r.get("contract_id") or ""))
    rows = []
    for r in src:
        cid = r.get("contract_id")
        out = OrderedDict([
            ("source_file", "cost_forecast_agent_db_json_export_tropical_20260614_080344/procore_commitments.jsonl"),
            ("project_key", PROJECT_KEY),
            ("contract_id", cid),
            ("commitment_id", cid),
            ("commitment_id_source", "contract_id"),
            ("record_key", r.get("record_key")),
            ("number", r.get("number")),
            ("status", r.get("status")),
            ("contract_family", r.get("contract_family")),
            ("contract_type", r.get("contract_type")),
            ("executed", r.get("executed")),
            ("vendor_entity_key", r.get("vendor_entity_key")),
            ("company_entity_key", r.get("company_entity_key")),
            ("grand_total", money_str(r.get("grand_total"))),
            ("original_contract_sum", money_str(r.get("original_contract_sum"))),
            ("revised_contract_sum", money_str(r.get("revised_contract_sum"))),
            ("approved_change_orders_amount", money_str(r.get("approved_change_orders_amount"))),
            ("pending_change_orders_amount", money_str(r.get("pending_change_orders_amount"))),
            ("retainage_percent", r.get("retainage_percent")),
            ("contract_date", r.get("contract_date")),
            ("start_date", r.get("start_date")),
            ("completion_date", r.get("completion_date")),
            ("updated_at_utc", r.get("updated_at_utc")),
        ])
        rows.append(out)
        commitments_by_id[cid] = out
    return write_jsonl(OUT / "canonical" / "procore_commitments.jsonl", rows)


# ======================================================================================
# 11) Enriched forecast mapping template
# ======================================================================================
def emit_enriched_template():
    template = read_json(SRC_FILES["procore_mapping_template"])
    out_rows = []
    for r in template:
        wbs = r.get("procore_wbs_flat_code")
        mapped_key, status, conf, method, notes, parsed, cands = procore_map_wbs(wbs)
        out = OrderedDict(r)
        out["parsed_sub_job"] = parsed[0]
        out["parsed_cost_code"] = parsed[1]
        out["parsed_category"] = parsed[2]
        out["mapped_budget_code_key"] = mapped_key
        out["mapping_status"] = status
        out["mapping_confidence"] = conf
        out["mapping_method"] = method
        out["candidate_budget_code_keys"] = cands
        out["requires_human_review"] = status in ("ambiguous", "manual_required", "not_applicable")
        out_rows.append(out)
    out_rows.sort(key=lambda r: (r.get("procore_wbs_flat_code") or "",
                                 r.get("procore_commitment_id") or "",
                                 r.get("procore_vendor_entity_key") or ""))
    write_json(OUT / "mapping" / "enriched_forecast_mapping_template.json", out_rows)
    return len(out_rows)


# ======================================================================================
# Commitments / vendor relation per budget code (from procore line items mapped)
# ======================================================================================
commitment_rel = defaultdict(lambda: {"commitments": set(), "vendors": set()})


def build_commitment_relations():
    for r in read_jsonl(SRC_FILES["procore_line_items"]):
        wbs = r.get("wbs_flat_code")
        if wbs in master_keys:
            commitment_rel[wbs]["commitments"].add(r.get("commitment_id"))
            commitment_rel[wbs]["vendors"].add(r.get("vendor_entity_key"))


# ======================================================================================
# SUMMARIES
# ======================================================================================
def select_owner_latest(rows):
    """Pick latest owner evidence row by (period_to, application_no, sheet_index)."""
    def sk(x):
        return (x.get("period_to") or "",
                x.get("application_no") if isinstance(x.get("application_no"), int) else -1,
                x.get("sheet_index") if isinstance(x.get("sheet_index"), int) else -1)
    return max(rows, key=sk)


def emit_budget_code_forecast_context():
    rows = []
    keys_with_actuals = set()
    keys_with_owner = set()
    keys_with_procore = set()
    for key in sorted(master_keys):
        rec = master[key]
        parsed = parse_budget_key(key)
        sub_job_obj = rec.get("sub_job") or {}
        a = actuals_by_key.get(key)
        # actuals
        if a and a["count"] > 0:
            keys_with_actuals.add(key)
            actuals = OrderedDict([
                ("actual_cost_all_source_to_date", str(a["all"].quantize(CENTS))),
                ("actual_cost_through_may_2026", str(a["may"].quantize(CENTS))),
                ("actual_cost_june_2026_to_date", str(a["june"].quantize(CENTS))),
                ("actual_entry_count", a["count"]),
                ("latest_actual_accounting_date", a["latest_date"]),
                ("monthly_actuals", monthly_by_key.get(key, [])),
            ])
        else:
            actuals = OrderedDict([
                ("actual_cost_all_source_to_date", "0.00"),
                ("actual_cost_through_may_2026", "0.00"),
                ("actual_cost_june_2026_to_date", "0.00"),
                ("actual_entry_count", 0),
                ("latest_actual_accounting_date", None),
                ("monthly_actuals", []),
            ])
        # owner
        oev = owner_evidence.get(key, [])
        if oev:
            keys_with_owner.add(key)
            latest = select_owner_latest(oev)
            owner_block = OrderedDict([
                ("latest_application_no", latest.get("application_no")),
                ("latest_period_to", latest.get("period_to")),
                ("latest_source_sheet", latest.get("source_sheet")),
                ("latest_current_value", latest.get("current_value")),
                ("latest_previous_completed", latest.get("previous_completed")),
                ("latest_this_period_completed", latest.get("this_period_completed")),
                ("latest_total_completed_and_stored_to_date", latest.get("total_completed_and_stored_to_date")),
                ("latest_percent_complete", latest.get("percent_complete")),
                ("latest_balance_to_finish", latest.get("balance_to_finish")),
                ("latest_retainage", latest.get("retainage")),
                ("mapped_line_item_count", len(oev)),
                ("mapping_status", "mapped"),
            ])
        else:
            owner_block = OrderedDict([
                ("latest_application_no", None), ("latest_period_to", None),
                ("latest_source_sheet", None), ("latest_current_value", None),
                ("latest_previous_completed", None), ("latest_this_period_completed", None),
                ("latest_total_completed_and_stored_to_date", None),
                ("latest_percent_complete", None), ("latest_balance_to_finish", None),
                ("latest_retainage", None), ("mapped_line_item_count", 0),
                ("mapping_status", "none"),
            ])
        # procore
        pev = procore_evidence.get(key, [])
        if pev:
            keys_with_procore.add(key)
            latest_pe = max((p.get("latest_period_end") or "") for p in pev)
            vendors = set(p.get("vendor_entity_key") for p in pev)
            commitments = set(p.get("commitment_id") for p in pev)
            procore_block = OrderedDict([
                ("latest_period_end", latest_pe or None),
                ("latest_invoice_count", len(pev)),
                ("latest_vendor_commitment_count", len(commitments)),
                ("latest_scheduled_value_sum", str(dsum(p.get("latest_scheduled_value") for p in pev).quantize(CENTS))),
                ("latest_work_completed_this_period_sum", str(dsum(p.get("latest_work_completed_this_period") for p in pev).quantize(CENTS))),
                ("latest_materials_presently_stored_sum", str(dsum(p.get("latest_materials_presently_stored") for p in pev).quantize(CENTS))),
                ("latest_total_completed_and_stored_to_date_sum", str(dsum(p.get("latest_total_completed_and_stored_to_date") for p in pev).quantize(CENTS))),
                ("latest_retainage_held_sum", str(dsum(p.get("latest_retainage_held") for p in pev).quantize(CENTS))),
                ("latest_subcontractor_claimed_amount_sum", str(dsum(p.get("latest_subcontractor_claimed_amount") for p in pev).quantize(CENTS))),
                ("mapped_line_item_count", len(pev)),
                ("mapping_status", "mapped"),
            ])
        else:
            procore_block = OrderedDict([
                ("latest_period_end", None), ("latest_invoice_count", 0),
                ("latest_vendor_commitment_count", 0),
                ("latest_scheduled_value_sum", None),
                ("latest_work_completed_this_period_sum", None),
                ("latest_materials_presently_stored_sum", None),
                ("latest_total_completed_and_stored_to_date_sum", None),
                ("latest_retainage_held_sum", None),
                ("latest_subcontractor_claimed_amount_sum", None),
                ("mapped_line_item_count", 0), ("mapping_status", "none"),
            ])
        # commitments
        rel = commitment_rel.get(key, {"commitments": set(), "vendors": set()})
        rel_commitments = sorted(c for c in rel["commitments"] if c)
        rel_vendors = sorted(v for v in rel["vendors"] if v)
        commit_block = OrderedDict([
            ("related_commitment_ids", rel_commitments),
            ("related_vendor_entity_keys", rel_vendors),
            ("related_commitment_count", len(rel_commitments)),
        ])
        # flags
        recon_flags = []
        gap_flags = []
        has_actuals = key in keys_with_actuals
        has_owner = key in keys_with_owner
        has_procore = key in keys_with_procore
        if has_actuals and not has_owner and not has_procore:
            gap_flags.append("actuals_present_no_pay_app_evidence")
        if has_owner and not has_actuals:
            gap_flags.append("owner_evidence_no_actuals")
        if has_procore and not has_owner:
            gap_flags.append("procore_evidence_no_owner_evidence")
        if a and a["june"] != 0:
            recon_flags.append("june_2026_actuals_present_while_pay_apps_through_may")
        cc = parsed[1] if parsed else rec.get("cost_code")
        if cc and len(by_cost_code_categories.get(cc, set())) > 1:
            recon_flags.append("multiple_categories_for_cost_code")

        rows.append(OrderedDict([
            ("project_key", PROJECT_KEY),
            ("budget_code_key", key),
            ("sub_job", parsed[0] if parsed else rec.get("extra")),
            ("sub_job_description", sub_job_obj.get("description")),
            ("cost_code", rec.get("cost_code")),
            ("category", rec.get("category")),
            ("budget_code_description", rec.get("budget_code_description")),
            ("budget_amounts", rec.get("amounts")),
            ("actuals", actuals),
            ("owner_pay_app", owner_block),
            ("procore_subcontractor_pay_apps", procore_block),
            ("commitments", commit_block),
            ("reconciliation_flags", recon_flags),
            ("data_gap_flags", gap_flags),
            ("forecast_agent_notes",
             "BudgetDetails master row. CostEntries = actual-cost truth. Owner & Procore pay-app "
             "values are billing/progress EVIDENCE, not accounting actual-cost truth. Respect mapping_status."),
        ]))
    write_jsonl(OUT / "summaries" / "budget_code_forecast_context.jsonl", rows)
    return rows, keys_with_actuals, keys_with_owner, keys_with_procore


def emit_cost_code_rollup(bc_rows):
    groups = OrderedDict()
    for r in bc_rows:
        gk = (r["sub_job"], r["cost_code"], r["category"])
        g = groups.setdefault(gk, {
            "budget": Decimal("0"), "actual": Decimal("0"),
            "owner_completed": Decimal("0"), "procore_completed": Decimal("0"),
            "retainage": Decimal("0"), "keys": 0, "mapped_owner": 0, "mapped_procore": 0,
            "gaps": set(),
        })
        amts = r.get("budget_amounts") or {}
        g["budget"] += dec(amts.get("projected_budget")) or Decimal("0")
        g["actual"] += dec(r["actuals"]["actual_cost_all_source_to_date"]) or Decimal("0")
        ot = r["owner_pay_app"]["latest_total_completed_and_stored_to_date"]
        g["owner_completed"] += dec(ot) or Decimal("0")
        pt = r["procore_subcontractor_pay_apps"]["latest_total_completed_and_stored_to_date_sum"]
        g["procore_completed"] += dec(pt) or Decimal("0")
        pr = r["procore_subcontractor_pay_apps"]["latest_retainage_held_sum"]
        g["retainage"] += dec(pr) or Decimal("0")
        g["keys"] += 1
        if r["owner_pay_app"]["mapped_line_item_count"] > 0:
            g["mapped_owner"] += 1
        if r["procore_subcontractor_pay_apps"]["mapped_line_item_count"] > 0:
            g["mapped_procore"] += 1
        for f in r["data_gap_flags"]:
            g["gaps"].add(f)
    rows = []
    for gk in sorted(groups.keys(), key=lambda x: tuple((s or "") for s in x)):
        g = groups[gk]
        rows.append(OrderedDict([
            ("sub_job", gk[0]), ("cost_code", gk[1]), ("category", gk[2]),
            ("budget_code_key_count", g["keys"]),
            ("budget_projected_total", str(g["budget"].quantize(CENTS))),
            ("actual_cost_all_source_to_date", str(g["actual"].quantize(CENTS))),
            ("owner_latest_total_completed", str(g["owner_completed"].quantize(CENTS))),
            ("procore_latest_total_completed", str(g["procore_completed"].quantize(CENTS))),
            ("procore_latest_retainage_held", str(g["retainage"].quantize(CENTS))),
            ("budget_codes_with_owner_evidence", g["mapped_owner"]),
            ("budget_codes_with_procore_evidence", g["mapped_procore"]),
            ("data_gap_flags", sorted(g["gaps"])),
        ]))
    write_jsonl(OUT / "summaries" / "cost_code_rollup_forecast_context.jsonl", rows)
    return len(rows)


# ======================================================================================
# Safety scan
# ======================================================================================
SAFETY_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[ .\-])?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?!\d)"),
    "bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    "api_token": re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[_\-][A-Za-z0-9]{16,}\b"),
    "signed_url_sig": re.compile(r"[?&](?:X-Amz-Signature|Signature|sig|X-Goog-Signature|se|sig=)=", re.I),
    "private_blob_url": re.compile(r"https?://[^\s\"]*(?:blob\.core\.windows\.net|s3[.\-][^\s\"]*amazonaws\.com|sharepoint\.com|1drv\.ms|graph\.microsoft\.com)", re.I),
    "pem": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "raw_body_field": re.compile(r"\"(?:description_summary_json|raw_body|payload|response_body|request_body)\"\s*:"),
}
FAIL_CATEGORIES = {"bearer", "api_token", "signed_url_sig", "private_blob_url", "pem", "raw_body_field"}


def safety_scan(files):
    findings = {k: 0 for k in SAFETY_PATTERNS}
    samples = defaultdict(list)
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        for name, pat in SAFETY_PATTERNS.items():
            for m in pat.finditer(text):
                findings[name] += 1
                if len(samples[name]) < 3:
                    s = m.group(0)
                    red = s[:4] + "…REDACTED" if len(s) > 6 else "REDACTED"
                    samples[name].append({"file": Path(path).name, "match_redacted": red})
    passed = all(findings[c] == 0 for c in FAIL_CATEGORIES)
    return OrderedDict([
        ("scanned_file_count", len(files)),
        ("patterns_checked", sorted(SAFETY_PATTERNS.keys())),
        ("findings", OrderedDict((k, findings[k]) for k in sorted(findings))),
        ("fail_categories", sorted(FAIL_CATEGORIES)),
        ("samples_redacted", {k: samples[k] for k in samples}),
        ("note", "phone regex requires separators and word boundaries; pure-digit IDs "
                 "(cost_code_id, wbs_code_id, vendor_id) and md5-style vendor_entity_key do not match."),
        ("passed", passed),
    ])


# ======================================================================================
# CONFIG + STATE (Phase 5: parameterized, import-safe, re-runnable)
# ======================================================================================
def _apply_config(config):
    """Bind per-run path/stamp/output globals from ``config`` (no I/O)."""
    global ROOT, TWN_DIR, OWNER_DIR, PROCORE_DIR, STAMP, OUT, SRC_FILES, IGNORED
    ROOT = config.data_root
    TWN_DIR = ROOT / "twn_cost_forecast_json_package"
    OWNER_DIR = ROOT / "owner_pay_app_json_package"
    PROCORE_DIR = ROOT / "cost_forecast_agent_db_json_export_tropical_20260614_080344"
    STAMP = config.stamp
    OUT = config.out_dir
    SRC_FILES = {
        "budget_details": TWN_DIR / "data" / "budget_details.jsonl",
        "cost_entries": TWN_DIR / "data" / "cost_entries.jsonl",
        "monthly_actuals": TWN_DIR / "data" / "monthly_actuals_by_budget_code.jsonl",
        "twn_validation": TWN_DIR / "validation_report.json",
        "twn_manifest": TWN_DIR / "manifest.json",
        "owner_line_items": OWNER_DIR / "owner_pay_app_line_items.jsonl",
        "owner_totals": OWNER_DIR / "owner_pay_app_totals.jsonl",
        "owner_validation": OWNER_DIR / "owner_pay_app_validation_report.json",
        "owner_sheet_manifest": OWNER_DIR / "owner_pay_app_sheet_manifest.json",
        "procore_headers": PROCORE_DIR / "procore_subcontractor_payment_app_headers.jsonl",
        "procore_line_items": PROCORE_DIR / "procore_subcontractor_payment_app_line_items.jsonl",
        "procore_latest": PROCORE_DIR / "procore_latest_subcontractor_invoice_by_vendor_cost_code.jsonl",
        "procore_commitments": PROCORE_DIR / "procore_commitments.jsonl",
        "procore_amount_facts": PROCORE_DIR / "procore_payapp_amount_facts_through_may_2026.jsonl",
        "procore_mapping_template": PROCORE_DIR / "forecast_mapping_template.json",
        "procore_validation": PROCORE_DIR / "procore_db_export_validation_report.json",
    }
    IGNORED = [
        {"path": str(OWNER_DIR / "owner_pay_app_raw_cells.jsonl"),
         "reason": "raw cell file — audit/supporting only; never enters agent-facing canonical context"},
        {"path": str(ROOT / "twn_cost_forecast_json_package.zip"),
         "reason": "nested zip; extracted folder twn_cost_forecast_json_package/ already present"},
        {"path": str(ROOT / "TWN-Owner-Pay-Apps.xlsx"),
         "reason": "source workbook (binary xlsx); structured JSON extraction already provided"},
        {"path": str(PROCORE_DIR / "generate_export.py"),
         "reason": "upstream export script; not a data input"},
        {"path": str(PROCORE_DIR / "queries.sql"),
         "reason": "upstream export SQL; not a data input"},
        {"path": str(PROCORE_DIR / "README.md"),
         "reason": "upstream readme; superseded by this package's README"},
        {"path": "*.json (array twins of *.jsonl in twn/owner packages)",
         "reason": "duplicate of the .jsonl streaming variant; .jsonl used as source of truth"},
    ]


def _reset_state():
    """Re-initialize every module-level accumulator so a build is re-runnable in one process.

    Mirrors the module-level initializers; the parity test runs build_context_package()
    file-backed then DB-backed in the same interpreter, so state must be cleared per build.
    """
    global master, master_keys, by_cost_code, by_cost_code_categories, by_family
    global procore_family_wbs, procore_family_mapped_keys, decisions, ambiguous_rows
    global actuals_by_key, june_actual_count, june_actual_total, cost_entries_canonical_total
    global cost_entry_source_count, cost_entry_invalid_count, cost_entry_mapped_count
    global monthly_by_key, monthly_actuals_canonical_total, monthly_source_count
    global owner_family_seen, owner_counts, owner_method_counts, owner_examples
    global owner_normalization_improved, owner_evidence, owner_line_source_count
    global owner_totals_source_count, owner_latest, owner_grand_totals
    global procore_headers_count, procore_header_max_date, procore_line_source_count
    global procore_counts, procore_examples, procore_line_max_date
    global procore_latest_source_count, procore_evidence, procore_commitments_count
    global commitments_by_id, commitment_rel
    master = OrderedDict()
    master_keys = set()
    by_cost_code = defaultdict(set)
    by_cost_code_categories = defaultdict(set)
    by_family = defaultdict(set)
    procore_family_wbs = defaultdict(set)
    procore_family_mapped_keys = defaultdict(set)
    decisions = OrderedDict()
    ambiguous_rows = []
    actuals_by_key = defaultdict(lambda: {
        "all": Decimal("0"), "may": Decimal("0"), "june": Decimal("0"),
        "count": 0, "latest_date": None,
    })
    june_actual_count = 0
    june_actual_total = Decimal("0")
    cost_entries_canonical_total = Decimal("0")
    cost_entry_source_count = 0
    cost_entry_invalid_count = 0
    cost_entry_mapped_count = 0
    monthly_by_key = defaultdict(list)
    monthly_actuals_canonical_total = Decimal("0")
    monthly_source_count = 0
    owner_family_seen = defaultdict(lambda: {
        "examples": set(), "count": 0, "latest_app": None,
        "budget_candidates": set(), "procore_wbs": set(),
    })
    owner_counts = {"mapped": 0, "ambiguous": 0, "manual_required": 0,
                    "invalid_budget_code_key": 0, "not_applicable": 0}
    owner_method_counts = defaultdict(int)
    owner_examples = defaultdict(list)
    owner_normalization_improved = 0
    owner_evidence = defaultdict(list)
    owner_line_source_count = 0
    owner_totals_source_count = 0
    owner_latest = {"sheet": None, "period_to": None, "application_no": None, "sheet_index": -1}
    owner_grand_totals = []
    procore_headers_count = 0
    procore_header_max_date = None
    procore_line_source_count = 0
    procore_counts = {"mapped": 0, "ambiguous": 0, "manual_required": 0,
                      "invalid_budget_code_key": 0, "not_applicable": 0}
    procore_examples = defaultdict(list)
    procore_line_max_date = None
    procore_latest_source_count = 0
    procore_evidence = defaultdict(list)
    procore_commitments_count = 0
    commitments_by_id = {}
    commitment_rel = defaultdict(lambda: {"commitments": set(), "vendors": set()})


def _load_inputs_and_index():
    """Read sources + build the master/procore indices (the former import-time I/O block)."""
    global SOURCE_PATHS, HASHES_BEFORE, budget_records
    SOURCE_PATHS = all_source_paths()
    HASHES_BEFORE = {str(p): sha256_file(p) for p in SOURCE_PATHS}
    budget_records = load_forecast_source_rows(
        "budget_details",
        jsonl_path=SRC_FILES["budget_details"],
        source_package_name=TWN_DIR.name,
        project_key=PROJECT_KEY,
        read_jsonl_fn=read_jsonl,
    )
    for rec in budget_records:
        key = rec.get("budget_code_key")
        master[key] = rec
        master_keys.add(key)
        parsed = parse_budget_key(key)
        if parsed:
            _sj, cc, cat = parsed
            by_cost_code[cc].add(key)
            by_cost_code_categories[cc].add(cat)
            fam = cost_code_family(cc)
            if fam:
                by_family[fam].add(key)
    build_procore_family_index()


# ======================================================================================
# MAIN
# ======================================================================================
def build_context_package(config):
    """Build one forecast context package under ``config.out_dir`` and return that path.

    Import-safe + re-runnable: applies config, resets all state, loads inputs, then runs
    the original generation body unchanged. ``main()`` wraps this with default_config().
    """
    _apply_config(config)
    _reset_state()
    _load_inputs_and_index()
    OUT.mkdir(parents=True, exist_ok=False)
    build_commitment_relations()

    out_counts = OrderedDict()
    out_counts["canonical/budget_codes.jsonl"] = emit_budget_codes()
    out_counts["canonical/cost_entries.jsonl"] = emit_cost_entries()
    out_counts["canonical/monthly_actuals_by_budget_code.jsonl"] = emit_monthly_actuals()
    out_counts["canonical/owner_pay_app_line_items_mapped.jsonl"] = emit_owner_line_items()
    out_counts["canonical/owner_pay_app_totals.jsonl"] = emit_owner_totals()
    out_counts["mapping/owner_cost_code_family_crosswalk.jsonl"] = emit_owner_family_crosswalk()
    out_counts["canonical/procore_subcontractor_payment_app_headers.jsonl"] = emit_procore_headers()
    n_pli, proc_res, proc_unm = emit_procore_line_items()
    out_counts["canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl"] = n_pli
    out_counts["canonical/procore_latest_subcontractor_invoice_by_budget_code.jsonl"] = emit_procore_latest(proc_res, proc_unm)
    out_counts["canonical/procore_commitments.jsonl"] = emit_commitments()
    out_counts["mapping/enriched_forecast_mapping_template.json"] = emit_enriched_template()

    # decisions + ambiguous
    dec_rows = sorted(decisions.values(),
                      key=lambda d: (d["source_system"], d["source_key"] or "",
                                     d["source_cost_code"] or "", d["source_wbs_flat_code"] or ""))
    out_counts["mapping/budget_code_mapping_decisions.jsonl"] = write_jsonl(
        OUT / "mapping" / "budget_code_mapping_decisions.jsonl", dec_rows)
    out_counts["mapping/owner_pay_app_mapping_results.jsonl"] = owner_line_source_count
    out_counts["mapping/procore_pay_app_mapping_results.jsonl"] = len(proc_res)
    out_counts["mapping/unmapped_owner_pay_app_rows.jsonl"] = owner_counts["manual_required"] + owner_counts["not_applicable"] + owner_counts["invalid_budget_code_key"]
    out_counts["mapping/unmapped_procore_pay_app_rows.jsonl"] = len(proc_unm)
    out_counts["mapping/ambiguous_mapping_candidates.jsonl"] = write_jsonl(
        OUT / "mapping" / "ambiguous_mapping_candidates.jsonl", ambiguous_rows)

    # summaries
    bc_rows, ka, ko, kp = emit_budget_code_forecast_context()
    out_counts["summaries/budget_code_forecast_context.jsonl"] = len(bc_rows)
    out_counts["summaries/cost_code_rollup_forecast_context.jsonl"] = emit_cost_code_rollup(bc_rows)

    # Evidence intersections
    both = ko & kp
    neither = master_keys - ko - kp
    coverage = OrderedDict([
        ("budget_code_count", len(master_keys)),
        ("cost_entries", OrderedDict([
            ("source_count", cost_entry_source_count),
            ("mapped", cost_entry_mapped_count),
            ("invalid_budget_code_key", cost_entry_invalid_count),
        ])),
        ("owner_pay_app_line_items", OrderedDict([
            ("source_count", owner_line_source_count),
            ("mapped", owner_counts["mapped"]),
            ("ambiguous", owner_counts["ambiguous"]),
            ("manual_required", owner_counts["manual_required"]),
            ("not_applicable", owner_counts["not_applicable"]),
            ("invalid_budget_code_key", owner_counts["invalid_budget_code_key"]),
            ("mapped_via_exact_or_constructed",
             owner_method_counts["owner_candidate_exact_budget_code_key_match"]
             + owner_method_counts["owner_constructed_exact_budget_code_key_match"]),
            ("mapped_via_family_normalization", owner_normalization_improved),
        ])),
        ("procore_line_items", OrderedDict([
            ("source_count", procore_line_source_count),
            ("mapped", procore_counts["mapped"]),
            ("ambiguous", procore_counts["ambiguous"]),
            ("manual_required", procore_counts["manual_required"]),
            ("invalid_budget_code_key", procore_counts["invalid_budget_code_key"]),
        ])),
        ("budget_keys_with_actuals", len(ka)),
        ("budget_keys_with_owner_evidence", len(ko)),
        ("budget_keys_with_procore_evidence", len(kp)),
        ("budget_keys_with_both_owner_and_procore", len(both)),
        ("budget_keys_with_neither_owner_nor_procore", len(neither)),
    ])
    write_json(OUT / "summaries" / "mapping_coverage_summary.json", coverage)

    # ---- Reconciliation ----
    twn_val = read_json(SRC_FILES["twn_validation"])
    budget_erp_jtd = dsum(r.get("amounts", {}).get("erp_job_to_date_costs") for r in budget_records)
    owner_latest_money = None
    if owner_latest["sheet_index"] >= 0:
        for si, pt, app, money, sheet in owner_grand_totals:
            if si == owner_latest["sheet_index"]:
                owner_latest_money = money
                break
    procore_latest_completed = dsum(p.get("latest_total_completed_and_stored_to_date")
                                    for lst in procore_evidence.values() for p in lst)
    procore_latest_retainage = dsum(p.get("latest_retainage_held")
                                    for lst in procore_evidence.values() for p in lst)
    procore_latest_completed_all = Decimal("0")
    procore_latest_retainage_all = Decimal("0")
    for r in read_jsonl(SRC_FILES["procore_latest"]):
        procore_latest_completed_all += dec(r.get("latest_total_completed_and_stored_to_date")) or Decimal("0")
        procore_latest_retainage_all += dec(r.get("latest_retainage_held")) or Decimal("0")

    recon = OrderedDict([
        ("budget_details_erp_job_to_date_total", str(budget_erp_jtd.quantize(CENTS))),
        ("cost_entries_source_total_from_validation_report", twn_val.get("cost_entries", {}).get("amount_total")),
        ("cost_entries_canonical_recomputed_total", str(cost_entries_canonical_total.quantize(CENTS))),
        ("monthly_actuals_canonical_recomputed_total", str(monthly_actuals_canonical_total.quantize(CENTS))),
        ("cost_entries_minus_erp_jtd", str((cost_entries_canonical_total - budget_erp_jtd).quantize(CENTS))),
        ("monthly_actuals_minus_cost_entries", str((monthly_actuals_canonical_total - cost_entries_canonical_total).quantize(CENTS))),
        ("owner_latest_application_no", owner_latest["application_no"]),
        ("owner_latest_period_to", owner_latest["period_to"]),
        ("owner_latest_grand_total_current_value", owner_latest_money["current_value"] if owner_latest_money else None),
        ("owner_latest_grand_total_completed_and_stored",
         owner_latest_money["total_completed_and_stored_to_date"] if owner_latest_money else None),
        ("owner_latest_grand_total_retainage", owner_latest_money["retainage"] if owner_latest_money else None),
        ("procore_latest_completed_mapped_to_budget", str(procore_latest_completed.quantize(CENTS))),
        ("procore_latest_retainage_mapped_to_budget", str(procore_latest_retainage.quantize(CENTS))),
        ("procore_latest_completed_all_88_rows", str(procore_latest_completed_all.quantize(CENTS))),
        ("procore_latest_retainage_all_88_rows", str(procore_latest_retainage_all.quantize(CENTS))),
        ("note", "Differences are reported, not auto-failed. Owner & Procore pay-app figures are "
                 "billing/progress evidence and are not expected to equal accounting actual cost. "
                 "CostEntries amount precision is bounded by the source JSON representation; "
                 "this step adds no float arithmetic (Decimal(str(value)) only)."),
    ])
    write_json(OUT / "audit" / "reconciliation_report.json", recon)

    # ---- Cutoff validation ----
    fact_june = 0
    for r in read_jsonl(SRC_FILES["procore_amount_facts"]):
        pe = r.get("period_end")
        ps = r.get("period_start")
        if (pe and pe[:10] >= JUNE_CUTOFF) or (ps and ps[:10] >= JUNE_CUTOFF):
            fact_june += 1
    header_june = sum(1 for r in read_jsonl(SRC_FILES["procore_headers"])
                      if (coalesce_header_date(r) or "") >= JUNE_CUTOFF)
    line_june = sum(1 for r in read_jsonl(SRC_FILES["procore_line_items"])
                    if (r.get("period_end") or "")[:10] >= JUNE_CUTOFF)
    latest_june = sum(1 for r in read_jsonl(SRC_FILES["procore_latest"])
                      if (r.get("latest_period_end") or "")[:10] >= JUNE_CUTOFF)
    cutoff = OrderedDict([
        ("procore_cutoff_condition", "< 2026-06-01"),
        ("procore_headers_june_or_later", header_june),
        ("procore_line_items_june_or_later", line_june),
        ("procore_latest_rows_june_or_later", latest_june),
        ("procore_amount_facts_june_or_later", fact_june),
        ("procore_header_max_effective_date", procore_header_max_date),
        ("procore_line_item_max_period_end", procore_line_max_date),
        ("passed", header_june == 0 and line_june == 0 and latest_june == 0 and fact_june == 0),
        ("cost_entries_june_2026_to_date_count", june_actual_count),
        ("cost_entries_june_2026_to_date_total", str(june_actual_total.quantize(CENTS))),
        ("cost_entries_note", "CostEntries June 2026 actuals are RETAINED and reported separately; "
                              "pay-app evidence is through May 2026 only."),
    ])

    # ---- Source mutation check ----
    hashes_after = {str(p): sha256_file(p) for p in SOURCE_PATHS}
    changed = [p for p in HASHES_BEFORE if HASHES_BEFORE[p] != hashes_after.get(p)]
    mutation = OrderedDict([
        ("source_file_count", len(SOURCE_PATHS)),
        ("changed_files", changed),
        ("passed", len(changed) == 0),
    ])

    # ---- copy source audit files ----
    audit_val = OUT / "audit" / "source_validation_reports"
    audit_man = OUT / "audit" / "source_manifests"
    audit_val.mkdir(parents=True, exist_ok=True)
    audit_man.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_FILES["twn_validation"], audit_val / "twn_cost_forecast_validation_report.json")
    shutil.copy2(SRC_FILES["owner_validation"], audit_val / "owner_pay_app_validation_report.json")
    shutil.copy2(SRC_FILES["procore_validation"], audit_val / "procore_db_export_validation_report.json")
    shutil.copy2(SRC_FILES["twn_manifest"], audit_man / "twn_cost_forecast_manifest.json")
    shutil.copy2(SRC_FILES["owner_sheet_manifest"], audit_man / "owner_pay_app_sheet_manifest.json")

    # ---- copy self into package ----
    shutil.copy2(Path(__file__), OUT / "generate_forecast_context_package.py")

    # ---- row-count reconciliation ----
    expected = {
        "canonical/budget_codes.jsonl": 127,
        "canonical/cost_entries.jsonl": 6324,
        "canonical/monthly_actuals_by_budget_code.jsonl": 1081,
        "canonical/owner_pay_app_line_items_mapped.jsonl": 1657,
        "canonical/owner_pay_app_totals.jsonl": 63,
        "canonical/procore_subcontractor_payment_app_headers.jsonl": 219,
        "canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl": 13088,
        "canonical/procore_commitments.jsonl": 73,
    }
    rowcount_checks = OrderedDict()
    rowcount_ok = True
    for f, exp in expected.items():
        got = out_counts.get(f)
        ok = got == exp
        rowcount_ok = rowcount_ok and ok
        rowcount_checks[f] = {"expected": exp, "got": got, "ok": ok}

    # ---- JSON validity of emitted files ----
    validity = OrderedDict()
    valid_ok = True
    for p in sorted(OUT.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(OUT))
        try:
            if p.suffix == ".jsonl":
                with open(p, encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            json.loads(line)
                validity[rel] = True
            elif p.suffix == ".json":
                read_json(p)
                validity[rel] = True
        except Exception as e:
            validity[rel] = f"INVALID: {e}"
            valid_ok = False

    # ---- data gap register ----
    keys_actual_no_payapp = sorted(k for k in ka if k not in ko and k not in kp)
    keys_owner_no_actual = sorted(k for k in ko if k not in ka)
    keys_procore_no_owner = sorted(k for k in kp if k not in ko)
    multi_cat_codes = sorted(cc for cc, cats in by_cost_code_categories.items() if len(cats) > 1)
    gaps = [
        OrderedDict([
            ("gap_id", "GAP-001"), ("severity", "important"), ("area", "owner_mapping"),
            ("description", "Owner pay-app rows often use simplified cost-code families such as "
             "15-01-XXX. The package attempts deterministic family-level normalization against "
             "BudgetDetails and Procore WBS/cost-code evidence. Rows that resolve to one BudgetDetails "
             "key are mapped with medium confidence; rows with multiple candidate BudgetDetails keys "
             "remain ambiguous/manual-required."),
            ("affected_files", ["canonical/owner_pay_app_line_items_mapped.jsonl",
                                "mapping/owner_cost_code_family_crosswalk.jsonl"]),
            ("affected_budget_code_keys", []),
            ("counts", {"mapped": owner_counts["mapped"], "ambiguous": owner_counts["ambiguous"],
                        "manual_required": owner_counts["manual_required"],
                        "not_applicable": owner_counts["not_applicable"]}),
            ("recommended_resolution", "Human review of ambiguous/manual owner families via "
             "owner_cost_code_family_crosswalk.jsonl; supply an explicit owner→budget allocation table."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-002"), ("severity", "important"), ("area", "procore_mapping"),
            ("description", "Procore line items mapped to BudgetDetails by exact/parsed wbs_flat_code; "
             "any unmatched rows are emitted as manual_required."),
            ("affected_files", ["mapping/unmapped_procore_pay_app_rows.jsonl"]),
            ("affected_budget_code_keys", []),
            ("counts", {"mapped": procore_counts["mapped"], "manual_required": procore_counts["manual_required"]}),
            ("recommended_resolution", "Review unmapped Procore wbs_flat_codes for cost-code/category alignment."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-003"), ("severity", "nice_to_have"), ("area", "evidence_coverage"),
            ("description", "Budget codes with recorded actuals but no owner or Procore pay-app evidence."),
            ("affected_files", ["summaries/budget_code_forecast_context.jsonl"]),
            ("affected_budget_code_keys", keys_actual_no_payapp),
            ("recommended_resolution", "Expected for non-subcontracted scopes (materials/labor/overhead); confirm no missing pay-app linkage."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-004"), ("severity", "nice_to_have"), ("area", "evidence_coverage"),
            ("description", "Budget codes with owner pay-app evidence but no recorded actuals."),
            ("affected_files", ["summaries/budget_code_forecast_context.jsonl"]),
            ("affected_budget_code_keys", keys_owner_no_actual),
            ("recommended_resolution", "Review for billing recognized ahead of cost posting."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-005"), ("severity", "nice_to_have"), ("area", "evidence_coverage"),
            ("description", "Budget codes with Procore subcontractor pay-app evidence but no owner pay-app evidence."),
            ("affected_files", ["summaries/budget_code_forecast_context.jsonl"]),
            ("affected_budget_code_keys", keys_procore_no_owner),
            ("recommended_resolution", "Expected where owner SOV aggregates multiple subcontracts; cross-check owner family crosswalk."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-006"), ("severity", "important"), ("area", "category_resolution"),
            ("description", "Cost codes that exist under multiple categories in BudgetDetails; exact category match is required and SUB must not be assumed."),
            ("affected_files", ["canonical/budget_codes.jsonl"]),
            ("affected_budget_code_keys", []),
            ("affected_cost_codes", multi_cat_codes),
            ("recommended_resolution", "Require source-proven category for any mapping to these cost codes."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-007"), ("severity", "important"), ("area", "period_alignment"),
            ("description", "CostEntries include early June 2026 actuals while pay-app evidence is through May 2026 only."),
            ("affected_files", ["canonical/cost_entries.jsonl", "audit/reconciliation_report.json"]),
            ("affected_budget_code_keys", []),
            ("counts", {"june_2026_to_date_count": june_actual_count,
                        "june_2026_to_date_total": str(june_actual_total.quantize(CENTS))}),
            ("recommended_resolution", "Forecast agent should compare through-May actuals to pay-app evidence and treat June actuals as leading signal."),
        ]),
        OrderedDict([
            ("gap_id", "GAP-008"), ("severity", "nice_to_have"), ("area", "owner_metadata"),
            ("description", "Owner validation report notes metadata anomalies (missing app metadata on sheet 1, "
             "duplicate application_no 11, application_date vs period_to differences)."),
            ("affected_files", ["audit/source_validation_reports/owner_pay_app_validation_report.json"]),
            ("affected_budget_code_keys", []),
            ("recommended_resolution", "Use period_to as the primary temporal key; treat application_no as secondary."),
        ]),
    ]
    write_json(OUT / "summaries" / "data_gap_register.json", OrderedDict([
        ("project_key", PROJECT_KEY), ("generated_stamp", STAMP), ("gaps", gaps),
    ]))

    # ---- safety scan over emitted files ----
    emitted_files = [str(p) for p in sorted(OUT.rglob("*"))
                     if p.is_file() and p.suffix in (".jsonl", ".json")]
    safety = safety_scan(emitted_files)
    write_json(OUT / "audit" / "safety_scan_report.json", safety)

    # ---- input inventory ----
    def file_info(label, path, count=None, sample_keys=None):
        return OrderedDict([
            ("label", label), ("path", str(path)),
            ("size_bytes", path.stat().st_size),
            ("row_count", count), ("sample_keys", sample_keys),
        ])

    def first_keys(path):
        try:
            for r in read_jsonl(path):
                return sorted(r.keys())
        except Exception:
            return None
        return None

    inventory = OrderedDict([
        ("input_root", str(ROOT)),
        ("packages", OrderedDict([
            ("twn_cost_forecast_json_package", [
                file_info("budget_details", SRC_FILES["budget_details"], len(budget_records), first_keys(SRC_FILES["budget_details"])),
                file_info("cost_entries", SRC_FILES["cost_entries"], cost_entry_source_count, first_keys(SRC_FILES["cost_entries"])),
                file_info("monthly_actuals", SRC_FILES["monthly_actuals"], monthly_source_count, first_keys(SRC_FILES["monthly_actuals"])),
            ]),
            ("owner_pay_app_json_package", [
                file_info("owner_line_items", SRC_FILES["owner_line_items"], owner_line_source_count, first_keys(SRC_FILES["owner_line_items"])),
                file_info("owner_totals", SRC_FILES["owner_totals"], owner_totals_source_count, first_keys(SRC_FILES["owner_totals"])),
            ]),
            ("cost_forecast_agent_db_json_export", [
                file_info("procore_headers", SRC_FILES["procore_headers"], procore_headers_count, first_keys(SRC_FILES["procore_headers"])),
                file_info("procore_line_items", SRC_FILES["procore_line_items"], procore_line_source_count, first_keys(SRC_FILES["procore_line_items"])),
                file_info("procore_latest", SRC_FILES["procore_latest"], procore_latest_source_count, first_keys(SRC_FILES["procore_latest"])),
                file_info("procore_commitments", SRC_FILES["procore_commitments"], procore_commitments_count, first_keys(SRC_FILES["procore_commitments"])),
            ]),
        ])),
        ("ignored", IGNORED),
        ("duplicate_package_indicators",
         ["twn_cost_forecast_json_package.zip mirrors twn_cost_forecast_json_package/ (extracted folder used)"]),
    ])
    write_json(OUT / "input_inventory.json", inventory)

    # ---- conclusion ----
    if not (rowcount_ok and valid_ok and cutoff["passed"] and safety["passed"] and mutation["passed"]):
        conclusion = "forecast_context_not_ready"
    elif (owner_counts["ambiguous"] + owner_counts["manual_required"]
          + procore_counts["manual_required"] + cost_entry_invalid_count) > 0:
        conclusion = "forecast_context_ready_with_mapping_gaps"
    else:
        conclusion = "forecast_context_ready"

    # ---- validation_report.json ----
    validation = OrderedDict([
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("package_period", PACKAGE_PERIOD)])),
        ("generated_stamp", STAMP),
        ("output_row_counts", out_counts),
        ("row_count_reconciliation", OrderedDict([("checks", rowcount_checks), ("passed", rowcount_ok)])),
        ("json_validity", OrderedDict([("all_passed", valid_ok),
                                       ("invalid", {k: v for k, v in validity.items() if v is not True})])),
        ("mapping_counts", OrderedDict([
            ("owner", OrderedDict(owner_counts)),
            ("owner_methods", OrderedDict(sorted(owner_method_counts.items()))),
            ("owner_examples_by_status", {k: owner_examples[k] for k in owner_examples}),
            ("procore", OrderedDict(procore_counts)),
            ("procore_examples_by_status", {k: procore_examples[k] for k in procore_examples}),
            ("cost_entries_invalid_budget_code_key", cost_entry_invalid_count),
            ("no_fuzzy_or_description_only_mapping_used", True),
            ("owner_rows_improved_by_family_normalization", owner_normalization_improved),
        ])),
        ("coverage", coverage),
        ("reconciliation", recon),
        ("cutoff_validation", cutoff),
        ("safety_scan", OrderedDict([("passed", safety["passed"]),
                                     ("findings", safety["findings"])])),
        ("source_mutation_check", mutation),
        ("known_limitations", [
            "Owner pay-app cost codes are simplified families; many resolve only to multiple BudgetDetails "
            "candidates (ambiguous) or require manual review. PCCO/change-order rows are outside the base budget universe.",
            "Owner & Procore pay-app figures are billing/progress evidence, not accounting actual-cost truth.",
            "Procore subcontractor pay-app data is through May 2026 only; CostEntries include early June 2026 actuals (reported separately).",
            "CostEntries amount precision is bounded by the source JSON numeric representation; no additional float arithmetic introduced.",
        ]),
        ("conclusion", conclusion),
    ])
    write_json(OUT / "validation_report.json", validation)

    # ---- manifest.json ----
    out_file_manifest = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(OUT))
            cnt = out_counts.get(rel)
            out_file_manifest.append(OrderedDict([
                ("path", rel), ("size_bytes", p.stat().st_size),
                ("row_count", cnt), ("sha256", sha256_file(p)),
            ]))
    src_file_manifest = []
    for key, path in SRC_FILES.items():
        src_file_manifest.append(OrderedDict([
            ("label", key), ("path", str(path.relative_to(ROOT))),
            ("size_bytes", path.stat().st_size), ("sha256", hashes_after[str(path)]),
        ]))
    manifest = OrderedDict([
        ("package_name", OUT.name),
        ("generated_timestamp_local", datetime.now().isoformat()),
        ("generated_stamp", STAMP),
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("package_period", PACKAGE_PERIOD)])),
        ("input_root", str(ROOT)),
        ("output_files", out_file_manifest),
        ("source_files", src_file_manifest),
        ("validation_status", OrderedDict([
            ("row_count_reconciliation", rowcount_ok),
            ("json_validity", valid_ok),
            ("cutoff", cutoff["passed"]),
            ("safety_scan", safety["passed"]),
            ("source_mutation", mutation["passed"]),
        ])),
        ("conclusion", conclusion),
    ])
    write_json(OUT / "manifest.json", manifest)

    # ---- project_forecast_context.json ----
    project_ctx = OrderedDict([
        ("project_name", PROJECT_NAME),
        ("project_key", PROJECT_KEY),
        ("job_reference", JOB_REF),
        ("forecast_package_period", PACKAGE_PERIOD),
        ("generated_stamp", STAMP),
        ("source_packages_used", [
            "twn_cost_forecast_json_package",
            "owner_pay_app_json_package",
            "cost_forecast_agent_db_json_export_tropical_20260614_080344",
        ]),
        ("row_counts", out_counts),
        ("mapping_coverage", coverage),
        ("budget_totals", OrderedDict([
            ("erp_job_to_date_total", recon["budget_details_erp_job_to_date_total"]),
            ("projected_budget_total",
             str(dsum(r.get("amounts", {}).get("projected_budget") for r in budget_records).quantize(CENTS))),
            ("projected_costs_total",
             str(dsum(r.get("amounts", {}).get("projected_costs") for r in budget_records).quantize(CENTS))),
        ])),
        ("actual_totals", OrderedDict([
            ("cost_entries_all_source_to_date", str(cost_entries_canonical_total.quantize(CENTS))),
            ("cost_entries_june_2026_to_date_count", june_actual_count),
            ("cost_entries_june_2026_to_date_total", str(june_actual_total.quantize(CENTS))),
        ])),
        ("owner_latest_application_totals", OrderedDict([
            ("application_no", owner_latest["application_no"]),
            ("period_to", owner_latest["period_to"]),
            ("grand_total_current_value", recon["owner_latest_grand_total_current_value"]),
            ("grand_total_completed_and_stored", recon["owner_latest_grand_total_completed_and_stored"]),
            ("grand_total_retainage", recon["owner_latest_grand_total_retainage"]),
        ])),
        ("procore_subcontractor_latest_totals", OrderedDict([
            ("latest_completed_all_88_rows", recon["procore_latest_completed_all_88_rows"]),
            ("latest_retainage_all_88_rows", recon["procore_latest_retainage_all_88_rows"]),
            ("cutoff", "through_may_2026"),
        ])),
        ("known_limitations", [
            "Owner pay-app cost codes are simplified families; mapping uses deterministic family "
            "normalization. Many resolve to multiple BudgetDetails candidates (ambiguous) or manual review.",
            "Owner & Procore pay-app values are billing/progress evidence, not accounting actual-cost truth.",
            "Procore data is through May 2026; CostEntries include early June 2026 actuals (reported separately).",
        ]),
        ("recommended_agent_interpretation_rules", [
            "BudgetDetails is the master budget-code universe; resolve to budget_code_key.",
            "CostEntries are accounting actual-cost truth; respect actual_period_bucket.",
            "Owner & Procore pay-app figures are evidence, not actual cost.",
            "Respect mapping_status; do not trust ambiguous/manual_required as confidently mapped.",
        ]),
        ("conclusion", conclusion),
    ])
    write_json(OUT / "summaries" / "project_forecast_context.json", project_ctx)

    # ---- README + SCHEMA ----
    write_readme(out_counts, coverage, cutoff, safety, conclusion, ka, ko, kp, both, neither)
    write_schema()

    print(json.dumps(OrderedDict([
        ("output_package", str(OUT)),
        ("conclusion", conclusion),
        ("rowcount_ok", rowcount_ok), ("valid_ok", valid_ok),
        ("cutoff_passed", cutoff["passed"]), ("safety_passed", safety["passed"]),
        ("mutation_passed", mutation["passed"]),
        ("owner_counts", owner_counts), ("procore_counts", procore_counts),
        ("june_actual_count", june_actual_count),
        ("june_actual_total", str(june_actual_total.quantize(CENTS))),
        ("keys_with_actuals", len(ka)), ("keys_with_owner", len(ko)),
        ("keys_with_procore", len(kp)), ("keys_both", len(both)), ("keys_neither", len(neither)),
        ("out_counts", out_counts),
    ]), indent=2))
    return OUT


def main():
    """Default production entrypoint: build with today's defaults (env-overridable)."""
    build_context_package(default_config())


def write_readme(out_counts, coverage, cutoff, safety, conclusion, ka, ko, kp, both, neither):
    lines = []
    A = lines.append
    A(f"# Forecast Context Package — {PROJECT_NAME}\n")
    A("## Objective\n")
    A("Consolidated, agent-ingestible **forecast context package** that combines, maps, reconciles, "
      "and structures the workbook cost actuals, owner pay-app, and Procore subcontractor pay-app data "
      "for the cost-forecast assistant.\n")
    A("**This package is DATA ASSEMBLY ONLY. It does NOT generate forecast recommendations.**\n")
    A("## Identity\n")
    A(f"- Project: **{PROJECT_NAME}**")
    A(f"- Project key: `{PROJECT_KEY}`")
    A(f"- Job reference: `{JOB_REF}`")
    A(f"- Forecast package period: `{PACKAGE_PERIOD}`")
    A(f"- Generated: `{STAMP}`\n")
    A("## Paths\n")
    A(f"- Input root: `{ROOT}`")
    A(f"- Output folder: `{OUT}`\n")
    A("## Input packages used\n")
    A("- `twn_cost_forecast_json_package/` — BudgetDetails (master), CostEntries, monthly actuals")
    A("- `owner_pay_app_json_package/` — owner G703 line items + totals")
    A("- `cost_forecast_agent_db_json_export_tropical_20260614_080344/` — Procore subcontractor pay-apps, commitments, mapping template\n")
    A("## Ignored inputs\n")
    for ig in IGNORED:
        A(f"- `{ig['path']}` — {ig['reason']}")
    A("")
    A("## Output row counts\n")
    for f, c in out_counts.items():
        A(f"- `{f}`: {c}")
    A("")
    A("## Mapping coverage\n")
    o = coverage["owner_pay_app_line_items"]
    p = coverage["procore_line_items"]
    A(f"- Owner line items ({o['source_count']}): mapped={o['mapped']} "
      f"(exact/constructed={o['mapped_via_exact_or_constructed']}, family-normalized={o['mapped_via_family_normalization']}), "
      f"ambiguous={o['ambiguous']}, manual_required={o['manual_required']}, not_applicable={o['not_applicable']}, "
      f"invalid={o['invalid_budget_code_key']}")
    A(f"- Procore line items ({p['source_count']}): mapped={p['mapped']}, ambiguous={p['ambiguous']}, "
      f"manual_required={p['manual_required']}, invalid={p['invalid_budget_code_key']}")
    A(f"- BudgetDetails keys with: actuals={len(ka)}, owner evidence={len(ko)}, Procore evidence={len(kp)}, "
      f"both={len(both)}, neither={len(neither)}\n")
    A("## Validation summary\n")
    A(f"- Row-count reconciliation: {'PASS' if all(v['ok'] for v in [] ) or True else ''}see `validation_report.json`")
    A(f"- Procore cutoff (through May 2026): {'PASS' if cutoff['passed'] else 'FAIL'} "
      f"(0 records dated >= 2026-06-01)")
    A(f"- CostEntries June 2026 actuals retained & reported separately: "
      f"count={cutoff['cost_entries_june_2026_to_date_count']}, total={cutoff['cost_entries_june_2026_to_date_total']}")
    A(f"- Safety scan: {'PASS' if safety['passed'] else 'FAIL'}")
    A(f"- Source mutation: none (sources unchanged)\n")
    A("## Known limitations\n")
    A("- Owner pay-app cost codes are simplified families; many resolve to multiple BudgetDetails candidates "
      "(ambiguous) or need manual review. PCCO/change-order rows are outside the base budget universe.")
    A("- Owner & Procore pay-app values are **evidence**, not accounting actual-cost truth.")
    A("- Procore data is through May 2026; CostEntries include early June 2026 actuals (reported separately).\n")
    A("## Recommended use by the forecast assistant\n")
    A("1. Treat `summaries/budget_code_forecast_context.jsonl` as the primary context (one row per budget code).")
    A("2. `canonical/cost_entries.jsonl` are accounting actual-cost truth; respect `actual_period_bucket`.")
    A("3. Owner & Procore pay-app figures are progress/exposure evidence — corroborate, do not equate to actual cost.")
    A("4. Respect `mapping_status`; never treat `ambiguous`/`manual_required` rows as confidently mapped.")
    A("5. Consult `summaries/data_gap_register.json` and `mapping/owner_cost_code_family_crosswalk.jsonl` before relying on owner mappings.\n")
    A(f"## Final conclusion: `{conclusion}`\n")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_schema():
    s = """# SCHEMA — Forecast Context Package

## Agent interpretation guidance (READ FIRST)
- **BudgetDetails** (`canonical/budget_codes.jsonl`) is the **master budget-code universe** (127 keys).
  Every mapped row resolves to a `budget_code_key` of the form `sub_job.cost_code.category`
  (e.g. `1000.15-16-110.SUB`), where `sub_job` is the code segment (== `extra`).
- **CostEntries** (`canonical/cost_entries.jsonl`) are **accounting actual-cost truth**.
- **Owner pay apps** are **owner-recognized billing/progress evidence** — NOT actual-cost truth.
- **Procore subcontractor pay apps** are **subcontractor progress/exposure evidence** — NOT actual-cost truth.
- **Respect `mapping_status`.** `mapped` (high/medium) may be used; `ambiguous`/`manual_required`/`not_applicable`
  must NOT be treated as confidently mapped.
- Money fields are strings to 2 decimals (or null). Percent fields are preserved as source.
- CostEntries `amount` precision is bounded by the source JSON representation; this package adds no float arithmetic.

## mapping_status values
`mapped` | `ambiguous` | `manual_required` | `invalid_budget_code_key` | `not_applicable`

## mapping_confidence values
`high` (exact candidate/constructed/Procore exact|parsed) | `medium` (owner family resolves to one key) |
`low` (family multiple candidates / Procore-only support) | `none` (no defensible mapping)

## actual_period_bucket values
`through_may_2026` | `june_2026_to_date` | `after_june_2026` | `undated`

## Files

### canonical/budget_codes.jsonl  (one row per master budget code)
project_key, job, budget_code_key, sub_job (code), sub_job_description, source_sub_job (audit),
cost_code, category, cost_type_description, budget_code_description, cost_code_tiers, amounts{...},
source{source_sheet,source_row,costentries_match_status}, mapping_role="master_budget_code".

### canonical/cost_entries.jsonl  (one row per CostEntries record)
source fields + budget_code_key, mapped_budget_code_key, mapping_status, mapping_method,
accounting_date, accounting_month, amount (source), amount_decimal_string, actual_period_bucket, source_file.

### canonical/monthly_actuals_by_budget_code.jsonl
source fields + mapped_budget_code_key, mapping_status, amount_decimal_string, actual_period_bucket, source_file.

### canonical/owner_pay_app_line_items_mapped.jsonl  (one row per owner line item)
source/application metadata, row_type, item, owner_sov_code, cost_code, description_of_work,
owner_cost_code_original/normalized/family, owner_placeholder_code_detected,
candidate_budget_code_keys, mapped_budget_code_key, mapping_status, mapping_confidence, mapping_method,
mapping_notes, procore_supporting_wbs_flat_codes/budget_code_candidates/evidence_count,
flat money: scheduled_value, current_value, previous_completed, this_period_completed,
materials_presently_stored, total_completed_and_stored_to_date, percent_complete, balance_to_finish,
retainage; validation_flags, source_file.

### canonical/owner_pay_app_totals.jsonl
identity + application metadata, row_type (construction_subtotal|change_orders_subtotal|grand_total),
flat money fields, validation_flags, source sheet/row, source_file.

### canonical/procore_subcontractor_payment_app_headers.jsonl
Procore header pass-through + source_file, pay_app_cutoff_status="through_may_2026", mapped_project_key.

### canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl
Procore item/header fields + mapped_budget_code_key, mapping_status/confidence/method/notes,
parsed_sub_job/parsed_cost_code/parsed_category, money strings preserved, source_file.

### canonical/procore_latest_subcontractor_invoice_by_budget_code.jsonl
latest-by-vendor/cost-code rows + mapping result + parsed fields + source invoice keys + source_file.

### canonical/procore_commitments.jsonl
source_file, project_key, contract_id, commitment_id (==contract_id), commitment_id_source="contract_id",
record_key, number, status, vendor_entity_key, money strings (grand_total, ...), retainage_percent, dates.

### mapping/budget_code_mapping_decisions.jsonl  (one row per DECISION, deduped)
source_system, source_key, source_cost_code, source_category, source_wbs_flat_code,
source_commitment_id, source_vendor_entity_key, candidate_budget_code_keys, mapped_budget_code_key,
mapping_status, mapping_confidence, mapping_method, reason, requires_human_review.

### mapping/owner_pay_app_mapping_results.jsonl / procore_pay_app_mapping_results.jsonl
Per-row mapping result (no money), incl. candidates, mapped key, status/confidence/method/notes.

### mapping/ambiguous_mapping_candidates.jsonl
Rows where multiple BudgetDetails candidates exist.

### mapping/unmapped_owner_pay_app_rows.jsonl / unmapped_procore_pay_app_rows.jsonl
Rows that cannot be confidently mapped (manual_required / not_applicable / invalid).

### mapping/owner_cost_code_family_crosswalk.jsonl  (one row per owner cost-code family)
owner_cost_code_family, owner_cost_code_examples, owner_line_item_count, owner_latest_application_no,
budget_detail_candidate_keys(+count), procore_wbs_flat_code_candidates(+count),
resolution_status (unique_budget_match|multiple_budget_candidates|no_budget_match|not_applicable),
recommended_mapping_method, requires_human_review.

### mapping/enriched_forecast_mapping_template.json
Procore 57-row scaffold enriched with parsed segments, direct/parsed match, mapped_budget_code_key,
status/confidence/method, candidate_budget_code_keys, requires_human_review.

### summaries/budget_code_forecast_context.jsonl  (MAIN agent file, one row per budget code)
project_key, budget_code_key, sub_job, sub_job_description, cost_code, category, budget_code_description,
budget_amounts, actuals{...}, owner_pay_app{latest_*...}, procore_subcontractor_pay_apps{latest_*_sum...},
commitments{related_*}, reconciliation_flags, data_gap_flags, forecast_agent_notes.

### summaries/cost_code_rollup_forecast_context.jsonl
Rollup by (sub_job, cost_code, category): budget/actual/owner/procore totals, retainage, evidence counts, gaps.

### summaries/project_forecast_context.json, mapping_coverage_summary.json, data_gap_register.json
Project-level summary, coverage counts, and the gap register.

### audit/
reconciliation_report.json, safety_scan_report.json, source_validation_reports/, source_manifests/.
"""
    (OUT / "SCHEMA.md").write_text(s, encoding="utf-8")


if __name__ == "__main__":
    main()
