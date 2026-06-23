"""Phase E2 — gated certified promotion of an approved config-edit proposal into the live v60
config-registry DB, as a NEW snapshot.

Additive: promotion inserts exactly one new ``forecast_config_snapshots`` row (+ its self-contained
``forecast_config_snapshot_items`` and the backing sources/items) and never deletes — snapshot history
and non-tropical config are preserved. It mirrors the Phase 14 gated-live-write discipline
(``allow_live_db_write`` gate → preflight → byte backup → single transaction → post-write
certification).

The load-bearing safety: ``create_forecast_config_snapshot`` snapshots ``WHERE status='active'``, so
importing an edited config into the live DB (which already holds the base config's active items) would
double-count. Therefore the snapshot is built in a FRESH temp DB (only the edited config is active
there) and its rows are COPIED into the live DB in one transaction. The workflow NEVER calls
``create_forecast_config_snapshot`` against the live DB.

Scope: config is lineage-only — the controlled generators do not consume DB config — so promotion
updates the recorded current config / viewer, not generation.

CFR-only / stdlib at import; ``hb_assistant`` (migrator) is imported LAZILY and only against the temp
DB; the live DB is touched read-only (``cert._ro_conn``) except for the single backed-up transaction.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from ..common.project_eligibility import eligible_projects, is_project_eligible
from ..config_registry import (
    create_forecast_config_snapshot,
    import_forecast_config_to_db,
    materialize_forecast_config_snapshot_readonly,
)
from . import live_db_certification as cert

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = 60  # v60 config-registry tables
REPORT_SCHEMA_VERSION = 1
REPORT_NAME = "live_db_config_registry_promotion_report.json"
BACKUP_SUBDIR = "backups"
BACKUP_NAME = "hb-personal-assistant.before-phaseE2-config-promotion.sqlite"
TEMP_DB_SUBDIR = "temp_dbs"
DEFAULT_TEMP_DB_NAME = "config_registry_promotion.sqlite"
DECISION_CERTIFIED = "live_db_config_registry_certified"
DECISION_NOT_READY = "not_ready"
CERT_MATCH = "certified_match"
CONFIG_TABLES = (
    "forecast_config_sources",
    "forecast_config_items",
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
)
_LIVE_ROOT = cert._LIVE_ROOT


class LiveDbConfigRegistryPromotionError(RuntimeError):
    """Raised when a promotion run is refused (fail closed → CLI rc 3)."""


# -- helpers ------------------------------------------------------------------


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    # ``table`` is always a CONFIG_TABLES constant, never user input.
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot_headers(conn: sqlite3.Connection) -> dict[str, str]:
    """Map config_snapshot_id -> snapshot_sha256 for every snapshot (additive/unchanged proof)."""
    return {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT config_snapshot_id, snapshot_sha256 FROM forecast_config_snapshots"
        )
    }


def _snapshot_item_raw(conn: sqlite3.Connection, snapshot_id: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT raw_json FROM forecast_config_snapshot_items WHERE config_snapshot_id = ?",
            (snapshot_id,),
        )
    ]


def _backup_live_db(*, live_db_path: Path, work_root: Path, wal_size: int) -> dict[str, Any]:
    """Byte-for-byte backup of the live DB main file (fail closed on a nonzero WAL)."""
    if wal_size > 0:
        raise LiveDbConfigRegistryPromotionError(
            f"live DB has a nonzero WAL ({wal_size} bytes); refusing a byte-copy backup that would "
            "miss WAL frames"
        )
    backup_path = work_root / BACKUP_SUBDIR / BACKUP_NAME
    if backup_path.exists():
        raise LiveDbConfigRegistryPromotionError(
            f"backup path already exists (refusing to overwrite): {backup_path}"
        )
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_db_path, backup_path)
    conn = cert._ro_conn(backup_path)
    try:
        schema_version = _schema_version(conn)
    finally:
        conn.close()
    if schema_version < REQUIRED_SCHEMA_VERSION:
        raise LiveDbConfigRegistryPromotionError(
            f"backup verification failed: schema version {schema_version} < {REQUIRED_SCHEMA_VERSION}"
        )
    return {
        "path": str(backup_path),
        "size_bytes": int(Path(backup_path).stat().st_size),
        "sha256": _sha256_file(backup_path),
        "verified_readable": True,
        "schema_version": schema_version,
    }


def _require_config_tables(conn: sqlite3.Connection) -> None:
    missing = [t for t in CONFIG_TABLES if not cert._table_exists(conn, t)]
    if missing:
        raise LiveDbConfigRegistryPromotionError(
            f"live DB is missing required v60 config-registry tables: {missing}"
        )


# -- workflow -----------------------------------------------------------------


def run_live_db_config_registry_promotion(
    *,
    edited_config_root: Path,
    work_root: Path,
    context_stamp: str,
    live_db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
    allow_live_db_write: bool = False,
    snapshot_name: str,
    snapshot_reason: str,
    expected_item_count: int | None = None,
    expected_hashes_by_domain: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Promote an approved edited config into the live config DB as a new snapshot (gated + backed up).

    Fails closed (``LiveDbConfigRegistryPromotionError`` → rc 3) on any unsafe/missing input, a nonzero
    WAL, a schema/table/column mismatch, an expected-match mismatch, a backup failure, an existing
    promoted snapshot id, or a transaction failure (rolled back). After a committed write it certifies
    the promoted snapshot byte/canonical equivalent to the temp snapshot and asserts every pre-existing
    snapshot is unchanged; ``certified_match`` → rc 0, else ``not_ready`` rc 1 (backup recorded).
    """
    # --- Gate + preflight (fail closed; no output/temp/backup/write before it passes). -----------
    if not is_project_eligible(project_key):
        raise LiveDbConfigRegistryPromotionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not allow_live_db_write:
        raise LiveDbConfigRegistryPromotionError(
            "live DB write requires allow_live_db_write=True (explicit gate; refused)"
        )
    if not edited_config_root:
        raise LiveDbConfigRegistryPromotionError("edited_config_root is required")
    edited_config_root = Path(edited_config_root)
    if not edited_config_root.exists() or not edited_config_root.is_dir():
        raise LiveDbConfigRegistryPromotionError(
            f"edited_config_root not found or not a directory: {edited_config_root}"
        )
    if not (edited_config_root / "config").is_dir():
        raise LiveDbConfigRegistryPromotionError(
            f"edited_config_root has no 'config/' subtree: {edited_config_root}"
        )
    if not snapshot_name or not snapshot_reason:
        raise LiveDbConfigRegistryPromotionError("snapshot_name and snapshot_reason are required")
    if not work_root:
        raise LiveDbConfigRegistryPromotionError(
            "work_root is required (explicit; no implicit root)"
        )
    work_root = Path(work_root)
    if cert._is_under(work_root, _LIVE_ROOT):
        raise LiveDbConfigRegistryPromotionError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise LiveDbConfigRegistryPromotionError(
            "context_stamp is required (explicit; no latest-glob)"
        )

    live_db_path = Path(live_db_path) if live_db_path is not None else cert._resolve_live_db_path()
    if not cert._is_live_db(live_db_path):
        raise LiveDbConfigRegistryPromotionError(
            f"db is not the live/default DB (Phase E2 promotes the live config DB only): {live_db_path}"
        )
    if not live_db_path.exists():
        raise LiveDbConfigRegistryPromotionError(f"live DB not found: {live_db_path}")

    live_before = cert._file_provenance(live_db_path)

    # --- Pre-write read-only audit (schema >= v60; the 4 config tables present). ------------------
    pre_conn = cert._ro_conn(live_db_path)
    try:
        pre_schema_version = _schema_version(pre_conn)
        if pre_schema_version < REQUIRED_SCHEMA_VERSION:
            raise LiveDbConfigRegistryPromotionError(
                f"live DB schema version {pre_schema_version} < {REQUIRED_SCHEMA_VERSION}"
            )
        _require_config_tables(pre_conn)
        snapshot_headers_before = _snapshot_headers(pre_conn)
        snapshots_before = len(snapshot_headers_before)
    finally:
        pre_conn.close()
    pre_write_audit = {
        "schema_version": pre_schema_version,
        "config_tables_present": True,
        "snapshots_before": snapshots_before,
    }

    # --- Fresh non-live temp DB: import edited config -> snapshot (NEVER live). -------------------
    temp_db = work_root / TEMP_DB_SUBDIR / DEFAULT_TEMP_DB_NAME
    if temp_db.exists():
        raise LiveDbConfigRegistryPromotionError(
            f"temp db_path already exists (refusing to reuse for a deterministic run): {temp_db}"
        )
    if cert._is_live_db(temp_db):
        raise LiveDbConfigRegistryPromotionError("temp DB path resolves to the live DB (refused)")
    temp_db.parent.mkdir(parents=True, exist_ok=True)

    import_forecast_config_to_db(
        config_root=edited_config_root,
        db_path=temp_db,
        project_key=project_key,
        import_run_id=f"promote_{context_stamp}",
    )
    temp_snap = create_forecast_config_snapshot(
        db_path=temp_db,
        project_key=project_key,
        snapshot_name=snapshot_name,
        snapshot_reason=snapshot_reason,
        created_by=None,
    )
    promoted_id = temp_snap["config_snapshot_id"]
    temp_item_count = int(temp_snap.get("item_count") or 0)
    temp_hashes = dict(temp_snap.get("hashes_by_domain") or {})

    # --- Read temp columns + rows to copy; compute the promoted-snapshot dual digest. ------------
    temp_conn = cert._ro_conn(temp_db)
    try:
        temp_columns: dict[str, list[str]] = {t: _columns(temp_conn, t) for t in CONFIG_TABLES}
        temp_rows: dict[str, list[tuple]] = {}
        for t in ("forecast_config_sources", "forecast_config_items"):
            cols = ", ".join(temp_columns[t])
            temp_rows[t] = temp_conn.execute(
                f"SELECT {cols} FROM {t} WHERE project_key = ?", (project_key,)
            ).fetchall()
        for t in ("forecast_config_snapshots", "forecast_config_snapshot_items"):
            cols = ", ".join(temp_columns[t])
            temp_rows[t] = temp_conn.execute(
                f"SELECT {cols} FROM {t} WHERE config_snapshot_id = ?", (promoted_id,)
            ).fetchall()
        temp_promoted_raw = _snapshot_item_raw(temp_conn, promoted_id)
        temp_byte, temp_canon = cert._digests(temp_promoted_raw)
        temp_snapshot_item_count = len(temp_promoted_raw)
    finally:
        temp_conn.close()

    # --- Expected-match gate (binds promotion to the approved proposal) — BEFORE backup. ---------
    if expected_item_count is not None and int(expected_item_count) != temp_item_count:
        raise LiveDbConfigRegistryPromotionError(
            f"expected item_count {int(expected_item_count)} != temp snapshot {temp_item_count}"
        )
    if expected_hashes_by_domain is not None and dict(expected_hashes_by_domain) != temp_hashes:
        raise LiveDbConfigRegistryPromotionError(
            "expected hashes_by_domain do not match the temp snapshot (approved bytes differ)"
        )

    # --- Byte backup (fail closed on nonzero WAL). -----------------------------------------------
    backup = _backup_live_db(
        live_db_path=live_db_path,
        work_root=work_root,
        wal_size=int(live_before.get("wal_size_bytes", 0)),
    )

    # --- Single transaction: additive copy of the new snapshot (+ backing rows). -----------------
    write_result: dict[str, dict[str, int]] = {}
    committed = False
    conn = sqlite3.connect(str(live_db_path))
    try:
        for t in CONFIG_TABLES:
            live_cols = _columns(conn, t)
            if live_cols != temp_columns[t]:
                raise LiveDbConfigRegistryPromotionError(
                    f"column mismatch for {t}: live {live_cols} != temp {temp_columns[t]}"
                )
        exists = conn.execute(
            "SELECT 1 FROM forecast_config_snapshots WHERE config_snapshot_id = ?", (promoted_id,)
        ).fetchone()
        if exists is not None:
            raise LiveDbConfigRegistryPromotionError(
                f"promoted snapshot already present in the live DB (refusing double-promote): {promoted_id}"
            )
        conn.execute("BEGIN IMMEDIATE")
        si_table = "forecast_config_snapshot_items"
        si_idx = {c: i for i, c in enumerate(temp_columns[si_table])}
        for t in CONFIG_TABLES:
            col_names = temp_columns[t]
            collist = ", ".join(col_names)
            placeholders = ", ".join("?" * len(col_names))
            if t == si_table:
                # Re-resolve each snapshot item's config_item_id to the live row that WINS the
                # content-dedup UNIQUE(project, domain, name, item_key, canonical_sha). Editing one item
                # in a file changes that file's content_sha, hence its source_id, hence EVERY item's
                # config_item_id; the unchanged items' new ids then collide on that UNIQUE and are
                # INSERT OR IGNORE'd away, so copying the temp config_item_id verbatim would dangle
                # (ADR 283). Resolving by content key keeps every snapshot item reachable. The snapshot
                # digest is content-based (not id-based) and materialize groups by source_path, so the
                # mix of reused (unchanged) + new (edited) item ids still round-trips faithfully.
                rows: list[tuple] = []
                for row in temp_rows[t]:
                    live_item = conn.execute(
                        "SELECT config_item_id FROM forecast_config_items WHERE project_key=? AND "
                        "config_domain=? AND config_name=? AND item_key=? AND canonical_json_sha256=?",
                        (
                            row[si_idx["project_key"]],
                            row[si_idx["config_domain"]],
                            row[si_idx["config_name"]],
                            row[si_idx["item_key"]],
                            row[si_idx["canonical_json_sha256"]],
                        ),
                    ).fetchone()
                    if live_item is None:
                        raise LiveDbConfigRegistryPromotionError(
                            "snapshot item has no backing config item in the live DB after copy "
                            f"(item_key {row[si_idx['item_key']]!r}); refusing to commit"
                        )
                    new_row = list(row)
                    new_row[si_idx["config_item_id"]] = live_item[0]
                    rows.append(tuple(new_row))
            else:
                rows = list(temp_rows[t])
            conn.executemany(f"INSERT OR IGNORE INTO {t} ({collist}) VALUES ({placeholders})", rows)
            write_result[t] = {"inserted": len(rows)}
        promoted_count = conn.execute(
            "SELECT COUNT(*) FROM forecast_config_snapshot_items WHERE config_snapshot_id = ?",
            (promoted_id,),
        ).fetchone()[0]
        if int(promoted_count) != temp_snapshot_item_count:
            raise LiveDbConfigRegistryPromotionError(
                f"in-transaction verification failed: promoted snapshot_items {promoted_count} != "
                f"temp {temp_snapshot_item_count}"
            )
        # Reachability guard (fail closed BEFORE commit): every promoted snapshot item must join to a
        # present config item AND that item's source. An orphan here means generation could not
        # materialize the snapshot (the ADR 283 failure), so refuse rather than commit a broken snapshot.
        orphans = conn.execute(
            "SELECT COUNT(*) FROM forecast_config_snapshot_items si WHERE si.config_snapshot_id=? "
            "AND NOT EXISTS (SELECT 1 FROM forecast_config_items ci "
            "JOIN forecast_config_sources s ON s.config_source_id=ci.config_source_id "
            "WHERE ci.config_item_id=si.config_item_id)",
            (promoted_id,),
        ).fetchone()[0]
        if int(orphans) != 0:
            raise LiveDbConfigRegistryPromotionError(
                f"reachability check failed: {orphans} promoted snapshot_items are orphaned from their "
                "config source (refusing to commit)"
            )
        snapshots_after_total = conn.execute(
            "SELECT COUNT(*) FROM forecast_config_snapshots"
        ).fetchone()[0]
        if int(snapshots_after_total) != snapshots_before + 1:
            raise LiveDbConfigRegistryPromotionError(
                f"additive invariant failed: snapshots after {snapshots_after_total} != "
                f"{snapshots_before} + 1"
            )
        conn.commit()
        committed = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    live_after = cert._file_provenance(live_db_path)

    # --- Post-write certification: promoted snapshot only + pre-existing snapshots unchanged. -----
    post_conn = cert._ro_conn(live_db_path)
    try:
        live_promoted_raw = _snapshot_item_raw(post_conn, promoted_id)
        live_byte, live_canon = cert._digests(live_promoted_raw)
        headers_after = _snapshot_headers(post_conn)
    finally:
        post_conn.close()

    promoted_match = (
        live_byte == temp_byte
        and live_canon == temp_canon
        and len(live_promoted_raw) == temp_snapshot_item_count
    )
    preserved = all(
        sid in headers_after and headers_after[sid] == sha
        for sid, sha in snapshot_headers_before.items()
    )
    added_exactly_one = (
        set(snapshot_headers_before) <= set(headers_after)
        and len(headers_after) == snapshots_before + 1
        and promoted_id in headers_after
    )
    # Round-trip cert: materialize the live promoted snapshot read-only -> reimport into a fresh temp
    # DB -> resnap, and require it reproduces the stored item_count + snapshot_sha256 (the SAME invariant
    # the DB-config generation fidelity gate enforces). A snapshot that generation could not consume
    # (e.g. orphaned items, ADR 283) can therefore never certify. Post-commit, so a failure -> not_ready
    # (backup recorded for manual restore), never a crash.
    roundtrip: dict[str, Any] = {"match": False}
    try:
        rt_mat = materialize_forecast_config_snapshot_readonly(
            db_path=live_db_path, config_snapshot_id=promoted_id, out_root=work_root / "roundtrip"
        )
        rt_db = work_root / TEMP_DB_SUBDIR / "config_registry_promotion_roundtrip.sqlite"
        import_forecast_config_to_db(
            config_root=Path(rt_mat["materialized_config_root"]),
            db_path=rt_db,
            project_key=project_key,
            import_run_id=f"promote_roundtrip_{context_stamp}",
        )
        rt_snap = create_forecast_config_snapshot(
            db_path=rt_db,
            project_key=project_key,
            snapshot_name="promotion_roundtrip",
            snapshot_reason="post-write materialize round-trip",
        )
        roundtrip = {
            "match": (
                int(rt_snap["item_count"]) == temp_item_count
                and str(rt_snap["snapshot_sha256"]) == str(temp_snap["snapshot_sha256"])
            ),
            "resnap_item_count": int(rt_snap["item_count"]),
            "stored_item_count": temp_item_count,
            "resnap_sha256": str(rt_snap["snapshot_sha256"]),
            "stored_sha256": str(temp_snap["snapshot_sha256"]),
        }
    except Exception as exc:  # noqa: BLE001 — post-commit round-trip failure -> not_ready, not a crash
        roundtrip = {"match": False, "error": type(exc).__name__}
    roundtrip_match = bool(roundtrip["match"])
    certified = promoted_match and preserved and added_exactly_one and roundtrip_match
    decision = DECISION_CERTIFIED if certified else DECISION_NOT_READY
    status = "ready" if certified else "not_ready"

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "edited_config_root": str(edited_config_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "snapshot_name": snapshot_name,
        "snapshot_reason": snapshot_reason,
        "promoted_snapshot_id": promoted_id,
        "item_count": temp_item_count,
        "hashes_by_domain": temp_hashes,
        "expected": {
            "item_count": int(expected_item_count) if expected_item_count is not None else None,
            "hashes_by_domain": dict(expected_hashes_by_domain)
            if expected_hashes_by_domain is not None
            else None,
        },
        "live_db": {"path": str(live_db_path), "before": live_before, "after": live_after},
        "backup": backup,
        "pre_write_audit": pre_write_audit,
        "snapshots_before": snapshots_before,
        "snapshots_after": len(headers_after),
        "temp_db": {
            "path": str(temp_db),
            "promoted_snapshot_item_count": temp_snapshot_item_count,
            "digests": {"raw_json_digest": temp_byte, "canonical_digest": temp_canon},
        },
        "write_result": {"by_table": write_result, "transaction_committed": committed},
        "promotion_certification": {
            "decision": CERT_MATCH if promoted_match else "mismatch",
            "promoted_snapshot": {
                "raw_json_digest_live": live_byte,
                "raw_json_digest_temp": temp_byte,
                "canonical_digest_live": live_canon,
                "canonical_digest_temp": temp_canon,
                "live_rows": len(live_promoted_raw),
                "temp_rows": temp_snapshot_item_count,
                "match": promoted_match,
            },
            "pre_existing_snapshots_preserved": preserved,
            "added_exactly_one_snapshot": added_exactly_one,
            "round_trip": roundtrip,
        },
        "safety": {
            "live_db_written": True,
            "live_db_migrated": False,
            "live_snapshot_created_directly": False,
            "built_via_temp_db": True,
            "additive_only": True,
            "non_tropical_preserved": True,
            "live_root_written": False,
            "generation_changed": False,
            "production_defaults_changed": False,
        },
    }
    report_path = cert._write_json_deterministic(work_root / REPORT_NAME, report)
    return {**report, "report_path": str(report_path)}
