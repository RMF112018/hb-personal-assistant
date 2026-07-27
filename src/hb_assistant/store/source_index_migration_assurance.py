"""Read-only inventory & parity engine for source-index migration assurance (Phase C).

This module inspects a source-index SQLite database and produces a structured, redacted inventory
plus a deterministic *logical* inventory hash. It is strictly read-only and **fail-closed**: it opens
the database with a read-only URI (``mode=ro``) and issues only ``SELECT`` / ``PRAGMA`` statements. It
never creates, migrates, repairs, reindexes, or writes — a missing/unreadable path raises rather than
being silently created (S1-AUD-008).

Scope (Phase C Stage 1, C3): the *observation* primitive used by fixtures, by the (later)
migration/backup proofs, and by evidence generation. It performs no backup, restore, or migration
itself, and requires no live NAS root or running watcher.

Structural coverage (S1-AUD-007): tables, ordered column definitions (type/nullability/default/pk),
foreign keys, indexes (uniqueness/partial/columns/canonical SQL), triggers, views, and normalized
canonical DDL — all folded into the logical hash so a column/default/constraint/index change is
detectable.

Content coverage (S1-AUD-009 / S1-AUD-015): source text, chunks, relationships, summaries, source↔FTS
linkage parity (matched / dangling / orphan), and **per-row FTS content digests** for both FTS tables
are folded into the logical hash — so a deleted FTS row, a stale ``fts_rowid``, a changed excerpt, an
orphan FTS row, missing source text, or corrupted FTS *content at the same rowid* is detectable.

Read-only WAL safety (S1-AUD-014): inspection is rejected fail-closed when a non-empty ``-wal`` sidecar
is present, because the immutable read would ignore committed WAL state.

Redaction contract: the report emits structural facts (object names, column names/types, counts,
states, integrity verdicts, content *digests*) only. It never emits ``rel_path`` / ``text_excerpt``
path or content *values* — so a report can be committed as evidence without leaking source content or
host paths.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Source-index tables whose row counts are inventoried when present. Ordered for stable output.
SOURCE_INDEX_TABLES: tuple[str, ...] = (
    "source_index_entities",
    "source_index_locators",
    "source_index_move_signals",
    "source_intelligence_sources",
    "source_intelligence_metadata",
    "source_intelligence_text",
    "source_intelligence_chunks",
    "source_intelligence_relationships",
    "source_intelligence_generated_notes",
    "source_intelligence_events",
    "source_intelligence_state",
    "source_intelligence_summaries",
    "source_index_bootstrap_runs",
    "source_index_bootstrap_state",
    "source_index_reconciliation_runs",
    "source_index_scan_generations",
    "source_index_scan_quarantine",
    "source_structure_roots",
    "source_structure_folders",
)

# Tables whose full logical content feeds the deterministic logical hash.
_LOGICAL_HASH_TABLES: tuple[str, ...] = (
    "schema_migrations",
    "source_index_entities",
    "source_index_locators",
    "source_index_move_signals",
    "source_intelligence_sources",
    "source_intelligence_metadata",
    "source_intelligence_text",
    "source_intelligence_chunks",
    "source_intelligence_relationships",
    "source_intelligence_generated_notes",
    "source_intelligence_events",
    "source_intelligence_summaries",
    "source_index_bootstrap_runs",
    "source_index_scan_generations",
    "source_index_scan_quarantine",
)

# External files index into source_intelligence_fts; obsidian notes into obsidian_note_fts.
_FTS_TABLES: tuple[str, ...] = ("source_intelligence_fts", "obsidian_note_fts")

# Tables whose canonical column/FK/DDL structure feeds the structural signature. Covers every
# inventoried source-index table plus the FTS virtual tables (S1-AUD-016) so a schema change to any
# of them flips the structural signature and the logical hash.
_STRUCTURAL_TABLES: tuple[str, ...] = SOURCE_INDEX_TABLES + _FTS_TABLES

# Columns excluded from the logical hash because they carry migration wall-clock time, not logical
# state. ``schema_migrations.applied_at`` is stamped with ``datetime.now`` by the migrator.
_VOLATILE_HASH_COLUMNS: frozenset[str] = frozenset({"applied_at"})

# External files index into source_intelligence_fts; obsidian notes into obsidian_note_fts.
_FTS_BY_KIND: dict[str, str] = {
    "external_file": "source_intelligence_fts",
    "obsidian_note": "obsidian_note_fts",
}


@dataclass
class IntegrityReport:
    quick_check: str
    integrity_check: str
    foreign_key_violations: int


@dataclass
class FtsParity:
    matched: int
    dangling: int  # metadata.fts_rowid set but no FTS row at that rowid
    orphan: int  # FTS row not referenced by any metadata.fts_rowid


@dataclass
class InventoryReport:
    schema_head: int | None
    schema_versions: list[int]
    file_size_bytes: int
    wal_size_bytes: int
    journal_mode: str
    sqlite_version: str
    tables: list[str]
    indexes: list[str]
    triggers: list[str]
    views: list[str]
    row_counts: dict[str, int]
    structural_signature: dict[str, object]
    root_count: int
    duplicate_relpath_across_roots: int
    fts_present_count: int
    fts_missing_count: int
    fts_parity: FtsParity
    generation_counts_by_status: dict[str, int]
    quarantine_unresolved_count: int
    lineage_count: int
    events_by_status: dict[str, int]
    events_by_type: dict[str, int]
    events_moved_supported: bool
    integrity: IntegrityReport
    logical_inventory_hash: str
    warnings: list[str] = field(default_factory=list)


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    """Open a genuinely read-only connection, fail-closed (S1-AUD-008).

    Requires the path to exist and be a regular file, then opens the ``mode=ro&immutable=1`` URI. The
    SQLite layer rejects every write, and ``immutable=1`` guarantees **no** ``-wal``/``-shm``/journal
    sidecar is created even for a WAL-mode database (a plain ``mode=ro`` open of a WAL database creates
    shared-memory coordination files). There is **no** fall-back to a read-write connection — a
    missing/unreadable database raises rather than being silently created (S1-AUD-008).

    Because ``immutable=1`` ignores any ``-wal``, a database with committed-but-uncheckpointed WAL
    state would otherwise be inventoried from a **stale** main file. To prevent that, inspection is
    rejected fail-closed when a non-empty ``-wal`` sidecar is present (``uncheckpointed_wal_present``);
    it never checkpoints (that would be a write). The caller must supply a checkpointed rehearsal copy
    or a verified backup. The fixture builder truncates WAL before handing a database off, so its
    ``-wal`` is empty/absent.
    """
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"database does not exist (fail-closed, not created): {path}")
    if not path.is_file():
        raise ValueError(f"database path is not a regular file: {path}")
    wal = path.with_name(path.name + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise ValueError(
            f"uncheckpointed_wal_present: {wal} ({wal.stat().st_size} bytes) — immutable read would "
            "ignore committed WAL state; inspect a checkpointed copy or verified backup instead"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    return column in {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _objects(conn: sqlite3.Connection, obj_type: str) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE 'sqlite_%' ORDER BY name",
        (obj_type,),
    ).fetchall()
    return [r[0] for r in rows]


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


# --- Structural inventory (S1-AUD-007) ---------------------------------------------------------


def _normalize_sql(sql: str | None) -> str:
    return " ".join((sql or "").split())


def table_structure(conn: sqlite3.Connection, table: str) -> dict[str, object]:
    """Ordered columns, foreign keys, and canonical CREATE SQL for one table (read-only)."""
    columns = [
        {
            "cid": int(r["cid"]),
            "name": r["name"],
            "type": r["type"],
            "notnull": int(r["notnull"]),
            "default": r["dflt_value"],
            "pk": int(r["pk"]),
            "hidden": int(r["hidden"]),
        }
        for r in conn.execute(f"PRAGMA table_xinfo({table})").fetchall()
    ]
    fks = [
        {
            "table": r["table"],
            "from": r["from"],
            "to": r["to"],
            "on_update": r["on_update"],
            "on_delete": r["on_delete"],
        }
        for r in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    ]
    sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return {"columns": columns, "foreign_keys": fks, "create_sql": _normalize_sql(sql_row["sql"] if sql_row else None)}


def index_structure(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Every non-internal index: uniqueness, partial flag, ordered columns, canonical SQL."""
    result: dict[str, dict[str, object]] = {}
    for name in _objects(conn, "index"):
        list_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
        ).fetchone()
        sql = _normalize_sql(list_row["sql"] if list_row else None)
        cols = [r["name"] for r in conn.execute(f"PRAGMA index_info({name})").fetchall()]
        result[name] = {
            "unique": "UNIQUE" in sql.upper(),
            "partial": " WHERE " in f" {sql.upper()} ",
            "columns": cols,
            "sql": sql,
        }
    return result


def structural_signature(conn: sqlite3.Connection) -> dict[str, object]:
    """A deterministic, redacted structural fingerprint (columns/FKs/DDL/indexes/triggers/views)."""
    tables = {
        t: table_structure(conn, t) for t in _STRUCTURAL_TABLES if _table_exists(conn, t)
    }
    triggers = {
        r["name"]: _normalize_sql(r["sql"])
        for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    }
    views = {
        r["name"]: _normalize_sql(r["sql"])
        for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'view' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    }
    return {
        "tables": tables,
        "indexes": index_structure(conn),
        "triggers": triggers,
        "views": views,
    }


# --- FTS linkage parity (S1-AUD-009) -----------------------------------------------------------


def fts_content_digests(conn: sqlite3.Connection) -> list[str]:
    """Deterministic, redacted per-row content digests for both FTS tables (S1-AUD-015).

    A digest folds the table name, rowid, and the indexed field *values* (text/rel_path/aux) so that
    corrupting an existing referenced FTS row's content — while preserving its rowid — is detectable
    even though rowid-set parity (matched/dangling/orphan) is unchanged. Raw text/paths are never
    emitted, only their sha256 digest.
    """
    digests: list[str] = []
    for fts_table in _FTS_TABLES:
        if not _table_exists(conn, fts_table):
            continue
        for row in conn.execute(
            f"SELECT rowid, text_excerpt, rel_path, aux FROM {fts_table}"
        ).fetchall():
            payload = "\x1f".join(
                [fts_table, str(row[0]), row[1] or "", row[2] or "", row[3] or ""]
            )
            digests.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
    return sorted(digests)


def fts_parity(conn: sqlite3.Connection) -> FtsParity:
    """Cross-check ``metadata.fts_rowid`` against the kind-appropriate FTS table's rowids."""
    if not _table_exists(conn, "source_intelligence_metadata") or not _table_exists(
        conn, "source_intelligence_sources"
    ):
        return FtsParity(0, 0, 0)
    matched = dangling = orphan = 0
    entity_keyed = _column_exists(
        conn, "source_intelligence_metadata", "source_entity_id"
    )
    metadata_key = "source_entity_id" if entity_keyed else "source_id"
    source_key = "source_entity_id" if entity_keyed else "source_id"
    for kind, fts_table in _FTS_BY_KIND.items():
        if not _table_exists(conn, fts_table):
            continue
        referenced = {
            int(r[0])
            for r in conn.execute(
                "SELECT m.fts_rowid FROM source_intelligence_metadata m "
                f"JOIN source_intelligence_sources s ON s.{source_key} = m.{metadata_key} "
                "WHERE s.source_kind = ? AND m.fts_rowid IS NOT NULL",
                (kind,),
            ).fetchall()
        }
        existing = {int(r[0]) for r in conn.execute(f"SELECT rowid FROM {fts_table}").fetchall()}
        matched += len(referenced & existing)
        dangling += len(referenced - existing)
        orphan += len(existing - referenced)
    return FtsParity(matched=matched, dangling=dangling, orphan=orphan)


# --- Logical hash ------------------------------------------------------------------------------


def logical_inventory_hash(conn: sqlite3.Connection) -> str:
    """A deterministic, page-layout-independent digest of the source-index logical + structural state.

    Folds together: the row content of the logical tables (volatile ``applied_at`` excluded); the full
    structural signature (columns/FKs/DDL/indexes/triggers/views); and FTS linkage parity. Two
    databases with identical logical content, structure, and FTS linkage hash identically regardless of
    physical page layout; any column/default/constraint/index/text/FTS change flips the hash.
    """
    material: dict[str, object] = {}
    table_rows: dict[str, list[str]] = {}
    for table in _LOGICAL_HASH_TABLES:
        if not _table_exists(conn, table):
            continue
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        table_rows[table] = sorted(
            json.dumps(
                {k: v for k, v in dict(row).items() if k not in _VOLATILE_HASH_COLUMNS},
                sort_keys=True,
                default=str,
            )
            for row in rows
        )
    material["rows"] = table_rows
    material["structure"] = structural_signature(conn)
    parity = fts_parity(conn)
    material["fts_parity"] = {
        "matched": parity.matched,
        "dangling": parity.dangling,
        "orphan": parity.orphan,
    }
    material["fts_content"] = fts_content_digests(conn)
    canonical = json.dumps(material, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _integrity(conn: sqlite3.Connection) -> IntegrityReport:
    quick = conn.execute("PRAGMA quick_check").fetchone()
    integ = conn.execute("PRAGMA integrity_check").fetchone()
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    return IntegrityReport(
        quick_check=str(quick[0]) if quick else "unknown",
        integrity_check=str(integ[0]) if integ else "unknown",
        foreign_key_violations=len(fk_rows),
    )


def _events_breakdown(conn: sqlite3.Connection) -> tuple[dict[str, int], dict[str, int], bool]:
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    if not _table_exists(conn, "source_intelligence_events"):
        return by_status, by_type, False
    for status, n in conn.execute(
        "SELECT status, COUNT(*) FROM source_intelligence_events GROUP BY status"
    ).fetchall():
        by_status[str(status)] = int(n)
    for etype, n in conn.execute(
        "SELECT event_type, COUNT(*) FROM source_intelligence_events GROUP BY event_type"
    ).fetchall():
        by_type[str(etype)] = int(n)
    sql_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'source_intelligence_events'"
    ).fetchone()
    moved_supported = bool(sql_row and "'moved'" in (sql_row[0] or ""))
    return by_status, by_type, moved_supported


def collect_inventory(db_path: Path) -> InventoryReport:
    """Collect the read-only inventory of a source-index database at ``db_path``."""
    path = Path(db_path)
    warnings: list[str] = []
    conn = _open_readonly(path)
    try:
        schema_versions: list[int] = []
        schema_head: int | None = None
        if _table_exists(conn, "schema_migrations"):
            schema_versions = [
                int(r[0])
                for r in conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            schema_head = max(schema_versions) if schema_versions else None

        journal_mode_row = conn.execute("PRAGMA journal_mode").fetchone()
        journal_mode = str(journal_mode_row[0]) if journal_mode_row else "unknown"

        row_counts = {t: _count(conn, t) for t in SOURCE_INDEX_TABLES if _table_exists(conn, t)}

        root_count = 0
        duplicate_relpath = 0
        if _table_exists(conn, "source_intelligence_sources"):
            r = conn.execute(
                "SELECT COUNT(DISTINCT source_root_key) FROM source_intelligence_sources "
                "WHERE source_root_key IS NOT NULL"
            ).fetchone()
            root_count = int(r[0]) if r else 0
            dup = conn.execute(
                "SELECT COUNT(*) FROM ("
                "  SELECT rel_path FROM source_intelligence_sources "
                "  WHERE rel_path IS NOT NULL "
                "  GROUP BY rel_path HAVING COUNT(DISTINCT source_root_key) > 1"
                ")"
            ).fetchone()
            duplicate_relpath = int(dup[0]) if dup else 0

        fts_present = 0
        fts_missing = 0
        if _table_exists(conn, "source_intelligence_metadata"):
            fp = conn.execute(
                "SELECT COUNT(*) FROM source_intelligence_metadata WHERE fts_rowid IS NOT NULL"
            ).fetchone()
            fm = conn.execute(
                "SELECT COUNT(*) FROM source_intelligence_metadata WHERE fts_rowid IS NULL"
            ).fetchone()
            fts_present = int(fp[0]) if fp else 0
            fts_missing = int(fm[0]) if fm else 0

        gen_counts: dict[str, int] = {}
        if _table_exists(conn, "source_index_scan_generations"):
            for status, n in conn.execute(
                "SELECT status, COUNT(*) FROM source_index_scan_generations GROUP BY status"
            ).fetchall():
                gen_counts[str(status)] = int(n)

        quarantine_unresolved = 0
        if _table_exists(conn, "source_index_scan_quarantine"):
            q = conn.execute(
                "SELECT COUNT(*) FROM source_index_scan_quarantine "
                "WHERE resolution_state = 'unresolved'"
            ).fetchone()
            quarantine_unresolved = int(q[0]) if q else 0

        lineage_count = 0
        if _column_exists(conn, "source_intelligence_sources", "renamed_from_source_id"):
            lr = conn.execute(
                "SELECT COUNT(*) FROM source_intelligence_sources "
                "WHERE renamed_from_source_id IS NOT NULL"
            ).fetchone()
            lineage_count = int(lr[0]) if lr else 0

        events_by_status, events_by_type, events_moved = _events_breakdown(conn)

        integrity = _integrity(conn)
        logical_hash = logical_inventory_hash(conn)

        wal_path = path.with_name(path.name + "-wal")
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0

        return InventoryReport(
            schema_head=schema_head,
            schema_versions=schema_versions,
            file_size_bytes=path.stat().st_size if path.exists() else 0,
            wal_size_bytes=wal_size,
            journal_mode=journal_mode,
            sqlite_version=sqlite3.sqlite_version,
            tables=_objects(conn, "table"),
            indexes=_objects(conn, "index"),
            triggers=_objects(conn, "trigger"),
            views=_objects(conn, "view"),
            row_counts=row_counts,
            structural_signature=structural_signature(conn),
            root_count=root_count,
            duplicate_relpath_across_roots=duplicate_relpath,
            fts_present_count=fts_present,
            fts_missing_count=fts_missing,
            fts_parity=fts_parity(conn),
            generation_counts_by_status=gen_counts,
            quarantine_unresolved_count=quarantine_unresolved,
            lineage_count=lineage_count,
            events_by_status=events_by_status,
            events_by_type=events_by_type,
            events_moved_supported=events_moved,
            integrity=integrity,
            logical_inventory_hash=logical_hash,
            warnings=warnings,
        )
    finally:
        conn.close()


def to_redacted_dict(report: InventoryReport) -> dict[str, object]:
    """Serialize an inventory report to a redacted dict safe for committed evidence.

    Only structural facts, counts, and digests are present (no path or content values), so the result
    carries nothing sensitive. Kept as a distinct function so the redaction contract has one
    enforcement point that tests can assert against.
    """
    return asdict(report)


# --- Migration parity comparison + query plans (Phase C Stage 2, PC-WI-01) ----------------------
#
# These helpers compare two already-collected inventories (an origin fixture and its migrated head, or
# a migrated head and a fresh head) and classify the differences per the spec §5 parity model. They add
# no new database access to the inventory path and preserve the read-only, fail-closed contract
# (``query_plan`` reuses ``_open_readonly``; nothing here writes, migrates, or repairs).

# Parity classification vocabulary (Phase C spec §5).
PARITY_EXACT = "exact"
PARITY_MONOTONIC = "monotonic"
PARITY_MIGRATION_TRANSFORMED = "migration-transformed"
PARITY_ALLOWED_DIFFERENCE = "allowed-difference"
PARITY_INFORMATIONAL = "informational"

# Source-content tables whose row counts must be preserved across migration (present at every supported
# origin >= V121). A migration must never drop or fabricate their rows.
_DATA_PRESERVED_TABLES: tuple[str, ...] = (
    "source_index_entities",
    "source_index_locators",
    "source_index_move_signals",
    "source_intelligence_sources",
    "source_intelligence_metadata",
    "source_intelligence_text",
    "source_intelligence_chunks",
    "source_intelligence_relationships",
    "source_intelligence_generated_notes",
    "source_intelligence_summaries",
    "source_index_bootstrap_runs",
)


@dataclass
class ParityDiff:
    field: str
    classification: str
    before: object
    after: object
    ok: bool
    detail: str = ""


@dataclass
class ParityResult:
    ok: bool
    diffs: list[ParityDiff]

    def failures(self) -> list[ParityDiff]:
        return [d for d in self.diffs if not d.ok]


def ledger_complete(report: InventoryReport) -> tuple[bool, str]:
    """PC-AC-015: ``schema_migrations`` holds every version 1..head exactly once, no gaps/duplicates."""
    versions = report.schema_versions
    if not versions or report.schema_head is None:
        return False, "no schema versions present"
    expected = list(range(1, report.schema_head + 1))
    if versions == expected:
        return True, ""
    counts = Counter(versions)
    dups = sorted(v for v, n in counts.items() if n > 1)
    missing = [v for v in expected if v not in counts]
    return False, f"gaps={missing} duplicates={dups}"


def compare_migration_parity(before: InventoryReport, after: InventoryReport) -> ParityResult:
    """Classify origin(``before``) -> migrated-head(``after``) differences per the spec §5 model.

    - schema head is **monotonic** (must not regress);
    - each source-content table present at the origin keeps an **exact** row count (no data lost or
      fabricated);
    - root count and cross-root duplicate relpaths are **exact** (root-scoped identity preserved);
    - generation / quarantine / lineage counts are **exact** when the origin already carried them;
    - no dangling/orphan FTS linkage is introduced (**exact** zero);
    - file size is **informational**.
    """
    diffs: list[ParityDiff] = [
        ParityDiff(
            "schema_head",
            PARITY_MONOTONIC,
            before.schema_head,
            after.schema_head,
            ok=(
                before.schema_head is not None
                and after.schema_head is not None
                and after.schema_head >= before.schema_head
            ),
        )
    ]
    for table in _DATA_PRESERVED_TABLES:
        origin_count = before.row_counts.get(table)
        if origin_count is None:
            continue  # table absent at this origin -> not a preservation target
        head_count = after.row_counts.get(table)
        diffs.append(
            ParityDiff(
                f"row_count[{table}]", PARITY_EXACT, origin_count, head_count,
                ok=(head_count == origin_count),
            )
        )
    diffs.append(
        ParityDiff(
            "root_count", PARITY_EXACT, before.root_count, after.root_count,
            ok=(after.root_count == before.root_count),
        )
    )
    diffs.append(
        ParityDiff(
            "duplicate_relpath_across_roots", PARITY_EXACT,
            before.duplicate_relpath_across_roots, after.duplicate_relpath_across_roots,
            ok=(after.duplicate_relpath_across_roots == before.duplicate_relpath_across_roots),
        )
    )
    # Always compared, never truthiness-gated: a zero/absent origin state that gains fabricated rows
    # during migration must fail (PC-WI01-EXT-REV-F-004).
    diffs.append(
        ParityDiff(
            "generation_counts_by_status", PARITY_EXACT,
            before.generation_counts_by_status, after.generation_counts_by_status,
            ok=(after.generation_counts_by_status == before.generation_counts_by_status),
        )
    )
    diffs.append(
        ParityDiff(
            "quarantine_unresolved_count", PARITY_EXACT,
            before.quarantine_unresolved_count, after.quarantine_unresolved_count,
            ok=(after.quarantine_unresolved_count == before.quarantine_unresolved_count),
        )
    )
    diffs.append(
        ParityDiff(
            "lineage_count", PARITY_EXACT, before.lineage_count, after.lineage_count,
            ok=(after.lineage_count == before.lineage_count),
        )
    )
    diffs.append(
        ParityDiff(
            "fts_parity.dangling", PARITY_EXACT, before.fts_parity.dangling,
            after.fts_parity.dangling, ok=(after.fts_parity.dangling == 0),
        )
    )
    diffs.append(
        ParityDiff(
            "fts_parity.orphan", PARITY_EXACT, before.fts_parity.orphan,
            after.fts_parity.orphan, ok=(after.fts_parity.orphan == 0),
        )
    )
    diffs.append(
        ParityDiff(
            "file_size_bytes", PARITY_INFORMATIONAL, before.file_size_bytes,
            after.file_size_bytes, ok=True,
        )
    )
    return ParityResult(ok=all(d.ok for d in diffs), diffs=diffs)


def _scoped_indexes(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    """Index details, restricted to indexes defined ON a source-index structural table.

    ``index_structure`` returns *every* index in the database; for source-index parity we compare only
    indexes attached to the source-index / FTS tables (``sqlite_master.tbl_name``), so unrelated domains
    (e.g. schedule) cannot mask a real source-index difference or manufacture a false one.
    """
    scoped_tables = set(_STRUCTURAL_TABLES)
    result: dict[str, dict[str, object]] = {}
    for name in _objects(conn, "index"):
        owner = conn.execute(
            "SELECT tbl_name FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
        ).fetchone()
        if owner is None or owner["tbl_name"] not in scoped_tables:
            continue
        sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
        ).fetchone()
        sql = _normalize_sql(sql_row["sql"] if sql_row else None)
        cols = [r["name"] for r in conn.execute(f"PRAGMA index_info({name})").fetchall()]
        result[name] = {
            "unique": "UNIQUE" in sql.upper(),
            "partial": " WHERE " in f" {sql.upper()} ",
            "columns": cols,
            "sql": sql,
        }
    return result


def source_index_structural_signature(conn: sqlite3.Connection) -> dict[str, object]:
    """Source-index-scoped structural signature (tables/indexes/triggers on source-index tables only).

    Like ``structural_signature`` but restricted to the source-index + FTS tables and the indexes and
    triggers attached to them, so the Phase C migration/parity comparison is not polluted by other
    domains' schema. Views are omitted (the source-index schema defines none).
    """
    scoped_tables = set(_STRUCTURAL_TABLES)
    tables = {t: table_structure(conn, t) for t in _STRUCTURAL_TABLES if _table_exists(conn, t)}
    triggers = {
        r["name"]: _normalize_sql(r["sql"])
        for r in conn.execute(
            "SELECT name, sql, tbl_name FROM sqlite_master WHERE type = 'trigger' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        if r["tbl_name"] in scoped_tables
    }
    # Views: source-index-named only (PC-AC-017 requires view parity; the source-index schema
    # currently defines none, so this is normally the empty set — asserted explicitly, not omitted).
    views = {
        r["name"]: _normalize_sql(r["sql"])
        for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'view' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        if str(r["name"]).startswith(_SOURCE_INDEX_OBJECT_PREFIXES)
    }
    return {"tables": tables, "indexes": _scoped_indexes(conn), "triggers": triggers, "views": views}


def source_index_structure(db_path: Path) -> dict[str, object]:
    """Read-only, fail-closed source-index-scoped structural signature at ``db_path``."""
    conn = _open_readonly(Path(db_path))
    try:
        return source_index_structural_signature(conn)
    finally:
        conn.close()


def source_index_logical_hash(db_path: Path) -> str:
    """Source-index-scoped logical hash: source-index row content + scoped structure + FTS parity/content.

    A source-index-only analogue of ``logical_inventory_hash`` (whose structural component is
    database-wide). Two databases with identical source-index logical + source-index structural + FTS
    state hash identically, regardless of unrelated domains' schema. Used to assert source-index
    idempotency (PC-AC-016) without coupling to other domains.
    """
    conn = _open_readonly(Path(db_path))
    try:
        table_rows: dict[str, list[str]] = {}
        for table in _SCOPED_HASH_TABLES:
            if not _table_exists(conn, table):
                continue
            volatile = _VOLATILE_HASH_COLUMNS | _SCOPED_VOLATILE_BY_TABLE.get(table, frozenset())
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            table_rows[table] = sorted(
                json.dumps(
                    {k: v for k, v in dict(row).items() if k not in volatile},
                    sort_keys=True,
                    default=str,
                )
                for row in rows
            )
        parity = fts_parity(conn)
        material: dict[str, object] = {
            "rows": table_rows,
            "structure": source_index_structural_signature(conn),
            "fts_parity": {"matched": parity.matched, "dangling": parity.dangling, "orphan": parity.orphan},
            "fts_content": fts_content_digests(conn),
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    finally:
        conn.close()


def compare_source_index_structure(migrated_db: Path, reference_db: Path) -> ParityResult:
    """PC-AC-017: a migrated database's *source-index* structure must equal a fresh head database's.

    Compares the source-index-scoped structural signature (tables/columns/FKs/DDL, indexes and triggers
    on source-index tables). After migration to head, source-index structure is canonical regardless of
    origin — any difference is a failure.
    """
    migrated_sig = source_index_structure(migrated_db)
    reference_sig = source_index_structure(reference_db)
    diffs: list[ParityDiff] = []
    for key in ("tables", "indexes", "triggers", "views"):
        equal = migrated_sig.get(key) == reference_sig.get(key)
        diffs.append(
            ParityDiff(
                f"structure[{key}]", PARITY_EXACT, "reference-head", "migrated",
                ok=equal,
                detail="" if equal else _describe_key_diff(reference_sig.get(key), migrated_sig.get(key)),
            )
        )
    return ParityResult(ok=all(d.ok for d in diffs), diffs=diffs)


def _describe_key_diff(reference: object, migrated: object) -> str:
    """Compact description of the first differing sub-key (redacted; object names only)."""
    if isinstance(reference, dict) and isinstance(migrated, dict):
        only_ref = sorted(set(reference) - set(migrated))
        only_mig = sorted(set(migrated) - set(reference))
        changed = sorted(k for k in set(reference) & set(migrated) if reference[k] != migrated[k])
        return f"only_in_reference={only_ref} only_in_migrated={only_mig} changed={changed}"
    return "values differ"


def query_plan(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> list[str]:
    """Capture ``EXPLAIN QUERY PLAN`` detail lines for a query, read-only and fail-closed (PC-AC-026)."""
    conn = _open_readonly(Path(db_path))
    try:
        rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
        return [str(row["detail"]) for row in rows]
    finally:
        conn.close()


def plan_uses_index(plan: list[str], index_name: str | None = None) -> bool:
    """True if the plan uses an index (optionally a specific named index) rather than scanning."""
    joined = " ".join(plan).upper()
    if index_name is not None:
        needle = index_name.upper()
        return f"USING INDEX {needle}" in joined or f"USING COVERING INDEX {needle}" in joined
    return ("USING INDEX" in joined) or ("USING COVERING INDEX" in joined)


def plan_has_unindexed_scan(plan: list[str]) -> bool:
    """True if the plan contains a full-table SCAN not backed by an index."""
    for line in plan:
        upper = line.upper()
        if (
            upper.startswith("SCAN")
            and "USING INDEX" not in upper
            and "USING COVERING INDEX" not in upper
        ):
            return True
    return False


# --- Semantic parity oracle (Phase C Stage 2, PC-WI-01 corrective R2) ---------------------------
#
# Aggregate counts cannot prove event/FTS/authority/lineage/link semantics (PC-AC-020..025). These
# helpers build a redacted, deterministic semantic inventory (per-row identity digests + derived
# validity facts) so an origin snapshot can be compared against its migrated-head snapshot with
# explicit, origin-aware equality (never truthiness-gated). Raw paths/content are hashed, never emitted.

# Generation statuses that count as an "active" generation (matches the partial-unique index
# ``idx_source_index_scan_generations_active`` predicate: one active generation per root).
_ACTIVE_GENERATION_STATUSES: frozenset[str] = frozenset({"running", "partial", "reconcile_pending"})

# Complete protected-data table set for the scoped idempotency hash: the schema ledger plus every
# inventoried source-index table (fixes the earlier omission of source_intelligence_state,
# source_index_bootstrap_state / _reconciliation_runs, source_structure_roots / _folders — PC-AC-016).
_SCOPED_HASH_TABLES: tuple[str, ...] = ("schema_migrations", *SOURCE_INDEX_TABLES)

# Per-table volatile columns excluded from the scoped hash: the migrator idempotently re-asserts the
# ``source_intelligence_state`` ``fts_available`` row with a fresh ``updated_at`` on every apply, so that
# timestamp is bookkeeping (like ``schema_migrations.applied_at``), not a protected-data change. The
# row's ``state_key``/``state_value`` remain hashed, so real content changes are still detected.
_SCOPED_VOLATILE_BY_TABLE: dict[str, frozenset[str]] = {
    "source_intelligence_state": frozenset({"updated_at"}),
}

# Name prefixes identifying source-index views/objects (PC-AC-017 view parity is scoped to these; the
# source-index schema currently defines no views, so the scoped view set is normally empty).
_SOURCE_INDEX_OBJECT_PREFIXES: tuple[str, ...] = (
    "source_intelligence", "source_index", "source_structure", "obsidian_note",
)

# Per-table semantic identity columns (folded into a per-row digest). Timestamps and V127-added
# nullable columns are excluded so a legacy origin's rows preserve their digest across migration
# (the migration-transformed columns don't perturb identity).
_SEMANTIC_IDENTITY_COLUMNS: dict[str, tuple[str, ...]] = {
    "source_intelligence_events": (
        "event_id", "source_id", "rel_path", "source_root_key", "event_type", "status",
        "error_code", "attempts",
    ),
    "source_intelligence_generated_notes": (
        "generated_note_id", "source_id", "note_rel_path", "generation_status",
    ),
    # generation_id is added at V122 (NULL for pre-V122 rows), so it is migration-transformed and
    # excluded from the cross-origin identity digest; run identity is (run_id, root_key, mode, phase, status).
    "source_index_bootstrap_runs": ("run_id", "root_key", "mode", "phase", "status"),
    "source_index_scan_quarantine": (
        "quarantine_id", "source_root_key", "generation_id", "source_id", "rel_path", "status",
        "resolution_state",
    ),
    "source_intelligence_relationships": (
        "relationship_id", "src_source_id", "dst_kind", "dst_ref", "relation",
    ),
}


@dataclass
class SemanticInventory:
    permanent_identity_digests: list[str]
    move_signal_digests: list[str]
    events_by_status: dict[str, int]
    events_by_type: dict[str, int]
    event_digests: list[str]
    card_digests: list[str]
    pass_run_digests: list[str]
    relationship_digests: list[str]
    quarantine_unresolved_count: int
    quarantine_digests: list[str]
    fts_present: int
    fts_missing: int
    fts_matched: int
    fts_dangling: int
    fts_orphan: int
    fts_content_digests: list[str]
    generation_authority_per_root: dict[str, list[str]]
    generation_roots_multi_active: int
    lineage_edges: list[str]
    lineage_all_predecessors_exist: bool
    lineage_acyclic: bool


def _count_where(conn: sqlite3.Connection, table: str, predicate: str) -> int:
    if not _table_exists(conn, table):
        return 0
    row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}").fetchone()
    return int(row[0]) if row else 0


def _redacted_row_digests(
    conn: sqlite3.Connection, table: str, columns: tuple[str, ...]
) -> list[str]:
    """Sorted per-row sha256 digests over identity columns present in ``table`` (raw values hashed)."""
    if not _table_exists(conn, table):
        return []
    present = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    cols = [c for c in columns if c in present]
    if not cols:
        return []
    col_sql = ", ".join(cols)
    digests: list[str] = []
    for row in conn.execute(f"SELECT {col_sql} FROM {table}").fetchall():
        payload = "\x1f".join([table, *["" if v is None else str(v) for v in row]])
        digests.append(hashlib.sha256(payload.encode("utf-8")).hexdigest())
    return sorted(digests)


def _entity_rekeyed_digests(
    conn: sqlite3.Connection,
    table: str,
    legacy_source_column: str,
    entity_source_column: str,
    other_columns: tuple[str, ...],
) -> list[str]:
    """Digest a source child by stable locator ``source_id`` across the V128 entity re-key.

    V128 replaces each child's mutable-key column with ``source_entity_id`` while retaining the
    historical source id in the current locator. Joining through that locator gives the same logical
    identity before and after migration without treating the randomly minted entity id as user data.
    """
    if not _table_exists(conn, table):
        return []
    if _column_exists(conn, table, legacy_source_column):
        columns = (other_columns[0], legacy_source_column, *other_columns[1:])
        return _redacted_row_digests(conn, table, columns)
    if not _column_exists(conn, table, entity_source_column):
        return []
    select_cols = [f"t.{other_columns[0]}", "l.source_id"]
    select_cols.extend(f"t.{column}" for column in other_columns[1:])
    rows = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM {table} t "
        f"JOIN source_index_locators l ON l.source_entity_id = t.{entity_source_column} "
        "AND l.is_current_locator = 1"
    ).fetchall()
    return sorted(
        hashlib.sha256(
            "\x1f".join([table, *["" if value is None else str(value) for value in row]]).encode(
                "utf-8"
            )
        ).hexdigest()
        for row in rows
    )


def _generation_authority(conn: sqlite3.Connection) -> tuple[dict[str, list[str]], int]:
    """Per-root generation-authority digests and the number of roots with >1 active generation."""
    if not _table_exists(conn, "source_index_scan_generations"):
        return {}, 0
    per_root: dict[str, list[str]] = {}
    active_counts: dict[str, int] = {}
    for row in conn.execute(
        "SELECT root_key, generation_id, status, active_run_id FROM source_index_scan_generations"
    ).fetchall():
        root = "" if row["root_key"] is None else str(row["root_key"])
        digest = hashlib.sha256(
            "\x1f".join(
                "" if row[k] is None else str(row[k])
                for k in ("generation_id", "status", "active_run_id")
            ).encode("utf-8")
        ).hexdigest()
        per_root.setdefault(root, []).append(digest)
        if str(row["status"]) in _ACTIVE_GENERATION_STATUSES:
            active_counts[root] = active_counts.get(root, 0) + 1
    return ({k: sorted(v) for k, v in per_root.items()}, sum(1 for n in active_counts.values() if n > 1))


def _lineage_facts(conn: sqlite3.Connection) -> tuple[list[str], bool, bool]:
    """Redacted lineage edge digests + (all predecessors exist, acyclic)."""
    if not _column_exists(conn, "source_intelligence_sources", "renamed_from_source_id"):
        return [], True, True
    edges: dict[str, str] = {}
    ids: set[str] = set()
    if _column_exists(conn, "source_intelligence_sources", "source_id"):
        rows = conn.execute(
            "SELECT source_id, renamed_from_source_id FROM source_intelligence_sources"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT l.source_id, s.renamed_from_source_id "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "AND l.is_current_locator = 1"
        ).fetchall()
    for row in rows:
        ids.add(str(row["source_id"]))
        if row["renamed_from_source_id"] is not None:
            edges[str(row["source_id"])] = str(row["renamed_from_source_id"])
    all_exist = all(pred in ids for pred in edges.values())
    acyclic = True
    for start in edges:
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None and cur in edges:
            if cur in seen:
                acyclic = False
                break
            seen.add(cur)
            cur = edges[cur]
    edge_digests = sorted(
        hashlib.sha256(f"{src}\x1f{dst}".encode("utf-8")).hexdigest() for src, dst in edges.items()
    )
    return edge_digests, all_exist, acyclic


def source_index_semantic_inventory(db_path: Path) -> SemanticInventory:
    """Redacted, serializable semantic inventory for migration parity (PC-AC-020..025), read-only.

    Holds per-row identity digests (raw paths/content hashed, never emitted) plus derived validity
    facts (generation authority, lineage validity/acyclicity) so an origin snapshot can be compared
    to its migrated-head snapshot for semantic preservation.
    """
    conn = _open_readonly(Path(db_path))
    try:
        by_status, by_type, _ = _events_breakdown(conn)
        parity = fts_parity(conn)
        gen_per_root, gen_multi_active = _generation_authority(conn)
        lineage_edges, predecessors_exist, acyclic = _lineage_facts(conn)
        return SemanticInventory(
            permanent_identity_digests=sorted(
                _redacted_row_digests(
                    conn,
                    "source_index_entities",
                    ("source_entity_id", "created_at", "status"),
                )
                + _redacted_row_digests(
                    conn,
                    "source_index_locators",
                    (
                        "locator_id",
                        "source_entity_id",
                        "source_id",
                        "source_root_key",
                        "rel_path",
                        "is_current_locator",
                        "tombstoned_at",
                        "generation_seq",
                    ),
                )
            ),
            move_signal_digests=_redacted_row_digests(
                conn,
                "source_index_move_signals",
                (
                    "move_signal_id",
                    "source_locator_id",
                    "source_root_key",
                    "source_rel_path",
                    "target_root_key",
                    "target_rel_path",
                    "detected_at",
                    "generation_id",
                    "applied_at",
                ),
            ),
            events_by_status=by_status,
            events_by_type=by_type,
            event_digests=_redacted_row_digests(
                conn, "source_intelligence_events",
                _SEMANTIC_IDENTITY_COLUMNS["source_intelligence_events"],
            ),
            card_digests=_entity_rekeyed_digests(
                conn,
                "source_intelligence_generated_notes",
                "source_id",
                "source_entity_id",
                ("generated_note_id", "note_rel_path", "generation_status"),
            ),
            pass_run_digests=_redacted_row_digests(
                conn, "source_index_bootstrap_runs",
                _SEMANTIC_IDENTITY_COLUMNS["source_index_bootstrap_runs"],
            ),
            relationship_digests=_entity_rekeyed_digests(
                conn,
                "source_intelligence_relationships",
                "src_source_id",
                "src_source_entity_id",
                ("relationship_id", "dst_kind", "dst_ref", "relation"),
            ),
            quarantine_unresolved_count=_count_where(
                conn, "source_index_scan_quarantine", "resolution_state = 'unresolved'"
            ),
            quarantine_digests=_redacted_row_digests(
                conn, "source_index_scan_quarantine",
                _SEMANTIC_IDENTITY_COLUMNS["source_index_scan_quarantine"],
            ),
            fts_present=_count_where(conn, "source_intelligence_metadata", "fts_rowid IS NOT NULL"),
            fts_missing=_count_where(conn, "source_intelligence_metadata", "fts_rowid IS NULL"),
            fts_matched=parity.matched,
            fts_dangling=parity.dangling,
            fts_orphan=parity.orphan,
            fts_content_digests=fts_content_digests(conn),
            generation_authority_per_root=gen_per_root,
            generation_roots_multi_active=gen_multi_active,
            lineage_edges=lineage_edges,
            lineage_all_predecessors_exist=predecessors_exist,
            lineage_acyclic=acyclic,
        )
    finally:
        conn.close()


def compare_semantic_inventories(
    before: SemanticInventory, after: SemanticInventory
) -> ParityResult:
    """Compare an origin semantic inventory to its migrated-head inventory (PC-AC-020..025).

    Identity digest sets are **exact** (rows/fields preserved); event type map is
    migration-transformed but rows are preserved; FTS present/missing/matched/content are exact and no
    dangling/orphan may be introduced; generation-authority-per-root and lineage edges are exact; and
    the migrated database must independently satisfy the validity invariants (single active generation
    per root, acyclic lineage, all lineage predecessors present).
    """
    identity_preexisting = bool(before.permanent_identity_digests)
    move_signals_preexisting = bool(before.move_signal_digests)
    diffs: list[ParityDiff] = [
        ParityDiff(
            "permanent_identity.identity_digests",
            PARITY_EXACT if identity_preexisting else PARITY_MIGRATION_TRANSFORMED,
            before.permanent_identity_digests,
            after.permanent_identity_digests,
            ok=(
                after.permanent_identity_digests == before.permanent_identity_digests
                if identity_preexisting
                else bool(after.permanent_identity_digests)
            ),
        ),
        ParityDiff(
            "move_signals.identity_digests",
            PARITY_EXACT if move_signals_preexisting else PARITY_MIGRATION_TRANSFORMED,
            before.move_signal_digests,
            after.move_signal_digests,
            ok=(
                after.move_signal_digests == before.move_signal_digests
                if move_signals_preexisting
                else True
            ),
        ),
        ParityDiff("events.identity_digests", PARITY_EXACT, before.event_digests, after.event_digests,
                   ok=(after.event_digests == before.event_digests)),
        ParityDiff("events.by_status", PARITY_EXACT, before.events_by_status, after.events_by_status,
                   ok=(after.events_by_status == before.events_by_status)),
        ParityDiff("events.by_type", PARITY_MIGRATION_TRANSFORMED, before.events_by_type,
                   after.events_by_type, ok=(after.events_by_type == before.events_by_type)),
        ParityDiff("cards.identity_digests", PARITY_EXACT, before.card_digests, after.card_digests,
                   ok=(after.card_digests == before.card_digests)),
        ParityDiff("pass_runs.identity_digests", PARITY_EXACT, before.pass_run_digests,
                   after.pass_run_digests, ok=(after.pass_run_digests == before.pass_run_digests)),
        ParityDiff("relationships.identity_digests", PARITY_EXACT, before.relationship_digests,
                   after.relationship_digests, ok=(after.relationship_digests == before.relationship_digests)),
        ParityDiff("quarantine.unresolved_count", PARITY_EXACT, before.quarantine_unresolved_count,
                   after.quarantine_unresolved_count,
                   ok=(after.quarantine_unresolved_count == before.quarantine_unresolved_count)),
        ParityDiff("quarantine.identity_digests", PARITY_EXACT, before.quarantine_digests,
                   after.quarantine_digests, ok=(after.quarantine_digests == before.quarantine_digests)),
        ParityDiff("fts.present", PARITY_EXACT, before.fts_present, after.fts_present,
                   ok=(after.fts_present == before.fts_present)),
        ParityDiff("fts.missing", PARITY_EXACT, before.fts_missing, after.fts_missing,
                   ok=(after.fts_missing == before.fts_missing)),
        ParityDiff("fts.matched", PARITY_EXACT, before.fts_matched, after.fts_matched,
                   ok=(after.fts_matched == before.fts_matched)),
        ParityDiff("fts.content_digests", PARITY_EXACT, before.fts_content_digests,
                   after.fts_content_digests, ok=(after.fts_content_digests == before.fts_content_digests)),
        ParityDiff("fts.dangling", PARITY_EXACT, before.fts_dangling, after.fts_dangling,
                   ok=(after.fts_dangling == 0)),
        ParityDiff("fts.orphan", PARITY_EXACT, before.fts_orphan, after.fts_orphan,
                   ok=(after.fts_orphan == 0)),
        ParityDiff("generation_authority.per_root", PARITY_EXACT,
                   before.generation_authority_per_root, after.generation_authority_per_root,
                   ok=(after.generation_authority_per_root == before.generation_authority_per_root)),
        ParityDiff("generation_authority.single_active_per_root", PARITY_EXACT, 0,
                   after.generation_roots_multi_active, ok=(after.generation_roots_multi_active == 0)),
        ParityDiff("lineage.edges", PARITY_EXACT, before.lineage_edges, after.lineage_edges,
                   ok=(after.lineage_edges == before.lineage_edges)),
        ParityDiff("lineage.acyclic", PARITY_EXACT, True, after.lineage_acyclic,
                   ok=after.lineage_acyclic),
        ParityDiff("lineage.all_predecessors_exist", PARITY_EXACT, True,
                   after.lineage_all_predecessors_exist, ok=after.lineage_all_predecessors_exist),
    ]
    return ParityResult(ok=all(d.ok for d in diffs), diffs=diffs)
