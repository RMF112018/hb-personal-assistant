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
from .common.config_root import resolve_config_base
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
    # Phase 16: CFR_CONFIG_ROOT (opt-in) overrides the base; unset -> SUBPROJECT_ROOT (unchanged).
    cfg = resolve_config_base(SUBPROJECT_ROOT) / "config" / "projects" / f"{project}.json"
    if not cfg.exists():
        raise SystemExit(f"ERROR: no project config at {cfg}")
    return read_json(cfg)


def _resolve_crosswalk(cfg: dict) -> Path:
    rel = cfg.get("owner_sov_scope_crosswalk")
    if not rel:
        raise SystemExit("ERROR: project config missing 'owner_sov_scope_crosswalk'")
    # Phase 16: CFR_CONFIG_ROOT (opt-in) overrides the base; unset -> SUBPROJECT_ROOT (unchanged).
    base = resolve_config_base(SUBPROJECT_ROOT)
    p = (base / rel) if not Path(rel).is_absolute() else Path(rel)
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


def _run_validate_crosswalk(cfg: dict, *, config_source: str) -> dict:
    crosswalk = _resolve_crosswalk(cfg)
    context_pkg = _resolve_context_package(cfg)
    canonical, procore = xwval._load_universes(str(context_pkg) if context_pkg else None)
    report = xwval.validate(crosswalk, canonical, procore)
    report["project_key"] = cfg.get("project_key")
    report["context_package_used_for_coverage"] = str(context_pkg) if context_pkg else None
    report["config_source"] = config_source
    report["crosswalk_path"] = str(crosswalk)
    return report


def cmd_validate_crosswalk(cfg: dict, *, config_source: str = "file", config_db_path: str | None = None,
                           config_snapshot_id: str | None = None,
                           config_snapshot_root: str | None = None) -> int:
    """Validate the authoritative owner-SOV crosswalk (Phase 16: optional DB-snapshot config source).

    db_snapshot materializes the snapshot under --config-snapshot-root, points CFR_CONFIG_ROOT at it
    (scoped, restored), runs the existing resolver/validator, and proves parity vs file-backed."""
    if config_source == "file":
        report = _run_validate_crosswalk(cfg, config_source="file")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    # db_snapshot
    from .common.config_root import ENV_CONFIG_ROOT
    from .config_registry import ConfigRegistryError, materialize_forecast_config_snapshot
    if not (config_db_path and config_snapshot_id and config_snapshot_root):
        print(json.dumps({"command": "validate-crosswalk", "status": "refused",
                          "reason": "db_snapshot requires --config-db-path, --config-snapshot-id, "
                                    "--config-snapshot-root"}, indent=2))
        return 3
    try:
        with contextlib.redirect_stdout(sys.stderr):
            file_report = _run_validate_crosswalk(cfg, config_source="file")
            mat = materialize_forecast_config_snapshot(
                db_path=Path(config_db_path), config_snapshot_id=config_snapshot_id,
                out_root=Path(config_snapshot_root))
            mat_root = mat["materialized_config_root"]
            prev = os.environ.get(ENV_CONFIG_ROOT)
            os.environ[ENV_CONFIG_ROOT] = mat_root
            try:
                db_report = _run_validate_crosswalk(cfg, config_source="db_snapshot")
            finally:
                if prev is None:
                    os.environ.pop(ENV_CONFIG_ROOT, None)
                else:
                    os.environ[ENV_CONFIG_ROOT] = prev
    except (ConfigRegistryError, SystemExit) as exc:
        print(json.dumps({"command": "validate-crosswalk", "status": "refused",
                          "reason": str(exc)}, indent=2))
        return 3
    parity = {k: file_report[k] for k in ("passed", "row_count") if k in file_report}
    db_parity = {k: db_report[k] for k in ("passed", "row_count") if k in db_report}
    parity_pass = parity == db_parity and file_report.get("passed") is not None
    out = {"command": "validate-crosswalk", "config_source": "db_snapshot",
           "config_snapshot_id": config_snapshot_id, "materialized_config_root": mat_root,
           "file_vs_db_parity": "pass" if parity_pass else "fail",
           "report": db_report}
    print(json.dumps(out, indent=2))
    if not parity_pass:
        return 1
    return 0 if db_report["passed"] else 1


def cmd_forecast_config_import(*, project: str, config_root: str, db_path: str,
                               import_run_id: str | None, allow_live_db_write: bool) -> int:
    """Import file-backed forecast config into the v60 registry DB (Phase 16)."""
    from .config_registry import ConfigRegistryError, import_forecast_config_to_db
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = import_forecast_config_to_db(
                config_root=Path(config_root), db_path=Path(db_path), project_key=project,
                import_run_id=import_run_id, allow_live_db_write=allow_live_db_write)
    except ConfigRegistryError as exc:
        print(json.dumps({"command": "forecast-config-import", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-config-import", "status": "ok"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0


def cmd_forecast_config_snapshot(*, project: str, db_path: str, snapshot_name: str,
                                 snapshot_reason: str, out_root: str) -> int:
    """Create an immutable config snapshot and materialize it under out-root (Phase 16)."""
    from .config_registry import (
        ConfigRegistryError,
        create_forecast_config_snapshot,
        materialize_forecast_config_snapshot,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            snap = create_forecast_config_snapshot(
                db_path=Path(db_path), project_key=project, snapshot_name=snapshot_name,
                snapshot_reason=snapshot_reason)
            mat = materialize_forecast_config_snapshot(
                db_path=Path(db_path), config_snapshot_id=snap["config_snapshot_id"],
                out_root=Path(out_root))
    except ConfigRegistryError as exc:
        print(json.dumps({"command": "forecast-config-snapshot", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-config-snapshot", "status": "ok", "snapshot": snap,
           "materialized": mat}
    print(json.dumps(out, indent=2))
    return 0


def cmd_forecast_config_export(*, project: str, db_path: str, snapshot_id: str | None,
                               out_root: str) -> int:
    """Export DB config back to a file-compatible tree under out-root (Phase 16)."""
    from .config_registry import ConfigRegistryError, export_forecast_config_from_db
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = export_forecast_config_from_db(
                db_path=Path(db_path), out_root=Path(out_root), project_key=project,
                config_snapshot_id=snapshot_id)
    except ConfigRegistryError as exc:
        print(json.dumps({"command": "forecast-config-export", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-config-export", "status": "ok"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0


def cmd_forecast_model_controls_db_config_proof(*, project: str, live_db_path: str,
                                                config_snapshot_id: str, work_root: str,
                                                run_stamp: str | None, data_root: str | None,
                                                source_config_root: str | None,
                                                expect_item_count: int | None,
                                                require_live_snapshot: bool) -> int:
    """Phase 17: prove forecast_model_controls consumes the DB config snapshot with parity vs file-backed.

    Reads the live DB read-only to materialize the Phase 16 snapshot, runs the deterministic generator
    file-backed (CFR_CONFIG_ROOT unset) and DB-backed (CFR_CONFIG_ROOT = materialized root, scoped), and
    compares. Never writes the live DB; no --allow-live-db-write. rc 0 parity ready / 1 parity mismatch /
    3 controlled refusal."""
    from .workflows.forecast_model_controls_db_config_proof import (
        DECISION_READY,
        ForecastModelControlsDbConfigProofError,
        run_forecast_model_controls_db_config_proof,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_model_controls_db_config_proof(
                project_key=project, live_db_path=Path(live_db_path),
                config_snapshot_id=config_snapshot_id, work_root=Path(work_root), run_stamp=run_stamp,
                data_root=Path(data_root) if data_root else None,
                source_config_root=Path(source_config_root) if source_config_root else None,
                require_item_count=expect_item_count, require_live_snapshot=require_live_snapshot)
    except ForecastModelControlsDbConfigProofError as exc:
        print(json.dumps({"command": "forecast-model-controls-db-config-proof", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-model-controls-db-config-proof"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


def cmd_forecast_monthly_db_config_proof(*, project: str, live_db_path: str,
                                         config_snapshot_id: str, work_root: str,
                                         run_stamp: str | None, data_root: str | None,
                                         source_config_root: str | None,
                                         expect_item_count: int | None,
                                         require_live_snapshot: bool,
                                         preflight_stability_seconds: float) -> int:
    """Phase 18: prove forecast_monthly consumes the DB config snapshot with parity vs file-backed.

    Reads the live DB read-only to materialize the Phase 16 snapshot, runs the deterministic monthly
    generator file-backed (CFR_CONFIG_ROOT unset) and DB-backed (CFR_CONFIG_ROOT = materialized root,
    scoped), and compares. The data root is a read-only input (may be the live forecast root); only the
    generated artifacts must live outside it. Never writes/migrates/imports the live DB; no
    --allow-live-db-write. rc 0 parity ready / 1 parity mismatch / 3 controlled refusal."""
    from .workflows.forecast_monthly_db_config_proof import (
        DECISION_READY,
        ForecastMonthlyDbConfigProofError,
        run_forecast_monthly_db_config_proof,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_monthly_db_config_proof(
                project_key=project, live_db_path=Path(live_db_path),
                config_snapshot_id=config_snapshot_id, work_root=Path(work_root), run_stamp=run_stamp,
                data_root=Path(data_root) if data_root else None,
                source_config_root=Path(source_config_root) if source_config_root else None,
                require_item_count=expect_item_count, require_live_snapshot=require_live_snapshot,
                preflight_stability_seconds=preflight_stability_seconds)
    except ForecastMonthlyDbConfigProofError as exc:
        print(json.dumps({"command": "forecast-monthly-db-config-proof", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-monthly-db-config-proof"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


def cmd_forecast_probability_db_config_proof(*, project: str, live_db_path: str,
                                             config_snapshot_id: str, work_root: str,
                                             run_stamp: str | None, data_root: str | None,
                                             source_config_root: str | None,
                                             expect_item_count: int | None,
                                             require_live_snapshot: bool,
                                             preflight_stability_seconds: float,
                                             runs: int, seed: int,
                                             forecast_start_month: str | None) -> int:
    """Phase 19: prove forecast_probability consumes the DB config snapshot with parity vs file-backed.

    Reads the live DB read-only (pinned) to materialize the Phase 16 snapshot, runs the deterministic
    Monte-Carlo generator file-backed (CFR_CONFIG_ROOT unset) and DB-backed (CFR_CONFIG_ROOT = materialized
    root, scoped) with the same runs/seed/stamp, and compares. Reads the monthly package (never runs it);
    no comprehensive/CSV/LLM. Never writes/migrates/imports the live DB; no --allow-live-db-write. rc 0
    parity ready / 1 parity mismatch / 3 controlled refusal."""
    from .workflows.forecast_probability_db_config_proof import (
        DECISION_READY,
        ForecastProbabilityDbConfigProofError,
        run_forecast_probability_db_config_proof,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_probability_db_config_proof(
                project_key=project, live_db_path=Path(live_db_path),
                config_snapshot_id=config_snapshot_id, work_root=Path(work_root), run_stamp=run_stamp,
                data_root=Path(data_root) if data_root else None,
                source_config_root=Path(source_config_root) if source_config_root else None,
                require_item_count=expect_item_count, require_live_snapshot=require_live_snapshot,
                preflight_stability_seconds=preflight_stability_seconds, runs=runs, seed=seed,
                forecast_start_month=forecast_start_month)
    except ForecastProbabilityDbConfigProofError as exc:
        print(json.dumps({"command": "forecast-probability-db-config-proof", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-probability-db-config-proof"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


def cmd_forecast_comprehensive_db_config_proof(*, project: str, live_db_path: str,
                                               config_snapshot_id: str, work_root: str,
                                               run_stamp: str | None, data_root: str | None,
                                               source_config_root: str | None,
                                               expect_item_count: int | None,
                                               require_live_snapshot: bool,
                                               preflight_stability_seconds: float) -> int:
    """Phase 20: prove forecast_comprehensive consumes the DB config snapshot with parity vs file-backed.

    Reads the live DB read-only (pinned) to materialize the Phase 16 snapshot, runs the deterministic
    integrated generator file-backed (CFR_CONFIG_ROOT unset) and DB-backed (CFR_CONFIG_ROOT = materialized
    root, scoped) with the same stamp, and compares. Reads context/intelligence/monthly (+cost-frequency)
    packages read-only; refuses if the cost-frequency package is missing while frequency_enabled (never
    generates it). No comprehensive-internal generator/CSV-cutover/LLM. Never writes/migrates/imports the
    live DB; no --allow-live-db-write. rc 0 parity ready / 1 parity mismatch / 3 controlled refusal."""
    from .workflows.forecast_comprehensive_db_config_proof import (
        DECISION_READY,
        ForecastComprehensiveDbConfigProofError,
        run_forecast_comprehensive_db_config_proof,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_comprehensive_db_config_proof(
                project_key=project, live_db_path=Path(live_db_path),
                config_snapshot_id=config_snapshot_id, work_root=Path(work_root), run_stamp=run_stamp,
                data_root=Path(data_root) if data_root else None,
                source_config_root=Path(source_config_root) if source_config_root else None,
                require_item_count=expect_item_count, require_live_snapshot=require_live_snapshot,
                preflight_stability_seconds=preflight_stability_seconds)
    except ForecastComprehensiveDbConfigProofError as exc:
        print(json.dumps({"command": "forecast-comprehensive-db-config-proof", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-comprehensive-db-config-proof"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


def cmd_forecast_db_config_backed_generate(*, project: str, generator_kind: str, live_db_path: str,
                                           config_snapshot_id: str | None, work_root: str,
                                           run_stamp: str | None, data_root: str | None,
                                           source_config_root: str | None,
                                           require_live_snapshot: bool,
                                           prove_file_equivalence: bool,
                                           preflight_stability_seconds: float,
                                           runs: int, seed: int,
                                           forecast_start_month: str | None) -> int:
    """Generate a forecast package CONSUMING the live DB config snapshot.

    ``--generator-kind`` selects which generator (comprehensive [default] / model_controls / monthly /
    probability). Materializes the chosen (default latest) live config snapshot READ-ONLY, gates on
    materialization fidelity (round-trip digest match), then runs the deterministic generator with
    CFR_CONFIG_ROOT = materialized root so a PROMOTED config snapshot drives generation. Never writes/
    migrates/imports the live DB. ``--runs`` / ``--seed`` / ``--forecast-start-month`` apply to the
    probability generator only. rc 0 generated / 1 generated-but-validation-failed / 3 controlled
    refusal."""
    from .workflows.forecast_db_config_backed_generation import (
        STATUS_GENERATED,
        ForecastDbConfigGenerationError,
        run_forecast_db_config_backed_generation_for_kind,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_db_config_backed_generation_for_kind(
                generator_kind=generator_kind,
                project_key=project, live_db_path=Path(live_db_path),
                config_snapshot_id=config_snapshot_id, work_root=Path(work_root), run_stamp=run_stamp,
                data_root=Path(data_root) if data_root else None,
                source_config_root=Path(source_config_root) if source_config_root else None,
                require_live_snapshot=require_live_snapshot,
                prove_file_equivalence=prove_file_equivalence,
                preflight_stability_seconds=preflight_stability_seconds,
                runs=runs, seed=seed, forecast_start_month=forecast_start_month)
    except ForecastDbConfigGenerationError as exc:
        print(json.dumps({"command": "forecast-db-config-backed-generate", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-db-config-backed-generate"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("status") == STATUS_GENERATED else 1


def cmd_forecast_config_db_parity(*, project: str, config_root: str, work_root: str,
                                  db_path: str | None) -> int:
    """Prove reader-layer config parity: repo file config == DB import/snapshot/materialize (Phase 16)."""
    from .config_registry import ConfigRegistryError, run_forecast_config_db_parity
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_config_db_parity(
                config_root=Path(config_root), work_root=Path(work_root), project_key=project,
                db_path=Path(db_path) if db_path else None)
    except ConfigRegistryError as exc:
        print(json.dumps({"command": "forecast-config-db-parity", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-config-db-parity"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("status") == "pass" else 1


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


def cmd_controlled_context_analysis(*, data_root: str, work_root: str, context_stamp: str,
                                    mode: str, db_path: str | None, project: str) -> int:
    """Controlled, default-off context->analysis workflow (Phase 9; orchestration only).

    Runs the proven controlled chain end to end from EXPLICIT paths under <work-root>/<mode>:
    context generation -> analysis generation -> explicit package resolution -> deterministic chain
    manifest -> operator report. mode is one of file | db | parity. Prints structured JSON metadata
    (the operator/parity report). Fails closed (rc 3) on any controlled refusal. Adds no DB/schema
    and changes no existing command or production default."""
    from .workflows.controlled_db_context_analysis import (
        ControlledWorkflowError,
        run_controlled_context_analysis_parity,
        run_controlled_context_analysis_workflow,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: the generators' own progress chatter
        # (and the Phase 7 subprocess) is redirected to stderr for the duration of the run.
        with contextlib.redirect_stdout(sys.stderr):
            if mode == "parity":
                if not db_path:
                    raise ControlledWorkflowError(
                        "mode='parity' requires an explicit --db-path (fail closed)")
                report = run_controlled_context_analysis_parity(
                    data_root=Path(data_root), work_root=Path(work_root),
                    context_stamp=context_stamp, db_path=Path(db_path), project_key=project)
            else:
                report = run_controlled_context_analysis_workflow(
                    data_root=Path(data_root), work_root=Path(work_root),
                    context_stamp=context_stamp, mode=mode,
                    db_path=Path(db_path) if db_path else None, project_key=project)
    except ControlledWorkflowError as exc:
        print(json.dumps({"command": "controlled-context-analysis", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "controlled-context-analysis", "status": "ok"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0


def cmd_db_cutover_readiness(*, data_root: str, work_root: str, context_stamp: str,
                             db_path: str, project: str) -> int:
    """Controlled DB-cutover-readiness gate (Phase 10; evidence only).

    Validates readiness prerequisites for the DB-backed context->analysis chain against an EXPLICIT
    temp/non-live v59 DB and EXPLICIT work root, runs the Phase 9 parity workflow under
    <work-root>/readiness, and prints a deterministic readiness report. rc 0 = ready for guarded
    operator use; rc 1 = not-ready evidence (gate ran, parity did not match); rc 3 = controlled
    refusal (unsafe/missing/ambiguous input). Changes no existing command or production default."""
    from .workflows.db_cutover_readiness import (
        DbCutoverReadinessError,
        run_db_cutover_readiness,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_db_cutover_readiness(
                data_root=Path(data_root), work_root=Path(work_root),
                context_stamp=context_stamp, db_path=Path(db_path), project_key=project)
    except DbCutoverReadinessError as exc:
        print(json.dumps({"command": "db-cutover-readiness", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "db-cutover-readiness"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == "ready_for_guarded_operator_use" else 1


def cmd_model_engines_readiness(*, context_package: str, db_path: str, work_root: str,
                                project: str, gate_mode: str) -> int:
    """Phase I PR 1: model-engines data + semantic readiness evidence (read-only, no dependency).

    Reads an EXISTING tropical context package read-only (per-code monthly-actuals time-series
    sufficiency + budget-code coverage denominator), runs the hb_assistant forecasting semantic
    gates against --db-path read-only, and prints a deterministic readiness report judging whether
    the real data supports a future statsforecast estimator AND is semantically safe to feed it.
    Adds no dependency, edits no forecast core, writes nothing to the live data root or DB.
    rc 0 = data ready; rc 1 = insufficient/not-ready evidence (bundle ran); rc 3 = controlled
    refusal (unsafe/missing input)."""
    from .workflows.model_engines_readiness import (
        DECISION_READY,
        ModelEnginesReadinessError,
        run_model_engines_readiness,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_model_engines_readiness(
                context_package=Path(context_package), db_path=Path(db_path),
                work_root=Path(work_root), project_key=project, gate_mode=gate_mode)
    except ModelEnginesReadinessError as exc:
        print(json.dumps({"command": "model-engines-readiness", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "model-engines-readiness"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


def cmd_forecast_accuracy_gate(*, package: str | None, data_root: str | None, work_root: str,
                               project: str) -> int:
    """Production-forecast accuracy/trust gate (verdict over an existing intelligence package).

    Reads the reconciled as-of backtest emitted by forecast-intelligence and prints a deterministic
    go/no-go verdict on whether the production reconciled forecast is accurate + unbiased enough to
    trust. Evidence only. rc 0 = pass; rc 1 = review/not-ready/insufficient evidence (gate ran);
    rc 3 = controlled refusal (unsafe/missing input)."""
    from .workflows.forecast_accuracy_gate import (
        VERDICT_PASS,
        ForecastAccuracyGateError,
        run_forecast_accuracy_gate,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_forecast_accuracy_gate(
                package=Path(package) if package else None,
                data_root=Path(data_root) if data_root else None,
                work_root=Path(work_root), project_key=project)
    except ForecastAccuracyGateError as exc:
        print(json.dumps({"command": "forecast-accuracy-gate", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-accuracy-gate"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("verdict") == VERDICT_PASS else 1


def cmd_temp_db_readiness_rehearsal(*, source_package: str, work_root: str, context_stamp: str,
                                    db_path: str | None, project: str) -> int:
    """Controlled temp-DB preparation + readiness rehearsal (Phase 11).

    Prepares a non-live temp v59 DB from an EXPLICIT Tropical source package (migrate + project)
    under an EXPLICIT work root, runs the Phase 10 readiness gate against it, and prints a
    deterministic rehearsal report. rc 0 = rehearsal passed (readiness ready); rc 1 = rehearsal
    failed (readiness not_ready after successful prep); rc 3 = controlled refusal (unsafe/missing/
    ambiguous input or DB-prep/projection failure). Never writes the live DB or live root; changes
    no existing command or production default."""
    from .workflows.temp_db_readiness_rehearsal import (
        TempDbRehearsalError,
        run_temp_db_readiness_rehearsal,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_temp_db_readiness_rehearsal(
                source_package=Path(source_package), work_root=Path(work_root),
                context_stamp=context_stamp,
                db_path=Path(db_path) if db_path else None, project_key=project)
    except TempDbRehearsalError as exc:
        print(json.dumps({"command": "temp-db-readiness-rehearsal", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "temp-db-readiness-rehearsal"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("status") == "passed" else 1


def cmd_guarded_db_operator_run(*, source_package: str, work_root: str, context_stamp: str,
                                db_path: str | None, project: str,
                                allow_certified_live_db: bool = False,
                                live_db_certification: str | None = None) -> int:
    """Controlled guarded DB operator-run package (Phase 12 + Phase 13 live-DB opt-in).

    Runs the Phase 11 rehearsal from an EXPLICIT Tropical source package under an EXPLICIT work root,
    validates the nested DB-backed context/analysis/chain artifacts and the Phase 10/Phase 9 evidence
    chain, and prints a deterministic guarded operator-run manifest naming the approved artifacts.
    Phase 13 certified-equivalence: a live/default --db-path is refused unless --allow-certified-live-db
    AND a certified_match --live-db-certification are given; even then execution uses a FRESH temp DB
    (never the live DB) and the manifest records the live-DB certification as evidence.
    rc 0 = approved for guarded DB context->analysis use; rc 1 = not-ready evidence (rehearsal ran but
    returned failed/not_ready); rc 3 = controlled refusal (unsafe/missing/ambiguous input or a
    structural/provenance inconsistency after a passed rehearsal). Never writes the live DB or live
    root; changes no existing command or production default."""
    from .workflows.guarded_db_operator_run import (
        GuardedDbOperatorRunError,
        run_guarded_db_operator_run,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_guarded_db_operator_run(
                source_package=Path(source_package), work_root=Path(work_root),
                context_stamp=context_stamp,
                db_path=Path(db_path) if db_path else None, project_key=project,
                allow_certified_live_db=allow_certified_live_db,
                live_db_certification=Path(live_db_certification) if live_db_certification else None)
    except GuardedDbOperatorRunError as exc:
        print(json.dumps({"command": "guarded-db-operator-run", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "guarded-db-operator-run"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == "approved_for_guarded_db_context_analysis_use" else 1


def cmd_live_db_provenance_audit(*, work_root: str | None, live_db_path: str | None,
                                 project: str) -> int:
    """Strictly read-only provenance audit of the live/default v59 DB (Phase 13).

    Inspects schema version + migration history, required v59 source-domain table presence, and row
    counts by project_key; never creates/migrates/projects/writes the live DB. rc 0 = v59 source-domain
    tables present (schema_only/populated_tropical/populated_other_projects); rc 1 = missing_v59_tables;
    rc 3 = controlled refusal (missing/unreadable/not-the-live DB)."""
    from .workflows.live_db_certification import (
        AUDIT_MISSING_TABLES,
        LiveDbCertificationError,
        run_live_db_provenance_audit,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_live_db_provenance_audit(
                live_db_path=Path(live_db_path) if live_db_path else None,
                work_root=Path(work_root) if work_root else None, project_key=project)
    except LiveDbCertificationError as exc:
        print(json.dumps({"command": "live-db-provenance-audit", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "live-db-provenance-audit"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 1 if report.get("decision") == AUDIT_MISSING_TABLES else 0


def cmd_live_db_readonly_certification(*, source_package: str, work_root: str, context_stamp: str,
                                       live_db_path: str | None, project: str) -> int:
    """Read-only certification of the live DB against a fresh non-live temp projection (Phase 13).

    Audits the live DB read-only, builds a fresh non-live temp v59 DB from the EXPLICIT Tropical source
    package, and compares tropical source-domain rows per table (byte-exact raw_json + canonical row
    digests). Never writes the live DB. rc 0 = certified_match; rc 1 = completed but not certified
    (schema_only/stale_or_mismatch/uncertified); rc 3 = controlled refusal (unsafe/missing/unreadable/
    not-the-live DB)."""
    from .workflows.live_db_certification import (
        CERT_MATCH,
        LiveDbCertificationError,
        run_live_db_readonly_certification,
    )
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_live_db_readonly_certification(
                source_package=Path(source_package), work_root=Path(work_root),
                context_stamp=context_stamp,
                live_db_path=Path(live_db_path) if live_db_path else None, project_key=project)
    except LiveDbCertificationError as exc:
        print(json.dumps({"command": "live-db-readonly-certification", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "live-db-readonly-certification"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == CERT_MATCH else 1


def cmd_live_db_source_domain_project(*, source_package: str, work_root: str, context_stamp: str,
                                      live_db_path: str | None, allow_live_db_write: bool,
                                      allow_replace_existing: bool, run_guarded_operator_check: bool,
                                      expect_budget_details: int | None,
                                      expect_cost_entries: int | None,
                                      expect_monthly: int | None, project: str) -> int:
    """Controlled live-DB source-domain projection (Phase 14; first gated live write).

    Builds a fresh non-live temp projection, BACKS UP the live DB, then in one transaction replaces only
    project_key='tropical' rows in the three v59 source-domain tables with rows copied from the temp DB,
    and reruns Phase 13 certification. Requires --allow-live-db-write. Optional --expect-* gate the temp
    projection counts (exact match before any write). rc 0 = certified_match; rc 1 = post-write
    certification not matched / not-ready (backup recorded for manual restore); rc 3 = controlled refusal
    (unsafe input / nonzero-WAL / schema or column mismatch / count mismatch / backup or transaction
    failure). Never migrates or directly projects the live DB; changes no production default."""
    from .workflows.live_db_source_domain_projection import (
        DECISION_CERTIFIED,
        LiveDbSourceDomainProjectionError,
        run_controlled_live_db_source_domain_projection,
    )
    expected = {
        k: v
        for k, v in (
            ("forecast_budget_details", expect_budget_details),
            ("forecast_cost_entries", expect_cost_entries),
            ("forecast_monthly_actuals_by_budget_code", expect_monthly),
        )
        if v is not None
    }
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_controlled_live_db_source_domain_projection(
                source_package=Path(source_package), work_root=Path(work_root),
                context_stamp=context_stamp,
                live_db_path=Path(live_db_path) if live_db_path else None, project_key=project,
                allow_live_db_write=allow_live_db_write,
                allow_replace_existing=allow_replace_existing,
                run_guarded_operator_check=run_guarded_operator_check,
                expected_counts=expected or None)
    except LiveDbSourceDomainProjectionError as exc:
        print(json.dumps({"command": "live-db-source-domain-project", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "live-db-source-domain-project"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_CERTIFIED else 1


def cmd_live_db_run_output_project(*, analysis_package: str, source_package: str, work_root: str,
                                   context_stamp: str, run_id: str, live_db_path: str | None,
                                   allow_live_db_write: bool, allow_replace_existing: bool,
                                   monthly_package: str | None, probability_package: str | None,
                                   comprehensive_package: str | None, staffing_package: str | None,
                                   accuracy_package: str | None, expect_outputs: int | None,
                                   expect_budget_codes: int | None, project: str) -> int:
    """Controlled live-DB run-output + decision-support projection (Phase 3; gated live write).

    Builds a fresh non-live temp projection (v59 -> forecast_runs anchor -> v63 -> v66), BACKS UP the
    live DB, then in one transaction replaces only project_key='tropical' rows in the run-graph tables
    with rows copied from the temp DB, and certifies live == a fresh reprojection. Requires
    --allow-live-db-write. rc 0 = certified; rc 1 = post-write certification not matched (backup
    recorded); rc 3 = controlled refusal. Never migrates/directly-projects the live DB; v59 is read,
    not written; changes no production default."""
    from .workflows.live_db_run_output_projection import (
        DECISION_CERTIFIED,
        LiveDbRunOutputProjectionError,
        run_controlled_live_db_run_output_projection,
    )

    def _p(v: str | None):
        return Path(v) if v else None

    expected = {
        k: v for k, v in (("forecast_outputs", expect_outputs),
                          ("forecast_output_budget_codes", expect_budget_codes)) if v is not None
    }
    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_controlled_live_db_run_output_projection(
                analysis_package=Path(analysis_package), source_package=Path(source_package),
                work_root=Path(work_root), context_stamp=context_stamp, run_id=run_id,
                live_db_path=_p(live_db_path), project_key=project,
                allow_live_db_write=allow_live_db_write,
                allow_replace_existing=allow_replace_existing,
                expected_counts=expected or None,
                monthly_package=_p(monthly_package), probability_package=_p(probability_package),
                comprehensive_package=_p(comprehensive_package), staffing_package=_p(staffing_package),
                accuracy_package=_p(accuracy_package))
    except LiveDbRunOutputProjectionError as exc:
        print(json.dumps({"command": "live-db-run-output-project", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "live-db-run-output-project"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_CERTIFIED else 1


def cmd_forecast_config_registry_promote(*, edited_config_root: str, work_root: str,
                                         context_stamp: str, live_db_path: str | None,
                                         allow_live_db_write: bool, snapshot_name: str,
                                         snapshot_reason: str, expect_item_count: int | None,
                                         project: str) -> int:
    """Gated certified promotion of an approved config-edit proposal into the live config DB (Phase E2).

    Builds the snapshot in a fresh non-live temp DB (avoiding the active-item duplication trap), BACKS UP
    the live DB, then in one transaction ADDITIVELY copies the new snapshot (+ backing sources/items)
    into the live DB and certifies the promoted snapshot byte/canonical-equivalent while asserting every
    pre-existing snapshot is unchanged. Requires --allow-live-db-write. rc 0 = certified; rc 1 =
    post-write certification not matched / not-ready (backup recorded); rc 3 = controlled refusal."""
    from .workflows.live_db_config_registry_promotion import (
        DECISION_CERTIFIED,
        LiveDbConfigRegistryPromotionError,
        run_live_db_config_registry_promotion,
    )

    try:
        with contextlib.redirect_stdout(sys.stderr):
            report = run_live_db_config_registry_promotion(
                edited_config_root=Path(edited_config_root), work_root=Path(work_root),
                context_stamp=context_stamp,
                live_db_path=Path(live_db_path) if live_db_path else None, project_key=project,
                allow_live_db_write=allow_live_db_write, snapshot_name=snapshot_name,
                snapshot_reason=snapshot_reason,
                expected_item_count=expect_item_count)
    except LiveDbConfigRegistryPromotionError as exc:
        print(json.dumps({"command": "forecast-config-registry-promote", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "forecast-config-registry-promote"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_CERTIFIED else 1


def cmd_db_certified_final_output(*, phase14_report: str, source_package: str, work_root: str,
                                  context_stamp: str, live_db_path: str | None,
                                  require_guarded_operator_check: bool, generate_final_csv: bool,
                                  run_id: str | None, project: str) -> int:
    """Controlled DB-certified final forecast output generation (Phase 15).

    Uses Phase 14 certified evidence as an eligibility gate, reruns Phase 13 read-only certification
    (require certified_match + counts consistent with Phase 14), then runs the Phase 12 guarded operator
    run under <work-root>/guarded (a fresh non-live temp DB drives the chain; the live DB is never
    executed against) and copies the approved DB-certified analysis package under <work-root>/final_output.
    --generate-final-csv is a controlled refusal (rc 1): Phase 15 does not synthesize the true integrated
    CSV (produced by forecast_comprehensive/monthly/probability, deferred). rc 0 = ready; rc 1 = not-ready
    (incl. CSV requested); rc 3 = controlled refusal (unsafe input / missing or mismatched certification)."""
    from .workflows.db_certified_final_output import (
        DECISION_READY,
        DbCertifiedFinalOutputError,
        run_db_certified_final_output,
    )
    try:
        # Keep stdout a clean machine-readable JSON channel: workflow chatter -> stderr.
        with contextlib.redirect_stdout(sys.stderr):
            report = run_db_certified_final_output(
                phase14_report=Path(phase14_report), source_package=Path(source_package),
                work_root=Path(work_root), context_stamp=context_stamp,
                live_db_path=Path(live_db_path) if live_db_path else None, project_key=project,
                require_guarded_operator_check=require_guarded_operator_check,
                generate_final_csv=generate_final_csv, run_id=run_id)
    except DbCertifiedFinalOutputError as exc:
        print(json.dumps({"command": "db-certified-final-output", "project": project,
                          "status": "refused", "reason": str(exc)}, indent=2))
        return 3
    out = {"command": "db-certified-final-output"}
    out.update(report)
    print(json.dumps(out, indent=2))
    return 0 if report.get("decision") == DECISION_READY else 1


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
        if name == "validate-crosswalk":
            # Phase 16: optionally resolve config from a DB config snapshot (default: file-backed).
            sp.add_argument("--config-source", choices=("file", "db_snapshot"), default="file",
                            help="Config source for the crosswalk (default: file-backed repo config).")
            sp.add_argument("--config-db-path", default=None,
                            help="Explicit non-live registry DB path (with --config-source db_snapshot).")
            sp.add_argument("--config-snapshot-id", default=None,
                            help="Config snapshot id to materialize (with --config-source db_snapshot).")
            sp.add_argument("--config-snapshot-root", default=None,
                            help="Explicit non-live work root to materialize the snapshot under.")
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
    # Phase 9 — controlled, default-off context->analysis workflow (orchestration only) from
    # explicit paths under <work-root>/<mode>. Modes: file | db | parity.
    ccap = sub.add_parser("controlled-context-analysis")
    ccap.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 9).")
    ccap.add_argument("--data-root", required=True,
                      help="Explicit forecast source data root for this controlled run.")
    ccap.add_argument("--work-root", required=True,
                      help="Explicit work root (outputs under <work-root>/<mode>; not under the "
                           "live data root).")
    ccap.add_argument("--context-stamp", required=True,
                      help="Deterministic context-package stamp for the run.")
    ccap.add_argument("--mode", required=True, choices=("file", "db", "parity"),
                      help="file (default-off DB), db (explicit temp DB), or parity (run both + "
                           "compare).")
    ccap.add_argument("--db-path", default=None,
                      help="Explicit temp SQLite DB path (required for db/parity; refuses the "
                           "live/default DB).")
    # Phase 10 — controlled DB-cutover-readiness gate (evidence only) over an explicit temp v59 DB.
    drp = sub.add_parser("db-cutover-readiness")
    drp.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 10).")
    drp.add_argument("--data-root", required=True,
                     help="Explicit forecast source data root for the readiness run.")
    drp.add_argument("--work-root", required=True,
                     help="Explicit work root (outputs under <work-root>/readiness; not under the "
                          "live data root).")
    drp.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the run.")
    drp.add_argument("--db-path", required=True,
                     help="Explicit temp/non-live v59 SQLite DB path (refuses the live/default DB).")
    # Phase I PR 1 — model-engines data + semantic readiness (read-only; no dependency, no core edit).
    mer = sub.add_parser("model-engines-readiness")
    mer.add_argument("--project", required=True, help="Project key (only 'tropical').")
    mer.add_argument("--context-package", required=True,
                     help="Explicit EXISTING context package directory (read-only). Must contain "
                          "canonical/monthly_actuals_by_budget_code.jsonl and "
                          "canonical/budget_codes.jsonl.")
    mer.add_argument("--db-path", required=True,
                     help="Explicit SQLite DB path for the forecasting semantic gates (opened "
                          "read-only; the live hb_assistant DB is acceptable read-only).")
    mer.add_argument("--work-root", required=True,
                     help="Explicit work root (report under <work-root>/model_engines_readiness; "
                          "not under the live data root).")
    mer.add_argument("--gate-mode", default="warn", choices=("warn", "strict"),
                     help="Forecasting semantic-gate mode (default: warn).")
    # Production-forecast accuracy/trust gate — verdict over an existing intelligence package.
    fag = sub.add_parser("forecast-accuracy-gate")
    fag.add_argument("--project", required=True, help="Project key (only 'tropical').")
    fag.add_argument("--package", default=None,
                     help="Explicit forecast_accuracy_next_package_* directory to score "
                          "(else use --data-root to discover the latest).")
    fag.add_argument("--data-root", default=None,
                     help="Data root to discover the latest forecast_accuracy_next_package_<project>_* "
                          "(used when --package is omitted).")
    fag.add_argument("--work-root", required=True,
                     help="Explicit work root (report under <work-root>/forecast_accuracy_gate; "
                          "not under the live data root).")
    # Phase 11 — controlled temp-DB preparation + readiness rehearsal from an explicit source package.
    tdr = sub.add_parser("temp-db-readiness-rehearsal")
    tdr.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 11).")
    tdr.add_argument("--source-package", required=True,
                     help="Explicit Tropical twn_cost_forecast_json_package directory to project.")
    tdr.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (temp DB + readiness + report under it).")
    tdr.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the readiness run.")
    tdr.add_argument("--db-path", default=None,
                     help="Optional explicit temp DB path (must be under --work-root, non-live, and "
                          "not already exist); derived under <work-root>/temp_dbs/ if omitted.")
    # Phase 12 — controlled guarded DB operator-run package (operator handoff) atop the rehearsal.
    gor = sub.add_parser("guarded-db-operator-run")
    gor.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 12).")
    gor.add_argument("--source-package", required=True,
                     help="Explicit Tropical twn_cost_forecast_json_package directory to project.")
    gor.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (rehearsal + manifest under it).")
    gor.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the operator run.")
    gor.add_argument("--db-path", default=None,
                     help="Optional explicit temp DB path (must be under --work-root, non-live, and "
                          "not already exist); derived under <work-root>/temp_dbs/ if omitted.")
    gor.add_argument("--allow-certified-live-db", action="store_true",
                     help="Phase 13: permit a live/default --db-path ONLY with a certified_match "
                          "--live-db-certification; execution still uses a fresh non-live temp DB.")
    gor.add_argument("--live-db-certification", default=None,
                     help="Phase 13: path to a certified_match live-DB certification report (required "
                          "when --db-path is the live DB and --allow-certified-live-db is set).")
    # Phase 13 — read-only live DB provenance audit (no migrate/project/write of the live DB).
    lpa = sub.add_parser("live-db-provenance-audit")
    lpa.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 13).")
    lpa.add_argument("--work-root", default=None,
                     help="Optional explicit non-live evidence root to write the audit report under.")
    lpa.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path (tests only); resolves the default live DB "
                          "if omitted.")
    # Phase 13 — read-only certification of the live DB vs a fresh non-live temp projection.
    lrc = sub.add_parser("live-db-readonly-certification")
    lrc.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 13).")
    lrc.add_argument("--source-package", required=True,
                     help="Explicit Tropical twn_cost_forecast_json_package directory to project.")
    lrc.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (temp DB + certification report under it).")
    lrc.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the certification run.")
    lrc.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path (tests only); resolves the default live DB "
                          "if omitted.")
    # Phase 14 — controlled live-DB source-domain projection (first gated live write).
    lsp = sub.add_parser("live-db-source-domain-project")
    lsp.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 14).")
    lsp.add_argument("--source-package", required=True,
                     help="Explicit Tropical twn_cost_forecast_json_package directory to project.")
    lsp.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (temp DB + backup + report + sub-runs under it).")
    lsp.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the run.")
    lsp.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path (tests only); resolves the default live DB "
                          "if omitted.")
    lsp.add_argument("--allow-live-db-write", action="store_true",
                     help="Required gate to actually write the live DB (refused otherwise).")
    lsp.add_argument("--allow-replace-existing", action="store_true",
                     help="Permit replacing existing tropical source-domain rows (tropical only).")
    lsp.add_argument("--run-guarded-operator-check", action="store_true",
                     help="After certification, run the Phase 12 certified-equivalence guarded check.")
    lsp.add_argument("--expect-budget-details", type=int, default=None,
                     help="Optional exact expected temp count for forecast_budget_details.")
    lsp.add_argument("--expect-cost-entries", type=int, default=None,
                     help="Optional exact expected temp count for forecast_cost_entries.")
    lsp.add_argument("--expect-monthly", type=int, default=None,
                     help="Optional exact expected temp count for forecast_monthly_actuals_by_budget_code.")
    # Phase 3 (DB-native remediation) — gated live write of the run graph (run anchor + v63 + v66).
    lro = sub.add_parser("live-db-run-output-project")
    lro.add_argument("--project", required=True, help="Project key (only 'tropical').")
    lro.add_argument("--analysis-package", required=True,
                     help="Explicit forecast analysis package directory (the run-output spine).")
    lro.add_argument("--source-package", required=True,
                     help="Explicit twn_cost_forecast_json_package (re-projects v59 in the temp DBs).")
    lro.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (temp DBs + backup + report under it).")
    lro.add_argument("--context-stamp", required=True, help="Deterministic context stamp for the run.")
    lro.add_argument("--run-id", required=True, help="forecast_runs anchor key for this run.")
    lro.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path (tests only); resolves the default if omitted.")
    lro.add_argument("--allow-live-db-write", action="store_true",
                     help="Required gate to actually write the live DB (refused otherwise).")
    lro.add_argument("--allow-replace-existing", action="store_true",
                     help="Permit replacing existing tropical run-output/decision-support rows.")
    lro.add_argument("--monthly-package", default=None, help="Optional forecast_monthly package.")
    lro.add_argument("--probability-package", default=None, help="Optional forecast_probability package.")
    lro.add_argument("--comprehensive-package", default=None, help="Optional forecast_comprehensive package.")
    lro.add_argument("--staffing-package", default=None, help="Optional forecast_staffing_plan package.")
    lro.add_argument("--accuracy-package", default=None, help="Optional forecast_accuracy package.")
    lro.add_argument("--expect-outputs", type=int, default=None,
                     help="Optional exact expected temp count for forecast_outputs.")
    lro.add_argument("--expect-budget-codes", type=int, default=None,
                     help="Optional exact expected temp count for forecast_output_budget_codes.")
    # Phase E2 — gated certified promotion of an approved config-edit proposal into the live config DB.
    pcp = sub.add_parser("forecast-config-registry-promote")
    pcp.add_argument("--project", required=True, help="Project key (only 'tropical').")
    pcp.add_argument("--edited-config-root", required=True,
                     help="Explicit edited config tree (the approved proposal's edited_config dir).")
    pcp.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (temp DB + backup + report under it).")
    pcp.add_argument("--context-stamp", required=True, help="Deterministic stamp for the run.")
    pcp.add_argument("--snapshot-name", required=True, help="Name for the promoted snapshot.")
    pcp.add_argument("--snapshot-reason", required=True, help="Reason recorded on the promoted snapshot.")
    pcp.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path (tests only); resolves the default live DB "
                          "if omitted.")
    pcp.add_argument("--allow-live-db-write", action="store_true",
                     help="Required gate to actually write the live config DB (refused otherwise).")
    pcp.add_argument("--expect-item-count", type=int, default=None,
                     help="Optional exact expected snapshot item_count (binds promotion to the approval).")
    # Phase 15 — controlled DB-certified final forecast output generation (no production default flip).
    dfo = sub.add_parser("db-certified-final-output")
    dfo.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 15).")
    dfo.add_argument("--phase14-report", required=True,
                     help="Explicit Phase 14 live-DB source-domain projection report (certified evidence).")
    dfo.add_argument("--source-package", required=True,
                     help="Explicit Tropical twn_cost_forecast_json_package directory (must match Phase 14).")
    dfo.add_argument("--work-root", required=True,
                     help="Explicit non-live work root (guarded run + final_output + report under it).")
    dfo.add_argument("--context-stamp", required=True,
                     help="Deterministic context-package stamp for the run.")
    dfo.add_argument("--live-db-path", default=None,
                     help="Optional explicit live DB path for read-only verification (must match Phase 14).")
    dfo.add_argument("--require-guarded-operator-check", action="store_true", default=True,
                     help="Require the guarded operator run to approve the DB-backed chain (default on).")
    dfo.add_argument("--generate-final-csv", action="store_true",
                     help="Request the final integrated CSV — controlled refusal (rc 1); out of scope.")
    dfo.add_argument("--run-id", default=None, help="Optional run id recorded in the report.")
    # Phase 16 — governed forecast config registry (import / snapshot / export / parity).
    fci = sub.add_parser("forecast-config-import")
    fci.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 16).")
    fci.add_argument("--config-root", required=True,
                     help="Directory containing the config/ subtree (or the config/ dir itself).")
    fci.add_argument("--db-path", required=True,
                     help="Explicit registry DB path (non-live temp; live requires --allow-live-db-write).")
    fci.add_argument("--import-run-id", default=None, help="Optional deterministic import run id.")
    fci.add_argument("--allow-live-db-write", action="store_true",
                     help="Required gate to import into the live/default DB (refused otherwise).")
    fcs = sub.add_parser("forecast-config-snapshot")
    fcs.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 16).")
    fcs.add_argument("--db-path", required=True, help="Explicit registry DB path.")
    fcs.add_argument("--snapshot-name", required=True, help="Snapshot name.")
    fcs.add_argument("--snapshot-reason", required=True, help="Operator reason for the snapshot.")
    fcs.add_argument("--out-root", required=True,
                     help="Explicit non-live work root to materialize the snapshot under.")
    fce = sub.add_parser("forecast-config-export")
    fce.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 16).")
    fce.add_argument("--db-path", required=True, help="Explicit registry DB path.")
    fce.add_argument("--snapshot-id", default=None,
                     help="Snapshot id to export (default: active items).")
    fce.add_argument("--out-root", required=True,
                     help="Explicit non-live out root (never the repo config/ dir).")
    fcp16 = sub.add_parser("forecast-config-db-parity")
    fcp16.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 16).")
    fcp16.add_argument("--config-root", required=True,
                       help="Directory containing the config/ subtree (or the config/ dir itself).")
    fcp16.add_argument("--work-root", required=True,
                       help="Explicit non-live work root for the temp registry DB + materialization.")
    fcp16.add_argument("--db-path", default=None,
                       help="Optional explicit non-live registry DB path (refuses the live DB).")
    # Phase 17 — DB-backed config consumer proof for forecast_model_controls (read-only on the live DB).
    fmcp17 = sub.add_parser("forecast-model-controls-db-config-proof")
    fmcp17.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 17).")
    fmcp17.add_argument("--live-db-path", required=True,
                        help="Live (v60) DB holding the Phase 16 config snapshot; opened READ-ONLY.")
    fmcp17.add_argument("--config-snapshot-id", required=True,
                        help="Phase 16 config snapshot id to materialize and consume.")
    fmcp17.add_argument("--work-root", required=True,
                        help="Explicit non-live work root (materialized config + both output packages).")
    fmcp17.add_argument("--run-stamp", default=None,
                        help="Deterministic frozen stamp shared by both runs (default 20260101_000000).")
    fmcp17.add_argument("--data-root", default=None,
                        help="Override the forecast data root (must hold a context package); default cfg.")
    fmcp17.add_argument("--source-config-root", default=None,
                        help="Override the file-backed config base; default the CFR subproject root.")
    fmcp17.add_argument("--expect-item-count", type=int, default=194,
                        help="Required snapshot item count (live Phase 16 baseline 194; use -1 to skip).")
    fmcp17.add_argument("--no-require-live-snapshot", action="store_true",
                        help="Dev/test only: accept a non-live v60 DB (default requires the live DB).")
    # Phase 18 — DB-backed config consumer proof for forecast_monthly (read-only on the live DB).
    fmp18 = sub.add_parser("forecast-monthly-db-config-proof")
    fmp18.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 18).")
    fmp18.add_argument("--live-db-path", required=True,
                       help="Live (v60) DB holding the Phase 16 config snapshot; opened READ-ONLY.")
    fmp18.add_argument("--config-snapshot-id", required=True,
                       help="Phase 16 config snapshot id to materialize and consume.")
    fmp18.add_argument("--work-root", required=True,
                       help="Explicit work root (materialized config + both output packages); must be "
                            "OUTSIDE the live forecast root, source config tree, and live DB directory.")
    fmp18.add_argument("--run-stamp", default=None,
                       help="Deterministic frozen stamp shared by both runs (default 20260101_000000).")
    fmp18.add_argument("--data-root", default=None,
                       help="Forecast data root (read-only INPUT; may be the live forecast root); must "
                            "hold the three monthly predecessor packages. Default cfg default_data_root.")
    fmp18.add_argument("--source-config-root", default=None,
                       help="Override the file-backed config base; default the CFR subproject root.")
    fmp18.add_argument("--expect-item-count", type=int, default=194,
                       help="Required snapshot item count (live Phase 16 baseline 194; use -1 to skip).")
    fmp18.add_argument("--no-require-live-snapshot", action="store_true",
                       help="Dev/test only: accept a non-live v60 DB (default requires the live DB).")
    fmp18.add_argument("--preflight-stability-seconds", type=float, default=2.0,
                       help="Live-DB quiescence preflight window: sample the live DB at the start and end "
                            "of this window and refuse (rc 3) if it moved (default 2.0).")
    # Phase 19 — DB-backed config consumer proof for forecast_probability (read-only on the live DB).
    fpp19 = sub.add_parser("forecast-probability-db-config-proof")
    fpp19.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 19).")
    fpp19.add_argument("--live-db-path", required=True,
                       help="Live (v60) DB holding the Phase 16 config snapshot; opened READ-ONLY.")
    fpp19.add_argument("--config-snapshot-id", required=True,
                       help="Phase 16 config snapshot id to materialize and consume.")
    fpp19.add_argument("--work-root", required=True,
                       help="Explicit work root (materialized config + both output packages); must be "
                            "OUTSIDE the live forecast root, source config tree, live DB directory, and "
                            "the data root / source packages.")
    fpp19.add_argument("--run-stamp", default=None,
                       help="Deterministic frozen stamp shared by both runs (default 20260101_000000).")
    fpp19.add_argument("--data-root", default=None,
                       help="Forecast data root (read-only INPUT; may be the live forecast root); must "
                            "hold the accepted-accuracy + monthly predecessor packages. Default cfg.")
    fpp19.add_argument("--source-config-root", default=None,
                       help="Override the file-backed config base; default the CFR subproject root.")
    fpp19.add_argument("--expect-item-count", type=int, default=194,
                       help="Required snapshot item count (live Phase 16 baseline 194; use -1 to skip).")
    fpp19.add_argument("--no-require-live-snapshot", action="store_true",
                       help="Dev/test only: accept a non-live v60 DB (default requires the live DB).")
    fpp19.add_argument("--preflight-stability-seconds", type=float, default=2.0,
                       help="Live-DB quiescence preflight window: refuse (rc 3) if the live DB moved "
                            "(default 2.0).")
    fpp19.add_argument("--runs", type=int, default=10000, help="Monte Carlo runs (default 10000).")
    fpp19.add_argument("--seed", type=int, default=20260614, help="Deterministic RNG seed (default 20260614).")
    fpp19.add_argument("--forecast-start-month", default=None,
                       help="Override the forecast start month (YYYY-MM); default the monthly window.")
    # Phase 20 — DB-backed config consumer proof for forecast_comprehensive (read-only on the live DB).
    fcp20 = sub.add_parser("forecast-comprehensive-db-config-proof")
    fcp20.add_argument("--project", required=True, help="Project key (only 'tropical' in Phase 20).")
    fcp20.add_argument("--live-db-path", required=True,
                       help="Live (v60) DB holding the Phase 16 config snapshot; opened READ-ONLY.")
    fcp20.add_argument("--config-snapshot-id", required=True,
                       help="Phase 16 config snapshot id to materialize and consume.")
    fcp20.add_argument("--work-root", required=True,
                       help="Explicit work root (materialized config + both output packages); must be "
                            "OUTSIDE the live forecast root, source config tree, live DB directory, and "
                            "the data root / source packages.")
    fcp20.add_argument("--run-stamp", default=None,
                       help="Deterministic frozen stamp shared by both runs (default 20260101_000000).")
    fcp20.add_argument("--data-root", default=None,
                       help="Forecast data root (read-only INPUT; may be the live forecast root); must hold "
                            "context+intelligence+monthly (+cost-frequency if frequency_enabled). Default cfg.")
    fcp20.add_argument("--source-config-root", default=None,
                       help="Override the file-backed config base; default the CFR subproject root.")
    fcp20.add_argument("--expect-item-count", type=int, default=194,
                       help="Required snapshot item count (live Phase 16 baseline 194; use -1 to skip).")
    fcp20.add_argument("--no-require-live-snapshot", action="store_true",
                       help="Dev/test only: accept a non-live v60 DB (default requires the live DB).")
    fcp20.add_argument("--preflight-stability-seconds", type=float, default=2.0,
                       help="Live-DB quiescence preflight window: refuse (rc 3) if the live DB moved "
                            "(default 2.0).")

    fdcg = sub.add_parser("forecast-db-config-backed-generate")
    fdcg.add_argument("--project", default="tropical", help="Project key (only 'tropical').")
    fdcg.add_argument("--generator-kind", default="comprehensive",
                      choices=["comprehensive", "model_controls", "monthly", "probability"],
                      help="Which generator to run from the live config snapshot (default comprehensive).")
    fdcg.add_argument("--live-db-path", required=True,
                      help="Live (v60) DB holding the config snapshot; opened READ-ONLY.")
    fdcg.add_argument("--config-snapshot-id", default=None,
                      help="Config snapshot id to consume (default: the latest live snapshot).")
    fdcg.add_argument("--work-root", required=True,
                      help="Explicit work root (materialized config + output package); must be OUTSIDE "
                           "the live forecast root, source config tree, live DB directory, and data root.")
    fdcg.add_argument("--run-stamp", default=None,
                      help="Deterministic frozen stamp (default 20260101_000000).")
    fdcg.add_argument("--data-root", default=None,
                      help="Forecast data root (read-only INPUT); must hold context+intelligence+monthly "
                           "(+cost-frequency if frequency_enabled). Default from cfg.")
    fdcg.add_argument("--source-config-root", default=None,
                      help="Override the file-backed config base; default the CFR subproject root.")
    fdcg.add_argument("--no-require-live-snapshot", action="store_true",
                      help="Dev/test only: accept a non-live v60 DB (default requires the live DB).")
    fdcg.add_argument("--prove-file-equivalence", action="store_true",
                      help="Evidence only: also run file-backed and compare (default off; meaningful only "
                           "when config has not diverged from the on-disk files).")
    fdcg.add_argument("--preflight-stability-seconds", type=float, default=2.0,
                      help="Live-DB quiescence preflight window (default 2.0).")
    fdcg.add_argument("--runs", type=int, default=10000,
                      help="Probability generator only: Monte-Carlo run count (default 10000).")
    fdcg.add_argument("--seed", type=int, default=20260614,
                      help="Probability generator only: deterministic seed (default 20260614).")
    fdcg.add_argument("--forecast-start-month", default=None,
                      help="Probability/monthly generators only: forecast start month override.")
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
        return cmd_validate_crosswalk(
            cfg, config_source=getattr(args, "config_source", "file"),
            config_db_path=getattr(args, "config_db_path", None),
            config_snapshot_id=getattr(args, "config_snapshot_id", None),
            config_snapshot_root=getattr(args, "config_snapshot_root", None))
    if args.command == "forecast-config-import":
        return cmd_forecast_config_import(
            project=args.project, config_root=args.config_root, db_path=args.db_path,
            import_run_id=args.import_run_id, allow_live_db_write=args.allow_live_db_write)
    if args.command == "forecast-config-snapshot":
        return cmd_forecast_config_snapshot(
            project=args.project, db_path=args.db_path, snapshot_name=args.snapshot_name,
            snapshot_reason=args.snapshot_reason, out_root=args.out_root)
    if args.command == "forecast-config-export":
        return cmd_forecast_config_export(
            project=args.project, db_path=args.db_path, snapshot_id=args.snapshot_id,
            out_root=args.out_root)
    if args.command == "forecast-config-db-parity":
        return cmd_forecast_config_db_parity(
            project=args.project, config_root=args.config_root, work_root=args.work_root,
            db_path=args.db_path)
    if args.command == "forecast-model-controls-db-config-proof":
        return cmd_forecast_model_controls_db_config_proof(
            project=args.project, live_db_path=args.live_db_path,
            config_snapshot_id=args.config_snapshot_id, work_root=args.work_root,
            run_stamp=args.run_stamp, data_root=args.data_root,
            source_config_root=args.source_config_root,
            expect_item_count=(None if args.expect_item_count == -1 else args.expect_item_count),
            require_live_snapshot=not args.no_require_live_snapshot)
    if args.command == "forecast-monthly-db-config-proof":
        return cmd_forecast_monthly_db_config_proof(
            project=args.project, live_db_path=args.live_db_path,
            config_snapshot_id=args.config_snapshot_id, work_root=args.work_root,
            run_stamp=args.run_stamp, data_root=args.data_root,
            source_config_root=args.source_config_root,
            expect_item_count=(None if args.expect_item_count == -1 else args.expect_item_count),
            require_live_snapshot=not args.no_require_live_snapshot,
            preflight_stability_seconds=args.preflight_stability_seconds)
    if args.command == "forecast-probability-db-config-proof":
        return cmd_forecast_probability_db_config_proof(
            project=args.project, live_db_path=args.live_db_path,
            config_snapshot_id=args.config_snapshot_id, work_root=args.work_root,
            run_stamp=args.run_stamp, data_root=args.data_root,
            source_config_root=args.source_config_root,
            expect_item_count=(None if args.expect_item_count == -1 else args.expect_item_count),
            require_live_snapshot=not args.no_require_live_snapshot,
            preflight_stability_seconds=args.preflight_stability_seconds,
            runs=args.runs, seed=args.seed, forecast_start_month=args.forecast_start_month)
    if args.command == "forecast-comprehensive-db-config-proof":
        return cmd_forecast_comprehensive_db_config_proof(
            project=args.project, live_db_path=args.live_db_path,
            config_snapshot_id=args.config_snapshot_id, work_root=args.work_root,
            run_stamp=args.run_stamp, data_root=args.data_root,
            source_config_root=args.source_config_root,
            expect_item_count=(None if args.expect_item_count == -1 else args.expect_item_count),
            require_live_snapshot=not args.no_require_live_snapshot,
            preflight_stability_seconds=args.preflight_stability_seconds)
    if args.command == "forecast-db-config-backed-generate":
        return cmd_forecast_db_config_backed_generate(
            project=args.project, generator_kind=args.generator_kind,
            live_db_path=args.live_db_path,
            config_snapshot_id=args.config_snapshot_id, work_root=args.work_root,
            run_stamp=args.run_stamp, data_root=args.data_root,
            source_config_root=args.source_config_root,
            require_live_snapshot=not args.no_require_live_snapshot,
            prove_file_equivalence=args.prove_file_equivalence,
            preflight_stability_seconds=args.preflight_stability_seconds,
            runs=args.runs, seed=args.seed,
            forecast_start_month=args.forecast_start_month)
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
    if args.command == "controlled-context-analysis":
        return cmd_controlled_context_analysis(data_root=args.data_root, work_root=args.work_root,
                                               context_stamp=args.context_stamp, mode=args.mode,
                                               db_path=args.db_path, project=args.project)
    if args.command == "db-cutover-readiness":
        return cmd_db_cutover_readiness(data_root=args.data_root, work_root=args.work_root,
                                        context_stamp=args.context_stamp, db_path=args.db_path,
                                        project=args.project)
    if args.command == "model-engines-readiness":
        return cmd_model_engines_readiness(context_package=args.context_package,
                                           db_path=args.db_path, work_root=args.work_root,
                                           project=args.project, gate_mode=args.gate_mode)
    if args.command == "forecast-accuracy-gate":
        return cmd_forecast_accuracy_gate(package=args.package, data_root=args.data_root,
                                          work_root=args.work_root, project=args.project)
    if args.command == "temp-db-readiness-rehearsal":
        return cmd_temp_db_readiness_rehearsal(source_package=args.source_package,
                                               work_root=args.work_root,
                                               context_stamp=args.context_stamp,
                                               db_path=args.db_path, project=args.project)
    if args.command == "guarded-db-operator-run":
        return cmd_guarded_db_operator_run(source_package=args.source_package,
                                           work_root=args.work_root,
                                           context_stamp=args.context_stamp,
                                           db_path=args.db_path, project=args.project,
                                           allow_certified_live_db=args.allow_certified_live_db,
                                           live_db_certification=args.live_db_certification)
    if args.command == "live-db-provenance-audit":
        return cmd_live_db_provenance_audit(work_root=args.work_root,
                                            live_db_path=args.live_db_path, project=args.project)
    if args.command == "live-db-readonly-certification":
        return cmd_live_db_readonly_certification(source_package=args.source_package,
                                                  work_root=args.work_root,
                                                  context_stamp=args.context_stamp,
                                                  live_db_path=args.live_db_path,
                                                  project=args.project)
    if args.command == "live-db-source-domain-project":
        return cmd_live_db_source_domain_project(
            source_package=args.source_package, work_root=args.work_root,
            context_stamp=args.context_stamp, live_db_path=args.live_db_path,
            allow_live_db_write=args.allow_live_db_write,
            allow_replace_existing=args.allow_replace_existing,
            run_guarded_operator_check=args.run_guarded_operator_check,
            expect_budget_details=args.expect_budget_details,
            expect_cost_entries=args.expect_cost_entries,
            expect_monthly=args.expect_monthly, project=args.project)
    if args.command == "live-db-run-output-project":
        return cmd_live_db_run_output_project(
            analysis_package=args.analysis_package, source_package=args.source_package,
            work_root=args.work_root, context_stamp=args.context_stamp, run_id=args.run_id,
            live_db_path=args.live_db_path, allow_live_db_write=args.allow_live_db_write,
            allow_replace_existing=args.allow_replace_existing,
            monthly_package=args.monthly_package, probability_package=args.probability_package,
            comprehensive_package=args.comprehensive_package, staffing_package=args.staffing_package,
            accuracy_package=args.accuracy_package, expect_outputs=args.expect_outputs,
            expect_budget_codes=args.expect_budget_codes, project=args.project)
    if args.command == "forecast-config-registry-promote":
        return cmd_forecast_config_registry_promote(
            edited_config_root=args.edited_config_root, work_root=args.work_root,
            context_stamp=args.context_stamp, live_db_path=args.live_db_path,
            allow_live_db_write=args.allow_live_db_write, snapshot_name=args.snapshot_name,
            snapshot_reason=args.snapshot_reason, expect_item_count=args.expect_item_count,
            project=args.project)
    if args.command == "db-certified-final-output":
        return cmd_db_certified_final_output(
            phase14_report=args.phase14_report, source_package=args.source_package,
            work_root=args.work_root, context_stamp=args.context_stamp,
            live_db_path=args.live_db_path,
            require_guarded_operator_check=args.require_guarded_operator_check,
            generate_final_csv=args.generate_final_csv, run_id=args.run_id,
            project=args.project)
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
