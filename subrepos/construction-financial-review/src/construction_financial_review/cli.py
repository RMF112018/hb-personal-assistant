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
import contextlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .common import run_lineage
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
                         with_llm, llm_model, forecast_start_month, control_file=None) -> int:
    """Config-driven month-by-month forecast generator: time-phases the accepted forecast-intelligence
    final-cost package across the remaining forecast months using CostEntries + subcontractor-invoice
    trend evidence and schedule remaining-work phasing. Applies accepted operator forecast-model controls
    (window / shape / value / manual) when present. Import dispatch."""
    from .forecast_monthly import generate_monthly_forecast_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, forecast_start_month=forecast_start_month,
                   control_file=control_file)


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
                               with_llm, llm_model, control_file=None) -> int:
    """Integrated forecast model layer: discovers + consumes all accepted evidence packages (context,
    intelligence, monthly, probability, history-informed, cost-frequency, crosswalk-v2, schedule-
    integrated) into a per-code evidence registry, scores advisory evidence at bounded de-duplicated
    weights, and emits integrated final-cost / monthly / probability recommendations with lineage, an
    evidence-conflict register, and a human-acceptance review queue. Applies accepted operator forecast-
    model controls (window / shape / value / manual) as the highest-priority operator decision. Never
    mutates a package. Import dispatch."""
    from .forecast_comprehensive import generate_comprehensive_forecast_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, control_file=control_file)


def cmd_forecast_controls(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                          with_llm, llm_model) -> int:
    """Operator-controlled forecast stop-date / closeout-constraint layer: loads the operator control
    file, maps each control to a canonical budget code, resolves precedence (accepted > pending) into
    applied decisions, and emits applied decisions, a monthly-adjustment preview, a human-review queue,
    warnings, and fail-closed audits. Posture-changing controls apply only when human-accepted; pending
    controls are queued. Never mutates source Excel / accepted packages / SQLite; no live external calls.
    Import dispatch."""
    from .forecast_controls import generate_forecast_controls_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)


def cmd_forecast_model_controls(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                                with_llm, llm_model, control_file) -> int:
    """Operator forecast-model-control layer: loads the model-control file (committed dormant config or a
    --forecast-model-control-file override), resolves each control's forecast window, value constraint,
    model shape, and manual inputs into a controlled monthly forecast, maps it to a canonical budget code,
    enforces the actuals floor + window + manual + duplicate-conflict + acceptance gates, and emits applied
    decisions, resolved references, a monthly-reconciliation preview, a deterministic probability/
    plausibility assessment, a human-review queue, conflicts, warnings, and fail-closed audits. Only
    accepted controls apply; pending controls are queued. Never mutates source Excel / accepted packages /
    SQLite; no live external calls. Import dispatch."""
    from .forecast_model_controls import generate_forecast_model_controls_package as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, control_file=control_file)


def cmd_forecast_staffing_plan(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                               with_llm, llm_model) -> int:
    """Operator-supplied planned-staffing forecast layer: discovers + validates the extracted staffing
    JSON package, resolves each source cost code to a canonical .LAB budget-code key (LAB-only numeric;
    .LAB/.LBN/.MAT family is date-context only), and emits the per-code bridge (actual / accepted vs
    plan-implied final+CTC / deltas), BOTH the plan-implied and current-CTC-reconciled monthly forecasts,
    a mapping review queue, conflicts, warnings, and fail-closed audits. Never mutates source Excel, the
    staffing JSON package, accepted packages, or SQLite; no live external calls. Import dispatch."""
    from .forecast_staffing_plan import generate_forecast_staffing_plan_package as gen
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


def cmd_actuals_erp_crosscheck(cfg: dict, project: str, data_root, frozen_stamp, out_root,
                               strict: bool) -> int:
    """Additive CostEntries actuals to BudgetDetails ERP job-to-date cross-check. Advisory by
    default; strict mode fails closed on material variances and configured structural failures."""
    from .forecast_actuals import actuals_erp_crosscheck as gen
    return gen.run(project, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   strict=strict)


def cmd_procore_budget_details_parity(cfg: dict, project: str, data_root, db_path, strict: bool) -> int:
    """Body-free parity report for DB-backed Procore Budget Detail Rows."""
    from .procore_budget_details_db import parity_report

    report = parity_report(cfg, project_key=project, data_root=data_root, db_path=db_path)
    print(json.dumps(report, indent=2))
    ok = (
        bool(report["target_code_queryable"])
        and bool(report["target_code_selected_view_queryable"])
        and not report["source_quality_issues"]
        and not report["raw_payload_body_emitted"]
    )
    if strict:
        ok = ok and bool(report["strict_ok"])
    return 0 if ok else 3


def cmd_context_generate(*, data_root: str, out_dir: str, stamp: str, project: str,
                         db_backed: bool, db_path: str | None) -> int:
    """Controlled, default-off context-package generation (Phase 6).

    Runs the Phase 5 context generator from EXPLICIT paths in either file-backed mode (default)
    or DB-backed mode (the three v59 source-domain row sets via the Phase 4 adapter). Prints
    structured JSON metadata. Fails closed (nonzero) on unsafe/missing DB path, live/default DB,
    live-root output, or missing DB rows. Does NOT alter run-context or any existing default."""
    from .context.context_generation_runner import ContextRunnerError, run_context_generation
    from .context.db_source_adapter import ForecastDbReadError
    try:
        # Keep stdout a clean machine-readable JSON channel: the generator's own progress
        # chatter is redirected to stderr for the duration of the build.
        with contextlib.redirect_stdout(sys.stderr):
            meta = run_context_generation(
                data_root=Path(data_root),
                out_dir=Path(out_dir),
                stamp=stamp,
                db_backed=db_backed,
                db_path=Path(db_path) if db_path else None,
                project_key=project,
            )
    except (ContextRunnerError, ForecastDbReadError) as exc:
        print(json.dumps({"command": "context-generate", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "context-generate", "status": "ok"}
    out.update(meta)
    print(json.dumps(out, indent=2))
    return 0


def cmd_final_forecast_generate(*, context_package: str, project: str,
                                run_id: str | None = None) -> int:
    """Controlled, default-off final-forecast (analysis) generation from an explicit context package
    (Phase 7).

    Runs the downstream analysis generator against ONE explicit context package, hard-pinned (no
    latest-glob) under its own (temp) data root. Prints structured JSON metadata. Fails closed
    (nonzero) on missing/invalid context package, non-tropical project, live-root data root, or a
    pre-existing analysis package. Does NOT alter run-analysis or any existing default."""
    from .analysis.final_forecast_runner import (
        FinalForecastRunnerError,
        run_final_forecast_generation,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: the generator's own progress
        # chatter is redirected to stderr for the duration of the run.
        with contextlib.redirect_stdout(sys.stderr):
            meta = run_final_forecast_generation(
                context_package=Path(context_package),
                project_key=project,
                run_id=run_id,
            )
    except FinalForecastRunnerError as exc:
        print(json.dumps({"command": "final-forecast-generate", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "final-forecast-generate", "status": "ok"}
    out.update(meta)
    print(json.dumps(out, indent=2))
    return 0


def cmd_package_chain_manifest(*, context_package: str, analysis_package: str, out: str,
                               project: str) -> int:
    """Write a deterministic forecast package-chain manifest from explicit context/analysis paths
    (Phase 8).

    Resolves each explicit package directory into a validated ForecastPackageRef (no latest-glob),
    refuses live-root packages, and writes a sorted-key chain manifest. Prints structured JSON
    metadata; rc 3 on any invalid input. Adds no DB/schema and changes no existing command."""
    from .common import package_resolution as pr
    try:
        context_ref = pr.resolve_explicit_package(
            package_kind="context", package_path=Path(context_package), project_key=project)
        analysis_ref = pr.resolve_explicit_package(
            package_kind="analysis", package_path=Path(analysis_package), project_key=project)
        chain = pr.build_package_chain(
            project_key=project, data_root=context_ref.package_path.parent,
            refs=[context_ref, analysis_ref])
        manifest_path = pr.write_package_chain_manifest(chain=chain, out_path=Path(out))
    except pr.PackageResolutionError as exc:
        print(json.dumps({"command": "package-chain-manifest", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    print(json.dumps({
        "command": "package-chain-manifest", "status": "ok", "project": project,
        "manifest_path": str(manifest_path),
        "packages": {
            "context": {"package_path": str(context_ref.package_path), "stamp": context_ref.stamp},
            "analysis": {"package_path": str(analysis_ref.package_path),
                         "stamp": analysis_ref.stamp},
        },
    }, indent=2))
    return 0


def cmd_run_generator(command: str, project: str, *, overrides: dict | None = None,
                      lineage_state: str | None = None) -> int:
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
    # Forward the active full-fresh run lineage state (normally inherited from the runner's env) and any
    # debug/developer stamp overrides to the generator subprocess. The runner sets none of these by hand.
    env = dict(os.environ)
    if lineage_state:
        env["CFR_RUN_LINEAGE_STATE"] = lineage_state
    for cli_key, env_key in (("context_stamp", "CFR_CONTEXT_STAMP"),
                             ("analysis_stamp", "CFR_ANALYSIS_STAMP"),
                             ("mapping_workpaper_stamp", "CFR_MAPPING_WORKPAPER_STAMP")):
        v = (overrides or {}).get(cli_key)
        if v:
            env[env_key] = v
    print(f"[cfr] START {command} (tropical) -> {script.name}")
    print("[cfr] writing only to a new timestamped output package folder under the configured data root.")
    proc = subprocess.run([sys.executable, str(script)], env=env)
    print(f"[cfr] END {command} (exit {proc.returncode})")
    return proc.returncode


def cmd_lineage_init(cfg: dict, project: str) -> int:
    """Mint a FRESH run-specific full-fresh lineage state and print its path (for CFR_RUN_LINEAGE_STATE)."""
    data_root = cfg.get("default_data_root")
    if not data_root:
        raise SystemExit("ERROR: project config missing 'default_data_root'")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = run_lineage.new_run_state_path(SUBPROJECT_ROOT, project, run_id)
    run_lineage.start_run_state(project, data_root, run_id, path=path)
    print(str(path))   # stdout = the state path the runner exports as CFR_RUN_LINEAGE_STATE
    return 0


def cmd_lineage_record(cfg: dict, project: str, ptype: str) -> int:
    """Validate + record the freshly generated package of `ptype` into the active run state."""
    state = run_lineage.active_state_path()
    if state is None:
        raise SystemExit("ERROR: no active run lineage state (CFR_RUN_LINEAGE_STATE not set)")
    rec = run_lineage.record_latest(state, ptype, project_key=project)
    print(f"[cfr] recorded {ptype}: {Path(rec['path']).name} (stamp {rec['stamp']})")
    return 0


def cmd_lineage_show(cfg: dict, project: str, field: str | None = None) -> int:
    """Print the active run lineage state (or a single field like `context_stamp`)."""
    state = run_lineage.active_state()
    if state is None:
        raise SystemExit("ERROR: no active run lineage state (CFR_RUN_LINEAGE_STATE not set)")
    if field:
        if field.endswith("_stamp"):
            ptype = field[:-len("_stamp")]
            print((state.get("packages", {}).get(ptype) or {}).get("stamp") or "")
        elif field.endswith("_path"):
            ptype = field[:-len("_path")]
            print((state.get("packages", {}).get(ptype) or {}).get("path") or "")
        else:
            print(state.get(field) or "")
        return 0
    print(json.dumps(state, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="construction_financial_review.cli",
                                 description="Construction Financial Review toolkit.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("validate-crosswalk", "run-context", "run-analysis",
                 "run-mapping-workpaper", "run-crosswalk-v2"):
        sp = sub.add_parser(name)
        sp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
        if name in ("run-analysis", "run-mapping-workpaper", "run-crosswalk-v2"):
            # debug/developer overrides only — the full-fresh runner needs NONE of these.
            sp.add_argument("--lineage-state", default=None,
                            help="Path to a full-fresh run lineage state (else CFR_RUN_LINEAGE_STATE).")
            sp.add_argument("--context-stamp", default=None, help="Debug: pin upstream context stamp.")
            sp.add_argument("--analysis-stamp", default=None, help="Debug: pin upstream analysis stamp.")
            sp.add_argument("--mapping-workpaper-stamp", default=None,
                            help="Debug: pin upstream mapping-workpaper stamp.")
    # full-fresh run lineage state helpers (used by the runner; no per-command manual stamps needed)
    for name in ("lineage-init", "lineage-show"):
        lp = sub.add_parser(name)
        lp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    sub._name_parser_map["lineage-show"].add_argument(
        "--field", default=None, help="Print a single field (e.g. context_stamp) instead of full JSON.")
    lrp = sub.add_parser("lineage-record")
    lrp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    lrp.add_argument("--type", required=True,
                     choices=("context", "analysis", "mapping_workpaper", "crosswalk_v2"),
                     help="Package type to validate + record into the active run lineage state.")
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
    fmp.add_argument("--forecast-model-control-file", default=None,
                     help="Override the committed forecast-model-control file (no silent fallback).")
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
    fkp.add_argument("--forecast-model-control-file", default=None,
                     help="Override the committed forecast-model-control file (no silent fallback).")
    fkp.add_argument("--with-llm", action="store_true",
                     help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fkp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fctlp = sub.add_parser("forecast-controls")
    fctlp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fctlp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fctlp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fctlp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fctlp.add_argument("--with-llm", action="store_true",
                       help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fctlp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fmcp = sub.add_parser("forecast-model-controls")
    fmcp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fmcp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fmcp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fmcp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fmcp.add_argument("--with-llm", action="store_true",
                      help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fmcp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fmcp.add_argument("--forecast-model-control-file", default=None,
                      help="Override the committed model-control file (validation/operator override; no "
                           "silent fallback to the committed config).")
    fspp = sub.add_parser("forecast-staffing-plan")
    fspp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fspp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fspp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fspp.add_argument("--out-root", default=None, help="Override the output base dir.")
    fspp.add_argument("--with-llm", action="store_true",
                      help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fspp.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    fiap = sub.add_parser("forecast-improvement-audit")
    fiap.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    fiap.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    fiap.add_argument("--frozen-stamp", default=None, help="Deterministic stamp (determinism check).")
    fiap.add_argument("--out-root", default=None, help="Override the output base dir.")
    fiap.add_argument("--with-llm", action="store_true",
                      help="Engage the local Ollama advisory narrative layer (advisory only, never numeric).")
    fiap.add_argument("--llm-model", default=None, help="Override the configured Ollama model.")
    aecp = sub.add_parser("actuals-erp-crosscheck")
    aecp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    aecp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    aecp.add_argument("--frozen-stamp", default=None, help="Deterministic stamp.")
    aecp.add_argument("--out-root", default=None, help="Override the output base dir.")
    aecp.add_argument("--strict", action="store_true",
                      help="Fail closed on material variances and configured structural failures.")
    pbdp = sub.add_parser("procore-budget-details-parity")
    pbdp.add_argument("--project", required=True, help="Project key (e.g. tropical).")
    pbdp.add_argument("--data-root", default=None, help="Override the configured forecast data root.")
    pbdp.add_argument("--db-path", default=None, help="Override the configured HB Personal Assistant DB path.")
    pbdp.add_argument("--strict", action="store_true",
                      help="Fail closed on amount mismatches or package-only budget codes.")
    # Phase 6 — controlled, default-off DB-backed context generation from explicit paths.
    cgp = sub.add_parser("context-generate")
    cgp.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 6).")
    cgp.add_argument("--data-root", required=True,
                     help="Explicit forecast source data root for this controlled run.")
    cgp.add_argument("--out-dir", required=True,
                     help="Explicit output package dir (must not exist; not under the live data root).")
    cgp.add_argument("--stamp", required=True, help="Deterministic output stamp for the run.")
    cgp.add_argument("--db-backed", action="store_true",
                     help="Read the three v59 source-domain row sets from SQLite via the Phase 4 "
                          "adapter (default off: file-backed).")
    cgp.add_argument("--db-path", default=None,
                     help="Explicit temp SQLite DB path (required with --db-backed; refuses the "
                          "live/default DB).")
    # Phase 7 — controlled, default-off final-forecast (analysis) generation from an explicit
    # context package. Analysis is inherently deterministic (no LLM), so no deterministic flag.
    ffp = sub.add_parser("final-forecast-generate")
    ffp.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 7).")
    ffp.add_argument("--context-package", required=True,
                     help="Explicit context package dir to consume (hard-pinned; its parent is the "
                          "controlled data root, which must not be under the live forecast root).")
    ffp.add_argument("--run-id", default=None,
                     help="Optional run id recorded in the temp run-lineage state.")
    # Phase 8 — write a deterministic package-chain manifest from explicit context/analysis paths.
    pcmp = sub.add_parser("package-chain-manifest")
    pcmp.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 8).")
    pcmp.add_argument("--context-package", required=True,
                      help="Explicit context package dir (validated; refused under the live root).")
    pcmp.add_argument("--analysis-package", required=True,
                      help="Explicit analysis package dir (validated; refused under the live root).")
    pcmp.add_argument("--out", required=True,
                      help="Output path for the deterministic package-chain manifest JSON.")
    # --context-stamp pins the upstream context package for a lineage-consistent fresh full run.
    # Applied to the stages that consume context and participate in the lineage gate.
    for _p in (fip, fmp, fpp, fcp, fkp, fspp):
        _p.add_argument("--context-stamp", default=None,
                        help="Pin upstream context to forecast_context_package_<project>_<stamp> "
                             "(fail closed if missing; default latest-glob).")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_project(args.project)
    # carry an upstream context pin through cfg so every stage resolves the SAME context (fail closed).
    _ctx_stamp = getattr(args, "context_stamp", None)
    if _ctx_stamp:
        cfg = {**cfg, "_pinned_context_stamp": _ctx_stamp, "_strict_pin": True}
    if args.command == "validate-crosswalk":
        return cmd_validate_crosswalk(cfg)
    if args.command == "lineage-init":
        return cmd_lineage_init(cfg, args.project)
    if args.command == "lineage-record":
        return cmd_lineage_record(cfg, args.project, args.type)
    if args.command == "lineage-show":
        return cmd_lineage_show(cfg, args.project, getattr(args, "field", None))
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
                                    args.forecast_start_month, args.forecast_model_control_file)
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
                                          args.out_root, args.with_llm, args.llm_model,
                                          args.forecast_model_control_file)
    if args.command == "forecast-controls":
        return cmd_forecast_controls(cfg, args.project, args.data_root, args.frozen_stamp,
                                     args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-model-controls":
        return cmd_forecast_model_controls(cfg, args.project, args.data_root, args.frozen_stamp,
                                           args.out_root, args.with_llm, args.llm_model,
                                           args.forecast_model_control_file)
    if args.command == "forecast-staffing-plan":
        return cmd_forecast_staffing_plan(cfg, args.project, args.data_root, args.frozen_stamp,
                                          args.out_root, args.with_llm, args.llm_model)
    if args.command == "forecast-improvement-audit":
        return cmd_forecast_improvement_audit(cfg, args.project, args.data_root, args.frozen_stamp,
                                              args.out_root, args.with_llm, args.llm_model)
    if args.command == "actuals-erp-crosscheck":
        return cmd_actuals_erp_crosscheck(cfg, args.project, args.data_root, args.frozen_stamp,
                                          args.out_root, args.strict)
    if args.command == "procore-budget-details-parity":
        return cmd_procore_budget_details_parity(cfg, args.project, args.data_root, args.db_path,
                                                 args.strict)
    if args.command == "final-forecast-generate":
        return cmd_final_forecast_generate(context_package=args.context_package,
                                           project=args.project, run_id=args.run_id)
    if args.command == "package-chain-manifest":
        return cmd_package_chain_manifest(context_package=args.context_package,
                                          analysis_package=args.analysis_package,
                                          out=args.out, project=args.project)
    if args.command == "context-generate":
        return cmd_context_generate(data_root=args.data_root, out_dir=args.out_dir,
                                    stamp=args.stamp, project=args.project,
                                    db_backed=args.db_backed, db_path=args.db_path)
    overrides = {k: getattr(args, k, None)
                 for k in ("context_stamp", "analysis_stamp", "mapping_workpaper_stamp")}
    return cmd_run_generator(args.command, args.project, overrides=overrides,
                             lineage_state=getattr(args, "lineage_state", None))


if __name__ == "__main__":
    sys.exit(main())
