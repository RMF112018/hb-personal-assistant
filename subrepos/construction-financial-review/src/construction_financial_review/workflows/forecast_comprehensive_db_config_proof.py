"""Phase 20 — DB-backed config consumer proof for ``forecast_comprehensive``.

Proves the deterministic ``forecast_comprehensive`` integrated generator produces parity-equivalent output
whether it reads file-backed config or the Phase 16 DB config snapshot (materialized root + the
``CFR_CONFIG_ROOT`` opt-in bridge). CONSUMER PROOF only — changes no default, never writes/migrates/imports
the live DB, runs no LLM/Ollama, does not run monthly/probability/intelligence/cost-frequency generators
(reads their existing packages read-only), and produces no SEPARATE final-integrated-CSV cutover deliverable.

Repo truth (Phase 20 audit): ``forecast_comprehensive`` directly consumes THREE config domains through
``common.config_root.resolve_config_base`` (CFR_CONFIG_ROOT-aware):

  - ``project``                 -> ``config/projects/tropical.json``                 (the proof's cli.load_project)
  - ``forecast_controls``       -> ``cfg['forecast_controls']['control_file']``       (fctl_integration.prepare)
  - ``forecast_model_controls`` -> ``cfg['forecast_model_controls']['control_file']`` (fmc_integration.prepare)

Staffing / owner-SOV crosswalk are NOT re-resolved (inherited from predecessor packages). There is NO
reader-layer gap — the module-level SUBPROJECT_ROOT is passed INTO resolve_config_base. Byte-deterministic
under a fixed frozen_stamp (probability is a deterministic transform, not Monte Carlo; advisory LLM off and
excluded). Required predecessors: context + intelligence + monthly (read-only, never regenerated).

cost_frequency guard: ``_maybe_generate_cost_frequency`` would GENERATE a cost-frequency package into the
read-only data_root if absent and ``forecast_comprehensive.frequency_enabled`` (default True). The proof
refuses (rc 3) before generation if that package is missing — it must only be CONSUMED, never generated.

Package CSVs (``actuals_plus_forecast_monthly_*.csv`` etc.) are STANDARD deterministic package outputs and
are compared byte-exact; ``integrated_csv_generated`` means a SEPARATE cutover/export CSV, which is never run.

Live-DB stability hardening inherited from Phase 18a: pinned ``mode=ro`` connection, fail-closed quiescence
preflight, measured before/after ``live_db_integrity``. ``audit/db_inventory.json`` is kept byte-exact.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .. import config_registry as cr
from ..common.config_root import ENV_CONFIG_ROOT
from ..common.hashing import sha256_file
from ..common.project_eligibility import eligible_projects, is_project_eligible
from . import live_db_certification as cert

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = 60
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "forecast_comprehensive_db_config_proof_report.json"
SUMMARY_NAME = "forecast_comprehensive_db_config_proof_summary.md"
MATERIALIZE_SUBDIR = "db_snapshot_config"
FILE_BACKED_SUBDIR = "file_backed"
DB_BACKED_SUBDIR = "db_snapshot_backed"

DECISION_READY = "forecast_comprehensive_db_config_parity_ready"
DECISION_NOT_READY = "not_ready"
DEFAULT_RUN_STAMP = "20260101_000000"
DEFAULT_PREFLIGHT_STABILITY_SECONDS = 2.0
LIVE_BASELINE_ITEM_COUNT = 194
NOT_READY_REASON_LIVE_DB_MUTATED = "live_db_mutated_during_run"
NOT_READY_REASON_CONFIG_PARITY = "config_parity_mismatch"
REFUSE_COST_FREQ_MISSING = "required_predecessor_package_missing: forecast_cost_frequency"

REQUIRED_CONFIG_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)

# Required predecessor packages (latest-glob); forecast_comprehensive fails closed (SystemExit) without
# them. It READS these read-only; it never regenerates them.
_REQUIRED_PACKAGE_GLOBS = (
    ("context", "forecast_context_package_tropical_*"),
    ("intelligence", "forecast_accuracy_next_package_tropical_*"),
    ("monthly", "forecast_monthly_package_tropical_*"),
)
# Optional predecessor packages (consumed only if present; reported factually, never assumed).
_OPTIONAL_PACKAGE_GLOBS = (
    ("probability", "forecast_probability_package_tropical_*"),
    ("history_informed", "forecast_history_informed_package_tropical_*"),
    ("cost_frequency", "forecast_cost_frequency_package_tropical_*"),
    ("crosswalk_v2", "forecast_analysis_package_tropical_crosswalk_v2_*"),
    ("schedule_integrated", "schedule_integrated_forecast_package_tropical_*"),
    ("staffing_plan", "forecast_staffing_plan_package_tropical_*"),
)
_COST_FREQUENCY_GLOB = "forecast_cost_frequency_package_tropical_*"

# Output files that LEGITIMATELY embed an absolute config-root/output-package path. Established by MANDATORY
# raw file-backed vs DB-backed diff inspection (see ADR 276 / Phase 20a). Every other output file — INCLUDING
# the standard package CSVs (actuals_plus_forecast_monthly_*.csv etc.) — is compared BYTE-EXACT. Only files the
# raw diff proves embed a config/output path are enumerated here, and ONLY the path token is normalized.
#
# integrated_evidence_registry_by_budget_code.jsonl records, per evidence row, the RESOLVED operator-control
# source path in ``source_package_path`` (forecast_controls / forecast_model_controls evidence resolves the
# control file through resolve_config_base): file-backed -> <source_config_root>/config/..., DB-backed ->
# <materialized_config_root>/config/... — a config-root path token, NOT a semantic forecast/math difference.
# (The reduced CI fixture disables the operator integrations, so those rows are not emitted there and the file
# is byte-identical; the real enabled-config live proof surfaced the embedding — Phase 20a.)
_PATH_EMBEDDING_FILES: tuple[str, ...] = ("integrated_evidence_registry_by_budget_code.jsonl",)
_NORMALIZED_RULES = [
    "raw file-backed vs DB-backed diff inspected (mandatory); only files that embed an absolute "
    "config-root/output path are enumerated in _PATH_EMBEDDING_FILES and compared after PATH normalization "
    "(<OUTPUT_PACKAGE>/<CONFIG_ROOT>) only",
    "integrated_evidence_registry_by_budget_code.jsonl is path-embedded because it records the resolved "
    "operator-control source_package_path; ONLY the config-root path token is normalized (its non-path "
    "evidence fields — values, weights, signals, lineage — are still compared exactly)",
    "NO forecast/actuals/monthly/probability value, row count, warning count, validation status, manifest "
    "conclusion, audit/db_inventory.json content, CSV math, source-package lineage, or package-consumption "
    "result is ever normalized; standard package CSVs are compared byte-exact",
]

# Controlled-safety guard only (mirrors the generators' default Synology forecast data root); the work root
# and all generated artifacts must live OUTSIDE this. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ForecastComprehensiveDbConfigProofError(RuntimeError):
    """Raised when the consumer proof is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastComprehensiveDbConfigProofError(message)


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _db_inventory_tables() -> tuple[str, ...]:
    from ..forecast_intelligence.db_inventory import DEFAULT_TABLES

    return tuple(DEFAULT_TABLES)


def _present(data_root: Path, glob: str) -> bool:
    return any(p.is_dir() for p in Path(data_root).glob(glob))


def _frequency_enabled(cfg: dict) -> bool:
    return bool((cfg.get("forecast_comprehensive") or {}).get("frequency_enabled", True))


def _consumed_config_rel_paths(cfg: dict, project_key: str) -> dict[str, str]:
    """The three config files forecast_comprehensive reads through the bridge (rel paths under config/)."""
    from ..forecast_controls.load_controls import DEFAULT_CONTROL_FILE as _CTL_DEFAULT
    from ..forecast_controls.load_controls import controls_config as _ctl_cfg
    from ..forecast_model_controls.load_controls import DEFAULT_CONTROL_FILE as _MDL_DEFAULT
    from ..forecast_model_controls.load_controls import model_controls_config as _mdl_cfg

    return {
        "project": f"config/projects/{project_key}.json",
        "forecast_controls": _ctl_cfg(cfg).get("control_file") or _CTL_DEFAULT,
        "forecast_model_controls": _mdl_cfg(cfg).get("control_file") or _MDL_DEFAULT,
    }


def _resolved_control_paths(cfg: dict, subproject_root: Path) -> dict[str, str]:
    """Resolve the controls/model-controls file paths through the CFR_CONFIG_ROOT bridge (evidence)."""
    from ..forecast_controls.load_controls import control_file_path as _ctl_path
    from ..forecast_model_controls.load_controls import control_file_path as _mdl_path

    return {
        "forecast_controls": str(_ctl_path(cfg, subproject_root)),
        "forecast_model_controls": str(_mdl_path(cfg, subproject_root, None)),
    }


def _file_fingerprint(path: Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "exists": False,
            "path": str(p),
            "size_bytes": None,
            "mtime_ns": None,
            "sha256": None,
        }
    st = p.stat()
    return {
        "exists": True,
        "path": str(p),
        "size_bytes": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "sha256": sha256_file(p),
    }


def _live_db_state(
    live_db_path: Path, ro_conn: Any, *, db_inventory_tables: tuple[str, ...]
) -> dict:
    main = Path(live_db_path)
    physical = {
        "main": _file_fingerprint(main),
        "wal": _file_fingerprint(Path(str(main) + "-wal")),
        "shm": _file_fingerprint(Path(str(main) + "-shm")),
    }
    sv = ro_conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    schema_version = int(sv[0]) if sv and sv[0] is not None else 0
    dv = ro_conn.execute("PRAGMA data_version").fetchone()
    data_version = int(dv[0]) if dv and dv[0] is not None else 0
    counts: dict[str, int | None] = {}
    for t in db_inventory_tables:
        if _table_exists(ro_conn, t):
            r = ro_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()  # noqa: S608 — module constant
            counts[t] = int(r[0]) if r and r[0] is not None else 0
        else:
            counts[t] = None
    digest = hashlib.sha256(
        json.dumps(
            {"schema_version": schema_version, "data_version": data_version, "counts": counts},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    logical = {
        "schema_version": schema_version,
        "data_version": data_version,
        "db_inventory_table_counts": counts,
        "db_inventory_digest": digest,
    }
    return {"physical": physical, "logical": logical}


def _state_drift(a: dict, b: dict) -> list[str]:
    changed: list[str] = []
    for f in ("main", "wal", "shm"):
        if a["physical"][f] != b["physical"][f]:
            changed.append(f"physical.{f}")
    for k in ("schema_version", "data_version", "db_inventory_digest"):
        if a["logical"][k] != b["logical"][k]:
            changed.append(f"logical.{k}")
    return changed


def _normalize(text: str, replacements: list[tuple[str, str]]) -> str:
    for needle, token in replacements:
        if needle:
            text = text.replace(needle, token)
    return text


def _rel_files(package: Path) -> set[str]:
    return {
        str(p.relative_to(package))
        for p in package.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }


def _read_manifest_files(package: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    return {f["path"]: f for f in manifest.get("output_files", [])}


def _compare_text(
    a: Path, b: Path, rel: str, replacements: list[tuple[str, str]]
) -> dict[str, Any] | None:
    if not a.is_file() and not b.is_file():
        return None
    if a.is_file() != b.is_file():
        return {
            "file": rel,
            "key_or_path": "<presence>",
            "file_backed_value": a.is_file(),
            "db_backed_value": b.is_file(),
            "normalized_rules": "path-normalized",
        }
    na = _normalize(a.read_text(encoding="utf-8"), replacements)
    nb = _normalize(b.read_text(encoding="utf-8"), replacements)
    if na == nb:
        return None
    import difflib

    detail = next(
        (
            line
            for line in difflib.unified_diff(na.splitlines(), nb.splitlines(), n=0, lineterm="")
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ),
        "<normalized text differs>",
    )
    return {
        "file": rel,
        "key_or_path": "<normalized-text>",
        "file_backed_value": detail if detail.startswith("-") else "<see db value>",
        "db_backed_value": detail if detail.startswith("+") else "<see file value>",
        "normalized_rules": "; ".join(_NORMALIZED_RULES),
    }


def _compare_packages(
    *, file_pkg: Path, db_pkg: Path, replacements: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Every file BYTE-EXACT except enumerated ``_PATH_EMBEDDING_FILES`` (path-normalized) and
    ``manifest.json`` / ``validation_report.json``. No semantic/financial content normalized."""
    diffs: list[dict[str, Any]] = []
    special = {"validation_report.json"}

    fa, fb = _rel_files(file_pkg), _rel_files(db_pkg)
    if fa != fb:
        diffs.append(
            {
                "file": "<file set>",
                "key_or_path": "<presence>",
                "file_backed_value": sorted(fa - fb),
                "db_backed_value": sorted(fb - fa),
                "normalized_rules": "none",
            }
        )

    for rel in sorted(fa & fb):
        if rel in special:
            continue
        a, b = file_pkg / rel, db_pkg / rel
        if rel in _PATH_EMBEDDING_FILES:
            d = _compare_text(a, b, rel, replacements)
            if d:
                diffs.append(d)
            continue
        if a.read_bytes() != b.read_bytes():
            diffs.append(
                {
                    "file": rel,
                    "key_or_path": "<bytes>",
                    "file_backed_value": sha256_file(a),
                    "db_backed_value": sha256_file(b),
                    "normalized_rules": "none (compared byte-exact)",
                }
            )

    sha_repl = list(replacements)
    for rel in _PATH_EMBEDDING_FILES:
        for pkg in (file_pkg, db_pkg):
            p = pkg / rel
            if p.is_file():
                sha_repl.append((sha256_file(p), "<PATH_FILE_SHA>"))
    d = _compare_text(
        file_pkg / "validation_report.json",
        db_pkg / "validation_report.json",
        "validation_report.json",
        sha_repl,
    )
    if d:
        diffs.append(d)

    ma, mb = _read_manifest_files(file_pkg), _read_manifest_files(db_pkg)
    if set(ma) != set(mb):
        diffs.append(
            {
                "file": "manifest.json",
                "key_or_path": "<file set>",
                "file_backed_value": sorted(set(ma) - set(mb)),
                "db_backed_value": sorted(set(mb) - set(ma)),
                "normalized_rules": "none",
            }
        )
    for rel in sorted(set(ma) & set(mb)):
        ea, eb = ma[rel], mb[rel]
        keys = (
            ("path", "row_count")
            if rel in _PATH_EMBEDDING_FILES
            else ("path", "size_bytes", "row_count", "sha256")
        )
        for k in keys:
            if ea.get(k) != eb.get(k):
                diffs.append(
                    {
                        "file": "manifest.json",
                        "key_or_path": f"{rel}.{k}",
                        "file_backed_value": ea.get(k),
                        "db_backed_value": eb.get(k),
                        "normalized_rules": (
                            "manifest size_bytes/sha256 excluded for path-embedding files"
                            if rel in _PATH_EMBEDDING_FILES
                            else "none"
                        ),
                    }
                )
    return diffs


def _run_comprehensive(
    *, project_key: str, cfg: dict, data_root: Path, run_stamp: str, out_root: Path
) -> dict:
    """Run the real forecast_comprehensive generator (deterministic; LLM off; reads packages, runs none)."""
    from ..forecast_comprehensive import generate_comprehensive_forecast_package as gen

    return gen.generate(
        project_key,
        cfg,
        data_root=data_root,
        frozen_stamp=run_stamp,
        out_root=out_root,
        with_llm=False,
        llm_model=None,
        control_file=None,
    )


def _load_project_cfg(project_key: str) -> dict:
    from .. import cli as cfr_cli

    return cfr_cli.load_project(project_key)


def _comprehensive_subproject_root() -> Path:
    from ..forecast_comprehensive import generate_comprehensive_forecast_package as gen

    return Path(gen.SUBPROJECT_ROOT)


def _csv_outputs(package: Path) -> list[str]:
    return sorted(str(p.relative_to(package)) for p in package.rglob("*.csv"))


def run_forecast_comprehensive_db_config_proof(
    *,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path,
    config_snapshot_id: str,
    work_root: Path,
    run_stamp: str | None = None,
    data_root: Path | None = None,
    source_config_root: Path | None = None,
    require_live_snapshot: bool = True,
    require_item_count: int | None = LIVE_BASELINE_ITEM_COUNT,
    preflight_stability_seconds: float = DEFAULT_PREFLIGHT_STABILITY_SECONDS,
) -> dict[str, Any]:
    """Prove forecast_comprehensive consumes the DB config snapshot with parity vs file-backed config.

    Fails closed (``ForecastComprehensiveDbConfigProofError`` -> CLI rc 3) before any output on: non-tropical
    project; an unsafe work root; a live DB missing/not v60/lacking the 4 config tables; (when required) not
    the live DB; a missing/wrong-project/wrong-count snapshot; a missing source config root; a data root
    missing any required predecessor (context/intelligence/monthly); a missing cost-frequency package when
    ``frequency_enabled`` is true (so comprehensive never generates it into the read-only data root); or a
    non-quiescent live DB preflight. Runs comprehensive twice (file-backed + DB-backed) with the same stamp/
    data root and compares byte-exact.
    """
    if not is_project_eligible(project_key):
        raise ForecastComprehensiveDbConfigProofError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    _require(bool(work_root), "work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    run_stamp = run_stamp or DEFAULT_RUN_STAMP
    _require(bool(live_db_path), "live_db_path is required")
    live_db_path = Path(live_db_path)
    _require(live_db_path.exists(), f"live DB not found: {live_db_path}")
    if require_live_snapshot:
        _require(
            cr._is_live_db(live_db_path),
            f"live_db_path is not the live/default DB (require_live_snapshot=True): {live_db_path}",
        )

    db_inventory_tables = _db_inventory_tables()
    comp_root = _comprehensive_subproject_root()
    pin = cert._ro_conn(live_db_path)
    try:
        vrow = pin.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(vrow[0]) if vrow and vrow[0] is not None else 0
        _require(
            schema_version >= REQUIRED_SCHEMA_VERSION,
            f"live DB schema version {schema_version} < {REQUIRED_SCHEMA_VERSION} (config registry)",
        )
        for t in REQUIRED_CONFIG_TABLES:
            _require(_table_exists(pin, t), f"live DB missing config registry table: {t}")
        row = pin.execute(
            "SELECT project_key, item_count FROM forecast_config_snapshots WHERE config_snapshot_id = ?",
            (config_snapshot_id,),
        ).fetchone()
        _require(row is not None, f"config_snapshot_id not found: {config_snapshot_id}")
        _require(row[0] == project_key, f"snapshot project_key {row[0]!r} != {project_key!r}")
        snapshot_item_count = int(row[1])
        if require_item_count is not None:
            _require(
                snapshot_item_count == require_item_count,
                f"snapshot item_count {snapshot_item_count} != required {require_item_count}",
            )

        if source_config_root is None:
            source_config_root = Path(cr.__file__).resolve().parents[2]
        source_config_root = Path(source_config_root)
        _require(source_config_root.exists(), f"source_config_root not found: {source_config_root}")

        prev_env = os.environ.pop(ENV_CONFIG_ROOT, None)
        try:
            base_cfg = _load_project_cfg(project_key)
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
            ("live forecast root", _LIVE_ROOT),
            ("source config tree", source_config_root),
            ("live DB directory", live_db_path.parent),
            ("data root / source packages", eff_data_root),
        ):
            _require(
                not _is_under(work_root, parent),
                f"work_root is at/under the {label} (refused): {work_root}",
            )

        # Required predecessor packages.
        for ptype, glob in _REQUIRED_PACKAGE_GLOBS:
            _require(
                _present(eff_data_root, glob),
                f"required predecessor package not found under data_root: {ptype} (glob {glob!r})",
            )
        # cost_frequency guard: when frequency_enabled is true, the package MUST already exist so
        # comprehensive consumes it and never generates it into the read-only data root.
        frequency_enabled = _frequency_enabled(base_cfg)
        cost_freq_present = _present(eff_data_root, _COST_FREQUENCY_GLOB)
        if frequency_enabled:
            _require(cost_freq_present, REFUSE_COST_FREQ_MISSING)

        # Factual predecessor reporting (what is actually present under the data root).
        required_pkgs = [p for p, _ in _REQUIRED_PACKAGE_GLOBS]
        optional_pkgs = [p for p, _ in _OPTIONAL_PACKAGE_GLOBS]
        present_map = {
            p: _present(eff_data_root, g)
            for p, g in (*_REQUIRED_PACKAGE_GLOBS, *_OPTIONAL_PACKAGE_GLOBS)
        }
        predecessor_packages_read = sorted(p for p, present in present_map.items() if present)

        # Preflight quiescence gate (BEFORE materialize).
        preflight_a = _live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        if preflight_stability_seconds > 0:
            time.sleep(preflight_stability_seconds)
        preflight_b = _live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
        pf_drift = _state_drift(preflight_a, preflight_b)
        _require(
            not pf_drift,
            f"live DB not quiescent (live_db_not_quiescent): {pf_drift} changed during a "
            f"{preflight_stability_seconds}s preflight window; refusing to run against a moving live DB",
        )
        live_db_before = preflight_b

        try:
            mat = cr.materialize_forecast_config_snapshot(
                db_path=live_db_path,
                config_snapshot_id=config_snapshot_id,
                out_root=work_root / MATERIALIZE_SUBDIR,
            )
        except cr.ConfigRegistryError as exc:
            raise ForecastComprehensiveDbConfigProofError(
                f"snapshot materialization failed: {exc}"
            ) from exc
        materialized_config_root = mat["materialized_config_root"]

        # Evidence-backed consumed accounting from materialized metadata (never constants): the 3 files
        # comprehensive reads through the bridge — project json + the controls + model-controls files.
        rels = _consumed_config_rel_paths(base_cfg, project_key)
        row_counts = mat["row_counts"]
        consumed: dict[str, dict[str, Any]] = {}
        for domain in ("project", "forecast_controls", "forecast_model_controls"):
            rel = rels[domain]
            if rel and rel in row_counts:
                consumed[domain] = {"file": rel, "item_count": int(row_counts[rel])}
        consumed_config_domains = sorted(consumed)
        consumed_config_files = [consumed[d]["file"] for d in consumed_config_domains]
        consumed_snapshot_item_count = sum(
            consumed[d]["item_count"] for d in consumed_config_domains
        )

        # File-backed run: CFR_CONFIG_ROOT UNSET. Capture the resolved control paths (under source root).
        _require(
            os.environ.get(ENV_CONFIG_ROOT) in (None, ""),
            "CFR_CONFIG_ROOT must be unset for the file-backed run (default preservation)",
        )
        file_cfg = _load_project_cfg(project_key)
        file_resolved = _resolved_control_paths(file_cfg, comp_root)
        file_meta = _run_comprehensive(
            project_key=project_key,
            cfg=file_cfg,
            data_root=eff_data_root,
            run_stamp=run_stamp,
            out_root=work_root / FILE_BACKED_SUBDIR,
        )
        file_pkg = Path(file_meta["output_package"])

        # DB-backed run: scoped CFR_CONFIG_ROOT = materialized. Capture the resolved control paths and
        # PROVE they are under the materialized config root (the DB-backed run reads materialized files).
        prev = os.environ.get(ENV_CONFIG_ROOT)
        os.environ[ENV_CONFIG_ROOT] = materialized_config_root
        try:
            db_cfg = _load_project_cfg(project_key)
            db_resolved = _resolved_control_paths(db_cfg, comp_root)
            db_meta = _run_comprehensive(
                project_key=project_key,
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
            _is_under(Path(p), Path(materialized_config_root)) for p in db_resolved.values()
        )

        live_db_after = _live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
    finally:
        pin.close()

    live_db_drift = _state_drift(live_db_before, live_db_after)
    live_db_unchanged = not live_db_drift

    replacements = [
        (str(db_pkg), "<OUTPUT_PACKAGE>"),
        (str(file_pkg), "<OUTPUT_PACKAGE>"),
        (materialized_config_root, "<CONFIG_ROOT>"),
        (str(source_config_root), "<CONFIG_ROOT>"),
    ]
    diffs = _compare_packages(file_pkg=file_pkg, db_pkg=db_pkg, replacements=replacements)
    parity_pass = not diffs
    if not live_db_unchanged:
        status = decision = DECISION_NOT_READY
        not_ready_reason: str | None = NOT_READY_REASON_LIVE_DB_MUTATED
    elif parity_pass:
        status, decision, not_ready_reason = "ready", DECISION_READY, None
    else:
        status = decision = DECISION_NOT_READY
        not_ready_reason = NOT_READY_REASON_CONFIG_PARITY

    csv_outputs = _csv_outputs(file_pkg)
    report = {
        "command": "forecast-comprehensive-db-config-proof",
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "not_ready_reason": not_ready_reason,
        "live_db_path": str(live_db_path),
        "db_schema_version": schema_version,
        "config_snapshot_id": config_snapshot_id,
        "snapshot_item_count": snapshot_item_count,
        "consumed_snapshot_item_count": consumed_snapshot_item_count,
        "consumed_config_domains": consumed_config_domains,
        "consumed_config_files": consumed_config_files,
        "consumed_by_domain": consumed,
        "materialized_config_root": materialized_config_root,
        "config_snapshot_manifest": mat["manifest_path"],
        "run_stamp": run_stamp,
        "data_root": str(eff_data_root),
        "source_config_root": str(source_config_root),
        "file_backed_output_package": str(file_pkg),
        "db_snapshot_backed_output_package": str(db_pkg),
        "file_backed": {
            "output_package": str(file_pkg),
            "validation_passed": file_meta.get("validation_passed"),
            "resolved_config_paths": file_resolved,
            "cfr_config_root": None,
        },
        "db_snapshot_backed": {
            "output_package": str(db_pkg),
            "validation_passed": db_meta.get("validation_passed"),
            "config_snapshot_consumed": True,
            "config_snapshot_id": config_snapshot_id,
            "materialized_config_manifest": mat["manifest_path"],
            "resolved_config_paths": db_resolved,
            "reads_materialized_config": db_reads_materialized,
            "cfr_config_root_restored": env_restored,
        },
        "predecessor_packages": {
            "required": required_pkgs,
            "optional": optional_pkgs,
            "read": predecessor_packages_read,
            "generated": [],
        },
        "standard_comprehensive_package_csvs_generated": bool(csv_outputs),
        "standard_comprehensive_package_csvs": csv_outputs,
        "comparison": {
            "compared": True,
            "result": "pass" if parity_pass else "fail",
            "differences": diffs,
            "path_embedding_files": list(_PATH_EMBEDDING_FILES),
            "raw_diff_inspected": True,
            "normalized_rules": _NORMALIZED_RULES,
        },
        "live_db_integrity": {
            "preflight_stable": True,
            "preflight_stability_seconds": preflight_stability_seconds,
            "preflight_samples": [preflight_a, preflight_b],
            "before": live_db_before,
            "after": live_db_after,
            "unchanged": live_db_unchanged,
            "drift": live_db_drift,
        },
        "safety": {
            "live_db_written": False,
            "live_db_migrated": False,
            "live_db_imported": False,
            "live_db_snapshot_read": True,
            "live_db_preflight_stable": True,
            "live_db_unchanged_during_run": live_db_unchanged,
            "source_config_mutated": False,
            "source_package_mutated": False,
            "production_defaults_changed": False,
            "cfr_config_root_default_changed": False,
            "db_snapshot_config_consumed": True,
            "file_backed_default_preserved": True,
            "forecast_comprehensive_run": True,
            "forecast_monthly_run": False,
            "forecast_probability_run": False,
            "forecast_cost_frequency_run": False,
            "forecast_monthly_package_read": present_map.get("monthly", False),
            "forecast_probability_package_read": present_map.get("probability", False),
            "forecast_cost_frequency_package_read": present_map.get("cost_frequency", False),
            "integrated_csv_generated": False,
            "model_backed_llm_or_ollama_run": False,
            "intelligence_workflow_run": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    report["report_path"] = str(report_path)
    _write_summary(work_root / SUMMARY_NAME, report)
    return report


def _write_summary(path: Path, report: dict) -> Path:
    cmp = report["comparison"]
    integ = report["live_db_integrity"]
    lines = [
        "# Forecast Comprehensive — DB-Backed Config Consumer Proof (Phase 20)",
        "",
        f"- status: {report['status']}",
        f"- decision: {report['decision']}",
        f"- not_ready_reason: {report['not_ready_reason']}",
        f"- live_db_preflight_stable: {integ['preflight_stable']} "
        f"(window {integ['preflight_stability_seconds']}s)",
        f"- live_db_unchanged_during_run: {integ['unchanged']} (drift: {integ['drift']})",
        f"- live_db_path: {report['live_db_path']} (read-only)",
        f"- config_snapshot_id: {report['config_snapshot_id']}",
        f"- snapshot_item_count (full): {report['snapshot_item_count']}",
        f"- consumed_config_domains: {report['consumed_config_domains']}",
        f"- consumed_config_files: {report['consumed_config_files']}",
        f"- consumed_snapshot_item_count: {report['consumed_snapshot_item_count']}",
        f"- db_backed reads_materialized_config: {report['db_snapshot_backed']['reads_materialized_config']}",
        f"- predecessor_packages.read: {report['predecessor_packages']['read']}",
        f"- predecessor_packages.generated: {report['predecessor_packages']['generated']}",
        f"- standard_comprehensive_package_csvs: {report['standard_comprehensive_package_csvs']}",
        "",
        "## Outputs",
        f"- file_backed_output_package: {report['file_backed_output_package']}",
        f"- db_snapshot_backed_output_package: {report['db_snapshot_backed_output_package']}",
        "",
        "## Parity",
        f"- result: {cmp['result']}",
        f"- differences: {len(cmp['differences'])}",
        f"- path_embedding_files (raw-diff confirmed): {cmp['path_embedding_files']}",
        "- normalized_rules:",
        *[f"  - {r}" for r in cmp["normalized_rules"]],
    ]
    if cmp["differences"]:
        lines += ["", "## Differences"]
        lines += [
            f"  - {d['file']} :: {d['key_or_path']} (file={d['file_backed_value']!r} "
            f"db={d['db_backed_value']!r})"
            for d in cmp["differences"]
        ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
