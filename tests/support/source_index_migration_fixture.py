"""Deterministic legacy source-index fixture builder (Phase C Stage 1, C2).

Produces a source-index SQLite database at a supported legacy origin version by (1) applying the real
migrator to the current head on a *disposable* copy, (2) surgically reverting the schema down to the
target origin, and (3) seeding origin-aware synthetic data. This mirrors the established reversion
pattern in ``tests/test_migrator_v127_moved_event.py`` (``_revert_to_old_events`` / ``_install_events``)
but generalizes it across V122-V127. It also supports a distinct ``fresh`` fixture (empty database
migrated to head, no legacy seeding).

Independence (PCR-002): this builder *produces* origins with SQL mutation; the judgement of whether a
produced database matches an origin lives in the separate, hand-authored oracle
``tests/support/source_index_expected_inventory.py`` — no shared code path.

Historical fidelity (S1-AUD-006): a real pre-V123 deployed database carried the NARROW unique index
``idx_si_sources_relpath (source_kind, rel_path)``, which is exactly why it blocked duplicate
relative paths across roots. Pre-V123 fixtures (origin < 123) therefore install that index and seed
globally-unique rel_paths; V123+ fixtures omit it and seed cross-root duplicate paths. The current
migrator never creates the narrow index (it only appears in V99/V123 DROP statements), so it is
installed here explicitly to represent deployed reality.

Safety (PCR-001 / PCR-008): every database is written under a caller-provided rehearsal root. The
builder rejects destinations outside that root, rejects a symlinked root, refuses the configured
application database, and only rebuilds a target proven disposable (a fixture marker sits beside it).
All seeded data is synthetic — no production absolute paths, secrets, or real source content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from hb_assistant.obsidian_mcp.source_index_repository import source_id_for
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_migration_assurance import collect_inventory
from hb_assistant.store.source_intelligence_tables import (
    EVENT_STATUS_VALUES,
    EVENT_TYPE_VALUES,
)

SUPPORTED_ORIGINS: tuple[int, ...] = (121, 124, 125, 126, 127)
FRESH: str = "fresh"
HEAD_VERSION: int = 127
NARROW_INDEX_DROPPED_AT: int = 123

# Deterministic constants (no wall-clock, no randomness) so a fixture's logical content is stable.
_BASE_TS = "2020-01-01T00:00:00+00:00"
_ROOTS = ("work", "syn-work")
_GEN_ONLY_ROOT = "nas-archive"  # hosts the third active generation (reconcile_pending); no sources
_SHARED_REL_PATH = "shared/dup.pdf"  # duplicated under both roots at V123+ (narrow index gone)
_MARKER_SUFFIX = ".fixture-marker.json"

_NARROW_INDEX_SQL = (
    "CREATE UNIQUE INDEX idx_si_sources_relpath "
    "ON source_intelligence_sources(source_kind, rel_path) WHERE rel_path IS NOT NULL"
)


@dataclass
class FixtureResult:
    db_path: Path
    origin: int | str
    row_count: int
    marker_path: Path
    manifest_path: Path
    logical_inventory_hash: str
    file_sha256: str


# --- Path safety ------------------------------------------------------------------------------


def _marker_path(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + _MARKER_SUFFIX)


def _validate_target(rehearsal_root: Path, filename: str) -> Path:
    """Resolve and validate a fixture destination under a disposable rehearsal root.

    Raises ``ValueError`` if the root is missing / not a directory / a symlink, if the resolved
    destination escapes the root, if it collides with the configured application database, or if a
    pre-existing file is not marked disposable.
    """
    root = Path(rehearsal_root)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"rehearsal root is not an existing directory: {root}")
    if root.is_symlink():
        raise ValueError(f"rehearsal root must not be a symlink: {root}")
    resolved_root = root.resolve()

    if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
        raise ValueError(f"fixture filename must be a bare name, got: {filename!r}")
    db_path = (resolved_root / filename).resolve()
    if resolved_root not in db_path.parents:
        raise ValueError(f"fixture destination escapes rehearsal root: {db_path}")

    # Refuse the configured application database (inspect path policy for the value only). A
    # path-policy resolution error is narrowed to the expected exception types; anything else
    # propagates rather than silently dropping the guard (S1-AUD-011).
    from hb_assistant.config.path_policy import PathPolicy

    try:
        app_db: Path | None = Path(PathPolicy().get_db_path()).resolve()
    except (OSError, RuntimeError, ValueError):
        app_db = None
    if app_db is not None and db_path == app_db:
        raise ValueError("refusing to write a fixture over the configured application database")

    if db_path.exists() and not _marker_path(db_path).exists():
        raise ValueError(
            f"refusing to overwrite a non-fixture database (no disposable marker): {db_path}"
        )
    return db_path


# --- Schema reversion (head → origin) ---------------------------------------------------------


def _revert_events_to_pre_v127(conn: sqlite3.Connection) -> None:
    """Rebuild ``source_intelligence_events`` to its pre-V127 shape (no dest/backoff cols, no 'moved')."""
    et_csv = ", ".join(f"'{v}'" for v in EVENT_TYPE_VALUES)
    st_csv = ", ".join(f"'{v}'" for v in EVENT_STATUS_VALUES)
    conn.execute("DROP TABLE source_intelligence_events")
    conn.execute(
        "CREATE TABLE source_intelligence_events ("
        " event_id TEXT PRIMARY KEY, source_id TEXT, rel_path TEXT, source_root_key TEXT,"
        f" event_type TEXT NOT NULL CHECK(event_type IN ({et_csv})),"
        f" status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ({st_csv})),"
        " error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0,"
        " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    conn.execute(
        "CREATE INDEX idx_si_events_status ON source_intelligence_events(status, created_at)"
    )
    conn.execute("CREATE INDEX idx_si_events_source ON source_intelligence_events(source_id)")


def _revert_to_origin(conn: sqlite3.Connection, origin: int) -> None:
    """Drop every source-index object introduced after ``origin`` and trim the ledger to ``origin``.

    Also restores the pre-V123 narrow unique index when reverting below V123 (S1-AUD-006).
    """
    if origin >= HEAD_VERSION:
        return
    if origin < 127:
        _revert_events_to_pre_v127(conn)
    if origin < 126:
        conn.execute("DROP INDEX IF EXISTS idx_si_sources_renamed_from")
        conn.execute("ALTER TABLE source_intelligence_sources DROP COLUMN renamed_from_source_id")
    if origin < 125:
        conn.execute("DROP TABLE IF EXISTS source_index_scan_quarantine")
    if origin < 124:
        conn.execute("DROP INDEX IF EXISTS idx_si_metadata_fts_rowid")
    if origin < 122:
        conn.execute("DROP INDEX IF EXISTS idx_si_sources_last_seen_gen")
        for col in ("last_seen_generation", "last_seen_at", "last_indexed_fingerprint"):
            conn.execute(f"ALTER TABLE source_intelligence_sources DROP COLUMN {col}")
        for col in ("extraction_disposition", "content_indexed_at"):
            conn.execute(f"ALTER TABLE source_intelligence_metadata DROP COLUMN {col}")
        conn.execute("ALTER TABLE source_index_bootstrap_runs DROP COLUMN generation_id")
        conn.execute("DROP TABLE IF EXISTS source_index_scan_generations")
    # Pre-V123 deployed reality: the narrow unique index is present (V123 later drops it).
    if origin < NARROW_INDEX_DROPPED_AT:
        conn.execute(_NARROW_INDEX_SQL)
    conn.execute("DELETE FROM schema_migrations WHERE version > ?", (origin,))


# --- Origin-aware seeding ---------------------------------------------------------------------


def _seed(conn: sqlite3.Connection, origin: int, row_count: int) -> None:
    kind = "external_file"
    per_root = max(2, row_count)
    # Cross-root duplicate rel_paths are only valid once V123 drops the narrow unique index.
    allow_cross_root_dup = origin >= NARROW_INDEX_DROPPED_AT
    source_ids: dict[str, list[str]] = {root: [] for root in _ROOTS}

    for root in _ROOTS:
        for i in range(per_root):
            if i == 0 and allow_cross_root_dup:
                rel_path = _SHARED_REL_PATH  # same under both roots → distinct source_ids
            else:
                rel_path = f"{root}/docs/file_{i}.pdf"  # globally unique (narrow-index-safe)
            sid = source_id_for(kind, source_root_key=root, rel_path=rel_path)
            source_ids[root].append(sid)
            conn.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, source_root_key, rel_path, active, deleted, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
                (sid, kind, root, rel_path, _BASE_TS, _BASE_TS),
            )
            fts_present = i % 2 == 0
            fts_rowid: int | None = None
            if fts_present:
                cur = conn.execute(
                    "INSERT INTO source_intelligence_fts (text_excerpt, rel_path, aux) "
                    "VALUES (?, ?, ?)",
                    (f"excerpt for {root} {i}", rel_path, "proj-x"),
                )
                fts_rowid = int(cur.lastrowid) if cur.lastrowid is not None else None
                conn.execute(
                    "INSERT INTO source_intelligence_text "
                    "(source_id, text_excerpt, excerpt_char_count, full_text_sha256, "
                    " raw_body_persisted, redaction_applied, updated_at) VALUES (?, ?, ?, ?, 0, 1, ?)",
                    (
                        sid,
                        f"excerpt for {root} {i}",
                        len(f"excerpt for {root} {i}"),
                        hashlib.sha256(f"{root}{i}".encode()).hexdigest(),
                        _BASE_TS,
                    ),
                )
            conn.execute(
                "INSERT INTO source_intelligence_metadata "
                "(source_id, file_ext, extraction_status, fts_rowid, indexed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, "pdf", "ok" if fts_present else "pending", fts_rowid, _BASE_TS),
            )
            status = ("not_generated", "generated", "stale")[i % 3]
            conn.execute(
                "INSERT INTO source_intelligence_generated_notes "
                "(generated_note_id, source_id, note_rel_path, generation_status, generated_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"card-{root}-{i}",
                    sid,
                    f"Cards/{root}/{i}.md",
                    status,
                    _BASE_TS if status != "not_generated" else None,
                    _BASE_TS,
                ),
            )

    # A couple of obsidian_note sources under "work" so obsidian_note_fts is populated (distinct FTS
    # table from external files) — enables FTS-content parity coverage on both FTS tables.
    for j in range(2):
        rel_path = f"Notes/note_{j}.md"
        sid = source_id_for("obsidian_note", source_root_key="work", rel_path=rel_path)
        conn.execute(
            "INSERT INTO source_intelligence_sources "
            "(source_id, source_kind, source_root_key, rel_path, active, deleted, created_at, updated_at) "
            "VALUES (?, 'obsidian_note', 'work', ?, 1, 0, ?, ?)",
            (sid, rel_path, _BASE_TS, _BASE_TS),
        )
        cur = conn.execute(
            "INSERT INTO obsidian_note_fts (text_excerpt, rel_path, aux) VALUES (?, ?, ?)",
            (f"note excerpt {j}", rel_path, "tag-a"),
        )
        note_rowid = int(cur.lastrowid) if cur.lastrowid is not None else None
        conn.execute(
            "INSERT INTO source_intelligence_text "
            "(source_id, text_excerpt, excerpt_char_count, full_text_sha256, raw_body_persisted, "
            " redaction_applied, updated_at) VALUES (?, ?, ?, ?, 0, 1, ?)",
            (
                sid,
                f"note excerpt {j}",
                len(f"note excerpt {j}"),
                hashlib.sha256(f"note{j}".encode()).hexdigest(),
                _BASE_TS,
            ),
        )
        conn.execute(
            "INSERT INTO source_intelligence_metadata "
            "(source_id, file_ext, extraction_status, fts_rowid, indexed_at) "
            "VALUES (?, 'md', 'ok', ?, ?)",
            (sid, note_rowid, _BASE_TS),
        )

    for root in _ROOTS:
        conn.execute(
            "INSERT INTO source_index_bootstrap_runs "
            "(run_id, root_key, mode, status, started_at, created_at) "
            "VALUES (?, ?, 'bootstrap', 'completed', ?, ?)",
            (f"run-{root}", root, _BASE_TS, _BASE_TS),
        )

    # Generations (V122+): cover ALL six states; exactly one active (running/partial/reconcile_pending)
    # per root — the three active states live on three distinct roots (S1-AUD-012).
    if origin >= 122:
        gens = [
            ("gen-work-running", "work", "running"),
            ("gen-work-completed", "work", "completed"),
            ("gen-work-failed", "work", "failed"),
            ("gen-syn-partial", "syn-work", "partial"),
            ("gen-syn-abandoned", "syn-work", "abandoned"),
            ("gen-nas-reconcile", _GEN_ONLY_ROOT, "reconcile_pending"),
        ]
        for gen_id, root, status in gens:
            conn.execute(
                "INSERT INTO source_index_scan_generations "
                "(generation_id, root_key, status, root_path_hash, policy_fingerprint, started_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (gen_id, root, status, f"rph-{root}", "fp-v1", _BASE_TS, _BASE_TS),
            )
        for root in _ROOTS:
            active_gen = "gen-work-running" if root == "work" else "gen-syn-partial"
            conn.execute(
                "UPDATE source_intelligence_sources "
                "SET last_seen_generation = ?, last_seen_at = ?, last_indexed_fingerprint = 'fp-v1' "
                "WHERE source_id = ?",
                (active_gen, _BASE_TS, source_ids[root][0]),
            )

    if origin >= 125:
        conn.execute(
            "INSERT INTO source_index_scan_quarantine "
            "(quarantine_id, source_root_key, rel_path, failure_stage, error_code, attempt_count, "
            " first_seen_at, last_seen_at, status, resolution_state) "
            "VALUES (?, 'work', 'work/docs/poison.bin', 'observe', 'parse_failed', 3, ?, ?, "
            " 'quarantined', 'unresolved')",
            ("q-work-1", _BASE_TS, _BASE_TS),
        )

    if origin >= 126:
        predecessor = source_ids["work"][1]
        successor = source_ids["work"][2]
        conn.execute(
            "UPDATE source_intelligence_sources SET renamed_from_source_id = ? WHERE source_id = ?",
            (predecessor, successor),
        )
        conn.execute(
            "UPDATE source_intelligence_sources SET deleted = 1 WHERE source_id = ?",
            (predecessor,),
        )

    any_src = source_ids["work"][0]
    conn.execute(
        "INSERT INTO source_intelligence_events "
        "(event_id, source_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
        "VALUES (?, ?, ?, 'work', 'created', 'done', 1, ?, ?)",
        ("evt-created", any_src, "work/docs/file_0.pdf", _BASE_TS, _BASE_TS),
    )
    if origin >= 127:
        conn.execute(
            "INSERT INTO source_intelligence_events "
            "(event_id, source_id, rel_path, source_root_key, dest_rel_path, next_attempt_at, "
            " event_type, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, 'work/docs/file_1.pdf', 'work', 'work/docs/moved_1.pdf', ?, 'moved', 'queued', 2, ?, ?)",
            ("evt-moved", source_ids["work"][1], _BASE_TS, _BASE_TS, _BASE_TS),
        )
    else:
        conn.execute(
            "INSERT INTO source_intelligence_events "
            "(event_id, source_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, 'work/docs/file_1.pdf', 'work', 'modified', 'queued', 0, ?, ?)",
            ("evt-modified", source_ids["work"][1], _BASE_TS, _BASE_TS),
        )


# --- Public builder ---------------------------------------------------------------------------


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def build_fixture(
    rehearsal_root: Path,
    origin: int | str,
    *,
    row_count: int = 6,
    filename: str | None = None,
) -> FixtureResult:
    """Build a deterministic source-index fixture under ``rehearsal_root``.

    ``origin`` is a supported integer version (121/124/125/126/127) or the string ``"fresh"`` (an
    empty database migrated to head, no legacy seeding). Returns a :class:`FixtureResult` with the
    database path, a disposable marker, a manifest, the logical-inventory hash, and whole-file SHA-256.
    """
    is_fresh = origin == FRESH
    if not is_fresh and origin not in SUPPORTED_ORIGINS:
        raise ValueError(f"unsupported origin {origin!r}; supported: {SUPPORTED_ORIGINS} or {FRESH!r}")
    default_name = "source_index_fresh.sqlite" if is_fresh else f"source_index_v{origin}.sqlite"
    db_path = _validate_target(rehearsal_root, filename or default_name)

    for p in (db_path, db_path.with_name(db_path.name + "-wal"), db_path.with_name(db_path.name + "-shm")):
        if p.exists():
            p.unlink()

    head = SQLiteMigrator(db_path=str(db_path)).apply()
    if head != HEAD_VERSION:
        raise RuntimeError(f"migrator applied to {head}, expected head {HEAD_VERSION}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        if not is_fresh:
            assert isinstance(origin, int)
            _revert_to_origin(conn, origin)
            _seed(conn, origin, row_count)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    inventory = collect_inventory(db_path)
    logical_hash = inventory.logical_inventory_hash
    file_sha = _file_sha256(db_path)

    marker_path = _marker_path(db_path)
    marker_path.write_text(
        json.dumps(
            {"disposable": True, "purpose": "phase-c-source-index-migration-fixture", "origin": origin},
            indent=2,
        )
    )
    manifest = {
        "origin": origin,
        "row_count": row_count,
        "head_version": HEAD_VERSION,
        "schema_head": inventory.schema_head,
        "journal_mode": inventory.journal_mode,
        "row_counts": inventory.row_counts,
        "duplicate_relpath_across_roots": inventory.duplicate_relpath_across_roots,
        "fts_present_count": inventory.fts_present_count,
        "fts_missing_count": inventory.fts_missing_count,
        "fts_parity": {
            "matched": inventory.fts_parity.matched,
            "dangling": inventory.fts_parity.dangling,
            "orphan": inventory.fts_parity.orphan,
        },
        "generation_counts_by_status": inventory.generation_counts_by_status,
        "quarantine_unresolved_count": inventory.quarantine_unresolved_count,
        "lineage_count": inventory.lineage_count,
        "events_by_type": inventory.events_by_type,
        "events_moved_supported": inventory.events_moved_supported,
        "logical_inventory_hash": logical_hash,
        "file_sha256": file_sha,
    }
    manifest_path = db_path.with_name(db_path.name + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    return FixtureResult(
        db_path=db_path,
        origin=origin,
        row_count=row_count,
        marker_path=marker_path,
        manifest_path=manifest_path,
        logical_inventory_hash=logical_hash,
        file_sha256=file_sha,
    )
