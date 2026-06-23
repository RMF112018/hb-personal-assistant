"""Shared gated core for DB-config-backed forecast generation across all four generators.

Phases 17-20 PROVED that the real forecast generators (model_controls, monthly, probability,
comprehensive) produce parity-equivalent output when they read a materialized DB config snapshot
through the ``CFR_CONFIG_ROOT`` bridge. PR #66 productionized that path for ``forecast_comprehensive``.
This module factors the gated machinery — materialize-read-only -> fidelity gate -> quiescence
preflight -> ``CFR_CONFIG_ROOT`` bridge -> redacted report — into ONE generator-agnostic core, and a
per-kind ``GeneratorDescriptor`` registry that supplies only what differs between generators:

  * the deterministic generator invocation (the proof module's ``_run_<gen>`` helper),
  * the required/optional predecessor package globs,
  * how consumed config is accounted from the materialized manifest (a per-kind callable),
  * the kind-specific guard (comprehensive's cost-frequency refusal; monthly's SystemExit wrapper),
  * and the ``safety`` run-flag key.

Why a fidelity gate, not an output-parity gate: once an operator PROMOTES a config edit, the DB config
LEGITIMATELY differs from the on-disk file config, so a file-vs-DB output-parity gate would wrongly
block the intended change. The safety invariant is **materialization fidelity** — the materialized
config tree round-trips back to the snapshot it was read from (re-import -> re-snapshot ->
``snapshot_sha256`` + ``item_count`` equal the snapshot's STORED values). It is independent of whether
config diverged from the on-disk files.

Fail-closed (raises -> CLI rc 3) BEFORE any generation on: non-tropical project; unsafe work root; a
live DB missing/not v60/lacking the 4 config tables; (when required) not the live DB; no snapshot to
consume; a non-quiescent live DB; a missing required predecessor package; (comprehensive) a missing
cost-frequency package when ``frequency_enabled``; (monthly) an unsafe integration SystemExit; or a
fidelity-gate mismatch. The live DB is opened ``mode=ro`` only — never written, migrated, or copied.
Reuses the Phase 17-20 proof helpers (single source of truth).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config_registry as cr
from ..common.config_root import ENV_CONFIG_ROOT
from ..common.project_eligibility import eligible_projects, is_project_eligible
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

# Probability-only determinism knobs (the byte-deterministic Monte-Carlo core needs a fixed runs+seed).
DEFAULT_PROBABILITY_RUNS = 10000
DEFAULT_PROBABILITY_SEED = 20260614

STATUS_GENERATED = "generated"
STATUS_VALIDATION_FAILED = "generated_validation_failed"

REASON_NO_SNAPSHOT = "no_config_snapshot"
REASON_FIDELITY = "config_fidelity_failed"
REASON_PREDECESSOR = "predecessor_packages_missing"
REASON_COST_FREQ = "cost_frequency_package_missing"
REASON_NOT_QUIESCENT = "live_db_not_quiescent"
REASON_LIVE_MUTATED = "live_db_mutated_during_run"
REASON_GENERATOR_REFUSED = "generator_refused"
REASON_UNSUPPORTED_KIND = "unsupported_generator_kind"
REASON_FILE_EQUIVALENCE_UNSUPPORTED = "file_equivalence_unsupported"

SUPPORTED_GENERATOR_KINDS = ("comprehensive", "model_controls", "monthly", "probability")


class ForecastDbConfigGenerationError(RuntimeError):
    """Raised when DB-config-backed generation is refused (fail closed; no soft fallback).

    The first ``:``-delimited token of the message is a stable coded reason (see ``REASON_*``) so the
    caller can map it to a path-free, user-facing message.
    """


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastDbConfigGenerationError(message)


def _select_snapshot(
    pin: Any, project_key: str, config_snapshot_id: str | None
) -> tuple[str, int, str, str]:
    """Return (config_snapshot_id, item_count, snapshot_sha256, snapshot_name) for the snapshot to consume.

    Explicit id if given; otherwise the latest snapshot for the project (DESC by created_utc).
    """
    if config_snapshot_id:
        row = pin.execute(
            "SELECT config_snapshot_id, item_count, snapshot_sha256, snapshot_name "
            "FROM forecast_config_snapshots WHERE config_snapshot_id = ? AND project_key = ?",
            (config_snapshot_id, project_key),
        ).fetchone()
        _require(
            row is not None,
            f"{REASON_NO_SNAPSHOT}: config_snapshot_id not found {config_snapshot_id}",
        )
    else:
        row = pin.execute(
            "SELECT config_snapshot_id, item_count, snapshot_sha256, snapshot_name "
            "FROM forecast_config_snapshots WHERE project_key = ? "
            "ORDER BY snapshot_created_utc DESC, config_snapshot_id LIMIT 1",
            (project_key,),
        ).fetchone()
        _require(row is not None, f"{REASON_NO_SNAPSHOT}: no snapshot to consume for {project_key}")
    return (row[0], int(row[1]), str(row[2]), str(row[3]))


# --------------------------------------------------------------------------------------------------
# Per-kind consumed-config accounting (from the materialized manifest row_counts; never constants).
# Each generator reads a different set of config domains through the bridge — accounting is per-kind.
# --------------------------------------------------------------------------------------------------
def _comprehensive_consumed(
    base_cfg: dict, project_key: str, row_counts: dict
) -> dict[str, dict[str, Any]]:
    rels = proof._consumed_config_rel_paths(base_cfg, project_key)
    consumed: dict[str, dict[str, Any]] = {}
    for domain in ("project", "forecast_controls", "forecast_model_controls"):
        rel = rels.get(domain)
        if rel and rel in row_counts:
            consumed[domain] = {"file": rel, "item_count": int(row_counts[rel])}
    return consumed


def _model_controls_consumed(
    base_cfg: dict, project_key: str, row_counts: dict
) -> dict[str, dict[str, Any]]:
    files = sorted(r for r in row_counts if "/forecast_model_controls/" in f"/{r}")
    if not files:
        return {}
    return {
        "forecast_model_controls": {
            "file": files[0],
            "item_count": sum(int(row_counts[r]) for r in files),
        }
    }


def _monthly_consumed(
    base_cfg: dict, project_key: str, row_counts: dict
) -> dict[str, dict[str, Any]]:
    from . import forecast_monthly_db_config_proof as moproof

    consumed: dict[str, dict[str, Any]] = {}
    for rel, count in row_counts.items():
        for prefix, domain in moproof._CONSUMED_DOMAIN_PREFIXES.items():
            if rel.startswith(prefix):
                if domain in consumed:
                    consumed[domain]["item_count"] += int(count)
                else:
                    consumed[domain] = {"file": rel, "item_count": int(count)}
                break
    return consumed


def _probability_consumed(
    base_cfg: dict, project_key: str, row_counts: dict
) -> dict[str, dict[str, Any]]:
    project_rel = f"config/projects/{project_key}.json"
    crosswalk_rel = base_cfg.get("owner_sov_scope_crosswalk")
    consumed: dict[str, dict[str, Any]] = {}
    for domain, rel in (("project", project_rel), ("owner_sov_crosswalk", crosswalk_rel)):
        if rel and rel in row_counts:
            consumed[domain] = {"file": rel, "item_count": int(row_counts[rel])}
    return consumed


# --------------------------------------------------------------------------------------------------
# Per-kind "the generator read the materialized config" evidence (computed while CFR_CONFIG_ROOT is set).
# --------------------------------------------------------------------------------------------------
def _comprehensive_reads(db_cfg: dict, materialized_config_root: str, consumed: dict) -> bool:
    # Resolve the controls/model-controls file paths through the bridge and assert they're materialized.
    comp_root = proof._comprehensive_subproject_root()
    db_resolved = proof._resolved_control_paths(db_cfg, comp_root)
    return all(
        proof._is_under(Path(p), Path(materialized_config_root)) for p in db_resolved.values()
    )


def _generic_reads(db_cfg: dict, materialized_config_root: str, consumed: dict) -> bool:
    # Every consumed config file resolves to a real file under the materialized root the bridge points at.
    if not consumed:
        return False
    root = Path(materialized_config_root)
    for entry in consumed.values():
        f = root / entry["file"]
        if not (proof._is_under(f, root) and f.exists()):
            return False
    return True


def _comprehensive_compare(
    *, file_pkg: Path, db_pkg: Path, materialized_config_root: str, source_config_root: Path
) -> list:
    replacements = [
        (str(db_pkg), "<OUTPUT_PACKAGE>"),
        (str(file_pkg), "<OUTPUT_PACKAGE>"),
        (materialized_config_root, "<CONFIG_ROOT>"),
        (str(source_config_root), "<CONFIG_ROOT>"),
    ]
    return proof._compare_packages(file_pkg=file_pkg, db_pkg=db_pkg, replacements=replacements)


@dataclass(frozen=True)
class GeneratorDescriptor:
    """The per-generator pieces the shared core needs; everything else is generator-agnostic."""

    kind: str
    run: Callable[..., dict]  # (*, cfg, data_root, run_stamp, out_root) -> generator meta
    required_globs: tuple[tuple[str, str], ...]
    optional_globs: tuple[tuple[str, str], ...]
    consumed_domains: Callable[[dict, str, dict], dict]
    reads_materialized: Callable[[dict, str, dict], bool]
    safety_run_key: str
    cost_frequency_guard: bool = False
    catch_system_exit: bool = False
    compare: Callable[..., list] | None = None


def _comprehensive_descriptor() -> GeneratorDescriptor:
    return GeneratorDescriptor(
        kind="comprehensive",
        run=proof._run_comprehensive,
        required_globs=proof._REQUIRED_PACKAGE_GLOBS,
        optional_globs=proof._OPTIONAL_PACKAGE_GLOBS,
        consumed_domains=_comprehensive_consumed,
        reads_materialized=_comprehensive_reads,
        safety_run_key="forecast_comprehensive_run",
        cost_frequency_guard=True,
        compare=_comprehensive_compare,
    )


def _model_controls_descriptor() -> GeneratorDescriptor:
    from . import forecast_model_controls_db_config_proof as mcproof

    return GeneratorDescriptor(
        kind="model_controls",
        run=mcproof._run_model_controls,
        required_globs=(),  # the generator self-discovers predecessors; the proof declares no gating globs
        optional_globs=(),
        consumed_domains=_model_controls_consumed,
        reads_materialized=_generic_reads,
        safety_run_key="forecast_model_controls_run",
    )


def _monthly_descriptor() -> GeneratorDescriptor:
    from . import forecast_monthly_db_config_proof as moproof

    return GeneratorDescriptor(
        kind="monthly",
        run=moproof._run_monthly,
        required_globs=moproof._REQUIRED_PACKAGE_GLOBS,
        optional_globs=(),
        consumed_domains=_monthly_consumed,
        reads_materialized=_generic_reads,
        safety_run_key="forecast_monthly_run",
        catch_system_exit=True,  # monthly integrations assert_integration_safe() -> SystemExit when unsafe
    )


def _probability_descriptor(
    *, runs: int, seed: int, forecast_start_month: str | None
) -> GeneratorDescriptor:
    from . import forecast_probability_db_config_proof as pproof

    def _run(*, cfg: dict, data_root: Path, run_stamp: str, out_root: Path) -> dict:
        return pproof._run_probability(
            cfg=cfg,
            data_root=data_root,
            run_stamp=run_stamp,
            out_root=out_root,
            runs=runs,
            seed=seed,
            forecast_start_month=forecast_start_month,
        )

    return GeneratorDescriptor(
        kind="probability",
        run=_run,
        required_globs=pproof._REQUIRED_PACKAGE_GLOBS,
        optional_globs=(),
        consumed_domains=_probability_consumed,
        reads_materialized=_generic_reads,
        safety_run_key="forecast_probability_run",
    )


def get_descriptor(
    kind: str,
    *,
    runs: int = DEFAULT_PROBABILITY_RUNS,
    seed: int = DEFAULT_PROBABILITY_SEED,
    forecast_start_month: str | None = None,
) -> GeneratorDescriptor:
    """Resolve the descriptor for a generator kind (probability binds its determinism knobs)."""
    if kind == "comprehensive":
        return _comprehensive_descriptor()
    if kind == "model_controls":
        return _model_controls_descriptor()
    if kind == "monthly":
        return _monthly_descriptor()
    if kind == "probability":
        return _probability_descriptor(
            runs=runs, seed=seed, forecast_start_month=forecast_start_month
        )
    raise ForecastDbConfigGenerationError(f"{REASON_UNSUPPORTED_KIND}: {kind!r}")


def run_db_config_backed_generation(
    *,
    descriptor: GeneratorDescriptor,
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
    """Generate ``descriptor.kind``'s forecast package consuming the live DB config snapshot."""
    _require(
        is_project_eligible(project_key),
        f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}",
    )
    _require(bool(work_root), "work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    run_stamp = run_stamp or DEFAULT_RUN_STAMP
    _require(bool(live_db_path), "live_db_path is required")
    live_db_path = Path(live_db_path)
    _require(live_db_path.exists(), f"live DB not found: {live_db_path}")
    if require_live_snapshot:
        _require(
            cr._is_live_db(live_db_path), f"live_db_path is not the live/default DB: {live_db_path}"
        )

    db_inventory_tables = proof._db_inventory_tables()
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
        eff_data_root = (
            Path(data_root) if data_root is not None else Path(base_cfg["default_data_root"])
        )
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

        # Required predecessor packages (per-kind). The generators fail closed (SystemExit) without them;
        # we pre-check for a clean controlled refusal BEFORE invoking.
        for ptype, glob in descriptor.required_globs:
            _require(
                proof._present(eff_data_root, glob),
                f"{REASON_PREDECESSOR}: required predecessor package not found: {ptype}",
            )
        # Cost-frequency guard (comprehensive only) — never GENERATE cost_frequency into the read-only
        # data root; refuse if it's missing while frequency is enabled.
        if descriptor.cost_frequency_guard and proof._frequency_enabled(base_cfg):
            _require(
                proof._present(eff_data_root, proof._COST_FREQUENCY_GLOB),
                f"{REASON_COST_FREQ}: forecast_cost_frequency package missing",
            )
        present_map = {
            p: proof._present(eff_data_root, g)
            for p, g in (*descriptor.required_globs, *descriptor.optional_globs)
        }
        predecessor_packages_read = sorted(p for p, present in present_map.items() if present)

        # Quiescence preflight (BEFORE materialize).
        pf_a = proof._live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        if preflight_stability_seconds > 0:
            time.sleep(preflight_stability_seconds)
        pf_b = proof._live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        pf_drift = proof._state_drift(pf_a, pf_b)
        _require(
            not pf_drift, f"{REASON_NOT_QUIESCENT}: live DB changed during preflight: {pf_drift}"
        )
        live_db_before = pf_b

        # Materialize the snapshot READ-ONLY (never opens the live DB read-write).
        try:
            mat = cr.materialize_forecast_config_snapshot_readonly(
                db_path=live_db_path,
                config_snapshot_id=sel_id,
                out_root=work_root / MATERIALIZE_SUBDIR,
            )
        except cr.ConfigRegistryError as exc:
            raise ForecastDbConfigGenerationError(
                f"snapshot materialization failed: {exc}"
            ) from exc
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
            raise ForecastDbConfigGenerationError(
                f"{REASON_FIDELITY}: round-trip failed: {exc}"
            ) from exc
        fidelity_passed = (
            int(resnap["item_count"]) == stored_item_count
            and str(resnap["snapshot_sha256"]) == stored_sha
        )
        _require(
            fidelity_passed,
            f"{REASON_FIDELITY}: materialized config does not round-trip to the snapshot digest",
        )

        # Consumed accounting from the materialized manifest (per-kind; never constants).
        row_counts = mat["row_counts"]
        consumed = descriptor.consumed_domains(base_cfg, project_key, row_counts)
        consumed_config_domains = sorted(consumed)
        consumed_config_files = [consumed[d]["file"] for d in consumed_config_domains]

        # DB-backed generation: scoped CFR_CONFIG_ROOT = materialized root.
        prev = os.environ.get(ENV_CONFIG_ROOT)
        os.environ[ENV_CONFIG_ROOT] = materialized_config_root
        try:
            db_cfg = proof._load_project_cfg(project_key)
            try:
                db_meta = descriptor.run(
                    cfg=db_cfg,
                    data_root=eff_data_root,
                    run_stamp=run_stamp,
                    out_root=work_root / DB_BACKED_SUBDIR,
                )
            except SystemExit as exc:  # an unsafe generator integration must not kill the process
                if descriptor.catch_system_exit:
                    raise ForecastDbConfigGenerationError(
                        f"{REASON_GENERATOR_REFUSED}: {descriptor.kind} generator refused (unsafe integration)"
                    ) from exc
                raise
            # Evidence that the generator read the materialized config — computed while the bridge is set.
            db_reads_materialized = descriptor.reads_materialized(
                db_cfg, materialized_config_root, consumed
            )
        finally:
            if prev is None:
                os.environ.pop(ENV_CONFIG_ROOT, None)
            else:
                os.environ[ENV_CONFIG_ROOT] = prev
        db_pkg = Path(db_meta["output_package"])
        env_restored = os.environ.get(ENV_CONFIG_ROOT) in (None, "")

        # Optional evidence-only file-equivalence (default OFF; never on the UI path). Only meaningful
        # when config has NOT diverged from the on-disk files, and only for kinds with a comparator.
        file_equivalence: dict[str, Any] | None = None
        if prove_file_equivalence:
            if descriptor.compare is None:
                raise ForecastDbConfigGenerationError(
                    f"{REASON_FILE_EQUIVALENCE_UNSUPPORTED}: {descriptor.kind}"
                )
            file_cfg = proof._load_project_cfg(project_key)
            file_meta = descriptor.run(
                cfg=file_cfg,
                data_root=eff_data_root,
                run_stamp=run_stamp,
                out_root=work_root / FILE_BACKED_SUBDIR,
            )
            file_pkg = Path(file_meta["output_package"])
            diffs = descriptor.compare(
                file_pkg=file_pkg,
                db_pkg=db_pkg,
                materialized_config_root=materialized_config_root,
                source_config_root=source_config_root,
            )
            file_equivalence = {
                "compared": True,
                "result": "pass" if not diffs else "fail",
                "config_diverged_from_file": bool(diffs),
                "differences": diffs,
            }

        live_db_after = proof._live_db_state(
            live_db_path, pin, db_inventory_tables=db_inventory_tables
        )
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
        "generator_kind": descriptor.kind,
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
            "required": [p for p, _ in descriptor.required_globs],
            "optional": [p for p, _ in descriptor.optional_globs],
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
            descriptor.safety_run_key: True,
            "predecessor_generators_run": False,
            "model_backed_llm_or_ollama_run": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    report["report_path"] = str(report_path)
    return report
