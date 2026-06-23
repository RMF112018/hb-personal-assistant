"""Phase 16 — governed forecast config registry (import / export / snapshot / materialize / parity).

Migrates the file-backed operator-approved forecast config (project JSON, forecast controls, model
controls, staffing mapping, owner-SOV crosswalk) into the v60 SQLite registry tables, with immutable
snapshots and file-compatible materialization. DB-backed config becomes a real reader input by
materializing a snapshot to a file-compatible config root and pointing ``CFR_CONFIG_ROOT`` at it; the
existing readers are unchanged in default behavior.

Repo-truth scope (Phase 16): the controlled context->analysis->Phase 9/12/15 chain does NOT read
operator config — only the deterministic ``validate-crosswalk`` does (plus out-of-scope downstream
generators). So parity is proven at the reader layer + ``validate-crosswalk``; Phase 9/12/15 carry only
lineage metadata. CFR-only / stdlib at import time; ``hb_assistant`` (migrator + live-DB guard) is
imported lazily and never against the live DB unless explicitly authorized.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .common.io import read_json, write_csv, write_json
from .common.project_eligibility import eligible_projects, is_project_eligible
from .forecast_controls.load_controls import DEFAULT_CONTROL_FILE as _CONTROLS_DEFAULT
from .forecast_controls.load_controls import controls_config as _controls_config
from .forecast_model_controls.load_controls import DEFAULT_CONTROL_FILE as _MODEL_DEFAULT
from .forecast_model_controls.load_controls import model_controls_config as _model_config
from .forecast_staffing_plan.load_mapping import DEFAULT_MAPPING_FILE as _STAFFING_DEFAULT
from .forecast_staffing_plan.load_mapping import staffing_config as _staffing_config

SUPPORTED_PROJECT_KEY = "tropical"
REQUIRED_SCHEMA_VERSION = 60
MATERIALIZED_DIRNAME = "materialized_config"
SNAPSHOT_MANIFEST_NAME = "config_snapshot_manifest.json"
EXPORT_MANIFEST_NAME = "config_export_manifest.json"

# Config domains (order is deterministic and used for snapshot hashing).
DOMAIN_PROJECT = "project"
DOMAIN_CONTROLS = "forecast_controls"
DOMAIN_MODEL_CONTROLS = "forecast_model_controls"
DOMAIN_STAFFING = "forecast_staffing"
DOMAIN_CROSSWALK = "owner_sov_crosswalk"

_NOT_CONSUMED_REASON = (
    "Phase 6/7/9/12/15 controlled chain does not read operator config per repo-truth audit"
)


class ConfigRegistryError(RuntimeError):
    """Raised when a config registry operation is refused (fail closed; no soft fallback)."""


@dataclass(frozen=True)
class ForecastConfigResolution:
    """Resolved config source for a forecast run (file-backed or DB-snapshot-backed)."""

    source_mode: Literal["file", "db_snapshot"]
    config_root: Path
    config_snapshot_id: str | None = None
    manifest_path: Path | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    row_counts: dict[str, int] = field(default_factory=dict)


# --- hashing / time helpers ------------------------------------------------------------


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# --- live-DB safety (reuse the source-domain guard; never weaken) ----------------------


def _is_live_db(db_path: Path) -> bool:
    try:
        from hb_assistant.construction.forecast import source_domain_engine
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ConfigRegistryError(
            f"cannot verify db_path against the live DB; hb_assistant unavailable: {exc}"
        ) from exc
    return source_domain_engine.is_live_db_path(Path(db_path))


def _ensure_schema(db_path: Path) -> None:
    """Apply the migrator to a NON-LIVE temp DB so the v60 tables exist (lazy import)."""
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator(db_path=str(db_path)).apply()


def _require_v60(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    version = int(row[0]) if row and row[0] is not None else 0
    if version < REQUIRED_SCHEMA_VERSION:
        raise ConfigRegistryError(
            f"DB schema version {version} < required {REQUIRED_SCHEMA_VERSION} (config registry tables)"
        )


# --- config-base + discovery -----------------------------------------------------------


def _config_base(config_root: Path) -> Path:
    """Normalize config_root to the directory CONTAINING the ``config/`` subtree (fail closed)."""
    config_root = Path(config_root)
    if not config_root.exists() or not config_root.is_dir():
        raise ConfigRegistryError(f"config_root not found or not a directory: {config_root}")
    if (config_root / "config").is_dir():
        return config_root
    if config_root.name == "config":
        return config_root.parent
    raise ConfigRegistryError(
        f"config_root has no 'config/' subtree and is not a 'config/' directory: {config_root}"
    )


@dataclass(frozen=True)
class _SourceSpec:
    domain: str
    name: str
    rel_path: str
    fmt: str
    abs_path: Path


def _rel_join(base: Path, rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else (base / rel)


def discover_config_sources(config_root: Path, project_key: str) -> list[_SourceSpec]:
    """Discover the config file set the readers consume, resolved relative to the config base."""
    base = _config_base(config_root)
    proj_rel = f"config/projects/{project_key}.json"
    proj_abs = base / proj_rel
    if not proj_abs.is_file():
        raise ConfigRegistryError(f"project config not found: {proj_abs}")
    try:
        cfg = read_json(proj_abs)
    except json.JSONDecodeError as exc:
        raise ConfigRegistryError(f"{proj_abs}: invalid JSON: {exc}") from exc
    specs: list[_SourceSpec] = [
        _SourceSpec(DOMAIN_PROJECT, proj_abs.name, proj_rel, "json", proj_abs)
    ]

    def _add(domain: str, rel: str, fmt: str, *, required: bool) -> None:
        abs_path = _rel_join(base, rel)
        if not abs_path.is_file():
            if required:
                raise ConfigRegistryError(f"{domain} config file not found: {abs_path}")
            return
        rel_str = rel if not Path(rel).is_absolute() else str(abs_path)
        specs.append(_SourceSpec(domain, abs_path.name, rel_str, fmt, abs_path))

    _add(
        DOMAIN_CONTROLS,
        _controls_config(cfg).get("control_file") or _CONTROLS_DEFAULT,
        "jsonl",
        required=False,
    )
    _add(
        DOMAIN_MODEL_CONTROLS,
        _model_config(cfg).get("control_file") or _MODEL_DEFAULT,
        "jsonl",
        required=False,
    )
    _add(
        DOMAIN_STAFFING,
        _staffing_config(cfg).get("mapping_file") or _STAFFING_DEFAULT,
        "jsonl",
        required=False,
    )
    xw_rel = cfg.get("owner_sov_scope_crosswalk")
    if xw_rel:
        _add(DOMAIN_CROSSWALK, xw_rel, "jsonl", required=True)
        # Also import the sibling CSV (alternate representation) when present.
        csv_rel = str(Path(xw_rel).with_suffix(".csv"))
        _add(DOMAIN_CROSSWALK, csv_rel, "csv", required=False)
    return specs


def _item_key(domain: str, obj: dict, order: int) -> str:
    if domain == DOMAIN_PROJECT:
        return str(obj.get("project_key") or "project")
    if domain in (DOMAIN_CONTROLS, DOMAIN_MODEL_CONTROLS):
        k = obj.get("control_id")
    elif domain == DOMAIN_STAFFING:
        sc, tg = obj.get("source_cost_code"), obj.get("target_budget_code_key")
        k = f"{sc}|{tg}" if sc is not None else None
    elif domain == DOMAIN_CROSSWALK:
        k = obj.get("crosswalk_id")
    else:
        k = None
    if not k:
        return f"row_{order}"
    return str(k)


@dataclass(frozen=True)
class _ParsedItem:
    item_key: str
    item_order: int
    raw_json: str
    canonical_sha256: str


def _parse_source(spec: _SourceSpec) -> tuple[list[_ParsedItem], str, str]:
    """Parse a config source into ordered items. Returns (items, source_sha256, content_sha256)."""
    source_sha = _sha256_file(spec.abs_path)
    items: list[_ParsedItem] = []
    if spec.fmt == "json":
        text = spec.abs_path.read_text(encoding="utf-8")
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigRegistryError(f"{spec.abs_path}: invalid JSON: {exc}") from exc
        items.append(
            _ParsedItem(_item_key(spec.domain, obj, 0), 0, text, _sha256_text(_canonical(obj)))
        )
    elif spec.fmt == "jsonl":
        order = 0
        with spec.abs_path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ConfigRegistryError(
                        f"{spec.abs_path}:{lineno}: invalid JSON: {exc}"
                    ) from exc
                items.append(
                    _ParsedItem(
                        _item_key(spec.domain, obj, order),
                        order,
                        stripped,
                        _sha256_text(_canonical(obj)),
                    )
                )
                order += 1
    elif spec.fmt == "csv":
        with spec.abs_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            try:
                rows = list(reader)
            except csv.Error as exc:
                raise ConfigRegistryError(f"{spec.abs_path}: invalid CSV: {exc}") from exc
            for order, row in enumerate(rows):
                obj = dict(row)
                items.append(
                    _ParsedItem(
                        _item_key(spec.domain, obj, order),
                        order,
                        json.dumps(obj, ensure_ascii=False),
                        _sha256_text(_canonical(obj)),
                    )
                )
    else:  # pragma: no cover - guarded by discovery
        raise ConfigRegistryError(f"unsupported source format: {spec.fmt}")

    seen: set[str] = set()
    for it in items:
        if it.item_key in seen:
            raise ConfigRegistryError(
                f"{spec.abs_path}: duplicate item_key {it.item_key!r} in config source "
                f"{spec.domain}/{spec.name} (fail closed)"
            )
        seen.add(it.item_key)
    content_sha = _sha256_text("\n".join(it.canonical_sha256 for it in items))
    return items, source_sha, content_sha


# --- import ----------------------------------------------------------------------------


def import_forecast_config_to_db(
    *,
    config_root: Path,
    db_path: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    import_run_id: str | None = None,
    allow_live_db_write: bool = False,
) -> dict[str, Any]:
    """Import the file-backed forecast config into the v60 registry tables (idempotent).

    Fails closed on a non-tropical project, a missing/invalid config tree, invalid JSON/CSV, or a
    duplicate item-key. Writing the live/default DB requires ``allow_live_db_write=True`` (and is never
    done in tests). Non-live temp DBs are migrated automatically.
    """
    if not is_project_eligible(project_key):
        raise ConfigRegistryError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    db_path = Path(db_path)
    live = _is_live_db(db_path)
    if live and not allow_live_db_write:
        raise ConfigRegistryError(
            "db_path resolves to the live/default DB; config import requires allow_live_db_write=True"
        )
    if not live:
        _ensure_schema(db_path)

    specs = discover_config_sources(config_root, project_key)
    parsed = [(spec, *_parse_source(spec)) for spec in specs]
    combined = _sha256_text("\n".join(content for (_s, _i, _src, content) in parsed))
    run_id = import_run_id or f"import_{combined[:16]}"
    now = _utc_now()

    conn = sqlite3.connect(str(db_path))
    sources_report: list[dict[str, Any]] = []
    try:
        _require_v60(conn)
        conn.execute("BEGIN IMMEDIATE")
        for spec, items, source_sha, content_sha in parsed:
            source_id = _sha256_text(f"{project_key}|{spec.domain}|{spec.name}|{content_sha}")
            conn.execute(
                """INSERT OR IGNORE INTO forecast_config_sources
                   (config_source_id, project_key, config_domain, config_name, source_path,
                    source_format, source_sha256, content_sha256, row_count, imported_at_utc,
                    import_run_id, is_active, created_utc, updated_utc)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (
                    source_id,
                    project_key,
                    spec.domain,
                    spec.name,
                    spec.rel_path,
                    spec.fmt,
                    source_sha,
                    content_sha,
                    len(items),
                    now,
                    run_id,
                    now,
                    now,
                ),
            )
            for it in items:
                item_id = _sha256_text(
                    f"{source_id}|{it.item_order}|{it.item_key}|{it.canonical_sha256}"
                )
                conn.execute(
                    """INSERT OR IGNORE INTO forecast_config_items
                       (config_item_id, config_source_id, project_key, config_domain, config_name,
                        item_key, item_order, effective_from, effective_to, status, raw_json,
                        canonical_json_sha256, created_utc, updated_utc)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item_id,
                        source_id,
                        project_key,
                        spec.domain,
                        spec.name,
                        it.item_key,
                        it.item_order,
                        None,
                        None,
                        "active",
                        it.raw_json,
                        it.canonical_sha256,
                        now,
                        now,
                    ),
                )
            sources_report.append(
                {
                    "config_source_id": source_id,
                    "config_domain": spec.domain,
                    "config_name": spec.name,
                    "source_path": spec.rel_path,
                    "source_format": spec.fmt,
                    "source_sha256": source_sha,
                    "content_sha256": content_sha,
                    "row_count": len(items),
                }
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "project_key": project_key,
        "db_path": str(db_path),
        "import_run_id": run_id,
        "config_base": str(_config_base(config_root)),
        "sources": sources_report,
        "source_count": len(sources_report),
        "item_count": sum(s["row_count"] for s in sources_report),
        "safety": {
            "live_db_written": bool(live and allow_live_db_write),
            "live_db_migrated": False,
            "source_files_mutated": False,
        },
    }


# --- snapshot --------------------------------------------------------------------------


def create_forecast_config_snapshot(
    *,
    db_path: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    snapshot_name: str,
    snapshot_reason: str,
    created_by: str | None = None,
    source_mode: str = "db_current",
) -> dict[str, Any]:
    """Create an immutable snapshot of the active config items for ``project_key``."""
    if not is_project_eligible(project_key):
        raise ConfigRegistryError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not snapshot_name or not snapshot_reason:
        raise ConfigRegistryError("snapshot_name and snapshot_reason are required")
    db_path = Path(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        _require_v60(conn)
        rows = conn.execute(
            """SELECT config_item_id, config_domain, config_name, item_key, item_order, raw_json,
                      canonical_json_sha256
               FROM forecast_config_items
               WHERE project_key = ? AND status = 'active'
               ORDER BY config_domain, config_name, item_order""",
            (project_key,),
        ).fetchall()
        if not rows:
            raise ConfigRegistryError(
                f"no active config items for {project_key!r}; import config before snapshotting"
            )
        snapshot_sha = _sha256_text("\n".join(f"{r[1]}|{r[2]}|{r[4]}|{r[6]}" for r in rows))
        snapshot_id = _sha256_text(f"{project_key}|{snapshot_name}|{snapshot_sha}")
        now = _utc_now()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT OR IGNORE INTO forecast_config_snapshots
               (config_snapshot_id, project_key, snapshot_name, snapshot_created_utc, snapshot_reason,
                source_mode, item_count, snapshot_sha256, created_by, created_utc)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot_id,
                project_key,
                snapshot_name,
                now,
                snapshot_reason,
                source_mode,
                len(rows),
                snapshot_sha,
                created_by,
                now,
            ),
        )
        for r in rows:
            conn.execute(
                """INSERT OR IGNORE INTO forecast_config_snapshot_items
                   (config_snapshot_id, config_item_id, project_key, config_domain, config_name,
                    item_key, item_order, raw_json, canonical_json_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (snapshot_id, r[0], project_key, r[1], r[2], r[3], r[4], r[5], r[6]),
            )
        conn.commit()
    except ConfigRegistryError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    counts_by_domain: dict[str, int] = {}
    counts_by_name: dict[str, int] = {}
    digests_by_domain: dict[str, list[str]] = {}
    for r in rows:
        counts_by_domain[r[1]] = counts_by_domain.get(r[1], 0) + 1
        counts_by_name[f"{r[1]}/{r[2]}"] = counts_by_name.get(f"{r[1]}/{r[2]}", 0) + 1
        digests_by_domain.setdefault(r[1], []).append(r[6])
    hashes_by_domain = {d: _sha256_text("\n".join(v)) for d, v in digests_by_domain.items()}
    return {
        "config_snapshot_id": snapshot_id,
        "project_key": project_key,
        "snapshot_name": snapshot_name,
        "snapshot_reason": snapshot_reason,
        "source_mode": source_mode,
        "item_count": len(rows),
        "snapshot_sha256": snapshot_sha,
        "counts_by_domain": counts_by_domain,
        "counts_by_name": counts_by_name,
        "hashes_by_domain": hashes_by_domain,
    }


# --- emit file tree (shared by materialize + export) -----------------------------------


def _snapshot_grouped(conn: sqlite3.Connection, config_snapshot_id: str) -> list[dict[str, Any]]:
    """Snapshot items joined to their source path/format, ordered deterministically."""
    rows = conn.execute(
        """SELECT s.source_path, s.source_format, si.config_domain, si.config_name, si.item_order,
                  si.raw_json
           FROM forecast_config_snapshot_items si
           JOIN forecast_config_items ci ON ci.config_item_id = si.config_item_id
           JOIN forecast_config_sources s ON s.config_source_id = ci.config_source_id
           WHERE si.config_snapshot_id = ?
           ORDER BY s.source_path, si.item_order""",
        (config_snapshot_id,),
    ).fetchall()
    return [
        {
            "source_path": r[0],
            "source_format": r[1],
            "config_domain": r[2],
            "config_name": r[3],
            "item_order": r[4],
            "raw_json": r[5],
        }
        for r in rows
    ]


def _emit_config_tree(grouped: list[dict[str, Any]], dest_base: Path) -> list[dict[str, Any]]:
    """Write file-compatible config files under ``dest_base`` from grouped snapshot items."""
    by_file: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in grouped:
        by_file.setdefault((row["source_path"], row["source_format"]), []).append(row)
    files: list[dict[str, Any]] = []
    for (rel_path, fmt), items in sorted(by_file.items()):
        items = sorted(items, key=lambda r: r["item_order"])
        dest = dest_base / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            dest.write_text(items[0]["raw_json"], encoding="utf-8")
        elif fmt == "jsonl":
            dest.write_text("".join(it["raw_json"] + "\n" for it in items), encoding="utf-8")
        elif fmt == "csv":
            objs = [json.loads(it["raw_json"]) for it in items]
            fieldnames = list(objs[0].keys()) if objs else []
            write_csv(dest, fieldnames, objs)
        else:  # pragma: no cover
            raise ConfigRegistryError(f"unsupported source format on emit: {fmt}")
        files.append(
            {
                "rel_path": rel_path,
                "path": str(dest),
                "source_format": fmt,
                "row_count": len(items),
                "sha256": _sha256_file(dest),
            }
        )
    return files


def _materialize_from_conn(
    conn: sqlite3.Connection, *, config_snapshot_id: str, out_root: Path
) -> dict[str, Any]:
    """Shared core: read a snapshot from an OPEN connection and emit the file tree + manifest.

    The connection's open mode (read-write vs ``mode=ro``) is the caller's choice; this body only
    SELECTs, so a read-only connection is sufficient (and required for the live DB).
    """
    out_root = Path(out_root)
    materialized_root = out_root / MATERIALIZED_DIRNAME
    _require_v60(conn)
    snap = conn.execute(
        "SELECT project_key, snapshot_name, item_count, snapshot_sha256 FROM "
        "forecast_config_snapshots WHERE config_snapshot_id = ?",
        (config_snapshot_id,),
    ).fetchone()
    if snap is None:
        raise ConfigRegistryError(f"config_snapshot_id not found: {config_snapshot_id}")
    grouped = _snapshot_grouped(conn, config_snapshot_id)
    if not grouped:
        raise ConfigRegistryError(f"snapshot has no items: {config_snapshot_id}")
    files = _emit_config_tree(grouped, materialized_root)
    manifest = {
        "config_snapshot_id": config_snapshot_id,
        "project_key": snap[0],
        "snapshot_name": snap[1],
        "item_count": int(snap[2]),
        "snapshot_sha256": snap[3],
        "materialized_config_root": str(materialized_root),
        "files": files,
        "row_counts": {f["rel_path"]: f["row_count"] for f in files},
        "hashes": {f["rel_path"]: f["sha256"] for f in files},
    }
    manifest_path = out_root / SNAPSHOT_MANIFEST_NAME
    write_json(manifest_path, manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def materialize_forecast_config_snapshot(
    *,
    db_path: Path,
    config_snapshot_id: str,
    out_root: Path,
) -> dict[str, Any]:
    """Materialize a snapshot to a file-compatible config root + manifest under ``out_root``.

    Opens the DB read-write. For the LIVE config DB use
    :func:`materialize_forecast_config_snapshot_readonly` instead.
    """
    conn = sqlite3.connect(str(Path(db_path)))
    try:
        return _materialize_from_conn(
            conn, config_snapshot_id=config_snapshot_id, out_root=out_root
        )
    finally:
        conn.close()


def materialize_forecast_config_snapshot_readonly(
    *,
    db_path: Path,
    config_snapshot_id: str,
    out_root: Path,
) -> dict[str, Any]:
    """Read-only materialize: open the DB with ``mode=ro`` (never writes/creates ``-wal``/``-shm``).

    Use this to consume the LIVE config DB — materialize only SELECTs, so a read-only connection is
    sufficient and safe against the multi-GB live database.
    """
    p = Path(db_path)
    if not p.exists():
        raise ConfigRegistryError(f"config DB not found: {p}")
    try:
        conn = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ConfigRegistryError(f"config DB could not be opened read-only: {p}") from exc
    try:
        return _materialize_from_conn(
            conn, config_snapshot_id=config_snapshot_id, out_root=out_root
        )
    finally:
        conn.close()


def export_forecast_config_from_db(
    *,
    db_path: Path,
    out_root: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    config_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Export DB config back to a file-compatible tree under ``out_root`` (audit/rollback)."""
    if not is_project_eligible(project_key):
        raise ConfigRegistryError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    db_path = Path(db_path)
    out_root = Path(out_root)
    conn = sqlite3.connect(str(db_path))
    try:
        _require_v60(conn)
        if config_snapshot_id is not None:
            snap = conn.execute(
                "SELECT 1 FROM forecast_config_snapshots WHERE config_snapshot_id = ?",
                (config_snapshot_id,),
            ).fetchone()
            if snap is None:
                raise ConfigRegistryError(f"config_snapshot_id not found: {config_snapshot_id}")
            grouped = _snapshot_grouped(conn, config_snapshot_id)
        else:
            rows = conn.execute(
                """SELECT s.source_path, s.source_format, ci.config_domain, ci.config_name,
                          ci.item_order, ci.raw_json
                   FROM forecast_config_items ci
                   JOIN forecast_config_sources s ON s.config_source_id = ci.config_source_id
                   WHERE ci.project_key = ? AND ci.status = 'active'
                   ORDER BY s.source_path, ci.item_order""",
                (project_key,),
            ).fetchall()
            grouped = [
                {
                    "source_path": r[0],
                    "source_format": r[1],
                    "config_domain": r[2],
                    "config_name": r[3],
                    "item_order": r[4],
                    "raw_json": r[5],
                }
                for r in rows
            ]
    finally:
        conn.close()
    if not grouped:
        raise ConfigRegistryError("no config to export (empty snapshot / no active items)")
    files = _emit_config_tree(grouped, out_root)
    manifest = {
        "project_key": project_key,
        "config_snapshot_id": config_snapshot_id,
        "out_root": str(out_root),
        "files": files,
        "row_counts": {f["rel_path"]: f["row_count"] for f in files},
        "hashes": {f["rel_path"]: f["sha256"] for f in files},
    }
    manifest_path = out_root / EXPORT_MANIFEST_NAME
    write_json(manifest_path, manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


# --- reader-layer parity ---------------------------------------------------------------


def _records_for_spec(spec: _SourceSpec) -> Any:
    """Parse a config source into comparable records (json -> dict; jsonl/csv -> list of dicts)."""
    items, _src, _content = _parse_source(spec)
    if spec.fmt == "json":
        return json.loads(items[0].raw_json)
    return [json.loads(it.raw_json) for it in items]


def run_forecast_config_db_parity(
    *,
    config_root: Path,
    work_root: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Prove reader-layer parity: repo-file config == DB import->snapshot->materialize config.

    For each discovered domain, compares the records the readers would parse from the repo config base
    against those from the materialized DB snapshot. Returns ``status`` in {"pass","fail"} with exact
    differing domains. Uses a NON-LIVE temp DB by default (refuses the live DB).
    """
    work_root = Path(work_root)
    base = _config_base(config_root)
    if db_path is None:
        db_path = work_root / "parity_db" / "config_registry.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        db_path = Path(db_path)
    if _is_live_db(db_path):
        raise ConfigRegistryError(f"parity refuses the live/default DB: {db_path}")

    import_forecast_config_to_db(
        config_root=base, db_path=db_path, project_key=project_key, import_run_id="parity"
    )
    snap = create_forecast_config_snapshot(
        db_path=db_path,
        project_key=project_key,
        snapshot_name="parity_snapshot",
        snapshot_reason="reader-layer config parity",
    )
    mat = materialize_forecast_config_snapshot(
        db_path=db_path,
        config_snapshot_id=snap["config_snapshot_id"],
        out_root=work_root / "parity_materialized",
    )
    mat_base = Path(mat["materialized_config_root"])

    file_specs = discover_config_sources(base, project_key)
    domains: dict[str, dict[str, Any]] = {}
    differences: list[str] = []
    for spec in file_specs:
        mat_abs = mat_base / spec.rel_path
        key = f"{spec.domain}/{spec.name}"
        if not mat_abs.is_file():
            domains[key] = {"match": False, "reason": "materialized file missing"}
            differences.append(f"{key}: materialized file missing ({mat_abs})")
            continue
        file_records = _records_for_spec(spec)
        mat_records = _records_for_spec(
            _SourceSpec(spec.domain, spec.name, spec.rel_path, spec.fmt, mat_abs)
        )
        match = file_records == mat_records
        domains[key] = {
            "match": match,
            "file_count": 1 if spec.fmt == "json" else len(file_records),
            "db_count": 1 if spec.fmt == "json" else len(mat_records),
        }
        if not match:
            differences.append(f"{key}: file-backed records != db-snapshot records")
    status = "pass" if all(d["match"] for d in domains.values()) and domains else "fail"
    return {
        "status": status,
        "project_key": project_key,
        "config_base": str(base),
        "config_snapshot_id": snap["config_snapshot_id"],
        "materialized_config_root": str(mat_base),
        "config_snapshot_manifest": mat["manifest_path"],
        "domains": domains,
        "differences": differences,
    }


# --- resolution + lineage --------------------------------------------------------------


def resolve_forecast_config(
    *,
    source_mode: Literal["file", "db_snapshot"],
    config_root: Path | None = None,
    db_path: Path | None = None,
    config_snapshot_id: str | None = None,
    work_root: Path | None = None,
) -> ForecastConfigResolution:
    """Resolve a config source. ``file`` returns the base directly; ``db_snapshot`` materializes."""
    if source_mode == "file":
        if config_root is None:
            raise ConfigRegistryError("file source_mode requires config_root")
        return ForecastConfigResolution(source_mode="file", config_root=_config_base(config_root))
    if source_mode == "db_snapshot":
        if not (db_path and config_snapshot_id and work_root):
            raise ConfigRegistryError(
                "db_snapshot source_mode requires db_path, config_snapshot_id, and work_root"
            )
        mat = materialize_forecast_config_snapshot(
            db_path=Path(db_path), config_snapshot_id=config_snapshot_id, out_root=Path(work_root)
        )
        return ForecastConfigResolution(
            source_mode="db_snapshot",
            config_root=Path(mat["materialized_config_root"]),
            config_snapshot_id=config_snapshot_id,
            manifest_path=Path(mat["manifest_path"]),
            hashes=dict(mat["hashes"]),
            row_counts=dict(mat["row_counts"]),
        )
    raise ConfigRegistryError(f"unsupported source_mode: {source_mode!r}")


def config_snapshot_lineage_block(config_snapshot_root: Path) -> dict[str, Any]:
    """Lineage-only metadata for the controlled chain (Phase 9/12/15); NOT an execution dependency.

    The controlled context->analysis chain does not read operator config (repo-truth), so this block is
    explicitly labeled not-consumed. ``config_snapshot_root`` is a materialized snapshot out_root that
    contains ``config_snapshot_manifest.json``.
    """
    root = Path(config_snapshot_root)
    manifest_path = root / SNAPSHOT_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ConfigRegistryError(f"config snapshot manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    return {
        "config_snapshot_consumed": False,
        "config_snapshot_attached_for_lineage": True,
        "config_consuming_components": [],
        "config_not_consumed_reason": _NOT_CONSUMED_REASON,
        "config_snapshot_id": manifest.get("config_snapshot_id"),
        "config_snapshot_manifest": str(manifest_path),
        "materialized_config_root": manifest.get("materialized_config_root"),
        "row_counts": manifest.get("row_counts", {}),
        "hashes": manifest.get("hashes", {}),
    }
