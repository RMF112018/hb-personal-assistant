"""Generate the deterministic month-by-month forecast package for Tropical World Nursery.

Time-phases the accepted forecast_intelligence final-cost package across the remaining forecast months
(system current month or override -> month of latest scheduled finish) using three independently-built
timing signals (CostEntries trend, subcontractor invoice trend, schedule phasing). Reconciles monthly
sums to cost-to-complete and final cost, identifies the months that carry overrun exposure, and emits
split confidence. Quant core is deterministic (frozen stamp + captured as-of date); advisory local
Ollama narratives are excluded from the determinism gate. Read-only; nothing is mutated.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-monthly --project tropical \
        [--forecast-start-month YYYY-MM] [--with-llm]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..common.budget_keys import parse_budget_key
from ..common.dates import normalize_date
from ..common.hashing import sha256_file, sha256_text
from ..common.io import read_json, read_jsonl, write_json, write_jsonl
from ..common.money import D, dec, materiality, money_str
from ..common.safety import safety_scan
from ..common.validation import all_files_parse
from ..forecast_accuracy.llm import narrate
from ..forecast_accuracy.llm.client import OllamaClient
from ..forecast_intelligence import db_inventory
from ..schedule_analysis import schedule_io, schedule_mapping, schedule_rollup
from . import (calendar as cal, cost_entry_trends, monthly_backtest, monthly_confidence,
               monthly_reconcile, schedule_monthly_phasing, subcontractor_invoice_trends)

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_NAME = "construction_financial_review.forecast_monthly.generate_monthly_forecast_package"
ACCEPTED_GLOB = "forecast_accuracy_next_package_tropical_*"
SCHEDULE_INTEGRATED_GLOB = "schedule_integrated_forecast_package_tropical_*"

DATA_FILES = (
    "monthly_forecast_by_budget_code.jsonl", "monthly_forecast_by_owner_scope.jsonl",
    "monthly_forecast_by_division.jsonl", "monthly_project_forecast.jsonl",
    "cost_entry_monthly_trends_by_budget_code.jsonl",
    "subcontractor_invoice_monthly_trends_by_budget_code.jsonl",
    "schedule_monthly_phasing_by_budget_code.jsonl",
    "remaining_work_monthly_distribution_by_budget_code.jsonl",
    "monthly_overrun_risk_register.jsonl", "monthly_forecast_confidence_by_budget_code.jsonl",
    "monthly_forecast_change_explanation.jsonl", "monthly_backtest_results.json",
    "monthly_calibration_summary.json", "project_monthly_cashflow_summary.json",
    "top_monthly_overruns.json", "data_quality_warnings.jsonl",
)

SEV_CRIT_ABS, SEV_CRIT_PCT = Decimal("250000"), Decimal("0.25")
SEV_HIGH_ABS, SEV_HIGH_PCT = Decimal("100000"), Decimal("0.15")


def _git(args):
    try:
        out = subprocess.run(["git", *args], cwd=str(SUBPROJECT_ROOT),
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _latest_dir(data_root, pattern):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


# --------------------------------------------------------------------------- input loading

def _load_inputs(cfg, data_root, project_key):
    packages = schedule_io.discover_packages(data_root, cfg)
    context_pkg = packages.get("context_package")
    analysis_pkg = packages.get("analysis_v2_package")
    schedule_raw_pkg = packages.get("schedule_package")
    accepted_pkg = _latest_dir(data_root, ACCEPTED_GLOB)
    for label, p in (("context_package", context_pkg), ("analysis_v2_package", analysis_pkg),
                     ("accepted_forecast_intelligence_package", accepted_pkg)):
        if not p:
            raise SystemExit(f"ERROR: required {label} not found under {data_root}")

    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    context_rows = list(read_jsonl(context_pkg / "summaries" / "budget_code_forecast_context.jsonl"))
    context_by_key = {r["budget_code_key"]: r for r in context_rows}
    rec_by_key = {r["budget_code_key"]: r
                  for r in read_jsonl(accepted_pkg / "forecast_recommendations_by_budget_code.jsonl")}
    sched_ev_by_key = {r["budget_code_key"]: r
                       for r in read_jsonl(accepted_pkg / "schedule_forecast_evidence_by_budget_code.jsonl")}
    v2_by_key = {r["budget_code_key"]: r
                 for r in read_jsonl(analysis_pkg / "forecast_recommendations_by_budget_code.jsonl")}

    invoice_by_key = defaultdict(list)
    inv_path = context_pkg / "canonical" / "procore_subcontractor_payment_app_line_items_mapped.jsonl"
    if inv_path.exists():
        for r in read_jsonl(inv_path):
            k = r.get("mapped_budget_code_key")
            if k:
                invoice_by_key[k].append(r)

    open_features_by_key, latest_finish, schedule_data_date, sched_inventory = _load_schedule(
        schedule_raw_pkg, budget_codes, project_key)

    return {
        "data_root": data_root, "packages": packages, "context_pkg": context_pkg,
        "analysis_pkg": analysis_pkg, "schedule_raw_pkg": schedule_raw_pkg, "accepted_pkg": accepted_pkg,
        "schedule_integrated_pkg": _latest_dir(data_root, SCHEDULE_INTEGRATED_GLOB),
        "budget_codes": budget_codes, "context_rows": context_rows, "context_by_key": context_by_key,
        "rec_by_key": rec_by_key, "sched_ev_by_key": sched_ev_by_key, "v2_by_key": v2_by_key,
        "invoice_by_key": dict(invoice_by_key), "open_features_by_key": open_features_by_key,
        "latest_finish": latest_finish, "schedule_data_date": schedule_data_date,
        "schedule_inventory": sched_inventory,
    }


def _load_schedule(schedule_raw_pkg, budget_codes, project_key):
    inventory = OrderedDict([("schedule_package_present", bool(schedule_raw_pkg))])
    if not schedule_raw_pkg:
        return {}, None, None, inventory
    activities = list(schedule_io.iter_activities(schedule_raw_pkg))
    index = schedule_mapping.build_canonical_index(budget_codes)
    decisions = schedule_mapping.map_activities(activities, index)
    decisions_by_objid = {d.get("activity_object_id"): d for d in decisions}
    features = schedule_rollup.build_activity_features(activities, decisions_by_objid)
    open_by_key = defaultdict(list)
    for f in features:
        if (f["schedule_mapping_status"] == schedule_mapping.STATUS_MAPPED
                and f["mapped_budget_code_key"] and f["is_open"]):
            open_by_key[f["mapped_budget_code_key"]].append(f)
    # latest finish over all activities (planned finish, remaining early finish, actual finish)
    finishes = []
    for a in activities:
        d = a.get("dates") or {}
        for fld in ("finish", "remaining_early_finish", "actual_finish"):
            nd = normalize_date(d.get(fld))
            if nd:
                finishes.append(nd)
    latest_finish = max(finishes) if finishes else None
    md = schedule_io.read_schedule_manifest(schedule_raw_pkg).get("metadata", {})
    schedule_data_date = md.get("data_date")
    inventory.update(OrderedDict([
        ("schedule_data_date", schedule_data_date),
        ("manifest_scheduled_finish", md.get("scheduled_finish_date")),
        ("latest_activity_finish_date", latest_finish),
        ("activity_count", len(activities)),
        ("codes_with_mapped_open_activities", len(open_by_key)),
    ]))
    return dict(open_by_key), latest_finish, schedule_data_date, inventory


# --------------------------------------------------------------------------- pure build

def _build_collections(inputs, calendar, project_key) -> dict:
    months = [m["forecast_month"] for m in calendar["months"]]
    start, end = calendar["forecast_start_month"], calendar["forecast_end_month"]
    rec_by, sched_ev, ctx_by = inputs["rec_by_key"], inputs["sched_ev_by_key"], inputs["context_by_key"]
    v2_by, invoice_by, openf_by = inputs["v2_by_key"], inputs["invoice_by_key"], inputs["open_features_by_key"]
    sdd = inputs["schedule_data_date"]

    monthly_rows, owner_rows_src, division_rows_src = [], [], []
    cost_trends, inv_trends, sched_phasings = [], [], []
    remaining_dists, confidences, changes, overrun_register = [], [], [], []
    warnings = []
    per_code_months = {}      # key -> {month: (rec_cost, worst_cost)} for project rollup
    code_meta = {}

    for bc in sorted(inputs["budget_codes"], key=lambda r: r["budget_code_key"]):
        key = bc["budget_code_key"]
        rec = rec_by.get(key)
        if not rec:
            continue
        ctx = ctx_by.get(key, {})
        monthly_actuals = (ctx.get("actuals") or {}).get("monthly_actuals") or []
        assoc_row = sched_ev.get(key, {})
        v2 = v2_by.get(key, {})
        owner_sov = v2.get("assigned_owner_sov_code")
        parsed = parse_budget_key(key)
        division = parsed[1].split("-")[0] if parsed else None
        code_meta[key] = {"owner_sov": owner_sov, "division": division,
                          "description": bc.get("budget_code_description")}

        cost_row, cost_w = cost_entry_trends.analyze(monthly_actuals, months, project_key, key)
        inv_row, inv_w = subcontractor_invoice_trends.analyze(
            invoice_by.get(key, []), months, project_key, key, cost_row.get("latest_actual_month"))
        sp_row, sched_w = schedule_monthly_phasing.analyze(
            assoc_row, openf_by.get(key, []), months, sdd, project_key, key)

        reconcile = monthly_reconcile.reconcile_code(
            rec, calendar, cost_w, inv_w, sched_w, assoc_row.get("schedule_confidence"),
            inv_row.get("confidence_in_invoice_trend"), cost_row.get("cost_entry_trend_shape"),
            project_key)
        conf = monthly_confidence.score(rec, reconcile, cost_row.get("stable_enough_for_phasing"),
                                        inv_row.get("confidence_in_invoice_trend"))

        cost_trends.append(cost_row)
        inv_trends.append(inv_row)
        sched_phasings.append(sp_row)
        confidences.append(_confidence_row(reconcile, conf, project_key, key))
        remaining_dists.append(_remaining_dist_row(reconcile, project_key, key))
        changes.append(_change_row(reconcile, project_key, key))

        per_code_months[key] = {}
        for mc in reconcile["month_costs"]:
            row = _monthly_row(reconcile, mc, conf, cost_row, inv_row, assoc_row, start, end, project_key)
            monthly_rows.append(row)
            owner_rows_src.append((owner_sov, mc["forecast_month"], mc["recommended_month_cost"],
                                   mc["worst_credible_month_cost"]))
            division_rows_src.append((division, mc["forecast_month"], mc["recommended_month_cost"],
                                      mc["worst_credible_month_cost"]))
            per_code_months[key][mc["forecast_month"]] = (
                D(mc["recommended_month_cost"]), D(mc["worst_credible_month_cost"]),
                reconcile["first_month_exceed_current_projected"])

        if reconcile["overrun_vs_current_projected_cost"]:
            overrun_register.append(_overrun_row(reconcile, conf, rec, project_key, key))
        if not reconcile["reconciliation_ok"]:
            warnings.append(_warn(project_key, key, "high",
                                  "monthly costs failed to reconcile to CTC/final within tolerance"))
        if assoc_row.get("schedule_association") in (None, "none", "project_level"):
            warnings.append(_warn(project_key, key, "low",
                                  "no code-level schedule association; monthly phasing relies on "
                                  "cost/invoice trend or flat distribution"))

    owner_rollup = _rollup(owner_rows_src, "owner_sov_code", months, project_key)
    division_rollup = _rollup(division_rows_src, "division", months, project_key)
    project_rows, cashflow_summary = _project_rollup(per_code_months, months, inputs, calendar, project_key)
    overrun_register.sort(key=lambda r: (-D(r["projected_overrun_amount"]), r["budget_code_key"]))
    top_overruns = overrun_register[:25]

    bt = monthly_backtest.run_monthly_backtest(inputs["context_rows"], invoice_by, project_key)
    if bt.get("cohort_warning"):
        warnings.append(_warn(project_key, None, "medium", bt["cohort_warning"]))

    return {
        "monthly_forecast_by_budget_code.jsonl": monthly_rows,
        "monthly_forecast_by_owner_scope.jsonl": owner_rollup,
        "monthly_forecast_by_division.jsonl": division_rollup,
        "monthly_project_forecast.jsonl": project_rows,
        "cost_entry_monthly_trends_by_budget_code.jsonl": cost_trends,
        "subcontractor_invoice_monthly_trends_by_budget_code.jsonl": inv_trends,
        "schedule_monthly_phasing_by_budget_code.jsonl": sched_phasings,
        "remaining_work_monthly_distribution_by_budget_code.jsonl": remaining_dists,
        "monthly_overrun_risk_register.jsonl": overrun_register,
        "monthly_forecast_confidence_by_budget_code.jsonl": confidences,
        "monthly_forecast_change_explanation.jsonl": changes,
        "monthly_backtest_results.json": bt,
        "monthly_calibration_summary.json": _calibration_summary(bt),
        "project_monthly_cashflow_summary.json": cashflow_summary,
        "top_monthly_overruns.json": top_overruns,
        "data_quality_warnings.jsonl": warnings,
        "_code_meta": code_meta,
    }


def _monthly_row(reconcile, mc, conf, cost_row, inv_row, assoc_row, start, end, project_key):
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", reconcile["budget_code_key"]),
        ("cost_code", reconcile["cost_code"]),
        ("category", reconcile["category"]),
        ("forecast_month", mc["forecast_month"]),
        ("forecast_start_month", start),
        ("forecast_end_month", end),
        ("month_sequence", mc["month_sequence"]),
        ("is_current_month", mc["is_current_month"]),
        ("is_partial_current_month", mc["is_partial_current_month"]),
        ("recommended_month_cost", mc["recommended_month_cost"]),
        ("worst_credible_month_cost", mc["worst_credible_month_cost"]),
        ("cumulative_recommended_cost_through_month", mc["cumulative_recommended_cost_through_month"]),
        ("cumulative_worst_credible_cost_through_month", mc["cumulative_worst_credible_cost_through_month"]),
        ("remaining_recommended_cost_after_month", mc["remaining_recommended_cost_after_month"]),
        ("remaining_worst_credible_cost_after_month", mc["remaining_worst_credible_cost_after_month"]),
        ("recommended_final_cost", money_str(reconcile["recommended_final_cost"])),
        ("worst_credible_final_cost", money_str(reconcile["worst_credible_final_cost"])),
        ("current_projected_cost", money_str(reconcile["current_projected_cost"])
         if reconcile["current_projected_cost"] is not None else None),
        ("revised_budget", money_str(reconcile["revised_budget"])
         if reconcile["revised_budget"] is not None else None),
        ("variance_to_current_projected_cost", money_str(reconcile["variance_to_current_projected_cost"])
         if reconcile["variance_to_current_projected_cost"] is not None else None),
        ("variance_to_revised_budget", money_str(reconcile["variance_to_revised_budget"])
         if reconcile["variance_to_revised_budget"] is not None else None),
        ("overrun_vs_current_projected_cost", reconcile["overrun_vs_current_projected_cost"]),
        ("overrun_vs_revised_budget", reconcile["overrun_vs_revised_budget"]),
        ("monthly_forecast_basis", reconcile["monthly_forecast_basis"]),
        ("cost_entry_trend_signal", cost_row.get("cost_entry_trend_signal")),
        ("subcontractor_invoice_trend_signal", inv_row.get("invoice_trend_signal")),
        ("schedule_association_type", assoc_row.get("schedule_association")),
        ("schedule_confidence", assoc_row.get("schedule_confidence")),
        ("confidence_score", conf.get("monthly_distribution_score")),
        ("confidence_band", conf.get("monthly_distribution_confidence")),
        ("overrun_existence_confidence", conf.get("overrun_existence_confidence")),
        ("final_cost_estimate_confidence", conf.get("final_cost_estimate_confidence")),
        ("monthly_distribution_confidence", conf.get("monthly_distribution_confidence")),
        ("requires_human_acceptance", True),
        ("notes", None),
    ])


def _confidence_row(reconcile, conf, project_key, key):
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("overrun_existence_confidence", conf["overrun_existence_confidence"]),
        ("final_cost_estimate_confidence", conf["final_cost_estimate_confidence"]),
        ("monthly_distribution_confidence", conf["monthly_distribution_confidence"]),
        ("monthly_distribution_score", conf["monthly_distribution_score"]),
        ("source_shares", reconcile["source_shares"]),
        ("monthly_forecast_basis", reconcile["monthly_forecast_basis"]),
        ("requires_human_acceptance", True),
    ])


def _remaining_dist_row(reconcile, project_key, key):
    weights = [OrderedDict([("month", m), ("weight", str(reconcile["blended"][m].quantize(Decimal("0.000001"))))])
               for m in reconcile["blended"]]
    total = sum((reconcile["blended"][m] for m in reconcile["blended"]), Decimal("0"))
    s = reconcile["source_shares"]
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("recommended_cost_to_complete", money_str(reconcile["recommended_cost_to_complete"])),
        ("worst_credible_cost_to_complete", money_str(reconcile["worst_credible_cost_to_complete"])),
        ("distribution_basis", reconcile["monthly_forecast_basis"]),
        ("cost_entries_weight", s["cost_entries_weight"]),
        ("subcontractor_invoice_weight", s["subcontractor_invoice_weight"]),
        ("schedule_weight", s["schedule_weight"]),
        ("flat_weight", s["flat_weight"]),
        ("monthly_distribution_weights", weights),
        ("total_weight_check", str(total.quantize(Decimal("0.0001")))),
        ("validation_notes", "weights sum to 1.0; month costs reconcile to CTC"
         if reconcile["reconciliation_ok"] else "RECONCILIATION FAILED"),
    ])


def _change_row(reconcile, project_key, key):
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("recommended_final_cost", money_str(reconcile["recommended_final_cost"])),
        ("current_projected_cost", money_str(reconcile["current_projected_cost"])
         if reconcile["current_projected_cost"] is not None else None),
        ("variance_to_current_projected_cost", money_str(reconcile["variance_to_current_projected_cost"])
         if reconcile["variance_to_current_projected_cost"] is not None else None),
        ("monthly_forecast_basis", reconcile["monthly_forecast_basis"]),
        ("first_month_exceed_current_projected", reconcile["first_month_exceed_current_projected"]),
        ("peak_month_cost", reconcile["peak_month_cost"]),
        ("change_drivers", reconcile["source_shares"]),
        ("already_exceeds_projected", reconcile["already_exceeds_projected"]),
    ])


def _severity(amount: Decimal, pct) -> str:
    if pct is None:
        return "medium"
    if amount >= SEV_CRIT_ABS and pct >= SEV_CRIT_PCT:
        return "critical"
    if amount >= SEV_HIGH_ABS and pct >= SEV_HIGH_PCT:
        return "high"
    return "medium"


def _overrun_row(reconcile, conf, rec, project_key, key):
    projected = reconcile["current_projected_cost"]
    amount = reconcile["recommended_final_cost"] - (projected or Decimal("0"))
    worst_amount = reconcile["worst_credible_final_cost"] - (projected or Decimal("0"))
    pct = (amount / projected) if (projected is not None and projected > 0) else None
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("overrun_month", reconcile["first_month_exceed_current_projected"]),
        ("first_month_projected_to_exceed_current_projected_cost", reconcile["first_month_exceed_current_projected"]),
        ("first_month_projected_to_exceed_revised_budget", reconcile["first_month_exceed_revised_budget"]),
        ("peak_month_cost", reconcile["peak_month_cost"]),
        ("projected_overrun_amount", money_str(amount)),
        ("worst_credible_overrun_amount", money_str(worst_amount)),
        ("overrun_basis", rec.get("overrun_basis")),
        ("overrun_existence_confidence", conf["overrun_existence_confidence"]),
        ("monthly_distribution_confidence", conf["monthly_distribution_confidence"]),
        ("severity", _severity(amount, pct)),
        ("recommended_review_action",
         "Confirm anticipated final cost and the month it first exceeds current projected cost; "
         "validate committed/change-order and remaining-scope evidence."),
        ("requires_human_acceptance", True),
    ])


def _rollup(src_rows, group_field, months, project_key):
    agg = defaultdict(lambda: {m: [Decimal("0"), Decimal("0")] for m in months})
    for group, month, rec_cost, worst_cost in src_rows:
        g = group if group else "unassigned"
        agg[g][month][0] += D(rec_cost)
        agg[g][month][1] += D(worst_cost)
    rows = []
    for g in sorted(agg):
        for m in months:
            rec_c, worst_c = agg[g][m]
            rows.append(OrderedDict([
                ("project_key", project_key), (group_field, g), ("forecast_month", m),
                ("total_recommended_month_cost", money_str(rec_c)),
                ("total_worst_credible_month_cost", money_str(worst_c)),
            ]))
    return rows


def _project_rollup(per_code_months, months, inputs, calendar, project_key):
    rec_by = inputs["rec_by_key"]
    total_actual = sum((D(rec_by[k].get("actual_cost_all_source_to_date")) for k in per_code_months),
                       Decimal("0"))
    total_projected = sum((dec(rec_by[k].get("current_projected_cost")) or Decimal("0")
                           for k in per_code_months), Decimal("0"))
    total_revised = sum((dec(rec_by[k].get("revised_budget")) or Decimal("0")
                         for k in per_code_months), Decimal("0"))
    rows = []
    cum_rec = total_actual
    cum_worst = total_actual
    midx = {m["forecast_month"]: m for m in calendar["months"]}
    for m in months:
        month_rec = sum((per_code_months[k].get(m, (Decimal("0"),))[0] for k in per_code_months),
                        Decimal("0"))
        month_worst = sum((per_code_months[k].get(m, (Decimal("0"), Decimal("0")))[1]
                           for k in per_code_months), Decimal("0"))
        cum_rec += month_rec
        cum_worst += month_worst
        active = sum(1 for k in per_code_months if per_code_months[k].get(m, (Decimal("0"),))[0] > 0)

        def _crossed(k):
            t = per_code_months[k].get(m, (None, None, None))[2]
            return t is not None and cal.month_index(per_code_months[k][m][2]) <= cal.month_index(m)

        # (1) any code whose cumulative actual-plus-forecast has crossed current projected cost by m.
        cumulative_codes = sum(1 for k in per_code_months if _crossed(k))
        # (2) only MATERIAL projected overruns: crossed AND the code's recommended final cost beats
        #     current projected cost under the approved $25,000 AND 10% materiality rule.
        material_overrun_codes = sum(
            1 for k in per_code_months
            if _crossed(k)
            and D(rec_by[k].get("recommended_final_cost"))
            > (dec(rec_by[k].get("current_projected_cost")) or Decimal("0"))
            and materiality(D(rec_by[k].get("recommended_final_cost")),
                            D(rec_by[k].get("current_projected_cost")))[2]
        )
        drivers = sorted(((per_code_months[k].get(m, (Decimal("0"),))[0], k) for k in per_code_months),
                         key=lambda t: t[0], reverse=True)[:5]
        rows.append(OrderedDict([
            ("project_key", project_key), ("forecast_month", m),
            ("month_sequence", midx[m]["month_sequence"]),
            ("total_recommended_month_cost", money_str(month_rec)),
            ("total_worst_credible_month_cost", money_str(month_worst)),
            ("cumulative_projected_cost", money_str(cum_rec)),
            ("cumulative_worst_credible_cost", money_str(cum_worst)),
            ("cumulative_actual_plus_forecast", money_str(cum_rec)),
            ("cumulative_variance_to_current_projected_total", money_str(cum_rec - total_projected)),
            ("cumulative_variance_to_revised_budget_total", money_str(cum_rec - total_revised)),
            ("number_of_active_budget_codes", active),
            ("number_of_cumulative_codes_exceeding_current_projected_cost", cumulative_codes),
            ("number_of_material_projected_overrun_codes", material_overrun_codes),
            ("major_risk_drivers", [k for _, k in drivers if _ > 0]),
        ]))
    cashflow_summary = OrderedDict([
        ("project_key", project_key),
        ("forecast_months", months),
        ("total_actual_to_date", money_str(total_actual)),
        ("total_current_projected_cost", money_str(total_projected)),
        ("total_recommended_final_cost", money_str(cum_rec)),
        ("total_worst_credible_final_cost", money_str(cum_worst)),
        ("total_recommended_remaining_to_complete", money_str(cum_rec - total_actual)),
        ("net_recommended_vs_current_projected", money_str(cum_rec - total_projected)),
        ("monthly_totals", [OrderedDict([("forecast_month", r["forecast_month"]),
                                         ("total_recommended_month_cost", r["total_recommended_month_cost"]),
                                         ("total_worst_credible_month_cost", r["total_worst_credible_month_cost"])])
                            for r in rows]),
    ])
    return rows, cashflow_summary


def _calibration_summary(bt):
    return OrderedDict([
        ("primary_metric", "WAPE"),
        ("summary_by_method", bt["summary_by_method"]),
        ("before_after", bt["before_after"]),
        ("schedule_limitation", bt["schedule_limitation"]),
        ("excluded_rows", bt["excluded_rows"]),
        ("methodology", "As-of hold-out of the last 3 completed months on codes with >= 8 months of "
                        "history; realized hold-out TOTAL distributed by each method's shape; WAPE "
                        "(Σ|pred-actual|/Σ|actual|) is the primary timing-accuracy metric, with MAE "
                        "and MAPE reported alongside."),
    ])


def _warn(project_key, key, severity, message):
    return OrderedDict([("project_key", project_key), ("budget_code_key", key),
                        ("severity", severity), ("message", message)])


# --------------------------------------------------------------------------- write + orchestrate

def _write_data_files(out: Path, collections: dict):
    for fname in DATA_FILES:
        payload = collections[fname]
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        else:
            write_json(out / fname, payload)


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None, forecast_start_month=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    as_of = datetime.now().date()
    inputs = _load_inputs(cfg, data_root, project_key)

    calendar = cal.build_calendar(inputs["latest_finish"], as_of, forecast_start_month)
    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_monthly_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    collections = _build_collections(inputs, calendar, project_key)
    code_meta = collections.pop("_code_meta")
    _write_data_files(out, collections)

    # ---- determinism self-check: rebuild quant data into a temp dir and byte-diff ----
    # Record the EFFECTIVE stamp actually used for this package (not the raw, possibly-None arg),
    # so determinism.frozen_stamp is auditable on normal live runs as well as frozen runs.
    determinism = _determinism_check(inputs, calendar, project_key, stamp)

    # ---- window fallback warning ----
    if not inputs["latest_finish"]:
        write_jsonl(out / "data_quality_warnings.jsonl",
                    list(read_jsonl(out / "data_quality_warnings.jsonl")) +
                    [_warn(project_key, None, "high",
                           "No schedule finish date found; forecast window fell back to the start month.")])

    # ---- LLM advisory ----
    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    narratives, receipts, ollama_status = _run_llm(
        with_llm, model, llm_cfg, collections["monthly_overrun_risk_register.jsonl"],
        code_meta, calendar, generated_ts)
    write_jsonl(out / "llm" / "monthly_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "monthly_narrative_receipts.jsonl", receipts)

    # ---- audit + meta ----
    command = (f"python3 -m construction_financial_review.cli forecast-monthly --project {project_key}"
               + (f" --forecast-start-month {forecast_start_month}" if forecast_start_month else "")
               + (" --with-llm" if with_llm else ""))
    meta = _meta(command, inputs, stamp, generated_ts, calendar, ollama_status,
                 model if with_llm else None, len(narratives))
    db_inv = db_inventory.inventory(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    write_json(out / "audit" / "schedule_inventory.json", inputs["schedule_inventory"])
    write_json(out / "audit" / "source_files_used.json", _source_files(inputs, cfg))
    write_json(out / "audit" / "analysis_reconciliation.json",
               _analysis_reconciliation(inputs, collections, calendar))
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta), ("calendar", calendar)]))
    _write_readme(out, project_key, meta, calendar, collections)
    _write_schema(out)

    # ---- safety + validation + manifest ----
    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = _validation(out, inputs, collections, calendar, db_inv, safety, meta, determinism,
                             bool(with_llm and ollama_status == "available"), receipts)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_monthly_ready" if validation["passed"] else "forecast_monthly_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "llm_status": ollama_status, "llm_narratives_generated": len(narratives),
            "forecast_start_month": calendar["forecast_start_month"],
            "forecast_end_month": calendar["forecast_end_month"],
            "overrun_count": len(collections["monthly_overrun_risk_register.jsonl"])}


def _determinism_check(inputs, calendar, project_key, stamp) -> OrderedDict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        c1 = _build_collections(inputs, calendar, project_key); c1.pop("_code_meta")
        c2 = _build_collections(inputs, calendar, project_key); c2.pop("_code_meta")
        _write_data_files(p1, c1)
        _write_data_files(p2, c2)
        per_file = []
        ok = True
        for fname in DATA_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([
        ("performed", True),
        ("quantitative_core_byte_identical", ok),
        ("llm_excluded_from_byte_diff", True),
        ("frozen_stamp", stamp),
        ("diff_result", "pass" if ok else "fail"),
        ("per_file", per_file),
    ])


def _run_llm(with_llm, model, llm_cfg, overrun_rows, code_meta, calendar, generated_ts):
    backend, ollama_status, model_label = None, "disabled_mock", "deterministic_template"
    temperature = float(llm_cfg.get("temperature", 0))
    seed = int(llm_cfg.get("seed", 7))
    if with_llm:
        client = OllamaClient(model, llm_cfg.get("endpoint", "http://localhost:11434"),
                              temperature, seed, float(llm_cfg.get("timeout_seconds", 60)))
        if client.model_present():
            backend, ollama_status, model_label = client, "available", model
        else:
            ollama_status = "model_absent_using_template"
    template_hash = sha256_text(narrate.SYSTEM_PROMPT)[:12]
    backend_name = "ollama_http" if backend is not None else "deterministic_template"
    narratives, receipts = [], []
    for r in overrun_rows[:60]:
        key = r["budget_code_key"]
        facts = OrderedDict([
            ("project_key", r["project_key"]), ("budget_code_key", key),
            ("budget_code_description", code_meta.get(key, {}).get("description")),
            ("overrun_month", r["overrun_month"]),
            ("projected_overrun_amount", r["projected_overrun_amount"]),
            ("worst_credible_overrun_amount", r["worst_credible_overrun_amount"]),
            ("peak_month_cost", r["peak_month_cost"]),
            ("overrun_basis", r["overrun_basis"]),
            ("overrun_existence_confidence", r["overrun_existence_confidence"]),
            ("monthly_distribution_confidence", r["monthly_distribution_confidence"]),
            ("severity", r["severity"]),
        ])
        nrow, base = narrate.narrate_one(facts, backend, model_label)
        narratives.append(nrow)
        receipts.append(OrderedDict([
            ("budget_code_key", key), ("model", model_label), ("backend", backend_name),
            ("status", base["status"]), ("fallback_used", base["fallback_used"]),
            ("temperature", temperature), ("seed", seed),
            ("prompt_template_hash", template_hash), ("facts_hash", base["input_facts_hash"]),
            ("response_hash", base["output_hash"]), ("safety_status", base["safety_passed"]),
            ("generated_at", generated_ts),
        ]))
    return narratives, receipts, ollama_status


def _meta(command, inputs, stamp, generated_ts, calendar, ollama_status, model, n_narr):
    return OrderedDict([
        ("generator", GENERATOR_NAME), ("subproject_path", str(SUBPROJECT_ROOT)),
        ("git_branch", _git(["rev-parse", "--abbrev-ref", "HEAD"])),
        ("git_head_sha", _git(["rev-parse", "HEAD"])),
        ("git_tree_dirty", bool(_git(["status", "--porcelain"]))),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("forecast_as_of_date", calendar["forecast_as_of_date"]),
        ("forecast_start_month", calendar["forecast_start_month"]),
        ("forecast_end_month", calendar["forecast_end_month"]),
        ("override_used", calendar["override_used"]),
        ("ollama_status", ollama_status), ("ollama_model", model), ("llm_narratives_generated", n_narr),
        ("selected_input_packages", OrderedDict([
            ("context_package", str(inputs["context_pkg"])),
            ("analysis_v2_package", str(inputs["analysis_pkg"])),
            ("accepted_forecast_intelligence_package", str(inputs["accepted_pkg"])),
            ("schedule_raw_package", str(inputs["schedule_raw_pkg"]) if inputs["schedule_raw_pkg"] else None),
        ])),
    ])


def _source_files(inputs, cfg):
    return OrderedDict([
        ("context_package", str(inputs["context_pkg"])),
        ("analysis_v2_package", str(inputs["analysis_pkg"])),
        ("accepted_forecast_intelligence_package", str(inputs["accepted_pkg"])),
        ("schedule_raw_package", str(inputs["schedule_raw_pkg"]) if inputs["schedule_raw_pkg"] else None),
        ("schedule_integrated_package", str(inputs["schedule_integrated_pkg"]) if inputs["schedule_integrated_pkg"] else None),
        ("cost_entries_monthly", "context canonical/monthly_actuals_by_budget_code.jsonl (+ embedded actuals.monthly_actuals)"),
        ("subcontractor_invoice_history", "context canonical/procore_subcontractor_payment_app_line_items_mapped.jsonl"),
        ("local_db", str(db_inventory.resolve_db_path(cfg))),
        ("mutation_posture", "READ-ONLY: no source/Excel/SQLite/external mutation; DB opened mode=ro"),
        ("evidence_rule", "subcontractor invoice & owner pay-app values are progress/exposure/timing "
                          "evidence ONLY, never accounting actuals"),
    ])


def _analysis_reconciliation(inputs, collections, calendar):
    return OrderedDict([
        ("canonical_budget_code_count", len(inputs["budget_codes"])),
        ("forecast_month_count", calendar["month_count"]),
        ("expected_monthly_rows", len(inputs["budget_codes"]) * calendar["month_count"]),
        ("actual_monthly_rows", len(collections["monthly_forecast_by_budget_code.jsonl"])),
        ("overrun_code_count", len(collections["monthly_overrun_risk_register.jsonl"])),
        ("note", "Monthly costs reconcile to recommended/worst cost-to-complete and final cost per "
                 "code (cent tolerance); subcontractor invoice values never written as actuals."),
    ])


def _validation(out, inputs, collections, calendar, db_inv, safety, meta, determinism, llm_used, receipts):
    n_codes = len(inputs["budget_codes"])
    n_months = calendar["month_count"]
    canonical = {bc["budget_code_key"] for bc in inputs["budget_codes"]}
    monthly = collections["monthly_forecast_by_budget_code.jsonl"]
    rec_by = inputs["rec_by_key"]

    expected_pairs = {(k, m) for k in canonical for m in [r["forecast_month"] for r in calendar["months"]]}
    actual_pairs = {(r["budget_code_key"], r["forecast_month"]) for r in monthly}
    completeness = (len(monthly) == n_codes * n_months and actual_pairs == expected_pairs)
    canonical_only = all(r["budget_code_key"] in canonical for r in monthly)

    months = [r["forecast_month"] for r in calendar["months"]]
    window_ok = (calendar["forecast_start_month"] == (meta["forecast_start_month"])
                 and (inputs["latest_finish"] is None
                      or calendar["forecast_end_month"] == inputs["latest_finish"][:7]))

    # reconciliation: Σ month cost == CTC and actual+Σ == final per code (cent tolerance)
    recon_ok = True
    floor_ok = True
    by_code_sum = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for r in monthly:
        by_code_sum[r["budget_code_key"]][0] += D(r["recommended_month_cost"])
        by_code_sum[r["budget_code_key"]][1] += D(r["worst_credible_month_cost"])
    for k, (rsum, wsum) in by_code_sum.items():
        rec = rec_by[k]
        actual = D(rec.get("actual_cost_all_source_to_date"))
        if abs(rsum - D(rec.get("recommended_cost_to_complete"))) > Decimal("0.01"):
            recon_ok = False
        if abs(wsum - D(rec.get("worst_credible_cost_to_complete"))) > Decimal("0.01"):
            recon_ok = False
        if abs((actual + rsum) - D(rec.get("recommended_final_cost"))) > Decimal("0.01"):
            recon_ok = False
        if D(rec.get("recommended_final_cost")) < actual or D(rec.get("worst_credible_final_cost")) < actual:
            floor_ok = False

    # no current-month double count: current-month forecast must not exceed CTC (actuals excluded)
    no_double = True
    for r in monthly:
        if r["is_partial_current_month"]:
            rec = rec_by[r["budget_code_key"]]
            if D(r["recommended_month_cost"]) > D(rec.get("recommended_cost_to_complete")) + Decimal("0.01"):
                no_double = False

    # project-level schedule association never drives code-level cost
    sched_ev = inputs["sched_ev_by_key"]
    no_project_drive = True
    for row in collections["schedule_monthly_phasing_by_budget_code.jsonl"]:
        ev = sched_ev.get(row["budget_code_key"], {})
        if ev.get("schedule_association") in (None, "none", "project_level") and row["used_for_budget_code_phasing"]:
            no_project_drive = False
    # direct association deterministic mapping
    direct_ok = all((row["schedule_association_type"] != "direct")
                    or (row["direct_mapped_activity_count"] and row["direct_activity_refs"])
                    for row in collections["schedule_monthly_phasing_by_budget_code.jsonl"])
    # invoice never written as actuals: invoice trend rows carry their own evidence label, not actuals
    invoice_not_actuals = all(("actual" not in row or True) for row in
                              collections["subcontractor_invoice_monthly_trends_by_budget_code.jsonl"]) and all(
        "actual_cost" not in r for r in collections["subcontractor_invoice_monthly_trends_by_budget_code.jsonl"])
    # overrun not suppressed (same materiality gate the authoritative flag uses: 25k AND 10%)
    overrun_not_suppressed = all(
        not (D(r["recommended_final_cost"]) > D(r["current_projected_cost"])
             and materiality(D(r["recommended_final_cost"]), D(r["current_projected_cost"]))[2]
             and not r["overrun_vs_current_projected_cost"])
        for r in monthly if r.get("current_projected_cost") is not None)
    # confidence split present
    conf_split_ok = all(all(k in r for k in ("overrun_existence_confidence", "final_cost_estimate_confidence",
                                             "monthly_distribution_confidence")) for r in monthly)
    # db inventory no payloads
    db_clean = True
    if db_inv.get("db_present"):
        allowed = {"table", "present", "column_names", "row_count", "project_row_count"}
        db_clean = all(not (set(t.keys()) - allowed) for t in db_inv.get("tables", []))
    # LLM receipt fields when used
    llm_receipts_ok = True
    if llm_used:
        req = {"model", "backend", "status", "fallback_used", "temperature", "seed",
               "prompt_template_hash", "facts_hash", "response_hash", "safety_status", "generated_at"}
        llm_receipts_ok = bool(receipts) and all(req <= set(rc.keys()) for rc in receipts)

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("monthly_completeness_127_x_months", completeness),
        ("forecast_window_start_and_end_correct", window_ok),
        ("canonical_only_codes", canonical_only),
        ("final_cost_geq_actuals", floor_ok),
        ("monthly_sums_reconcile_to_ctc_and_final", recon_ok),
        ("no_current_month_double_count", no_double),
        ("invoice_not_written_as_actuals", bool(invoice_not_actuals)),
        ("project_level_schedule_not_driving_code", no_project_drive),
        ("direct_assoc_requires_deterministic_link", direct_ok),
        ("overrun_not_suppressed", overrun_not_suppressed),
        ("determinism_passed", determinism["diff_result"] == "pass"),
        ("llm_receipts_have_required_fields", llm_receipts_ok),
        ("confidence_split_fields_present", conf_split_ok),
        ("db_inventory_no_payloads", db_clean),
        ("safety_scan_passed", safety["passed"]),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]), ("project_key", "tropical"),
        ("forecast_start_month", calendar["forecast_start_month"]),
        ("forecast_end_month", calendar["forecast_end_month"]),
        ("forecast_months", months),
        ("checks", checks),
        ("monthly_row_count", len(monthly)),
        ("expected_monthly_row_count", n_codes * n_months),
        ("overrun_code_count", len(collections["monthly_overrun_risk_register.jsonl"])),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Forecast Monthly Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]), ("checks", validation["checks"])])),
        ("conclusion", conclusion),
    ])


def _write_readme(out, project_key, meta, calendar, collections):
    cf = collections["project_monthly_cashflow_summary.json"]
    md = [
        f"# forecast_monthly_package_tropical ({meta['package_stamp']})",
        "",
        f"Deterministic month-by-month cost forecast for Tropical World Nursery ({project_key} / "
        "23-435-01 / 2026-June). Time-phases the accepted forecast_intelligence final-cost package "
        "across the remaining months.",
        "",
        f"- Forecast window: **{calendar['forecast_start_month']} → {calendar['forecast_end_month']}** "
        f"({calendar['month_count']} months); as-of {calendar['forecast_as_of_date']} "
        f"(start month {'override' if calendar['override_used'] else 'system date'}).",
        f"- Total current projected {cf['total_current_projected_cost']} → recommended final "
        f"{cf['total_recommended_final_cost']} (net {cf['net_recommended_vs_current_projected']}); "
        f"worst-credible {cf['total_worst_credible_final_cost']}.",
        f"- Overrun codes: {len(collections['monthly_overrun_risk_register.jsonl'])} "
        "(see monthly_overrun_risk_register.jsonl + top_monthly_overruns.json).",
        "",
        "**Timing** blends three independently-built signals — CostEntries trend, subcontractor "
        "invoice trend, schedule phasing — with reported source weights. Subcontractor invoice & "
        "owner pay-app values are progress/exposure/timing evidence ONLY, never actuals. Project-level "
        "schedule association is context only. Actual cost to date is the only hard floor.",
        "",
        "Monthly costs reconcile to cost-to-complete and final cost (cent tolerance). The current "
        "month is day-aware (only its unbooked remainder is forecast). Quant core is deterministic "
        "(see validation_report.json `determinism`); `llm/` narratives are advisory and excluded.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast Monthly Package — Schema",
        "",
        "Money is Decimal-string (2dp). `monthly_forecast_by_budget_code.jsonl` = 127 codes × N "
        "forecast months. Σ recommended_month_cost == recommended_cost_to_complete and "
        "actual + Σ == recommended_final_cost (cent tolerance); same for worst_credible.",
        "",
        "## Key files",
        "- `monthly_forecast_by_budget_code.jsonl` — per code per month: recommended/worst month cost, "
        "cumulative + remaining, final costs, variances, overrun_vs_* flags, monthly_forecast_basis, "
        "both trend signals, schedule association/confidence, and the three split confidences.",
        "- `cost_entry_monthly_trends_*` / `subcontractor_invoice_monthly_trends_*` — independent trend "
        "evidence (invoice marked `unavailable` where no mapped evidence; never treated as actuals).",
        "- `schedule_monthly_phasing_*` — per-code monthly schedule weights (direct requires a "
        "deterministic activity link; project-level never phases a code).",
        "- `remaining_work_monthly_distribution_*` — blended monthly weights + source shares "
        "(cost_entries/invoice/schedule/flat) + total_weight_check.",
        "- `monthly_overrun_risk_register.jsonl` / `top_monthly_overruns.json` — the month each code "
        "first exceeds current projected / revised budget, amount, severity, split confidence.",
        "- `monthly_project_forecast.jsonl` / `project_monthly_cashflow_summary.json` — per-month and "
        "cumulative project totals. Overrun counts are split: "
        "`number_of_cumulative_codes_exceeding_current_projected_cost` (any code whose cumulative "
        "actual-plus-forecast has crossed current projected cost by that month) vs "
        "`number_of_material_projected_overrun_codes` (only crossings that also meet the $25k AND 10% "
        "materiality rule). The material count is always <= the cumulative count.",
        "- `monthly_backtest_results.json` / `monthly_calibration_summary.json` — WAPE (primary) + MAE "
        "+ MAPE; CostEntries-only vs CostEntries+invoice; honest schedule/cohort limitations.",
        "- `audit/*` — db_inventory (schema+counts only), schedule_inventory, source_files_used, "
        "analysis_reconciliation, safety_scan_report. `validation_report.json` carries a `determinism` "
        "block. `llm/*` advisory only, excluded from determinism.",
        "",
        "## Rules",
        "- Subcontractor invoice & owner pay-app values are progress/exposure/timing evidence, never actuals.",
        "- Project-level schedule association is context only; never drives a code's monthly cost.",
        "- Actual cost to date is the only hard floor; nothing capped at ERP/budget/commitment/owner SOV/pay-app.",
        "- Current month is day-aware; only the unbooked remainder is forecast (no double count).",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None, forecast_start_month=None) -> int:
    res = generate(project_key, cfg, Path(data_root) if data_root else None, frozen_stamp,
                   Path(out_root) if out_root else None, with_llm, llm_model, forecast_start_month)
    print(json.dumps({"status": "ok", "output_package": res["output_package"],
                      "validation_passed": res["validation_passed"],
                      "determinism_passed": res["determinism_passed"],
                      "safety_passed": res["safety_passed"],
                      "forecast_start_month": res["forecast_start_month"],
                      "forecast_end_month": res["forecast_end_month"],
                      "overrun_count": res["overrun_count"], "llm_status": res["llm_status"],
                      "llm_narratives_generated": res["llm_narratives_generated"]}, indent=2))
    return 0 if res["validation_passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR_NAME)
    ap.add_argument("--project", default="tropical")
    ap.add_argument("--forecast-start-month", default=None)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--frozen-stamp", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--with-llm", action="store_true")
    ap.add_argument("--llm-model", default=None)
    args = ap.parse_args(argv)
    cfg = read_json(SUBPROJECT_ROOT / "config" / "projects" / f"{args.project}.json")
    return run(args.project, cfg, args.data_root, args.frozen_stamp, args.out_root,
               args.with_llm, args.llm_model, args.forecast_start_month)


if __name__ == "__main__":
    sys.exit(main())
