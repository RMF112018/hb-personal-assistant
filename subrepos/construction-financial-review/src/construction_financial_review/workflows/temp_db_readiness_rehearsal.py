"""Phase 11 — controlled temp-DB preparation + readiness rehearsal (operator-safe).

Closes the operational gap Phase 10 left open: Phase 10 *consumes* an already-prepared non-live v59
DB, but provided no controlled way to build one. Phase 11 runs the whole rehearsal in one explicit
operation:

    explicit Tropical source package -> non-live temp v59 DB (migrate + project) -> Phase 10
    readiness gate -> deterministic rehearsal evidence report.

It is a rehearsal, not a default flip: it never writes the live/default DB, never makes DB-backed
reads the default, runs no model-backed/intelligence/comprehensive/CSV workflow, and adds no schema.

CFR-only / stdlib at import time: the migration + projection helpers (`hb_assistant`) are imported
LAZILY, only inside the explicit DB-preparation path; the Phase 10 readiness gate is reused as-is.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from .db_cutover_readiness import (
    REQUIRED_SCHEMA_VERSION,
    REQUIRED_SOURCE_DOMAIN_TABLES,
    DbCutoverReadinessError,
    run_db_cutover_readiness,
)

SUPPORTED_PROJECT_KEY = "tropical"
REHEARSAL_REPORT_SCHEMA_VERSION = 1

# The explicit Tropical source package the source-domain projection consumes; its PARENT is the data
# root (containing the sibling owner/procore packages the context generator reads).
EXPECTED_SOURCE_PACKAGE_NAME = "twn_cost_forecast_json_package"
# Required source JSONL members under <source_package>/data/ (structural validity check).
_REQUIRED_SOURCE_MEMBERS = (
    "data/budget_details.jsonl",
    "data/cost_entries.jsonl",
    "data/monthly_actuals_by_budget_code.jsonl",
)

TEMP_DB_SUBDIR = "temp_dbs"
DEFAULT_TEMP_DB_NAME = "forecast_source_domain_tropical.sqlite"
REHEARSAL_REPORT_NAME = "temp_db_readiness_rehearsal_report.json"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class TempDbRehearsalError(RuntimeError):
    """Raised when a rehearsal run is rejected by a preflight/prep safety check (fail closed)."""


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _schema_version(db_path: Path) -> int:
    """Read-only ``MAX(schema_migrations.version)`` (URL-encoded path, mode=ro never creates)."""
    uri = f"file:{urllib.parse.quote(str(Path(db_path).resolve(strict=False)))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def _tropical_rowcount(db_path: Path, table: str) -> int:
    """Read-only count of ``project_key='tropical'`` rows for one required source-domain table."""
    uri = f"file:{urllib.parse.quote(str(Path(db_path).resolve(strict=False)))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        # ``table`` is only ever one of REQUIRED_SOURCE_DOMAIN_TABLES (module constants).
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_key = ?", (SUPPORTED_PROJECT_KEY,)
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()


def _refuse_if_live_db(db_path: Path) -> None:
    """Fail closed if ``db_path`` is the live/default DB (lazy module-ref call; monkeypatchable)."""
    try:
        from hb_assistant.construction.forecast import source_domain_engine
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise TempDbRehearsalError(
            f"cannot verify db_path against the live DB; hb_assistant unavailable: {exc}"
        ) from exc
    if source_domain_engine.is_live_db_path(Path(db_path)):
        raise TempDbRehearsalError(
            f"db_path resolves to the live/default DB (or is unresolvable): {db_path}"
        )


def run_temp_db_readiness_rehearsal(
    *,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Rehearse the DB-backed chain from explicit source data to Phase 10 readiness evidence.

    Preflight fails closed (``TempDbRehearsalError``) BEFORE creating any output on: non-tropical
    project; missing/non-dir source package or wrong name/structure; missing work root or a work root
    under the live forecast root; a non-empty work root; empty context stamp; a db_path outside the
    work root, equal to the live DB, or already existing. Then migrates + projects a non-live temp v59
    DB and runs the Phase 10 readiness gate; a DB-prep/projection failure also fails closed. Returns
    the rehearsal report dict (plus ``report_path``); ``status`` is ``passed`` (readiness ready) or
    ``failed`` (readiness not_ready).
    """
    # --- Preflight (fail closed before any output). ----------------------------------------------
    if project_key != SUPPORTED_PROJECT_KEY:
        raise TempDbRehearsalError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported "
            "in Phase 11 (multi-project generalization is deferred)"
        )
    if not source_package:
        raise TempDbRehearsalError("source_package is required for a rehearsal run")
    source_package = Path(source_package)
    if not source_package.exists() or not source_package.is_dir():
        raise TempDbRehearsalError(f"source_package not found or not a directory: {source_package}")
    if source_package.name != EXPECTED_SOURCE_PACKAGE_NAME:
        raise TempDbRehearsalError(
            f"source_package is not the expected Tropical package "
            f"{EXPECTED_SOURCE_PACKAGE_NAME!r}: {source_package.name}"
        )
    missing = [m for m in _REQUIRED_SOURCE_MEMBERS if not (source_package / m).exists()]
    if missing:
        raise TempDbRehearsalError(
            f"source_package is structurally invalid (missing {missing}): {source_package}"
        )

    if not work_root:
        raise TempDbRehearsalError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise TempDbRehearsalError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise TempDbRehearsalError("context_stamp is required (explicit; no latest-glob)")

    # Resolve the temp DB path (derive under work_root if omitted) and validate it.
    if db_path is None:
        db_path = work_root / TEMP_DB_SUBDIR / DEFAULT_TEMP_DB_NAME
    db_path = Path(db_path)
    # Robust containment: resolve BOTH paths so symlinks / ".." cannot escape the work root.
    resolved_db = db_path.resolve(strict=False)
    resolved_work = work_root.resolve(strict=False)
    if not (resolved_db == resolved_work or resolved_db.is_relative_to(resolved_work)):
        raise TempDbRehearsalError(
            f"db_path must be under work_root (refused): {db_path} not under {work_root}"
        )
    _refuse_if_live_db(db_path)
    if db_path.exists():
        raise TempDbRehearsalError(
            f"db_path already exists (refusing to reuse for a deterministic rehearsal): {db_path}"
        )
    # Checked after db_path (a pre-existing DB under work_root reports the clearer db-path error).
    if work_root.exists() and any(work_root.iterdir()):
        raise TempDbRehearsalError(
            f"work_root already contains output (refusing to reuse): {work_root}"
        )

    data_root = source_package.parent

    # --- DB preparation (lazy hb_assistant imports; explicit non-live temp DB only). -------------
    from hb_assistant.construction.forecast import source_domain_engine
    from hb_assistant.store.migrator import SQLiteMigrator

    db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db_path)).apply()
    schema_version = _schema_version(db_path)
    if schema_version < REQUIRED_SCHEMA_VERSION:
        raise TempDbRehearsalError(
            f"migrated temp DB schema version {schema_version} is below the required "
            f"{REQUIRED_SCHEMA_VERSION}: {db_path}"
        )

    projection = source_domain_engine.project_source_domain(
        source_package=source_package,
        project_key=project_key,
        db_path=db_path,
        apply=True,
    )
    if not projection.get("ok"):
        raise TempDbRehearsalError(
            f"source-domain projection failed: {projection.get('reason', 'unknown')} ({db_path})"
        )

    required_tables = {
        t: {"rows": _tropical_rowcount(db_path, t)} for t in REQUIRED_SOURCE_DOMAIN_TABLES
    }
    empty = sorted(t for t, c in required_tables.items() if c["rows"] == 0)
    if empty:
        raise TempDbRehearsalError(
            f"projected temp DB has empty required v59 source-domain tables for "
            f"project_key={project_key!r} {empty}: {db_path}"
        )

    # --- Phase 10 readiness gate against the prepared temp DB. -----------------------------------
    try:
        readiness = run_db_cutover_readiness(
            data_root=data_root,
            work_root=work_root,
            context_stamp=context_stamp,
            db_path=db_path,
            project_key=project_key,
        )
    except DbCutoverReadinessError as exc:
        raise TempDbRehearsalError(f"readiness gate refused the prepared temp DB: {exc}") from exc

    passed = readiness["decision"] == "ready_for_guarded_operator_use"
    status = "passed" if passed else "failed"

    report = {
        "schema_version": REHEARSAL_REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": readiness["decision"],
        "source_package": str(source_package),
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "db": {
            "path": str(db_path),
            "created": True,
            "schema_version": schema_version,
            "live_db_refused": True,
        },
        "projection": {
            "applied": True,
            "required_tables": required_tables,
        },
        "readiness": {
            "decision": readiness["decision"],
            "report_path": readiness["report_path"],
        },
        # Grounded in this controlled run's preflight + explicit-path checks (NOT a global FS audit):
        # work root is verified outside the live root and the temp DB is verified to not be the live DB.
        "safety": {
            "production_defaults_changed": False,
            "live_db_written": False,
            "live_root_written": False,
        },
    }
    report_path = work_root / REHEARSAL_REPORT_NAME
    _write_json_deterministic(report_path, report)
    return {**report, "report_path": str(report_path)}
