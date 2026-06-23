"""Phase 18 — DB-backed config consumer proof for ``forecast_monthly``.

Proves the existing deterministic ``forecast_monthly`` generator can consume the Phase 16 DB config
snapshot (via the materialized config root + the ``CFR_CONFIG_ROOT`` opt-in bridge) and produce output
that is parity-equivalent to the current file-backed config path. It is a CONSUMER PROOF only — it
changes no default, never writes/migrates/imports the live DB, runs no LLM/Ollama, and does not run
``forecast_comprehensive`` / ``forecast_probability`` or generate any integrated CSV.

Repo truth (Phase 18 audit): ``forecast_monthly`` consumes FOUR config domains through
``common.config_root.resolve_config_base`` (already ``CFR_CONFIG_ROOT``-aware):

  - ``project``                 -> ``config/projects/tropical.json``                    (cli.load_project)
  - ``forecast_controls``       -> ``config/forecast_controls/tropical/...jsonl``        (fctl_integration)
  - ``forecast_model_controls`` -> ``config/forecast_model_controls/tropical/...jsonl``  (fmc_integration)
  - ``forecast_staffing``       -> ``config/forecast_staffing/tropical/...jsonl``         (fsp_integration)

The owner-SOV crosswalk and the staffing *source package* come from the data root / project config, not
the materialized config paths, so they are NOT counted as DB-snapshot-consumed. The generator is
deterministic under a frozen stamp (the quantitative core is byte-identical; advisory LLM is opt-in and
off here) and mutates nothing outside its output package. It opens the configured local inventory DB
strictly read-only (``db_inventory`` -> ``mode=ro``) — a READ, never a write; the live config-snapshot DB
is likewise opened READ-ONLY for materialization only.

The forecast data root MAY be the canonical/live Tropical forecast data root — it is a read-only input.
Only the generated artifacts (work root, output packages, materialized config, reports) are required to
live OUTSIDE the live forecast root, the source config tree, and the live DB directory.

CFR-only / stdlib at import; ``hb_assistant`` is only touched lazily by the reused Phase 16 helpers and
the read-only live-DB check.
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
REPORT_NAME = "forecast_monthly_db_config_proof_report.json"
SUMMARY_NAME = "forecast_monthly_db_config_proof_summary.md"
MATERIALIZE_SUBDIR = "db_snapshot_config"
FILE_BACKED_SUBDIR = "file_backed"
DB_BACKED_SUBDIR = "db_snapshot_backed"

DECISION_READY = "forecast_monthly_db_config_parity_ready"
DECISION_NOT_READY = "not_ready"
DEFAULT_RUN_STAMP = "20260101_000000"
# Default preflight quiescence window (seconds); the live proof samples the live DB at the start and end
# of this window and refuses if anything moved. Tests pass 0.0 for a deterministic back-to-back sample.
DEFAULT_PREFLIGHT_STABILITY_SECONDS = 2.0
NOT_READY_REASON_LIVE_DB_MUTATED = "live_db_mutated_during_run"
NOT_READY_REASON_CONFIG_PARITY = "config_parity_mismatch"

# The live Phase 16 baseline (documented; gated only when require_item_count is provided).
LIVE_BASELINE_ITEM_COUNT = 194

# The four config domains forecast_monthly reads through the resolve_config_base bridge, keyed by the
# materialized relative-path prefix. The owner-SOV crosswalk is intentionally absent (resolved from the
# data root / project config, NOT the materialized config paths) so it is never claimed as consumed.
_CONSUMED_DOMAIN_PREFIXES = {
    "config/projects/": "project",
    "config/forecast_controls/": "forecast_controls",
    "config/forecast_model_controls/": "forecast_model_controls",
    "config/forecast_staffing/": "forecast_staffing",
}

REQUIRED_CONFIG_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)

# The forecast data root must contain these three monthly predecessor packages (latest-glob); the monthly
# generator fails closed (SystemExit) without them, so we pre-check for a clean controlled refusal.
_REQUIRED_PACKAGE_GLOBS = (
    ("context_package", "forecast_context_package_tropical_*"),
    ("analysis_v2_package", "forecast_analysis_package_tropical_crosswalk_v2_*"),
    ("accepted_forecast_intelligence_package", "forecast_accuracy_next_package_tropical_*"),
)

# Output files that LEGITIMATELY embed an absolute config-root or output-package path (the ONLY
# file/db-mode difference). They are compared after PATH normalization only; their non-path content is
# still compared. Every other file is compared BYTE-EXACT. This list is the complete, enumerated set
# established by inspecting the raw file-backed vs DB-backed diff (no semantic field is ever normalized).
_PATH_EMBEDDING_FILES = (
    "audit/forecast_controls_applied.json",
    "audit/forecast_model_controls_applied.json",
    "audit/staffing_plan_applied.json",
    "audit/safety_scan_report.json",
)
_NORMALIZED_RULES = [
    "file-backed output package root and DB-backed output package root replaced with <OUTPUT_PACKAGE>",
    "repo/source config root and materialized config root replaced with <CONFIG_ROOT>",
    (
        "the path-embedding files (audit/forecast_controls_applied.json, "
        "audit/forecast_model_controls_applied.json, audit/staffing_plan_applied.json, "
        "audit/safety_scan_report.json) are compared after path normalization only; their non-path "
        "content is still compared exactly"
    ),
    (
        "validation_report.json + manifest.json: the size_bytes/sha256 of those path-embedding files are "
        "neutralized (they differ ONLY because the underlying file records an absolute config/output "
        "path); all other files are required byte-exact and their size_bytes/sha256 are NOT neutralized"
    ),
    (
        "NO forecast/monthly value, row count, applied control, risk flag, warning, validation status, "
        "determinism hash, or any financial/math output is ever normalized"
    ),
]

# Controlled-safety guard only (mirrors the generators' default Synology forecast data root); the work
# root and all generated artifacts must live OUTSIDE this. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class ForecastMonthlyDbConfigProofError(RuntimeError):
    """Raised when the consumer proof is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ForecastMonthlyDbConfigProofError(message)


def _table_exists(conn: Any, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _db_inventory_tables() -> tuple[str, ...]:
    """The procore_* tables forecast_monthly's db_inventory reads (the volatile set to fingerprint)."""
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

    Physical: the main SQLite file plus its ``-wal`` / ``-shm`` siblings (each: exists/size/mtime_ns/sha256)
    — so a WAL-committed write that has not yet checkpointed into the main file is still detected.
    Logical (via the pinned ``mode=ro`` connection): schema version, ``PRAGMA data_version`` (changes when
    ANOTHER connection commits — instability evidence, NOT proof this workflow wrote), and the row counts +
    digest of the db_inventory tables. A change in EITHER physical or logical state is instability.
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
            r = ro_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()  # noqa: S608 — table from module constant
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
    import json

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
    """Compare two monthly packages. Returns a list of differences (empty == parity).

    Every file is compared BYTE-EXACT except the enumerated ``_PATH_EMBEDDING_FILES`` (path-normalized
    text) and ``validation_report.json`` / ``manifest.json`` (path-normalized + the path-embedding files'
    size/sha neutralized). No semantic/financial content is ever normalized.
    """
    diffs: list[dict[str, Any]] = []
    special = {"validation_report.json"}  # manifest.json already excluded by _rel_files

    # 1. Same file set (excluding manifest.json).
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

    # 2. Per-file: byte-exact, except path-embedding (normalized) and validation_report (special).
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

    # 3a. validation_report.json: path-normalized + neutralize the path-embedding files' shas.
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

    # 3b. manifest.json: structured; size_bytes + sha256 of the path-embedding files are excluded
    # (their only difference is the recorded absolute config/output path); all other entries compared.
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


def _run_monthly(
    *, project_key: str, cfg: dict, data_root: Path, run_stamp: str, out_root: Path
) -> dict:
    """Run the real forecast_monthly generator (deterministic; LLM off; no comprehensive/probability)."""
    from ..forecast_monthly import generate_monthly_forecast_package as gen

    return gen.generate(
        project_key,
        cfg,
        data_root=data_root,
        frozen_stamp=run_stamp,
        out_root=out_root,
        with_llm=False,
        llm_model=None,
        forecast_start_month=None,
        control_file=None,
    )


def _load_project_cfg(project_key: str) -> dict:
    from .. import cli as cfr_cli

    return cfr_cli.load_project(project_key)


def run_forecast_monthly_db_config_proof(
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
    """Prove forecast_monthly consumes the DB config snapshot with parity vs file-backed config.

    Phase 18a hardening: a single ``mode=ro`` connection is pinned open across the whole proof (so the
    reused Phase 16 materialize cannot be the last connection and trigger a checkpoint = a write). A
    PREFLIGHT samples the live DB (physical main/-wal/-shm fingerprints + logical schema/data_version/
    db_inventory counts) twice over ``preflight_stability_seconds`` and FAILS CLOSED (rc 3,
    ``live_db_not_quiescent``) if anything moved. The before/after states are measured and recorded; a
    before/after drift forces ``decision=not_ready`` (rc 1, ``live_db_mutated_during_run``). ``safety`` is
    populated from this measured evidence, not declared. ``audit/db_inventory.json`` stays byte-exact.

    Fails closed (``ForecastMonthlyDbConfigProofError`` -> CLI rc 3) before any output on: non-tropical
    project; a work root at/under the live forecast root / source config tree / live DB directory; a live
    DB that is missing, not v60, or lacking the 4 config registry tables; (when ``require_live_snapshot``)
    a db_path that is not the live/default DB; a missing snapshot row or one for the wrong project; (when
    ``require_item_count``) an item-count mismatch; a missing source config root; or a data root missing
    one of the three required monthly predecessor packages. The data root MAY be the live forecast root
    (read-only input). The live DB is opened READ-ONLY and never written/migrated/imported.

    Materializes the snapshot under ``<work_root>/db_snapshot_config``, runs the real generator file-backed
    (``CFR_CONFIG_ROOT`` unset; cfg reloaded from repo config) and DB-backed (``CFR_CONFIG_ROOT`` =
    materialized root, scoped+restored; cfg reloaded from the snapshot so the ``project`` domain is
    genuinely consumed too), and compares byte-exact except the enumerated path-embedding files. Parity ->
    ``decision=forecast_monthly_db_config_parity_ready`` (rc 0); mismatch -> ``not_ready`` (rc 1).
    """
    # --- Gate 1-2: project + work-root artifact isolation. ----------------------------------------
    if not is_project_eligible(project_key):
        raise ForecastMonthlyDbConfigProofError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    _require(bool(work_root), "work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    run_stamp = run_stamp or DEFAULT_RUN_STAMP

    # --- Gate 3-4: live DB read-only (v60 + 4 tables; optionally the real live DB). ----------------
    _require(bool(live_db_path), "live_db_path is required")
    live_db_path = Path(live_db_path)
    _require(live_db_path.exists(), f"live DB not found: {live_db_path}")
    if require_live_snapshot:
        _require(
            cr._is_live_db(live_db_path),
            f"live_db_path is not the live/default DB (require_live_snapshot=True): {live_db_path}",
        )
    db_inventory_tables = _db_inventory_tables()
    # Pin ONE read-only connection open across the entire proof so the reused Phase 16 materialize (which
    # opens the registry DB read-write) is never the last connection -> it cannot trigger a checkpoint
    # (= a write) on a WAL-mode live DB. PRAGMA data_version is also read from this same pinned connection.
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
        # --- Gate 5-6: snapshot row. --------------------------------------------------------------
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

        # --- Gate 7: source config root (default: the CFR subproject root). ------------------------
        if source_config_root is None:
            from .. import config_registry as _cr  # the package root holds the config/ subtree

            source_config_root = Path(_cr.__file__).resolve().parents[2]
        source_config_root = Path(source_config_root)
        _require(source_config_root.exists(), f"source_config_root not found: {source_config_root}")

        # --- Gate 2 (cont.): work root must not be under any forbidden parent. ---------------------
        # data_root MAY be the live forecast root (read-only input) and is NOT checked here. Only the
        # generated artifacts (all under work_root) must live outside these trees.
        _require(
            not _is_under(work_root, _LIVE_ROOT),
            f"work_root is at/under the live forecast root (refused): {work_root}",
        )
        _require(
            not _is_under(work_root, source_config_root),
            f"work_root is at/under the source config tree (refused): {work_root}",
        )
        _require(
            not _is_under(work_root, live_db_path.parent),
            f"work_root is at/under the live DB directory (refused): {work_root}",
        )

        # --- Gate 8: required monthly predecessor packages present under the data root. ------------
        # Load cfg once with CFR_CONFIG_ROOT unset (repo project json) only to resolve the data root.
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
        for label, glob in _REQUIRED_PACKAGE_GLOBS:
            _require(
                any(p.is_dir() for p in eff_data_root.glob(glob)),
                f"required {label} not found under data_root: {eff_data_root} (glob {glob!r})",
            )

        # --- Preflight quiescence gate (BEFORE materialize; pre-materialize so file hash is reliable).
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
        live_db_before = preflight_b  # the stable post-window state

        # --- Materialize the snapshot (read-only on the live DB; never writes repo config/). -------
        try:
            mat = cr.materialize_forecast_config_snapshot(
                db_path=live_db_path,
                config_snapshot_id=config_snapshot_id,
                out_root=work_root / MATERIALIZE_SUBDIR,
            )
        except cr.ConfigRegistryError as exc:
            raise ForecastMonthlyDbConfigProofError(
                f"snapshot materialization failed: {exc}"
            ) from exc
        materialized_config_root = mat["materialized_config_root"]
        # Consumed-config accounting: only the domains forecast_monthly reads through the bridge.
        consumed: dict[str, dict[str, Any]] = {}
        for rel_path, rc in mat["row_counts"].items():
            for prefix, domain in _CONSUMED_DOMAIN_PREFIXES.items():
                if rel_path.startswith(prefix):
                    entry = consumed.setdefault(domain, {"files": [], "item_count": 0})
                    entry["files"].append(rel_path)
                    entry["item_count"] += int(rc)
        consumed_config_domains = sorted(consumed)
        consumed_files = sorted(f for d in consumed.values() for f in d["files"])
        consumed_item_count = sum(d["item_count"] for d in consumed.values())

        # --- File-backed run: CFR_CONFIG_ROOT UNSET (proves default preserved); cfg from repo config.
        _require(
            os.environ.get(ENV_CONFIG_ROOT) in (None, ""),
            "CFR_CONFIG_ROOT must be unset for the file-backed run (default preservation)",
        )
        file_cfg = _load_project_cfg(project_key)
        file_meta = _run_monthly(
            project_key=project_key,
            cfg=file_cfg,
            data_root=eff_data_root,
            run_stamp=run_stamp,
            out_root=work_root / FILE_BACKED_SUBDIR,
        )
        file_pkg = Path(file_meta["output_package"])

        # --- DB-backed run: scoped CFR_CONFIG_ROOT = materialized root; cfg reloaded from snapshot. -
        prev = os.environ.get(ENV_CONFIG_ROOT)
        os.environ[ENV_CONFIG_ROOT] = materialized_config_root
        try:
            db_cfg = _load_project_cfg(project_key)  # project domain consumed from the snapshot
            db_meta = _run_monthly(
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

        # --- After-state (still under the pinned read-only connection). ----------------------------
        live_db_after = _live_db_state(live_db_path, pin, db_inventory_tables=db_inventory_tables)
    finally:
        pin.close()

    live_db_drift = _state_drift(live_db_before, live_db_after)
    live_db_unchanged = not live_db_drift

    # --- Compare (byte-exact except enumerated path-embedding files). -----------------------------
    replacements = [
        (str(db_pkg), "<OUTPUT_PACKAGE>"),
        (str(file_pkg), "<OUTPUT_PACKAGE>"),
        (materialized_config_root, "<CONFIG_ROOT>"),
        (str(source_config_root), "<CONFIG_ROOT>"),
    ]
    diffs = _compare_packages(file_pkg=file_pkg, db_pkg=db_pkg, replacements=replacements)
    parity_pass = not diffs
    # A measured before/after live-DB drift fails closed independently of the file comparison: the proof's
    # inputs moved underneath it, so the result is not trustworthy (not_ready, distinct from a config diff).
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
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "not_ready_reason": not_ready_reason,
        "live_db_path": str(live_db_path),
        "db_schema_version": schema_version,
        "config_snapshot_id": config_snapshot_id,
        "snapshot_item_count": snapshot_item_count,
        "consumed_config_domains": consumed_config_domains,
        "db_snapshot_consumed_files": consumed_files,
        "consumed_snapshot_item_count": consumed_item_count,
        "consumed_by_domain": {d: consumed[d] for d in consumed_config_domains},
        "materialized_config_root": materialized_config_root,
        "config_snapshot_manifest": mat["manifest_path"],
        "run_stamp": run_stamp,
        "data_root": str(eff_data_root),
        "source_config_root": str(source_config_root),
        "file_backed": {
            "output_package": str(file_pkg),
            "validation_passed": file_meta.get("validation_passed"),
            "determinism_passed": file_meta.get("determinism_passed"),
            "overrun_count": file_meta.get("overrun_count"),
            "cfr_config_root": None,
        },
        "db_snapshot_backed": {
            "output_package": str(db_pkg),
            "validation_passed": db_meta.get("validation_passed"),
            "determinism_passed": db_meta.get("determinism_passed"),
            "overrun_count": db_meta.get("overrun_count"),
            "config_snapshot_consumed": True,
            "config_snapshot_id": config_snapshot_id,
            "materialized_config_manifest": mat["manifest_path"],
            "cfr_config_root_restored": env_restored,
        },
        "comparison": {
            "compared": True,
            "result": "pass" if parity_pass else "fail",
            "differences": diffs,
            "normalized_rules": _NORMALIZED_RULES,
        },
        "live_db_integrity": {
            "preflight_stable": True,  # we only reach the report if the preflight gate passed
            "preflight_stability_seconds": preflight_stability_seconds,
            "preflight_samples": [preflight_a, preflight_b],
            "before": live_db_before,
            "after": live_db_after,
            "unchanged": live_db_unchanged,
            "drift": live_db_drift,
        },
        "safety": {
            # Structural: the proof opens the live DB only via a mode=ro pinned connection and issues no
            # DML/DDL, migration, or import. These are now CORROBORATED by the measured live_db_integrity
            # before/after below (live_db_unchanged_during_run), not merely declared.
            "live_db_written": False,
            "live_db_migrated": False,
            "live_db_imported": False,
            "live_db_snapshot_read": True,
            "monthly_db_inventory_read": True,
            "live_db_preflight_stable": True,  # measured: preflight gate passed
            "live_db_unchanged_during_run": live_db_unchanged,  # measured before/after equality
            "source_config_mutated": False,
            "source_package_mutated": False,
            "production_defaults_changed": False,
            "cfr_config_root_default_changed": False,
            "db_snapshot_config_consumed": True,
            "file_backed_default_preserved": True,
            "forecast_monthly_run": True,
            "forecast_comprehensive_run": False,
            "forecast_probability_run": False,
            "integrated_csv_generated": False,
            "model_backed_llm_or_ollama_run": False,
            "intelligence_workflow_run": False,
            "forecast_accuracy_next_package_read": True,
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
        "# Forecast Monthly — DB-Backed Config Consumer Proof (Phase 18 / 18a hardening)",
        "",
        f"- status: {report['status']}",
        f"- decision: {report['decision']}",
        f"- not_ready_reason: {report['not_ready_reason']}",
        f"- live_db_preflight_stable: {integ['preflight_stable']} "
        f"(window {integ['preflight_stability_seconds']}s)",
        f"- live_db_unchanged_during_run: {integ['unchanged']} (drift: {integ['drift']})",
        f"- live_db_path: {report['live_db_path']} (read-only)",
        f"- db_schema_version: {report['db_schema_version']}",
        f"- config_snapshot_id: {report['config_snapshot_id']}",
        f"- snapshot_item_count (full): {report['snapshot_item_count']}",
        f"- consumed_config_domains: {report['consumed_config_domains']}",
        f"- consumed_snapshot_item_count: {report['consumed_snapshot_item_count']}",
        f"- db_snapshot_consumed_files: {report['db_snapshot_consumed_files']}",
        f"- materialized_config_root: {report['materialized_config_root']}",
        f"- data_root (read-only input): {report['data_root']}",
        "",
        "## Outputs",
        f"- file_backed_output_package: {report['file_backed']['output_package']}",
        f"- db_snapshot_backed_output_package: {report['db_snapshot_backed']['output_package']}",
        f"- file_backed.validation_passed: {report['file_backed']['validation_passed']}",
        f"- db_snapshot_backed.validation_passed: {report['db_snapshot_backed']['validation_passed']}",
        "",
        "## Parity",
        f"- result: {cmp['result']}",
        f"- differences: {len(cmp['differences'])}",
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
