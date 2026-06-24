"""Phase 14 — controlled live DB source-domain projection (first gated live write).

Phase 13 certified the real live/default DB as ``schema_only``: v59 schema present, the three
source-domain tables empty. Phase 14 is the FIRST workflow that may WRITE the live DB — narrowly,
gated, and reversible:

    fresh non-live temp projection (migrate + project) -> verify -> BACKUP the live DB -> one
    transaction that replaces ONLY ``project_key='tropical'`` rows in the three v59 tables with rows
    copied from the temp DB -> deterministic evidence -> rerun Phase 13 certification (require
    ``certified_match``).

It never migrates the live DB, never runs ``project_source_domain(apply=True)`` against the live DB,
and writes no table other than the three v59 source-domain tables (tropical rows only; non-tropical
rows are preserved). It is not a production default cutover.

CFR-only / stdlib at import time; ``hb_assistant`` (PathPolicy, migrator, source-domain engine) is
imported lazily, and only on a NON-LIVE temp DB. Reuses Phase 13 (``live_db_certification``) for the
read-only audit, certification, digests, and read-only connection helper.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from ..common.project_eligibility import (
    eligible_projects,
    is_project_eligible,
    source_package_name,
)
from . import live_db_certification as cert
from .db_cutover_readiness import REQUIRED_SCHEMA_VERSION, REQUIRED_SOURCE_DOMAIN_TABLES

SUPPORTED_PROJECT_KEY = "tropical"
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "live_db_source_domain_projection_report.json"

BACKUP_SUBDIR = "backups"
BACKUP_NAME_PREFIX = "hb-personal-assistant.before-phase14"
TEMP_DB_SUBDIR = "temp_dbs"
DEFAULT_TEMP_DB_NAME = "forecast_source_domain_tropical.sqlite"
POST_WRITE_CERT_SUBDIR = "post_write_cert"
GUARDED_CHECK_SUBDIR = "guarded"

DECISION_CERTIFIED = "live_db_source_domain_certified"
DECISION_NOT_READY = "not_ready"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class LiveDbSourceDomainProjectionError(RuntimeError):
    """Raised when a controlled live-DB source-domain projection is refused (fail closed)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    # ``table`` is only ever one of REQUIRED_SOURCE_DOMAIN_TABLES (module constants), never user input.
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _tropical_count(conn: sqlite3.Connection, table: str, project_key: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE project_key = ?", (project_key,)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _verify_inserted(conn: sqlite3.Connection, table: str, project_key: str, expected: int) -> int:
    """In-transaction post-insert verification seam (raises → rollback). A real check, not test-only."""
    got = _tropical_count(conn, table, project_key)
    if got != expected:
        raise LiveDbSourceDomainProjectionError(
            f"in-transaction verification failed for {table}: live tropical rows {got} != temp {expected}"
        )
    return got


def _backup_name(context_stamp: str) -> str:
    """Stamp-qualified backup filename so durable re-runs don't collide and stay traceable."""
    return f"{BACKUP_NAME_PREFIX}.{context_stamp}.sqlite"


def _backup_live_db(
    *,
    live_db_path: Path,
    work_root: Path,
    context_stamp: str,
    wal_size: int,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    """Byte-for-byte backup of the main DB file (fail closed if a nonzero WAL would make it inconsistent).

    Writes to ``backup_root`` when supplied (a durable location resolved by the caller), otherwise to
    the ephemeral ``work_root / BACKUP_SUBDIR``. The filename is stamp-qualified to keep durable
    backups distinct and traceable.
    """
    if wal_size > 0:
        raise LiveDbSourceDomainProjectionError(
            f"live DB has a nonzero WAL ({wal_size} bytes); refusing a byte-copy backup that would "
            "miss WAL frames (no safe consistent-snapshot mechanism is enabled in Phase 14)"
        )
    base = backup_root if backup_root is not None else (work_root / BACKUP_SUBDIR)
    backup_path = base / _backup_name(context_stamp)
    if backup_path.exists():
        raise LiveDbSourceDomainProjectionError(
            f"backup path already exists (refusing to overwrite): {backup_path}"
        )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_db_path, backup_path)
    # Verify the backup is a readable v59 SQLite DB before allowing any live write.
    conn = cert._ro_conn(backup_path)
    try:
        schema_version = _schema_version(conn)
    finally:
        conn.close()
    # Phase 16: accept v59+ (the live/temp DB may be at v60 after the config-registry migration).
    if schema_version < REQUIRED_SCHEMA_VERSION:
        raise LiveDbSourceDomainProjectionError(
            f"backup verification failed: schema version {schema_version} < {REQUIRED_SCHEMA_VERSION}"
        )
    return {
        "path": str(backup_path),
        "backup_root": str(base),
        "size_bytes": int(Path(backup_path).stat().st_size),
        "sha256": _sha256_file(backup_path),
        "verified_readable": True,
        "schema_version": schema_version,
    }


def run_controlled_live_db_source_domain_projection(
    *,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    live_db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
    allow_live_db_write: bool = False,
    allow_replace_existing: bool = False,
    run_guarded_operator_check: bool = False,
    expected_counts: dict[str, int] | None = None,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    """Populate the live DB's v59 source-domain tables for tropical, gated + backed up + certified.

    Fails closed (``LiveDbSourceDomainProjectionError`` → CLI rc 3) on any unsafe/missing input, a
    nonzero-WAL live DB, a schema/table mismatch, an expected-count mismatch, a backup failure, or a
    transaction failure (rolled back). After a successful committed write it reruns Phase 13
    certification; ``certified_match`` → ``decision='live_db_source_domain_certified'`` (rc 0),
    otherwise ``decision='not_ready'`` (rc 1) with the backup path recorded for manual restore. Only
    the three v59 tables' ``project_key='tropical'`` rows are touched; non-tropical rows are preserved.
    """
    # --- Preflight (fail closed; no output/backup/write before it passes). ------------------------
    if not is_project_eligible(project_key):
        raise LiveDbSourceDomainProjectionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not allow_live_db_write:
        raise LiveDbSourceDomainProjectionError(
            "live DB write requires allow_live_db_write=True (explicit gate; refused)"
        )
    if not source_package:
        raise LiveDbSourceDomainProjectionError("source_package is required")
    source_package = Path(source_package)
    if not source_package.exists() or not source_package.is_dir():
        raise LiveDbSourceDomainProjectionError(
            f"source_package not found or not a directory: {source_package}"
        )
    expected_source = source_package_name(project_key)
    if source_package.name != expected_source:
        raise LiveDbSourceDomainProjectionError(
            f"source_package is not the expected Tropical package "
            f"{expected_source!r}: {source_package.name}"
        )
    if not work_root:
        raise LiveDbSourceDomainProjectionError(
            "work_root is required (explicit; no implicit root)"
        )
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise LiveDbSourceDomainProjectionError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise LiveDbSourceDomainProjectionError(
            "context_stamp is required (explicit; no latest-glob)"
        )
    if backup_root is not None:
        backup_root = Path(backup_root)
        if _is_under(backup_root, _LIVE_ROOT):
            raise LiveDbSourceDomainProjectionError(
                f"backup_root is at/under the live forecast root (refused): {backup_root}"
            )

    live_db_path = Path(live_db_path) if live_db_path is not None else cert._resolve_live_db_path()
    if not cert._is_live_db(live_db_path):
        raise LiveDbSourceDomainProjectionError(
            f"db is not the live/default DB (Phase 14 writes the live DB only): {live_db_path}"
        )
    if not live_db_path.exists():
        raise LiveDbSourceDomainProjectionError(f"live DB not found: {live_db_path}")

    data_root = source_package.parent
    live_before = cert._file_provenance(live_db_path)

    # --- Pre-write read-only audit (reuse Phase 13). ---------------------------------------------
    pre_write_audit = cert.run_live_db_provenance_audit(
        live_db_path=live_db_path, project_key=project_key
    )
    # Phase 16: accept v59+ (the live DB may be at v60 after the config-registry migration).
    if pre_write_audit["schema"]["schema_version"] < REQUIRED_SCHEMA_VERSION:
        raise LiveDbSourceDomainProjectionError(
            f"live DB schema version {pre_write_audit['schema']['schema_version']} < "
            f"{REQUIRED_SCHEMA_VERSION}"
        )
    if not all(
        pre_write_audit["schema"]["required_tables_present"].get(t)
        for t in REQUIRED_SOURCE_DOMAIN_TABLES
    ):
        raise LiveDbSourceDomainProjectionError(
            "live DB is missing one or more required v59 source-domain tables"
        )
    existing_tropical = int(pre_write_audit["source_domain"].get("tropical_total", 0))
    if existing_tropical > 0 and not allow_replace_existing:
        raise LiveDbSourceDomainProjectionError(
            f"live DB already has {existing_tropical} tropical source-domain rows; pass "
            "allow_replace_existing=True to replace them (tropical rows only)"
        )

    # --- Fresh non-live temp projection (lazy hb_assistant; temp DB only). ------------------------
    db_path = work_root / TEMP_DB_SUBDIR / DEFAULT_TEMP_DB_NAME
    if db_path.exists():
        raise LiveDbSourceDomainProjectionError(
            f"temp db_path already exists (refusing to reuse for a deterministic run): {db_path}"
        )
    from hb_assistant.construction.forecast import source_domain_engine
    from hb_assistant.store.migrator import SQLiteMigrator

    db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db_path)).apply()
    projection = source_domain_engine.project_source_domain(
        source_package=source_package, project_key=project_key, db_path=db_path, apply=True
    )
    if not projection.get("ok"):
        raise LiveDbSourceDomainProjectionError(
            f"source-domain projection into the temp DB failed: {projection.get('reason', 'unknown')}"
        )

    # Read temp counts, digests, columns, and rows (in memory) — then close the temp connection.
    temp_conn = cert._ro_conn(db_path)
    try:
        temp_schema_version = _schema_version(temp_conn)
        temp_counts: dict[str, int] = {}
        temp_digests: dict[str, dict[str, str]] = {}
        temp_columns: dict[str, list[str]] = {}
        temp_rows: dict[str, list[tuple]] = {}
        for t in REQUIRED_SOURCE_DOMAIN_TABLES:
            temp_counts[t] = _tropical_count(temp_conn, t, project_key)
            byte_d, canon_d = cert._digests(
                cert._raw_strings(temp_conn, t, project_key=project_key)
            )
            temp_digests[t] = {"raw_json_digest": byte_d, "canonical_digest": canon_d}
            cols = _columns(temp_conn, t)
            temp_columns[t] = cols
            collist = ", ".join(cols)
            temp_rows[t] = temp_conn.execute(
                f"SELECT {collist} FROM {t} WHERE project_key = ?", (project_key,)
            ).fetchall()
    finally:
        temp_conn.close()

    # --- Expected-count gate (operator-supplied; default off) — BEFORE backup/write. -------------
    count_mismatches = []
    if expected_counts:
        for t, want in expected_counts.items():
            if t in temp_counts and int(want) != temp_counts[t]:
                count_mismatches.append(
                    {"table": t, "expected": int(want), "actual": temp_counts[t]}
                )
    if count_mismatches:
        raise LiveDbSourceDomainProjectionError(
            f"expected temp-projection row counts did not match: {count_mismatches}"
        )

    # --- Backup the live DB (fail closed on nonzero WAL). ----------------------------------------
    backup = _backup_live_db(
        live_db_path=live_db_path,
        work_root=work_root,
        context_stamp=context_stamp,
        wal_size=int(live_before.get("wal_size_bytes", 0)),
        backup_root=backup_root,
    )

    # --- Live write: one transaction; tropical rows of the three v59 tables only. -----------------
    write_plan = {
        t: {"columns": temp_columns[t], "temp_rows": temp_counts[t]}
        for t in REQUIRED_SOURCE_DOMAIN_TABLES
    }
    write_result: dict[str, dict[str, int]] = {}
    committed = False
    conn = sqlite3.connect(str(live_db_path))
    try:
        # Require identical column sets/order between temp and live before any mutation.
        for t in REQUIRED_SOURCE_DOMAIN_TABLES:
            live_cols = _columns(conn, t)
            if live_cols != temp_columns[t]:
                raise LiveDbSourceDomainProjectionError(
                    f"column mismatch for {t}: live {live_cols} != temp {temp_columns[t]}"
                )
        conn.execute("BEGIN IMMEDIATE")
        for t in REQUIRED_SOURCE_DOMAIN_TABLES:
            cols = temp_columns[t]
            collist = ", ".join(cols)
            placeholders = ", ".join("?" * len(cols))
            deleted = conn.execute(
                f"DELETE FROM {t} WHERE project_key = ?", (project_key,)
            ).rowcount
            conn.executemany(f"INSERT INTO {t} ({collist}) VALUES ({placeholders})", temp_rows[t])
            inserted = len(temp_rows[t])
            _verify_inserted(conn, t, project_key, temp_counts[t])
            write_result[t] = {"deleted": int(deleted), "inserted": int(inserted)}
        conn.commit()
        committed = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    live_after = cert._file_provenance(live_db_path)

    # --- Post-write read-only audit + certification (reuse Phase 13; separate sub-roots). ---------
    post_write_audit = cert.run_live_db_provenance_audit(
        live_db_path=live_db_path, project_key=project_key
    )
    post_cert = cert.run_live_db_readonly_certification(
        source_package=source_package,
        work_root=work_root / POST_WRITE_CERT_SUBDIR,
        context_stamp=context_stamp,
        live_db_path=live_db_path,
        project_key=project_key,
    )
    certified = post_cert.get("decision") == cert.CERT_MATCH

    guarded_check = None
    if run_guarded_operator_check and certified:
        from .guarded_db_operator_run import run_guarded_db_operator_run

        manifest = run_guarded_db_operator_run(
            source_package=source_package,
            work_root=work_root / GUARDED_CHECK_SUBDIR,
            context_stamp=context_stamp,
            db_path=live_db_path,
            project_key=project_key,
            allow_certified_live_db=True,
            live_db_certification=Path(post_cert["report_path"]),
        )
        guarded_check = {
            "status": manifest.get("status"),
            "decision": manifest.get("decision"),
            "live_db": manifest.get("live_db"),
            "report_path": manifest.get("report_path"),
        }

    decision = DECISION_CERTIFIED if certified else DECISION_NOT_READY
    status = "ready" if certified else "not_ready"

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "source_package": str(source_package),
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "allow_replace_existing": allow_replace_existing,
        "replaced_existing_tropical_rows": existing_tropical,
        "live_db": {
            "path": str(live_db_path),
            "before": live_before,
            "after": live_after,
        },
        "backup": backup,
        "pre_write_audit": pre_write_audit,
        "temp_db": {
            "path": str(db_path),
            "schema_version": temp_schema_version,
            "counts": temp_counts,
            "digests": temp_digests,
            "expected_counts": dict(expected_counts) if expected_counts else None,
        },
        "write_plan": write_plan,
        "write_result": {
            "by_table": write_result,
            "transaction_committed": committed,
        },
        "post_write_audit": post_write_audit,
        "post_write_certification": {
            "decision": post_cert.get("decision"),
            "report_path": post_cert.get("report_path"),
            "tables": post_cert.get("tables"),
        },
        "guarded_operator_check": guarded_check,
        # Grounded in this run's gates: backup taken + verified; only the three v59 tables' tropical
        # rows replaced from a temp projection; the live DB was never migrated or directly projected.
        "safety": {
            "live_db_written": True,
            "live_db_migrated": False,
            "live_db_projected_directly": False,
            "projected_via_temp_db": True,
            "live_root_written": False,
            "production_defaults_changed": False,
            "final_integrated_csv_generated": False,
            "true_live_execution_used": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
