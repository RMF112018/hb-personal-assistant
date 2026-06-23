"""Phase 13 — live DB provenance audit + read-only certification (operator-safe).

Resolves the Phase 12 blocker: during Phase 12 validation the live/default SQLite DB was found
already at schema v59 with the three v59 source-domain tables populated (pre-existing, not caused by
Phase 12). Before any live-DB operator eligibility can exist, the live DB must be audited and, if
populated, certified to MATCH a fresh non-live temp projection from the explicit Tropical source
package.

Two strictly read-only operations (the live DB is opened only via a ``mode=ro`` URI — never created,
migrated, projected, or written):

  - ``run_live_db_provenance_audit``: schema version + full migration history, required-table
    presence, source-domain row counts by project_key, and filesystem provenance (size/mtime/WAL/SHM).
  - ``run_live_db_readonly_certification``: builds a fresh NON-LIVE temp v59 DB (migrate + project)
    from the explicit Tropical source package and compares the live DB's tropical source-domain rows
    against it per table, both byte-exact (sorted exact ``raw_json`` strings) AND canonically
    (``json.loads`` → sorted-key re-dump). ``certified_match`` requires both, for all three tables.

CFR-only / stdlib at import time; ``hb_assistant`` (PathPolicy, migrator, source-domain engine +
repository) is imported LAZILY inside the functions. No schema change; the temp-DB guarded operator
path (Phases 11/12) is untouched.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from ..common.project_eligibility import (
    eligible_projects,
    is_project_eligible,
    source_package_name,
)
from .db_cutover_readiness import REQUIRED_SCHEMA_VERSION, REQUIRED_SOURCE_DOMAIN_TABLES

SUPPORTED_PROJECT_KEY = "tropical"
AUDIT_REPORT_SCHEMA_VERSION = 1
CERT_REPORT_SCHEMA_VERSION = 1

TEMP_DB_SUBDIR = "temp_dbs"
DEFAULT_TEMP_DB_NAME = "forecast_source_domain_tropical.sqlite"
AUDIT_REPORT_NAME = "live_db_provenance_audit_report.json"
CERT_REPORT_NAME = "live_db_readonly_certification_report.json"

# Audit decisions.
AUDIT_POPULATED_TROPICAL = "populated_tropical"
AUDIT_SCHEMA_ONLY = "schema_only"
AUDIT_POPULATED_OTHER = "populated_other_projects"
AUDIT_MISSING_TABLES = "missing_v59_tables"

# Certification decisions.
CERT_MATCH = "certified_match"
CERT_SCHEMA_ONLY = "schema_only"
CERT_STALE_OR_MISMATCH = "stale_or_mismatch"
CERT_UNCERTIFIED = "uncertified"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class LiveDbCertificationError(RuntimeError):
    """Raised when an audit/certification run is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _resolve_live_db_path() -> Path:
    """Resolve the live/default DB path via the path policy (lazy import; fail closed)."""
    try:
        from hb_assistant.config.path_policy import PathPolicy
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise LiveDbCertificationError(
            f"cannot resolve the live DB path; hb_assistant unavailable: {exc}"
        ) from exc
    return Path(PathPolicy().get_db_path())


def _is_live_db(db_path: Path) -> bool:
    """True if ``db_path`` is the live/default DB (lazy module-ref call; monkeypatchable)."""
    try:
        from hb_assistant.construction.forecast import source_domain_engine
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise LiveDbCertificationError(
            f"cannot verify the live DB; hb_assistant unavailable: {exc}"
        ) from exc
    return source_domain_engine.is_live_db_path(Path(db_path))


def _ro_conn(db_path: Path) -> sqlite3.Connection:
    """Open a strictly read-only SQLite connection (mode=ro never creates the file)."""
    uri = f"file:{urllib.parse.quote(str(Path(db_path).resolve(strict=False)))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
    except sqlite3.Error as exc:
        raise LiveDbCertificationError(
            f"live DB is not a readable SQLite database: {db_path} ({exc})"
        ) from exc
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _rowcount(conn: sqlite3.Connection, table: str, *, project_key: str | None) -> int:
    # ``table`` is only ever one of REQUIRED_SOURCE_DOMAIN_TABLES (module constants), never user input.
    if project_key is None:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    else:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_key = ?", (project_key,)
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _raw_strings(conn: sqlite3.Connection, table: str, *, project_key: str) -> list[str]:
    # ``table`` is only ever one of REQUIRED_SOURCE_DOMAIN_TABLES (module constants), never user input.
    return [
        r[0]
        for r in conn.execute(f"SELECT raw_json FROM {table} WHERE project_key = ?", (project_key,))
    ]


def _digests(raw_strings: list[str]) -> tuple[str, str]:
    """Return (byte_exact_digest, canonical_digest), both order-independent.

    Byte-exact: sha256 over the sorted exact stored ``raw_json`` strings (true byte equivalence).
    Canonical: sha256 over each row re-dumped with sorted keys (robust to JSON field ordering).
    """
    ordered = sorted(raw_strings)
    byte_digest = hashlib.sha256("\n".join(ordered).encode("utf-8")).hexdigest()
    canon = sorted(
        json.dumps(json.loads(s), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for s in raw_strings
    )
    canon_digest = hashlib.sha256("\n".join(canon).encode("utf-8")).hexdigest()
    return byte_digest, canon_digest


def _file_provenance(db_path: Path) -> dict[str, Any]:
    """Read-only filesystem provenance for the live DB + its WAL/SHM (no mutation)."""
    p = Path(db_path)
    st = p.stat()
    info: dict[str, Any] = {
        "path": str(p),
        "exists": True,
        "size_bytes": int(st.st_size),
        "mtime_epoch": int(st.st_mtime),
    }
    for suffix, key in (("-wal", "wal"), ("-shm", "shm")):
        sidecar = Path(str(p) + suffix)
        if sidecar.exists():
            info[f"{key}_exists"] = True
            info[f"{key}_size_bytes"] = int(sidecar.stat().st_size)
        else:
            info[f"{key}_exists"] = False
            info[f"{key}_size_bytes"] = 0
    return info


def _audit_core(conn: sqlite3.Connection, *, project_key: str) -> dict[str, Any]:
    """Read-only schema + source-domain audit on an open RO connection."""
    if not _table_exists(conn, "schema_migrations"):
        raise LiveDbCertificationError(
            "live DB has no schema_migrations table (cannot determine schema version)"
        )
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    schema_version = int(row[0]) if row and row[0] is not None else 0
    migrations = [
        {"version": int(v), "name": n, "applied_at": a}
        for (v, n, a) in conn.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        )
    ]
    present = {t: _table_exists(conn, t) for t in REQUIRED_SOURCE_DOMAIN_TABLES}
    all_present = all(present.values()) and schema_version >= REQUIRED_SCHEMA_VERSION

    by_table: dict[str, dict[str, int]] = {}
    distinct_pks: list[str] = []
    tropical_total = 0
    grand_total = 0
    if all_present:
        pks: set[str] = set()
        for t in REQUIRED_SOURCE_DOMAIN_TABLES:
            trop = _rowcount(conn, t, project_key=project_key)
            total = _rowcount(conn, t, project_key=None)
            by_table[t] = {"tropical_rows": trop, "total_rows": total}
            tropical_total += trop
            grand_total += total
            for (pk,) in conn.execute(
                f"SELECT DISTINCT project_key FROM {t}"  # noqa: S608 - table is a module constant
            ):
                if pk is not None:
                    pks.add(str(pk))
        distinct_pks = sorted(pks)

    if not all_present:
        decision = AUDIT_MISSING_TABLES
    elif tropical_total > 0:
        decision = AUDIT_POPULATED_TROPICAL
    elif grand_total > 0:
        decision = AUDIT_POPULATED_OTHER
    else:
        decision = AUDIT_SCHEMA_ONLY

    return {
        "decision": decision,
        "schema": {
            "schema_version": schema_version,
            "required_schema_version": REQUIRED_SCHEMA_VERSION,
            "migrations": migrations,
            "required_tables_present": present,
        },
        "source_domain": {
            "distinct_project_keys": distinct_pks,
            "by_table": by_table,
            "tropical_total": tropical_total,
            "all_projects_total": grand_total,
        },
    }


def run_live_db_provenance_audit(
    *,
    live_db_path: Path | None = None,
    work_root: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Strictly read-only provenance audit of the live/default v59 DB.

    Creates, migrates, projects, and mutates NOTHING. Fails closed (``LiveDbCertificationError``) on a
    non-tropical project, a missing live DB, a path that is not the live/default DB, or an unreadable
    DB. Returns the audit report dict; if ``work_root`` (not under the live root) is given, also writes
    ``<work_root>/live_db_provenance_audit_report.json`` (plus ``report_path``).
    """
    if not is_project_eligible(project_key):
        raise LiveDbCertificationError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    live_db_path = Path(live_db_path) if live_db_path is not None else _resolve_live_db_path()
    if not live_db_path.exists():
        raise LiveDbCertificationError(f"live DB not found: {live_db_path}")
    if not _is_live_db(live_db_path):
        raise LiveDbCertificationError(
            f"db is not the live/default DB (this audit is for the live DB only): {live_db_path}"
        )

    conn = _ro_conn(live_db_path)
    try:
        core = _audit_core(conn, project_key=project_key)
    finally:
        conn.close()

    report = {
        "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "decision": core["decision"],
        "live_db": _file_provenance(live_db_path),
        "schema": core["schema"],
        "source_domain": core["source_domain"],
        "safety": {
            "live_db_written": False,
            "live_db_migrated": False,
            "live_db_projected": False,
            "read_only": True,
        },
    }
    if work_root is not None:
        work_root = Path(work_root)
        if _is_under(work_root, _LIVE_ROOT):
            raise LiveDbCertificationError(
                f"work_root is at/under the live forecast root (refused): {work_root}"
            )
        report_path = _write_json_deterministic(work_root / AUDIT_REPORT_NAME, report)
        return {**report, "report_path": str(report_path)}
    return report


def run_live_db_readonly_certification(
    *,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    live_db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Certify (read-only) that the live DB's tropical source-domain rows match a fresh temp projection.

    Preflight fails closed (``LiveDbCertificationError``) BEFORE any output on: non-tropical project;
    missing/non-dir source package or wrong name; missing/non-explicit work root or one under the live
    root; empty context stamp; a live DB that does not exist or is not the live/default DB. Then runs
    the read-only audit, builds a fresh NON-LIVE temp v59 DB (migrate + project) under the work root,
    and compares per table (byte-exact ``raw_json`` + canonical row digests). Decision: ``certified_match``
    (all tables match AND live has tropical rows), ``schema_only`` (no live tropical rows),
    ``stale_or_mismatch`` (live tropical rows differ), or ``uncertified``. The live DB is opened
    read-only only; it is never migrated, projected, or written.
    """
    if not is_project_eligible(project_key):
        raise LiveDbCertificationError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not source_package:
        raise LiveDbCertificationError("source_package is required for a certification run")
    source_package = Path(source_package)
    if not source_package.exists() or not source_package.is_dir():
        raise LiveDbCertificationError(
            f"source_package not found or not a directory: {source_package}"
        )
    expected_source = source_package_name(project_key)
    if source_package.name != expected_source:
        raise LiveDbCertificationError(
            f"source_package is not the expected Tropical package "
            f"{expected_source!r}: {source_package.name}"
        )
    if not work_root:
        raise LiveDbCertificationError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise LiveDbCertificationError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise LiveDbCertificationError("context_stamp is required (explicit; no latest-glob)")
    live_db_path = Path(live_db_path) if live_db_path is not None else _resolve_live_db_path()
    if not live_db_path.exists():
        raise LiveDbCertificationError(f"live DB not found: {live_db_path}")
    if not _is_live_db(live_db_path):
        raise LiveDbCertificationError(
            f"db is not the live/default DB (certification is for the live DB only): {live_db_path}"
        )

    data_root = source_package.parent

    # --- Read-only audit of the live DB. ---------------------------------------------------------
    audit = run_live_db_provenance_audit(live_db_path=live_db_path, project_key=project_key)

    # --- Build a fresh NON-LIVE temp v59 DB (migrate + project); never the live DB. ---------------
    db_path = work_root / TEMP_DB_SUBDIR / DEFAULT_TEMP_DB_NAME
    if db_path.exists():
        raise LiveDbCertificationError(
            f"temp db_path already exists (refusing to reuse for a deterministic run): {db_path}"
        )
    from hb_assistant.construction.forecast import source_domain_engine
    from hb_assistant.store.migrator import SQLiteMigrator

    db_path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db_path)).apply()
    projection = source_domain_engine.project_source_domain(
        source_package=source_package,
        project_key=project_key,
        db_path=db_path,
        apply=True,
    )
    if not projection.get("ok"):
        raise LiveDbCertificationError(
            f"source-domain projection into the temp DB failed: "
            f"{projection.get('reason', 'unknown')} ({db_path})"
        )

    # --- Compare live (read-only) vs fresh temp, per table. --------------------------------------
    live_conn = _ro_conn(live_db_path)
    temp_conn = _ro_conn(db_path)
    try:
        tables: dict[str, dict[str, Any]] = {}
        mismatch_summary: list[str] = []
        live_tropical_total = 0
        for t in REQUIRED_SOURCE_DOMAIN_TABLES:
            live_raw = _raw_strings(live_conn, t, project_key=project_key)
            temp_raw = _raw_strings(temp_conn, t, project_key=project_key)
            live_byte, live_canon = _digests(live_raw)
            temp_byte, temp_canon = _digests(temp_raw)
            raw_json_match = live_byte == temp_byte
            canonical_match = live_canon == temp_canon
            match = raw_json_match and canonical_match and len(live_raw) == len(temp_raw)
            live_tropical_total += len(live_raw)
            tables[t] = {
                "live_rows": len(live_raw),
                "temp_rows": len(temp_raw),
                "raw_json_digest_live": live_byte,
                "raw_json_digest_temp": temp_byte,
                "canonical_digest_live": live_canon,
                "canonical_digest_temp": temp_canon,
                "raw_json_match": raw_json_match,
                "canonical_match": canonical_match,
                "match": match,
            }
            if not match:
                mismatch_summary.append(
                    f"{t}: live_rows={len(live_raw)} temp_rows={len(temp_raw)} "
                    f"raw_json_match={raw_json_match} canonical_match={canonical_match}"
                )
    finally:
        live_conn.close()
        temp_conn.close()

    all_match = all(tables[t]["match"] for t in REQUIRED_SOURCE_DOMAIN_TABLES)
    if live_tropical_total == 0:
        decision = CERT_SCHEMA_ONLY
    elif all_match:
        decision = CERT_MATCH
    else:
        decision = CERT_STALE_OR_MISMATCH

    report = {
        "schema_version": CERT_REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "decision": decision,
        "live_db": str(live_db_path),
        "source_package": str(source_package),
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "temp_db": str(db_path),
        "audit": {
            "decision": audit["decision"],
            "schema_version": audit["schema"]["schema_version"],
            "live_db": audit["live_db"],
        },
        "tables": tables,
        "mismatch_summary": mismatch_summary,
        "comparison": "byte_exact_raw_json_and_canonical_row_equivalence",
        "safety": {
            "live_db_written": False,
            "live_db_migrated": False,
            "live_db_projected": False,
            "live_root_written": False,
        },
    }
    report_path = _write_json_deterministic(work_root / CERT_REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
