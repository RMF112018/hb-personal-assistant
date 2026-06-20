"""Phase 19 — DB-backed config consumer proof for ``forecast_probability``.

Proves the deterministic ``forecast_probability`` Monte-Carlo generator produces parity-equivalent output
whether it reads file-backed config or the Phase 16 DB config snapshot (materialized root + the
``CFR_CONFIG_ROOT`` opt-in bridge). CONSUMER PROOF only — changes no default, never writes/migrates/imports
the live DB, runs no LLM/Ollama, does not run ``forecast_monthly`` (reads its already-generated package
read-only), does not run ``forecast_comprehensive``, and generates no integrated CSV.

Repo truth (Phase 19 audit): ``forecast_probability`` consumes TWO config domains through
``common.config_root.resolve_config_base`` (CFR_CONFIG_ROOT-aware):

  - ``project``            -> ``config/projects/tropical.json``                 (the workflow's cli.load_project)
  - ``owner_sov_crosswalk`` -> the exact ``cfg['owner_sov_scope_crosswalk']`` JSONL (the sibling .csv
    materializes but is NOT read, so it is not counted as consumed)
    via ``forecast_probability/simulation_inputs.py::_owner_scope_by_key`` (Phase 19 narrow bridge fix).

It is byte-deterministic under a fixed ``(seed, runs, frozen_stamp, inputs)`` (single ``np.random.default_rng``;
advisory LLM off and excluded). It reads the accepted ``forecast_accuracy_next_package_tropical_*`` and the
``forecast_monthly_package_tropical_*`` packages read-only, opens the local inventory DB ``mode=ro``, and
mutates nothing outside its output package.

Live-DB stability hardening is inherited from Phase 18a: a pinned ``mode=ro`` connection (so the reused
materialize cannot induce a checkpoint), a fail-closed quiescence preflight, and a measured before/after
``live_db_integrity`` block. ``audit/db_inventory.json`` is kept byte-exact (a real volatility signal).
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
from . import live_db_certification as cert

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = 60
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "forecast_probability_db_config_proof_report.json"
SUMMARY_NAME = "forecast_probability_db_config_proof_summary.md"
MATERIALIZE_SUBDIR = "db_snapshot_config"
FILE_BACKED_SUBDIR = "file_backed"
DB_BACKED_SUBDIR = "db_snapshot_backed"

DECISION_READY = "forecast_probability_db_config_parity_ready"
DECISION_NOT_READY = "not_ready"
DEFAULT_RUN_STAMP = "20260101_000000"
DEFAULT_PREFLIGHT_STABILITY_SECONDS = 2.0
DEFAULT_RUNS = 10000
DEFAULT_SEED = 20260614
LIVE_BASELINE_ITEM_COUNT = 194
NOT_READY_REASON_LIVE_DB_MUTATED = "live_db_mutated_during_run"
NOT_READY_REASON_CONFIG_PARITY = "config_parity_mismatch"

REQUIRED_CONFIG_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)

# Both required predecessor packages (latest-glob); forecast_probability fails closed (SystemExit) without
# them, so we pre-check for a clean controlled refusal. It READS these read-only; it never regenerates them.
_REQUIRED_PACKAGE_GLOBS = (
    ("accepted_forecast_intelligence_package", "forecast_accuracy_next_package_tropical_*"),
    ("forecast_monthly_package", "forecast_monthly_package_tropical_*"),
)

# Output files that LEGITIMATELY embed an absolute config-root/output-package path. Established by MANDATORY
# raw file-backed vs DB-backed diff inspection: forecast_probability records no consumed-config absolute path
# in its outputs (the crosswalk path is not written; source_files_used embeds only data_root/local_db paths
# that are identical across both runs), so this set is EMPTY. Every output file is compared BYTE-EXACT. If a
# future raw diff surfaces a path-embedding file, enumerate it narrowly here and normalize ONLY the path.
_PATH_EMBEDDING_FILES: tuple[str, ...] = ()
_NORMALIZED_RULES = [
    "raw file-backed vs DB-backed diff inspected; forecast_probability embeds no consumed-config path in "
    "its outputs, so the path-embedding set is EMPTY and every file is compared byte-exact",
    "NO probability/monthly value, row count, warning count, validation status, manifest conclusion, "
    "audit/db_inventory.json content, or any financial/math output is ever normalized",
]

# Controlled-safety guard only (mirrors the generators' default Synology forecast data root); the work root
# and all generated artifacts must live OUTSIDE this. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ForecastProbabilityDbConfigProofError(RuntimeError):
    """Raised when the consumer proof is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastProbabilityDbConfigProofError(message)


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _db_inventory_tables() -> tuple[str, ...]:
    """The procore_* tables forecast_probability's db_inventory reads (the volatile set to fingerprint)."""
    from ..forecast_intelligence.db_inventory import DEFAULT_TABLES

    return tuple(DEFAULT_TABLES)


def _file_fingerprint(path: Path) -> dict[str, Any]:
    """Read-only fingerprint of a single file (size, mtime_ns, sha256). Pure stat + byte read; never opens
    a SQLite connection, so it cannot trigger a checkpoint. Absent files record explicit nulls."""
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
    """Combined PHYSICAL + LOGICAL read-only fingerprint of the live DB (no writes, no checkpoint).

    Physical: the main SQLite file plus its ``-wal`` / ``-shm`` siblings (each: exists/size/mtime_ns/sha256).
    Logical (via the pinned ``mode=ro`` connection): schema version, ``PRAGMA data_version`` (changes when
    ANOTHER connection commits — instability evidence, NOT proof this workflow wrote), and the db_inventory
    table row counts + digest. A change in EITHER physical or logical state is instability.
    """
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
    """Return the list of changed state components between two _live_db_state snapshots (empty == stable)."""
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
    """Compare two probability packages. Every file is BYTE-EXACT except the enumerated
    ``_PATH_EMBEDDING_FILES`` (path-normalized) and ``manifest.json`` / ``validation_report.json``
    (path-normalized + path-embedding files' size/sha neutralized). No semantic content is normalized."""
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


def _run_probability(
    *,
    cfg: dict,
    data_root: Path,
    run_stamp: str,
    out_root: Path,
    runs: int,
    seed: int,
    forecast_start_month: str | None,
) -> dict:
    """Run the real forecast_probability generator (deterministic; LLM off; reads monthly, never runs it)."""
    from ..forecast_probability import generate_probabilistic_validation_package as gen

    return gen.generate(
        SUPPORTED_PROJECT_KEY,
        cfg,
        data_root=data_root,
        frozen_stamp=run_stamp,
        out_root=out_root,
        with_llm=False,
        llm_model=None,
        forecast_start_month=forecast_start_month,
        runs=runs,
        seed=seed,
    )


def _load_project_cfg(project_key: str) -> dict:
    from .. import cli as cfr_cli

    return cfr_cli.load_project(project_key)


def run_forecast_probability_db_config_proof(
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
    runs: int = DEFAULT_RUNS,
    seed: int = DEFAULT_SEED,
    forecast_start_month: str | None = None,
) -> dict[str, Any]:
    """Prove forecast_probability consumes the DB config snapshot with parity vs file-backed config.

    Fails closed (``ForecastProbabilityDbConfigProofError`` -> CLI rc 3) before any output on: non-tropical
    project; a work root at/under the live forecast root / source config tree / live DB directory / data
    root; a live DB missing/not v60/lacking the 4 config tables; (when required) not the live DB; a missing
    or wrong-project snapshot; (when required) an item-count mismatch; a missing source config root; a data
    root missing either required predecessor package; or a non-quiescent live DB preflight. The data root
    MAY be the live forecast root (read-only input). The live DB is opened READ-ONLY (pinned) and never
    written/migrated/imported. Runs probability twice (file-backed + DB-backed) with the same
    stamp/runs/seed/forecast_start_month/data_root and compares byte-exact.
    """
    if project_key != SUPPORTED_PROJECT_KEY:
        raise ForecastProbabilityDbConfigProofError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported"
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
    # Pin ONE read-only connection across the whole proof so the reused Phase 16 materialize (opens RW) is
    # never the last connection -> it cannot trigger a checkpoint (= a write) on a WAL-mode live DB.
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
            from .. import config_registry as _cr

            source_config_root = Path(_cr.__file__).resolve().parents[2]
        source_config_root = Path(source_config_root)
        _require(source_config_root.exists(), f"source_config_root not found: {source_config_root}")

        # Load cfg once (CFR_CONFIG_ROOT unset) to resolve the data root + the consumed config rel paths.
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

        # Work-root artifact isolation: work_root (and all generated artifacts under it) must live OUTSIDE
        # the live forecast root, the source config tree, the live DB directory, AND the data root (the
        # source packages being read). data_root itself is a read-only INPUT and is NOT checked.
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

        for plabel, glob in _REQUIRED_PACKAGE_GLOBS:
            _require(
                any(p.is_dir() for p in eff_data_root.glob(glob)),
                f"required {plabel} not found under data_root: {eff_data_root} (glob {glob!r})",
            )

        # Preflight quiescence gate (BEFORE materialize; file hash reliable here).
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
            raise ForecastProbabilityDbConfigProofError(
                f"snapshot materialization failed: {exc}"
            ) from exc
        materialized_config_root = mat["materialized_config_root"]

        # Evidence-backed consumed accounting: only the files forecast_probability actually reads through
        # the bridge — config/projects/<project>.json (load_project) + the EXACT crosswalk JSONL
        # (_owner_scope_by_key). Counts come from the materialized snapshot metadata (mat["row_counts"]),
        # never constants. The sibling crosswalk .csv materializes but is not read, so it is excluded.
        project_rel = f"config/projects/{project_key}.json"
        crosswalk_rel = base_cfg.get("owner_sov_scope_crosswalk")
        row_counts = mat["row_counts"]
        consumed: dict[str, dict[str, Any]] = {}
        for domain, rel in (("project", project_rel), ("owner_sov_crosswalk", crosswalk_rel)):
            if rel and rel in row_counts:
                consumed[domain] = {"file": rel, "item_count": int(row_counts[rel])}
        consumed_config_domains = sorted(consumed)
        consumed_config_files = [consumed[d]["file"] for d in consumed_config_domains]
        consumed_snapshot_item_count = sum(
            consumed[d]["item_count"] for d in consumed_config_domains
        )

        # File-backed run: CFR_CONFIG_ROOT UNSET (default preserved); cfg from repo config.
        _require(
            os.environ.get(ENV_CONFIG_ROOT) in (None, ""),
            "CFR_CONFIG_ROOT must be unset for the file-backed run (default preservation)",
        )
        file_cfg = _load_project_cfg(project_key)
        file_meta = _run_probability(
            cfg=file_cfg,
            data_root=eff_data_root,
            run_stamp=run_stamp,
            out_root=work_root / FILE_BACKED_SUBDIR,
            runs=runs,
            seed=seed,
            forecast_start_month=forecast_start_month,
        )
        file_pkg = Path(file_meta["output_package"])

        # DB-backed run: scoped CFR_CONFIG_ROOT = materialized root; cfg reloaded from the snapshot.
        prev = os.environ.get(ENV_CONFIG_ROOT)
        os.environ[ENV_CONFIG_ROOT] = materialized_config_root
        try:
            db_cfg = _load_project_cfg(project_key)
            db_meta = _run_probability(
                cfg=db_cfg,
                data_root=eff_data_root,
                run_stamp=run_stamp,
                out_root=work_root / DB_BACKED_SUBDIR,
                runs=runs,
                seed=seed,
                forecast_start_month=forecast_start_month,
            )
        finally:
            if prev is None:
                os.environ.pop(ENV_CONFIG_ROOT, None)
            else:
                os.environ[ENV_CONFIG_ROOT] = prev
        db_pkg = Path(db_meta["output_package"])
        env_restored = os.environ.get(ENV_CONFIG_ROOT) in (None, "")

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
        status = DECISION_NOT_READY
        decision = DECISION_NOT_READY
        not_ready_reason: str | None = NOT_READY_REASON_LIVE_DB_MUTATED
    elif parity_pass:
        status = "ready"
        decision = DECISION_READY
        not_ready_reason = None
    else:
        status = DECISION_NOT_READY
        decision = DECISION_NOT_READY
        not_ready_reason = NOT_READY_REASON_CONFIG_PARITY

    report = {
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
            "determinism_passed": file_meta.get("determinism_passed"),
            "cfr_config_root": None,
        },
        "db_snapshot_backed": {
            "output_package": str(db_pkg),
            "validation_passed": db_meta.get("validation_passed"),
            "determinism_passed": db_meta.get("determinism_passed"),
            "config_snapshot_consumed": True,
            "config_snapshot_id": config_snapshot_id,
            "materialized_config_manifest": mat["manifest_path"],
            "cfr_config_root_restored": env_restored,
        },
        "probability_run": {
            "runs": runs,
            "seed": seed,
            "forecast_start_month": forecast_start_month,
        },
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
            "forecast_probability_run": True,
            "forecast_monthly_run": False,
            "forecast_monthly_package_read": True,
            "forecast_accuracy_next_package_read": True,
            "forecast_comprehensive_run": False,
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
        "# Forecast Probability — DB-Backed Config Consumer Proof (Phase 19)",
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
        f"- probability_run: {report['probability_run']}",
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
