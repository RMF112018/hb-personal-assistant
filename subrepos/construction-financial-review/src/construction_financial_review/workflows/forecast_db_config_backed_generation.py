"""Wire ``forecast_comprehensive`` to CONSUME the live DB config snapshot (productionizes Phase 20).

Phases 17-20 PROVED the real generators produce parity-equivalent output when they read a materialized
DB config snapshot through the ``CFR_CONFIG_ROOT`` bridge. This workflow productionizes that path for
``forecast_comprehensive``: it materializes the live config snapshot (read-only) and runs the real
comprehensive generator against it, emitting the integrated package with ``config_snapshot_consumed:
True`` so a PROMOTED config snapshot actually drives generation (not just the viewer).

Why a fidelity gate, not an output-parity gate: once an operator promotes a config edit, the DB config
LEGITIMATELY differs from the on-disk file config, so a file-vs-DB output-parity gate would wrongly
block the intended change. The safety invariant here is **materialization fidelity** — that the
materialized config tree faithfully round-trips back to the snapshot it was read from
(re-import -> re-snapshot -> ``snapshot_sha256`` + ``item_count`` equal the snapshot's STORED values).
This is independent of whether config diverged from the on-disk files.

Fail-closed (raises -> CLI rc 3) BEFORE any generation on: non-tropical project; unsafe work root; a
live DB missing/not v60/lacking the 4 config tables; (when required) not the live DB; no snapshot to
consume; a non-quiescent live DB; a missing required predecessor package (context/intelligence/monthly);
a missing cost-frequency package when ``frequency_enabled`` (so comprehensive never generates it into the
read-only data root); or a fidelity-gate mismatch. Live DB is opened ``mode=ro`` only — never written,
migrated, or copied. Reuses the Phase 20 proof helpers (single source of truth).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .. import config_registry as cr
from ..common.config_root import ENV_CONFIG_ROOT
from . import forecast_comprehensive_db_config_proof as proof
from . import live_db_certification as cert

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = proof.REQUIRED_SCHEMA_VERSION
REQUIRED_CONFIG_TABLES = proof.REQUIRED_CONFIG_TABLES
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "forecast_db_config_backed_generation_report.json"
MATERIALIZE_SUBDIR = "db_snapshot_config"
DB_BACKED_SUBDIR = "db_config_backed"
FILE_BACKED_SUBDIR = "file_backed"
FIDELITY_DB_SUBDIR = "fidelity_db"
DEFAULT_RUN_STAMP = proof.DEFAULT_RUN_STAMP
DEFAULT_PREFLIGHT_STABILITY_SECONDS = proof.DEFAULT_PREFLIGHT_STABILITY_SECONDS

STATUS_GENERATED = "generated"
STATUS_VALIDATION_FAILED = "generated_validation_failed"

REASON_NO_SNAPSHOT = "no_config_snapshot"
REASON_FIDELITY = "config_fidelity_failed"
REASON_PREDECESSOR = "predecessor_packages_missing"
REASON_COST_FREQ = "cost_frequency_package_missing"
REASON_NOT_QUIESCENT = "live_db_not_quiescent"
REASON_LIVE_MUTATED = "live_db_mutated_during_run"


class ForecastDbConfigGenerationError(RuntimeError):
    """Raised when DB-config-backed generation is refused (fail closed; no soft fallback).

    The first ``:``-delimited token of the message is a stable coded reason (see ``REASON_*``) so the
    caller can map it to a path-free, user-facing message.
    """


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastDbConfigGenerationError(message)


def _select_snapshot(pin: Any, project_key: str, config_snapshot_id: str | None) -> tuple[str, int, str, str]:
    """Return (config_snapshot_id, item_count, snapshot_sha256, snapshot_name) for the snapshot to consume.

    Explicit id if given; otherwise the latest snapshot for the project (DESC by created_utc).
    """
    if config_snapshot_id:
        row = pin.execute(
            "SELECT config_snapshot_id, item_count, snapshot_sha256, snapshot_name "
            "FROM forecast_config_snapshots WHERE config_snapshot_id = ? AND project_key = ?",
            (config_snapshot_id, project_key),
        ).fetchone()
        _require(row is not None, f"{REASON_NO_SNAPSHOT}: config_snapshot_id not found {config_snapshot_id}")
    else:
        row = pin.execute(
            "SELECT config_snapshot_id, item_count, snapshot_sha256, snapshot_name "
            "FROM forecast_config_snapshots WHERE project_key = ? "
            "ORDER BY snapshot_created_utc DESC, config_snapshot_id LIMIT 1",
            (project_key,),
        ).fetchone()
        _require(row is not None, f"{REASON_NO_SNAPSHOT}: no snapshot to consume for {project_key}")
    return (row[0], int(row[1]), str(row[2]), str(row[3]))


def run_forecast_db_config_backed_generation(
    *,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path,
    work_root: Path,
    data_root: Path | None = None,
    config_snapshot_id: str | None = None,
    run_stamp: str | None = None,
    source_config_root: Path | None = None,
    require_live_snapshot: bool = True,
    prove_file_equivalence: bool = False,
    preflight_stability_seconds: float = DEFAULT_PREFLIGHT_STABILITY_SECONDS,
) -> dict[str, Any]:
    """Generate the comprehensive forecast package consuming the live DB config snapshot."""
    _require(project_key == SUPPORTED_PROJECT_KEY, f"unsupported project_key {project_key!r}")
    _require(bool(work_root), "work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    run_stamp = run_stamp or DEFAULT_RUN_STAMP
    _require(bool(live_db_path), "live_db_path is required")
    live_db_path = Path(live_db_path)
    _require(live_db_path.exists(), f"live DB not found: {live_db_path}")
    if require_live_snapshot:
        _require(cr._is_live_db(live_db_path), f"live_db_path is not the live/default DB: {live_db_path}")

    db_inventory_tables = proof._db_inventory_tables()
    comp_root = proof._comprehensive_subproject_root()
    pin = cert._ro_conn(live_db_path)
    try:
        vrow = pin.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(vrow[0]) if vrow and vrow[0] is not None else 0
        _require(
            schema_version >= REQUIRED_SCHEMA_VERSION,
            f"live DB schema version {schema_version} < {REQUIRED_SCHEMA_VERSION} (config registry)",
        )
        for t in REQUIRED_CONFIG_TABLES:
            _require(proof._table_exists(pin, t), f"live DB missing config registry table: {t}")

        sel_id, stored_item_count, stored_sha, snapshot_name = _select_snapshot(
            pin, project_key, config_snapshot_id
        )

        if source_config_root is None:
            source_config_root = Path(cr.__file__).resolve().parents[2]
        source_config_root = Path(source_config_root)
        _require(source_config_root.exists(), f"source_config_root not found: {source_config_root}")

        prev_env = os.environ.pop(ENV_CONFIG_ROOT, None)
        try:
            base_cfg = proof._load_project_cfg(project_key)
        finally:
            if prev_env is not None:
                os.environ[ENV_CONFIG_ROOT] = prev_env
        eff_data_root = Path(data_root) if data_root is not None else Path(base_cfg["default_data_root"])
        _require(
            eff_data_root.exists() and eff_data_root.is_dir(),
            f"data_root not found or not a directory: {eff_data_root}",
        )

        for label, parent in (
            ("live forecast root", proof._LIVE_ROOT),
            ("source config tree", source_config_root),
            ("live DB directory", live_db_path.parent),
            ("data root / source packages", eff_data_root),
        ):
            _require(
                not proof._is_under(work_root, parent),
                f"work_root is at/under the {label} (refused): {work_root}",
            )

        # Required predecessor packages + cost-frequency guard (BEFORE invoking — comprehensive
        # SystemExits without predecessors and would GENERATE cost_frequency into the read-only data root).
        for ptype, glob in proof._REQUIRED_PACKAGE_GLOBS:
            _require(
                proof._present(eff_data_root, glob),
                f"{REASON_PREDECESSOR}: required predecessor package not found: {ptype}",
            )
        frequency_enabled = proof._frequency_enabled(base_cfg)
        cost_freq_present = proof._present(eff_data_root, proof._COST_FREQUENCY_GLOB)
        if frequency_enabled:
            _require(cost_freq_present, f"{REASON_COST_FREQ}: forecast_cost_frequency package missing")
        present_map = {
            p: proof._present(eff_data_root, g)
            for p, g in (*proof._REQUIRED_PACKAGE_GLOBS, *proof._OPTIONAL_PACKAGE_GLOBS)
        }
        predecessor_packages_read = sorted(p for p, present in present_map.items() if present)

        # Quiescence preflight (BEFORE materialize).
        pf_a = proof._live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        if preflight_stability_seconds > 0:
            time.sleep(preflight_stability_seconds)
        pf_b = proof._live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        pf_drift = proof._state_drift(pf_a, pf_b)
        _require(not pf_drift, f"{REASON_NOT_QUIESCENT}: live DB changed during preflight: {pf_drift}")
        live_db_before = pf_b

        # Materialize the snapshot READ-ONLY (never opens the live DB read-write).
        try:
            mat = cr.materialize_forecast_config_snapshot_readonly(
                db_path=live_db_path,
                config_snapshot_id=sel_id,
                out_root=work_root / MATERIALIZE_SUBDIR,
            )
        except cr.ConfigRegistryError as exc:
            raise ForecastDbConfigGenerationError(f"snapshot materialization failed: {exc}") from exc
        materialized_config_root = mat["materialized_config_root"]

        # FIDELITY GATE: re-import the materialized tree into a temp DB, re-snapshot, and assert the
        # resulting digest + item_count equal the live snapshot's STORED values.
        fidelity_db = work_root / FIDELITY_DB_SUBDIR / "config.sqlite"
        fidelity_db.parent.mkdir(parents=True, exist_ok=True)
        try:
            cr.import_forecast_config_to_db(
                config_root=Path(materialized_config_root),
                db_path=fidelity_db,
                project_key=project_key,
                import_run_id="db_config_backed_generation_fidelity",
            )
            resnap = cr.create_forecast_config_snapshot(
                db_path=fidelity_db,
                project_key=project_key,
                snapshot_name="db_config_backed_generation_fidelity",
                snapshot_reason="materialization fidelity round-trip",
            )
        except cr.ConfigRegistryError as exc:
            raise ForecastDbConfigGenerationError(f"{REASON_FIDELITY}: round-trip failed: {exc}") from exc
        fidelity_passed = (
            int(resnap["item_count"]) == stored_item_count
            and str(resnap["snapshot_sha256"]) == stored_sha
        )
        _require(
            fidelity_passed,
            f"{REASON_FIDELITY}: materialized config does not round-trip to the snapshot digest",
        )

        # Consumed accounting from the materialized manifest (never constants).
        rels = proof._consumed_config_rel_paths(base_cfg, project_key)
        row_counts = mat["row_counts"]
        consumed: dict[str, dict[str, Any]] = {}
        for domain in ("project", "forecast_controls", "forecast_model_controls"):
            rel = rels.get(domain)
            if rel and rel in row_counts:
                consumed[domain] = {"file": rel, "item_count": int(row_counts[rel])}
        consumed_config_domains = sorted(consumed)
        consumed_config_files = [consumed[d]["file"] for d in consumed_config_domains]

        # DB-backed generation: scoped CFR_CONFIG_ROOT = materialized root.
        prev = os.environ.get(ENV_CONFIG_ROOT)
        os.environ[ENV_CONFIG_ROOT] = materialized_config_root
        try:
            db_cfg = proof._load_project_cfg(project_key)
            db_resolved = proof._resolved_control_paths(db_cfg, comp_root)
            db_meta = proof._run_comprehensive(
                cfg=db_cfg,
                data_root=eff_data_root,
                run_stamp=run_stamp,
                out_root=work_root / DB_BACKED_SUBDIR,
            )
        finally:
            if prev is None:
                os.environ.pop(ENV_CONFIG_ROOT, None)
            else:
                os.environ[ENV_CONFIG_ROOT] = prev
        db_pkg = Path(db_meta["output_package"])
        env_restored = os.environ.get(ENV_CONFIG_ROOT) in (None, "")
        db_reads_materialized = all(
            proof._is_under(Path(p), Path(materialized_config_root)) for p in db_resolved.values()
        )

        # Optional evidence-only file-equivalence (default OFF; never on the UI path). Only meaningful
        # when config has NOT diverged from the on-disk files.
        file_equivalence: dict[str, Any] | None = None
        if prove_file_equivalence:
            file_cfg = proof._load_project_cfg(project_key)
            file_meta = proof._run_comprehensive(
                cfg=file_cfg,
                data_root=eff_data_root,
                run_stamp=run_stamp,
                out_root=work_root / FILE_BACKED_SUBDIR,
            )
            file_pkg = Path(file_meta["output_package"])
            replacements = [
                (str(db_pkg), "<OUTPUT_PACKAGE>"),
                (str(file_pkg), "<OUTPUT_PACKAGE>"),
                (materialized_config_root, "<CONFIG_ROOT>"),
                (str(source_config_root), "<CONFIG_ROOT>"),
            ]
            diffs = proof._compare_packages(
                file_pkg=file_pkg, db_pkg=db_pkg, replacements=replacements
            )
            file_equivalence = {
                "compared": True,
                "result": "pass" if not diffs else "fail",
                "config_diverged_from_file": bool(diffs),
                "differences": diffs,
            }

        live_db_after = proof._live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
    finally:
        pin.close()

    live_db_drift = proof._state_drift(live_db_before, live_db_after)
    live_db_unchanged = not live_db_drift
    # The snapshot is immutable and the generator never reads the live DB after materialize, so live-DB
    # drift during the run does not invalidate the package — record it, do not fail.

    validation_passed = bool(db_meta.get("validation_passed"))
    status = STATUS_GENERATED if validation_passed else STATUS_VALIDATION_FAILED

    report = {
        "command": "forecast-db-config-backed-generate",
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "config_snapshot_consumed": True,
        "config_snapshot_id": sel_id,
        "snapshot_name": snapshot_name,
        "snapshot_item_count": stored_item_count,
        "consumed_config_domains": consumed_config_domains,
        "consumed_config_files": consumed_config_files,
        "consumed_by_domain": consumed,
        "fidelity_gate": {
            "passed": fidelity_passed,
            "snapshot_sha256_match": str(resnap["snapshot_sha256"]) == stored_sha,
            "item_count_match": int(resnap["item_count"]) == stored_item_count,
        },
        "materialized_config_root": materialized_config_root,
        "config_snapshot_manifest": mat["manifest_path"],
        "db_schema_version": schema_version,
        "live_db_path": str(live_db_path),
        "data_root": str(eff_data_root),
        "source_config_root": str(source_config_root),
        "run_stamp": run_stamp,
        "output_package": str(db_pkg),
        "validation_passed": validation_passed,
        "reads_materialized_config": db_reads_materialized,
        "cfr_config_root_restored": env_restored,
        "package_csvs": proof._csv_outputs(db_pkg),
        "predecessor_packages": {
            "required": [p for p, _ in proof._REQUIRED_PACKAGE_GLOBS],
            "optional": [p for p, _ in proof._OPTIONAL_PACKAGE_GLOBS],
            "read": predecessor_packages_read,
            "generated": [],
        },
        "file_equivalence": file_equivalence,
        "live_db_integrity": {
            "preflight_stable": True,
            "preflight_stability_seconds": preflight_stability_seconds,
            "before": live_db_before,
            "after": live_db_after,
            "unchanged": live_db_unchanged,
            "drift": live_db_drift,
        },
        "safety": {
            "live_db_written": False,
            "live_db_migrated": False,
            "live_db_imported": False,
            "live_db_opened_read_only": True,
            "source_config_mutated": False,
            "source_package_mutated": False,
            "production_defaults_changed": False,
            "cfr_config_root_default_changed": False,
            "config_snapshot_consumed": True,
            "forecast_comprehensive_run": True,
            "predecessor_generators_run": False,
            "model_backed_llm_or_ollama_run": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    report["report_path"] = str(report_path)
    return report
