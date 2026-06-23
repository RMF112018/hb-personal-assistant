"""Phase 3 (DB-native remediation) — controlled live DB run-output + decision-support projection.

Generalizes the Phase-14 gated live write from the v59 source-domain tables to the forecast
RUN GRAPH: the ``forecast_runs`` anchor (v58) + the v63 run-output family + the v66
decision-support family. The shape is identical and equally narrow/reversible:

    fresh non-live temp projection (migrate -> project v59 -> forecast_runs anchor -> v63 -> v66)
    -> verify -> BACKUP the live DB -> ONE transaction that replaces ONLY ``project_key='tropical'``
    rows in the target tables with rows copied from the temp DB -> deterministic evidence ->
    re-project a fresh temp and certify live == reprojection (raw_json digests).

It never migrates the live DB, never projects directly against it, and touches only tropical
rows of the target tables (non-tropical rows preserved). v59 is NOT written here (Phase 14
already populated it); it is read on the live DB to confirm the v66 derivation input is present,
and re-projected into the temp DBs so the temp v66 derivation matches live.

CFR-only / stdlib at import; ``hb_assistant`` (migrator + the three forecast projectors) is
imported lazily and only against NON-LIVE temp DBs. Reuses Phase 13 (``live_db_certification``)
for the read-only audit/digests/connection and Phase 14 helpers for columns/counts/verify.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.project_eligibility import (
    eligible_projects,
    is_project_eligible,
    source_package_name,
)
from . import live_db_certification as cert
from . import live_db_source_domain_projection as p14
from .db_cutover_readiness import REQUIRED_SOURCE_DOMAIN_TABLES

SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "live_db_run_output_projection_report.json"

REQUIRED_SCHEMA_VERSION = 66  # v63 (run-output) + v66 (decision-support) must be present
BACKUP_SUBDIR = "backups"
BACKUP_NAME = "hb-personal-assistant.before-phase3-run-output.sqlite"
WRITE_TEMP_SUBDIR = "temp_dbs"
WRITE_TEMP_NAME = "forecast_run_output_tropical.sqlite"
CERT_TEMP_SUBDIR = "post_write_cert"
CERT_TEMP_NAME = "forecast_run_output_tropical.sqlite"

RUN_ANCHOR_TABLE = "forecast_runs"
V63_TABLES = (
    "forecast_outputs",
    "forecast_output_budget_codes",
    "forecast_output_risks",
    "forecast_output_monthly",
    "forecast_output_probability",
    "forecast_output_changes",
    "forecast_output_staffing",
    "forecast_output_commitment_exposure",
    "forecast_output_schedule_phasing",
)
V66_TABLES = (
    "forecast_project_maturity_snapshots",
    "forecast_data_availability_profiles",
    "forecast_confidence_scorecards",
    "forecast_confidence_factors",
    "forecast_method_eligibility",
    "forecast_model_selection_decisions",
)
# Order is informational only — the live txn uses PRAGMA defer_foreign_keys.
WRITE_TABLES = (RUN_ANCHOR_TABLE, *V63_TABLES, *V66_TABLES)
# Tables certified by raw_json digest (forecast_runs has no raw_json — verified by presence).
DIGEST_TABLES = (*V63_TABLES, *V66_TABLES)

DECISION_CERTIFIED = "live_db_run_output_certified"
DECISION_NOT_READY = "not_ready"


class LiveDbRunOutputProjectionError(RuntimeError):
    """Raised when a controlled live-DB run-output projection is refused (fail closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_live_db(*, live_db_path: Path, work_root: Path, wal_size: int) -> dict[str, Any]:
    """Byte-for-byte backup (fail closed on nonzero WAL). Mirrors Phase 14; phase-3 backup name."""
    if wal_size > 0:
        raise LiveDbRunOutputProjectionError(
            f"live DB has a nonzero WAL ({wal_size} bytes); refusing a byte-copy backup that would "
            "miss WAL frames (no safe consistent-snapshot mechanism is enabled here)"
        )
    backup_path = work_root / BACKUP_SUBDIR / BACKUP_NAME
    if backup_path.exists():
        raise LiveDbRunOutputProjectionError(
            f"backup path already exists (refusing to overwrite): {backup_path}"
        )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_db_path, backup_path)
    conn = cert._ro_conn(backup_path)
    try:
        schema_version = p14._schema_version(conn)
    finally:
        conn.close()
    if schema_version < REQUIRED_SCHEMA_VERSION:
        raise LiveDbRunOutputProjectionError(
            f"backup verification failed: schema version {schema_version} < {REQUIRED_SCHEMA_VERSION}"
        )
    return {
        "path": str(backup_path),
        "size_bytes": int(Path(backup_path).stat().st_size),
        "sha256": p14._sha256_file(backup_path),
        "verified_readable": True,
        "schema_version": schema_version,
    }


def _build_temp_projection(
    *,
    temp_db_path: Path,
    source_package: Path,
    analysis_package: Path,
    project_key: str,
    run_id: str,
    monthly_package: Path | None,
    probability_package: Path | None,
    comprehensive_package: Path | None,
    staffing_package: Path | None,
    accuracy_package: Path | None,
    context_package: Path | None = None,
) -> dict[str, Any]:
    """Build a fresh NON-LIVE temp DB: migrate -> v59 -> run anchor -> v63 -> v66. Capture rows.

    Returns per-table columns/rows/counts (for WRITE_TABLES) and raw_json digests (DIGEST_TABLES).
    Lazy hb_assistant import; refuses to reuse an existing temp DB (deterministic run).
    """
    if temp_db_path.exists():
        raise LiveDbRunOutputProjectionError(
            f"temp db_path already exists (refusing to reuse): {temp_db_path}"
        )
    from hb_assistant.construction.forecast import (
        decision_support_engine,
        output_projection_engine,
        source_domain_engine,
    )
    from hb_assistant.store.migrator import SQLiteMigrator

    temp_db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(temp_db_path)).apply()

    sd = source_domain_engine.project_source_domain(
        source_package=source_package, project_key=project_key, db_path=temp_db_path, apply=True
    )
    if not sd.get("ok"):
        raise LiveDbRunOutputProjectionError(
            f"v59 source-domain projection into temp failed: {sd.get('reason', 'unknown')}"
        )

    # forecast_runs anchor (FK parent for v63/v66). Inserted before the output projectors run.
    anchor_conn = sqlite3.connect(str(temp_db_path))
    try:
        anchor_conn.execute(
            "INSERT INTO forecast_runs (run_id, project_key, context_package, status, created_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, project_key, Path(analysis_package).name, "projected", _now()),
        )
        anchor_conn.commit()
    finally:
        anchor_conn.close()

    ro = output_projection_engine.project_run_output(
        analysis_package=analysis_package,
        project_key=project_key,
        db_path=temp_db_path,
        apply=True,
        run_id=run_id,
        monthly_package=monthly_package,
        probability_package=probability_package,
        comprehensive_package=comprehensive_package,
        staffing_package=staffing_package,
        context_package=context_package,
    )
    if not ro.get("ok"):
        raise LiveDbRunOutputProjectionError(
            f"v63 run-output projection into temp failed: {ro.get('reason', 'unknown')}"
        )

    ds = decision_support_engine.project_decision_support(
        db_path=temp_db_path,
        analysis_package=analysis_package,
        project_key=project_key,
        apply=True,
        run_id=run_id,
        accuracy_package=accuracy_package,
    )
    if not ds.get("ok"):
        raise LiveDbRunOutputProjectionError(
            f"v66 decision-support projection into temp failed: {ds.get('reason', 'unknown')}"
        )

    conn = cert._ro_conn(temp_db_path)
    try:
        schema_version = p14._schema_version(conn)
        columns: dict[str, list[str]] = {}
        rows: dict[str, list[tuple]] = {}
        counts: dict[str, int] = {}
        digests: dict[str, dict[str, str]] = {}
        v59_counts = {
            t: p14._tropical_count(conn, t, project_key) for t in REQUIRED_SOURCE_DOMAIN_TABLES
        }
        for t in WRITE_TABLES:
            cols = p14._columns(conn, t)
            columns[t] = cols
            collist = ", ".join(cols)
            rows[t] = conn.execute(
                f"SELECT {collist} FROM {t} WHERE project_key = ?", (project_key,)
            ).fetchall()
            counts[t] = p14._tropical_count(conn, t, project_key)
        for t in DIGEST_TABLES:
            byte_d, canon_d = cert._digests(cert._raw_strings(conn, t, project_key=project_key))
            digests[t] = {"raw_json_digest": byte_d, "canonical_digest": canon_d}
    finally:
        conn.close()

    return {
        "path": str(temp_db_path),
        "schema_version": schema_version,
        "columns": columns,
        "rows": rows,
        "counts": counts,
        "digests": digests,
        "v59_counts": v59_counts,
    }


def run_controlled_live_db_run_output_projection(
    *,
    analysis_package: Path,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    run_id: str,
    live_db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
    allow_live_db_write: bool = False,
    allow_replace_existing: bool = False,
    expected_counts: dict[str, int] | None = None,
    monthly_package: Path | None = None,
    probability_package: Path | None = None,
    comprehensive_package: Path | None = None,
    staffing_package: Path | None = None,
    accuracy_package: Path | None = None,
    context_package: Path | None = None,
) -> dict[str, Any]:
    """Populate live forecast_runs anchor + v63 run-output + v66 decision-support for tropical.

    Gated + backed up + certified, exactly like Phase 14. rc 0 on certified_match, rc 1 if the
    post-write certification does not match (backup recorded for restore), rc 3 (raises) on any
    unsafe/missing input, nonzero-WAL live DB, schema/column/count mismatch, backup failure, or
    transaction failure (rolled back). v59 is read (not written); only tropical rows of the
    run-graph tables are replaced; non-tropical rows are preserved.
    """
    # --- Preflight (fail closed). ----------------------------------------------------------------
    if not is_project_eligible(project_key):
        raise LiveDbRunOutputProjectionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not allow_live_db_write:
        raise LiveDbRunOutputProjectionError(
            "live DB write requires allow_live_db_write=True (explicit gate; refused)"
        )
    if not analysis_package:
        raise LiveDbRunOutputProjectionError("analysis_package is required")
    analysis_package = Path(analysis_package)
    if not analysis_package.exists() or not analysis_package.is_dir():
        raise LiveDbRunOutputProjectionError(
            f"analysis_package not found or not a directory: {analysis_package}"
        )
    if not source_package:
        raise LiveDbRunOutputProjectionError("source_package is required")
    source_package = Path(source_package)
    if not source_package.exists() or not source_package.is_dir():
        raise LiveDbRunOutputProjectionError(
            f"source_package not found or not a directory: {source_package}"
        )
    expected_source = source_package_name(project_key)
    if source_package.name != expected_source:
        raise LiveDbRunOutputProjectionError(
            f"source_package is not the expected Tropical package "
            f"{expected_source!r}: {source_package.name}"
        )
    if not work_root:
        raise LiveDbRunOutputProjectionError("work_root is required (explicit; no implicit root)")
    work_root = Path(work_root)
    if p14._is_under(work_root, p14._LIVE_ROOT):
        raise LiveDbRunOutputProjectionError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise LiveDbRunOutputProjectionError("context_stamp is required (explicit; no latest-glob)")
    if not run_id:
        raise LiveDbRunOutputProjectionError("run_id is required (the forecast_runs anchor key)")

    live_db_path = Path(live_db_path) if live_db_path is not None else cert._resolve_live_db_path()
    if not cert._is_live_db(live_db_path):
        raise LiveDbRunOutputProjectionError(
            f"db is not the live/default DB (this writes the live DB only): {live_db_path}"
        )
    if not live_db_path.exists():
        raise LiveDbRunOutputProjectionError(f"live DB not found: {live_db_path}")

    live_before = cert._file_provenance(live_db_path)

    # --- Pre-write read-only audit: schema >= 66, run-graph tables present, live v59 populated. ---
    pre_conn = cert._ro_conn(live_db_path)
    try:
        live_schema_version = p14._schema_version(pre_conn)
        present = {t: cert._table_exists(pre_conn, t) for t in WRITE_TABLES}
        live_v59_counts = {
            t: cert._rowcount(pre_conn, t, project_key=project_key)
            for t in REQUIRED_SOURCE_DOMAIN_TABLES
        }
        existing_tropical = {
            t: cert._rowcount(pre_conn, t, project_key=project_key)
            for t in (*V63_TABLES, *V66_TABLES)
        }
    finally:
        pre_conn.close()
    if live_schema_version < REQUIRED_SCHEMA_VERSION:
        raise LiveDbRunOutputProjectionError(
            f"live DB schema version {live_schema_version} < {REQUIRED_SCHEMA_VERSION}"
        )
    missing = [t for t, ok in present.items() if not ok]
    if missing:
        raise LiveDbRunOutputProjectionError(f"live DB is missing run-graph tables: {missing}")
    if sum(live_v59_counts.values()) == 0:
        raise LiveDbRunOutputProjectionError(
            "live DB has no tropical v59 source-domain rows; run Phase 14 first "
            "(the v66 decision-support derivation reads v59)"
        )
    already = sum(existing_tropical.values())
    if already > 0 and not allow_replace_existing:
        raise LiveDbRunOutputProjectionError(
            f"live DB already has {already} tropical run-output/decision-support rows; pass "
            "allow_replace_existing=True to replace them (tropical rows only)"
        )

    # --- Fresh non-live temp projection (write source). ------------------------------------------
    temp = _build_temp_projection(
        temp_db_path=work_root / WRITE_TEMP_SUBDIR / WRITE_TEMP_NAME,
        source_package=source_package,
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        monthly_package=monthly_package,
        probability_package=probability_package,
        comprehensive_package=comprehensive_package,
        staffing_package=staffing_package,
        accuracy_package=accuracy_package,
        context_package=context_package,
    )

    # v59 consistency gate: temp v59 must equal live v59 (else the temp v66 derivation would
    # not reflect the live DB — refuse rather than write inconsistent decision-support).
    v59_mismatch = [
        {"table": t, "live": live_v59_counts[t], "temp": temp["v59_counts"][t]}
        for t in REQUIRED_SOURCE_DOMAIN_TABLES
        if live_v59_counts[t] != temp["v59_counts"][t]
    ]
    if v59_mismatch:
        raise LiveDbRunOutputProjectionError(
            f"temp v59 counts differ from live v59 (source drift); refusing: {v59_mismatch}"
        )

    # --- Expected-count gate (operator-supplied) — BEFORE backup/write. --------------------------
    count_mismatches = [
        {"table": t, "expected": int(w), "actual": temp["counts"].get(t)}
        for t, w in (expected_counts or {}).items()
        if int(w) != temp["counts"].get(t)
    ]
    if count_mismatches:
        raise LiveDbRunOutputProjectionError(
            f"expected temp-projection row counts did not match: {count_mismatches}"
        )

    # --- Backup (fail closed on nonzero WAL). ----------------------------------------------------
    backup = _backup_live_db(
        live_db_path=live_db_path,
        work_root=work_root,
        wal_size=int(live_before.get("wal_size_bytes", 0)),
    )

    # --- Live write: one transaction; tropical rows of the run-graph tables only. ----------------
    write_result: dict[str, dict[str, int]] = {}
    committed = False
    conn = sqlite3.connect(str(live_db_path))
    try:
        for t in WRITE_TABLES:
            live_cols = p14._columns(conn, t)
            if live_cols != temp["columns"][t]:
                raise LiveDbRunOutputProjectionError(
                    f"column mismatch for {t}: live {live_cols} != temp {temp['columns'][t]}"
                )
        # Defer FK checks to commit so DELETE/INSERT order across the run graph is unconstrained.
        conn.execute("PRAGMA defer_foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        for t in WRITE_TABLES:
            cols = temp["columns"][t]
            collist = ", ".join(cols)
            placeholders = ", ".join("?" * len(cols))
            deleted = conn.execute(
                f"DELETE FROM {t} WHERE project_key = ?", (project_key,)
            ).rowcount
            conn.executemany(
                f"INSERT INTO {t} ({collist}) VALUES ({placeholders})", temp["rows"][t]
            )
            p14._verify_inserted(conn, t, project_key, temp["counts"][t])
            write_result[t] = {"deleted": int(deleted), "inserted": int(temp["counts"][t])}
        conn.commit()
        committed = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    live_after = cert._file_provenance(live_db_path)

    # --- Post-write certification: re-project a FRESH temp and compare live raw_json digests. ----
    cert_temp = _build_temp_projection(
        temp_db_path=work_root / CERT_TEMP_SUBDIR / CERT_TEMP_NAME,
        source_package=source_package,
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        monthly_package=monthly_package,
        probability_package=probability_package,
        comprehensive_package=comprehensive_package,
        staffing_package=staffing_package,
        accuracy_package=accuracy_package,
        context_package=context_package,
    )
    cert_tables: dict[str, dict[str, Any]] = {}
    all_match = True
    live_conn = cert._ro_conn(live_db_path)
    try:
        for t in DIGEST_TABLES:
            live_byte, live_canon = cert._digests(
                cert._raw_strings(live_conn, t, project_key=project_key)
            )
            ref = cert_temp["digests"][t]
            match = live_byte == ref["raw_json_digest"] and live_canon == ref["canonical_digest"]
            cert_tables[t] = {
                "match": match,
                "live": live_byte,
                "reprojected": ref["raw_json_digest"],
            }
            all_match = all_match and match
        anchor_present = cert._rowcount(live_conn, RUN_ANCHOR_TABLE, project_key=project_key) > 0
    finally:
        live_conn.close()
    certified = all_match and anchor_present

    decision = DECISION_CERTIFIED if certified else DECISION_NOT_READY
    status = "ready" if certified else "not_ready"
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "run_id": run_id,
        "analysis_package": str(analysis_package),
        "source_package": str(source_package),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "allow_replace_existing": allow_replace_existing,
        "replaced_existing_tropical_rows": already,
        "live_db": {"path": str(live_db_path), "before": live_before, "after": live_after},
        "backup": backup,
        "pre_write": {
            "schema_version": live_schema_version,
            "v59_counts": live_v59_counts,
            "existing_tropical": existing_tropical,
        },
        "temp_db": {
            "path": temp["path"],
            "schema_version": temp["schema_version"],
            "counts": temp["counts"],
            "digests": temp["digests"],
            "expected_counts": dict(expected_counts) if expected_counts else None,
        },
        "write_result": {"by_table": write_result, "transaction_committed": committed},
        "post_write_certification": {
            "decision": cert.CERT_MATCH if certified else cert.CERT_STALE_OR_MISMATCH,
            "anchor_present": anchor_present,
            "tables": cert_tables,
            "reprojection_temp": cert_temp["path"],
        },
        "safety": {
            "live_db_written": True,
            "live_db_migrated": False,
            "live_db_projected_directly": False,
            "projected_via_temp_db": True,
            "v59_written": False,
            "live_root_written": False,
            "production_defaults_changed": False,
            "true_live_execution_used": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
