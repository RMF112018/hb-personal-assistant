"""Construction Financial Review CLI (stdlib argparse; no third-party deps).

Run without installation via:
    PYTHONPATH=src python3 -m construction_financial_review.cli <command> --project tropical

Commands:
    validate-crosswalk    Fully wired — validates the authoritative owner SOV scope crosswalk.
    run-context           Tropical-only — runs the forecast context package generator.
    run-analysis          Tropical-only — runs the forecast analysis package generator (v1).
    run-mapping-workpaper Tropical-only — runs the mapping-discrepancy workpaper generator.
    run-crosswalk-v2      Tropical-only — runs the crosswalk-aware analysis v2 generator.
    schedule-integrate-forecast
                          Config-driven — runs the schedule-integrated forecast generator. Discovers
                          the latest schedule / context / crosswalk-v2 / workpaper packages from the
                          project config + data root and writes one new timestamped output package.

The run-* commands shell out to the verbatim, validated generators, which currently carry hardcoded
Tropical/2026-June paths. They fail clearly for any non-tropical project until the generators are
parameterized (deferred work). schedule-integrate-forecast is import-dispatched and config-driven.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .common.io import read_json
from .mapping import validate_owner_sov_scope_crosswalk as xwval

SUBPROJECT_ROOT = Path(__file__).resolve().parents[2]   # .../construction-financial-review
CONFIG_PROJECTS = SUBPROJECT_ROOT / "config" / "projects"

# Generator module file (relative to this package) per run-* command.
GENERATORS = {
    "run-context": Path(__file__).parent / "context" / "generate_forecast_context_package.py",
    "run-analysis": Path(__file__).parent / "analysis" / "generate_forecast_analysis_package.py",
    "run-mapping-workpaper": Path(__file__).parent / "mapping" / "generate_mapping_discrepancy_workpaper.py",
    "run-crosswalk-v2": Path(__file__).parent / "analysis" / "generate_forecast_analysis_crosswalk_v2.py",
}


def load_project(project: str) -> dict:
    cfg = CONFIG_PROJECTS / f"{project}.json"
    if not cfg.exists():
        raise SystemExit(f"ERROR: no project config at {cfg}")
    return read_json(cfg)


def _resolve_crosswalk(cfg: dict) -> Path:
    rel = cfg.get("owner_sov_scope_crosswalk")
    if not rel:
        raise SystemExit("ERROR: project config missing 'owner_sov_scope_crosswalk'")
    p = (SUBPROJECT_ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
    if not p.exists():
        raise SystemExit(f"ERROR: crosswalk not found at {p}")
    return p


def _resolve_context_package(cfg: dict):
    root = cfg.get("default_data_root")
    pkg = cfg.get("forecast_context_package")
    if root and pkg:
        cp = Path(root) / pkg
        if cp.exists():
            return cp
    return None


def cmd_validate_crosswalk(cfg: dict) -> int:
    crosswalk = _resolve_crosswalk(cfg)
    context_pkg = _resolve_context_package(cfg)
    canonical, procore = xwval._load_universes(str(context_pkg) if context_pkg else None)
    report = xwval.validate(crosswalk, canonical, procore)
    report["project_key"] = cfg.get("project_key")
    report["context_package_used_for_coverage"] = str(context_pkg) if context_pkg else None
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


def cmd_schedule_integrate_forecast(cfg: dict, project: str, data_root, frozen_stamp, out_root) -> int:
    """Config-driven schedule-integrated forecast generator (import dispatch)."""
    from .schedule_analysis import generate_schedule_integrated_forecast as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root)


def cmd_forecast_accuracy(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                          with_llm, llm_model) -> int:
    """Config-driven forecast-accuracy generator (independent EAC models + calibrated confidence
    + backtest + optional advisory local-Ollama narratives). Import dispatch."""
    from .forecast_accuracy import generate_forecast_accuracy_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_intelligence(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                              with_llm, llm_model) -> int:
    """Config-driven next-gen forecast-intelligence generator (uncapped anticipated final cost +
    overrun detection + schedule/trend evidence + stronger backtest + optional advisory local-Ollama
    narratives). Import dispatch."""
    from .forecast_intelligence import generate_forecast_intelligence_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_monthly(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                         with_llm, llm_model, forecast_start_month) -> int:
    """Config-driven month-by-month forecast generator: time-phases the accepted forecast-intelligence
    final-cost package across the remaining forecast months using CostEntries + subcontractor-invoice
    trend evidence and schedule remaining-work phasing. Import dispatch."""
    from .forecast_monthly import generate_monthly_forecast_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, forecast_start_month=forecast_start_month)


def cmd_forecast_probability(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                             with_llm, llm_model, forecast_start_month, runs, seed) -> int:
    """Probabilistic VALIDATION of the accepted deterministic forecast (numpy/scipy Monte Carlo:
    per-code lognormal cost-to-complete + one-factor correlation; P10..P95, overrun probabilities,
    downside drivers, monthly risk, sensitivity, dispersion calibration). Advisory; never caps above
    references; actuals-only floor. Import dispatch."""
    from .forecast_probability import generate_probabilistic_validation_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, forecast_start_month=forecast_start_month,
                   runs=runs, seed=seed)


def cmd_forecast_history_informed(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                                  with_llm, llm_model) -> int:
    """Additive historical-forecast-assumption evidence: mines prior cash-flow + GC/GR forecasts,
    validates each against CostEntries actuals, and surfaces ADVISORY recommendations, confidence/
    uncertainty shifts and monthly-shape signals. Never mutates accepted packages; history is evidence,
    not actuals, not caps. Import dispatch."""
    from .forecast_history_informed import generate_forecast_history_informed_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_cost_frequency(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                                with_llm, llm_model) -> int:
    """Config-driven cost-frequency / billing-cadence evidence generator: classifies each canonical
    code's incurrence cadence from CostEntries, recognizes weekly internal-staffing codes with
    weekday-normalized daily rates, revalidates cadence, and emits ADVISORY monthly phasing (timing
    only; never changes accepted final cost). Import dispatch."""
    from .forecast_cost_frequency import generate_forecast_cost_frequency_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_comprehensive(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                               with_llm, llm_model) -> int:
    """Integrated forecast model layer: discovers + consumes all accepted evidence packages (context,
    intelligence, monthly, probability, history-informed, cost-frequency, crosswalk-v2, schedule-
    integrated) into a per-code evidence registry, scores advisory evidence at bounded de-duplicated
    weights, and emits integrated final-cost / monthly / probability recommendations with lineage, an
    evidence-conflict register, and a human-acceptance review queue. Never mutates a package. Import
    dispatch."""
    from .forecast_comprehensive import generate_comprehensive_forecast_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_improvement_audit(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                                   with_llm, llm_model) -> int:
    """Additive forecast improvement-audit: validates the seven forecasting-priority improvements
    against repo + data truth and implements each only where the available JSON packages / SQLite
    tables support it (BOE + coverage, calibration enhancements, actual-cost lag diagnostics, schedule
    cost-loading readiness, GC/GR behavior + fee projected-budget cap, change-order exposure). Read-only
    against source data; advisory; never mutates accepted packages or the DB. Import dispatch."""
    from .forecast_improvement_audit import generate_forecast_improvement_audit_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_run_generator(command: str, project: str) -> int:
    if project != "tropical":
        print(json.dumps({
            "command": command, "project": project, "status": "not_supported",
            "reason": "Generators are not yet parameterized; only project 'tropical' is supported. "
                      "Parameterization is deferred work (see docs/decisions).",
        }, indent=2))
        return 2
    script = GENERATORS[command]
    if not script.exists():
        raise SystemExit(f"ERROR: generator not found at {script}")
    print(f"[cfr] START {command} (tropical) -> {script.name}")
    print("[cfr] writing only to a new timestamped output package folder under the configured data root.")
    proc = subprocess.run([sys.executable, str(script)])
    print(f"[cfr] END {command} (exit {proc.returncode})")
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="construction_financial_review.cli",
                                 description="Construction Financial Review toolkit.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("validate-crosswalk", "run-context", "run-analysis",
                 "run-mapping-workpaper", "run-crosswalk-v2"):
        sp = sub.add_parser(name)
        sp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    sfp = sub.add_parser("schedule-integrate-forecast")
    sfp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    sfp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    sfp.add_argument("--frozen-stamp", default=None,
                     help="Deterministic stamp for the output folder (used by the determinism check).")
    sfp.add_argument("--out-root", default=None,
                     help="Override the output base dir (defaults to the data root).")
    fap = sub.add_parser("forecast-accuracy")
    fap.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fap.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fap.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fap.add_argument("--out-root", default=None, help="Override the output base dir.")
    fap.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (default: deterministic mock).")
    fap.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fip = sub.add_parser("forecast-intelligence")
    fip.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fip.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fip.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fip.add_argument("--out-root", default=None, help="Override the output base dir.")
    fip.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (default: deterministic mock).")
    fip.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fmp = sub.add_parser("forecast-monthly")
    fmp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fmp.add_argument("--forecast-start-month", default=None,
                     help="Override the forecast start month (YYYY-MM); default is the system month.")
    fmp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fmp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fmp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fmp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (default: deterministic mock).")
    fmp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fpp = sub.add_parser("forecast-probability")
    fpp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fpp.add_argument("--runs", type=int, default=10000, help="Monte Carlo runs (default 10000).")
    fpp.add_argument("--seed", type=int, default=20260614, help="Deterministic RNG seed.")
    fpp.add_argument("--forecast-start-month", default=None,
                     help="Override the forecast start month (YYYY-MM); default is the monthly package window.")
    fpp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fpp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fpp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fpp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (default: deterministic mock).")
    fpp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fhp = sub.add_parser("forecast-history-informed")
    fhp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fhp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fhp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fhp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fhp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fhp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fcp = sub.add_parser("forecast-cost-frequency")
    fcp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fcp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fcp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fcp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fcp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fcp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fkp = sub.add_parser("forecast-comprehensive")
    fkp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fkp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fkp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fkp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fkp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fkp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fiap = sub.add_parser("forecast-improvement-audit")
    fiap.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fiap.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fiap.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fiap.add_argument("--out-root", default=None, help="Override the output base dir.")
    fiap.add_argument("--with-llm", action="store_true",
                      help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fiap.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_project(args.project)
    if args.command == "validate-crosswalk":
        return cmd_validate_crosswalk(cfg)
    if args.command == "schedule-integrate-forecast":
        return cmd_schedule_integrate_forecast(cfg, args.project, args.data_root,
                                               args.frozen_stamp, args.out_root)
    if args.command == "forecast-accuracy":
        return cmd_forecast_accuracy(cfg, args.project, args.data_root, args.frozen_stamp,
                                     args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-intelligence":
        return cmd_forecast_intelligence(cfg, args.project, args.data_root, args.frozen_stamp,
                                         args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-monthly":
        return cmd_forecast_monthly(cfg, args.project, args.data_root, args.frozen_stamp,
                                    args.out_root, args.with_llm, args.llm_model,
                                    args.forecast_start_month)
    if args.command == "forecast-probability":
        return cmd_forecast_probability(cfg, args.project, args.data_root, args.frozen_stamp,
                                        args.out_root, args.with_llm, args.llm_model,
                                        args.forecast_start_month, args.runs, args.seed)
    if args.command == "forecast-history-informed":
        return cmd_forecast_history_informed(cfg, args.project, args.data_root, args.frozen_stamp,
                                             args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-cost-frequency":
        return cmd_forecast_cost_frequency(cfg, args.project, args.data_root, args.frozen_stamp,
                                           args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-comprehensive":
        return cmd_forecast_comprehensive(cfg, args.project, args.data_root, args.frozen_stamp,
                                          args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-improvement-audit":
        return cmd_forecast_improvement_audit(cfg, args.project, args.data_root, args.frozen_stamp,
                                              args.out_root, args.with_llm, args.llm_model)
    return cmd_run_generator(args.command, args.project)


if __name__ == "__main__":
    sys.exit(main())
