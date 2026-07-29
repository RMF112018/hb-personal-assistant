"""Sole reader/writer of the V93 source-intelligence tables + explicit FTS sync.

No triggers: every write path here keeps the regular FTS5 tables in sync by storing the
SQLite-assigned ``rowid`` back in ``source_intelligence_metadata.fts_rowid`` so reindex/delete
is a plain ``DELETE ... WHERE rowid=?``. Only bounded, already-redacted fields are ever indexed
into FTS (excerpt/rel_path/project_key/tags) — never a raw email body or Text-Vault content.

Background callers (indexer/watcher worker thread) pass no connection and each call owns+closes
its own connection (sqlite connections are per-thread). A caller may thread one borrowed
connection through a hot path via ``conn=``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction
from hb_assistant.store.source_intelligence_tables import fts5_available

from .source_connector_models import (
    SourceConnectorValidationError,
    classify_source_ref,
    encode_source_ref,
    sanitize_fts_query,
)
from .source_skip_codes import normalize_skip_code

# F-015 tri-state legacy-resolution outcomes over the DISTINCT locator resolver. UNIQUE carries the
# single resolved entity; NO_MATCH (0 rows) and AMBIGUOUS (>=2 rows) are kept DISTINCT so the bare-value
# dst_ref resolver can fail closed on ambiguity without conflating it with no-match.
_LEGACY_NO_MATCH = "NO_MATCH"
_LEGACY_UNIQUE = "UNIQUE"
_LEGACY_AMBIGUOUS = "AMBIGUOUS"


class LifecycleOracleError(RuntimeError):
    """Pre-commit permanent-identity lifecycle-oracle violation (PI-WI-03a). Raised inside a lifecycle
    transaction BEFORE commit so the enclosing ``transaction()`` rolls the whole write back — a LIVE
    entity must have exactly one current locator, a TOMBSTONED entity zero, and current-locator
    (per-entity + per-live-path) uniqueness must hold. Never swallowed; surfaces as a real error."""


class DualAuthorityGuardError(RuntimeError):
    """A dual-authority violation (PC-AC-ID-001): an attempt to write a source_index_entities row
    outside the sole ``_mint_entity`` choke-point, or a raw parent-address write bypassing the locator
    lifecycle. Fail-closed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_after(delay_seconds: float) -> str:
    """``_now()`` shifted forward by ``delay_seconds`` — SAME normalized UTC/ISO representation as every
    queue timestamp, so lexical SQLite ``next_attempt_at <= ?`` comparisons stay deterministic."""
    return (datetime.now(timezone.utc) + timedelta(seconds=max(0.0, delay_seconds))).isoformat()


def is_sqlite_busy(exc: BaseException) -> bool:
    """True iff ``exc`` is a SQLite BUSY/LOCKED contention (retryable), masking any *extended* result code
    (e.g. ``SQLITE_BUSY_SNAPSHOT``) to its primary code with ``& 0xFF``. Only busy/locked is retryable —
    every other ``OperationalError`` is a real error. Falls back to a narrow message match ONLY when no
    numeric ``sqlite_errorcode`` is available (older interpreters); never treats an arbitrary error as busy."""
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int):
        return (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        return "database is locked" in msg or "database table is locked" in msg
    return False


# Bounded-backoff config for retryable 'moved' drain deferrals (Phase B / B4 corrective) — named
# constants, never magic numbers embedded in the drain. A recoverable condition (stale/unready root,
# ambiguous mount, dest not yet visible, dest reindex pending) re-queues the SAME move event with a
# future next_attempt_at; after MOVED_MAX_ATTEMPTS claim cycles the caller applies a terminal disposition.
MOVED_MAX_ATTEMPTS = 6
MOVED_BACKOFF_BASE_S = 30
MOVED_BACKOFF_CAP_S = 1800


def _map_disposition(disposition: str | None, extraction_status: str | None) -> str:
    """Effective extraction disposition, mapping a legacy NULL from the extraction_status (V122).

    Mirrors the read-time mapping in ``content_status_counts`` so search rows report the same disposition
    (``content|metadata_only|unsupported|too_large``) as health, with no row-wide backfill required.
    """
    if disposition:
        return disposition
    return {
        "ok": "content",
        "failed": "content",
        "unsupported": "unsupported",
        "skipped_too_large": "too_large",
    }.get(extraction_status or "", "metadata_only")


def _derive_match(
    *, snip_text: str | None, snip_path: str | None, snip_aux: str | None, has_text: bool
) -> tuple[str, str]:
    """Derive ``(match_basis, snippet)`` from per-column FTS snippets.

    A column matched when its snippet carries a highlight ``[`` marker. ``match_basis`` is a ``+``-joined
    combo of ``path``/``content``/``project`` (defaulting to ``path`` when nothing highlighted). The chosen
    snippet prefers content, then a HIGHLIGHTED rel_path snippet for a path-only match (never an empty
    content snippet that would imply "no match"), then the project/aux snippet.
    """
    content_hit = has_text and "[" in (snip_text or "")
    path_hit = "[" in (snip_path or "")
    project_hit = "[" in (snip_aux or "")
    bases: list[str] = []
    if path_hit:
        bases.append("path")
    if content_hit:
        bases.append("content")
    if project_hit:
        bases.append("project")
    if not bases:
        bases = ["path"]
    if content_hit:
        snippet = snip_text or ""
    elif path_hit:
        snippet = snip_path or ""
    elif project_hit:
        snippet = snip_aux or ""
    else:
        snippet = snip_path or ""
    return "+".join(bases), snippet


def source_id_for(
    source_kind: str,
    *,
    source_root_key: str | None = None,
    rel_path: str | None = None,
    domain_ref_table: str | None = None,
    domain_ref_id: str | None = None,
) -> str:
    """Stable 32-hex identity for a source.

    For file sources the identity folds in ``source_root_key`` so the SAME relative path
    under different roots (Home/Work/NAS/…) never collides. A missing root is normalised to
    the empty string so the key format is stable. Domain-link identity is unchanged.
    The V99 migration recomputes existing file ``source_id``s with this same scheme.
    """
    if rel_path is not None:
        root = source_root_key if source_root_key is not None else ""
        key = f"{source_kind}|file|{root}|{rel_path}"
    else:
        key = f"{source_kind}|link|{domain_ref_table}|{domain_ref_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


class SourceIndexRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- low-level -------------------------------------------------------------------------
    def _fts_available(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT state_value FROM source_intelligence_state WHERE state_key='fts_available'"
        ).fetchone()
        if row is not None:
            return row[0] == "1"
        return fts5_available(conn)

    def _set_state(self, c: sqlite3.Connection, key: str, value: str) -> None:
        """Upsert a singleton k/v row in the existing transaction (no schema change)."""
        c.execute(
            "INSERT INTO source_intelligence_state (state_key, state_value, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value, updated_at=excluded.updated_at",
            (key, value, _now()),
        )

    # ----- permanent-identity lifecycle primitives (PI-WI-03a; ADR-001 R5 / ADR-003 R8 §5) -------
    # Post-V128 the 7 content tables key on ``source_entity_id`` (a durable 32-hex identity); the
    # CURRENT locator (``source_index_locators`` WHERE ``is_current_locator=1``) is the single authority
    # for a source's current ``source_id``/``source_root_key``/``rel_path``. The internal repository
    # handle IS the ``source_entity_id``; the locator carries the legacy deterministic ``source_id`` so a
    # persisted legacy ref resolves via the fail-closed DISTINCT resolver (PC-AC-ID-005).
    def _mint_entity(self, c: sqlite3.Connection, *, created_at: str | None = None) -> str:
        """P1 — the SOLE ``INSERT INTO source_index_entities`` choke-point (PC-AC-ID-001). Mints one LIVE
        entity and returns its durable id. NEVER writes a locator/observation column."""
        eid = uuid.uuid4().hex
        c.execute(
            "INSERT INTO source_index_entities (source_entity_id, created_at, status) VALUES (?,?,'LIVE')",
            (eid, created_at or _now()),
        )
        return eid

    def _insert_current_locator(
        self,
        c: sqlite3.Connection,
        *,
        entity_id: str,
        source_id: str,
        source_root_key: str | None,
        rel_path: str | None,
    ) -> None:
        """P1/P3 — insert a fresh CURRENT locator for an entity. A pure-CA mint: it OMITS the three F-005
        observation columns (``last_seen_generation``/``last_seen_at``/``last_indexed_fingerprint``) and
        the serving-trust column, which are stamped only by a distinct OW/observation write."""
        c.execute(
            "INSERT INTO source_index_locators "
            "(locator_id, source_entity_id, source_id, source_root_key, rel_path, "
            " is_current_locator, tombstoned_at, generation_seq) VALUES (?,?,?,?,?,1,NULL,0)",
            (uuid.uuid4().hex, entity_id, source_id, source_root_key, rel_path),
        )

    def _demote_current_locator(
        self, c: sqlite3.Connection, entity_id: str, *, tombstone: bool
    ) -> None:
        """Demote the entity's current locator (P2 tombstone stamps ``tombstoned_at``)."""
        if tombstone:
            c.execute(
                "UPDATE source_index_locators SET is_current_locator=0, tombstoned_at=? "
                "WHERE source_entity_id=? AND is_current_locator=1",
                (_now(), entity_id),
            )
        else:
            c.execute(
                "UPDATE source_index_locators SET is_current_locator=0 "
                "WHERE source_entity_id=? AND is_current_locator=1",
                (entity_id,),
            )

    def _tombstone_entity(self, c: sqlite3.Connection, entity_id: str) -> None:
        """P2 — mark an entity TOMBSTONED (terminal) and demote its current locator. Idempotent by
        TOMBSTONED-terminal: re-tombstoning a TOMBSTONED entity is a no-op."""
        c.execute(
            "UPDATE source_index_entities SET status='TOMBSTONED' WHERE source_entity_id=?",
            (entity_id,),
        )
        self._demote_current_locator(c, entity_id, tombstone=True)

    def _locator_for_path(
        self,
        c: sqlite3.Connection,
        source_kind: str,
        rel_path: str,
        source_root_key: str | None = None,
    ) -> tuple[str, str, str | None, str | None] | None:
        """Resolve the CURRENT locator for a ``(kind, rel_path[, root])`` → ``(entity_id, source_id,
        source_root_key, rel_path)`` or None. Binds the current locator (``is_current_locator=1``) joined
        to its LIVE parent — the CA current-address resolution."""
        sql = (
            "SELECT s.source_entity_id, l.source_id, l.source_root_key, l.rel_path "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
            "WHERE s.source_kind=? AND l.rel_path=?"
        )
        params: list[Any] = [source_kind, rel_path]
        if source_root_key is not None:
            sql += " AND l.source_root_key=?"
            params.append(source_root_key)
        return c.execute(sql, tuple(params)).fetchone()

    def _resolve_entity_by_source_id(
        self, c: sqlite3.Connection, source_id: str
    ) -> tuple[str, str | None]:
        """PC-AC-ID-005 on an OPEN connection — DISTINCT legacy resolver, TRI-STATE (F-015). Returns
        ``(state, entity_id)`` where ``state`` ∈ {``NO_MATCH``, ``UNIQUE``, ``AMBIGUOUS``}: exactly-1
        DISTINCT source_entity_id → ``(UNIQUE, that entity)`` (LIVE or TOMBSTONED); 0 rows →
        ``(NO_MATCH, None)``; >=2 → ``(AMBIGUOUS, None)`` (UNRESOLVED). The single query is unchanged; the
        extra state lets the bare-value ``dst_ref`` resolver distinguish no-match from ambiguous (which the
        prior optional return conflated). NEVER disambiguates by ``is_current_locator`` / ``generation_seq``
        (that was the stale-handle rebinding bug). Callers that only need the optional entity read the
        second element (``None`` unless UNIQUE)."""
        rows = c.execute(
            "SELECT DISTINCT source_entity_id FROM source_index_locators WHERE source_id=?",
            (source_id,),
        ).fetchall()
        if not rows:
            return (_LEGACY_NO_MATCH, None)
        if len(rows) == 1:
            return (_LEGACY_UNIQUE, rows[0][0])
        return (_LEGACY_AMBIGUOUS, None)

    def resolve_entity(
        self,
        *,
        source_id: str | None = None,
        source_ref: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str | None:
        """Fail-closed DB-aware resolver wired at the connector call-sites. Decodes/classifies via the
        DB-free v2 codec, then resolves to a ``source_entity_id`` or None (UNRESOLVED):

        * v2 entity ref → the entity iff it exists (LIVE or TOMBSTONED); else None.
        * v1 ref / bare-32-hex legacy handle → the DISTINCT legacy resolver (PC-AC-ID-005).

        A bare 32-hex that happens to equal a current entity id resolving to UNRESOLVED is the correct
        posture (no bare/v1 entity fallback)."""
        kind, value = classify_source_ref(source_id=source_id, source_ref=source_ref)
        with borrow_connection(conn, self.db_path) as c:
            if kind == "entity":
                row = c.execute(
                    "SELECT source_entity_id FROM source_index_entities WHERE source_entity_id=?",
                    (value,),
                ).fetchone()
                return row[0] if row else None
            # bare/v1 legacy handle → DISTINCT resolver; only a UNIQUE match resolves (0 and >=2 → None).
            return self._resolve_entity_by_source_id(c, value)[1]

    def _assert_lifecycle_oracle(
        self, c: sqlite3.Connection, entity_id: str | None = None
    ) -> None:
        """Pre-commit lifecycle oracle (run as the LAST statement inside a lifecycle transaction; a
        violation raises → the enclosing ``transaction()`` ROLLS BACK). Invariants: every LIVE entity has
        exactly one current locator; every TOMBSTONED entity zero; current-locator uniqueness per entity
        AND per live path. The V128 partial-unique indexes (``idx_locators_current_per_entity`` /
        ``idx_locators_active_path``) DB-enforce the last two; F-004 realizes them here as EXPLICIT rechecks
        (``duplicate_current_locator_per_entity`` / ``duplicate_current_locator_per_live_path``) for
        defence-in-depth — so a duplicate-current that slips past the schema (a dropped/altered index, a raw
        bypassing write) still fails closed in-transaction → ROLLBACK. ``entity_id`` scopes the check to a
        single entity (hot-path cost O(1)); None runs the full-scan invariant (bounded-batch / test use)."""
        scope = "" if entity_id is None else " AND e.source_entity_id = :eid"
        scope_l = "" if entity_id is None else " AND l.source_entity_id = :eid"
        # Per-live-path scope: when checking one entity, restrict the path-uniqueness recheck to the
        # (root, rel_path) addresses that entity currently occupies, so a collision with ANY other current
        # locator (same OR a different entity) at one of those paths is still caught on the hot path.
        path_scope = "" if entity_id is None else (
            " AND (l.source_root_key, l.rel_path) IN (SELECT source_root_key, rel_path "
            "FROM source_index_locators WHERE is_current_locator=1 AND rel_path IS NOT NULL "
            "AND source_entity_id = :eid)"
        )
        params = {} if entity_id is None else {"eid": entity_id}
        bad_live = c.execute(
            "SELECT COUNT(*) FROM source_index_entities e WHERE e.status='LIVE' AND "
            "(SELECT COUNT(*) FROM source_index_locators l "
            " WHERE l.source_entity_id=e.source_entity_id AND l.is_current_locator=1) != 1" + scope,
            params,
        ).fetchone()[0]
        if bad_live:
            raise LifecycleOracleError("live_entity_not_single_current_locator")
        bad_tomb = c.execute(
            "SELECT COUNT(*) FROM source_index_entities e WHERE e.status='TOMBSTONED' AND "
            "(SELECT COUNT(*) FROM source_index_locators l "
            " WHERE l.source_entity_id=e.source_entity_id AND l.is_current_locator=1) != 0" + scope,
            params,
        ).fetchone()[0]
        if bad_tomb:
            raise LifecycleOracleError("tombstoned_entity_has_current_locator")
        # F-004 — EXPLICIT per-entity current-locator uniqueness (>1 current locator for one entity).
        dup_entity = c.execute(
            "SELECT COUNT(*) FROM (SELECT l.source_entity_id FROM source_index_locators l "
            "WHERE l.is_current_locator=1" + scope_l
            + " GROUP BY l.source_entity_id HAVING COUNT(*) > 1)",
            params,
        ).fetchone()[0]
        if dup_entity:
            raise LifecycleOracleError("duplicate_current_locator_per_entity")
        # F-004 — EXPLICIT per-live-path current-locator uniqueness (one live address ⇒ one current
        # locator). Mirrors idx_locators_active_path (is_current_locator=1 AND tombstoned_at IS NULL).
        dup_path = c.execute(
            "SELECT COUNT(*) FROM (SELECT l.source_root_key, l.rel_path FROM source_index_locators l "
            "WHERE l.is_current_locator=1 AND l.tombstoned_at IS NULL AND l.rel_path IS NOT NULL"
            + path_scope
            + " GROUP BY l.source_root_key, l.rel_path HAVING COUNT(*) > 1)",
            params,
        ).fetchone()[0]
        if dup_path:
            raise LifecycleOracleError("duplicate_current_locator_per_live_path")

    def record_drain(self, *, conn: sqlite3.Connection | None = None) -> None:
        """Stamp the last successful queue-drain time (operator queue-health signal)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._set_state(c, "last_drain_at", _now())

    def record_generation_result(
        self, *, cards: int, summaries: int, conn: sqlite3.Connection | None = None
    ) -> None:
        """Record the last auto-generation drain result (operator telemetry; no schema change)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._set_state(c, "last_generation_at", _now())
            self._set_state(c, "last_generation_cards", str(int(cards)))
            self._set_state(c, "last_generation_summaries", str(int(summaries)))

    def generated_note_counts(self, *, conn: sqlite3.Connection | None = None) -> dict[str, int]:
        """Counts of generated source cards by status (operator telemetry)."""
        with borrow_connection(conn, self.db_path) as c:
            generated = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_generated_notes "
                "WHERE generation_status='generated'"
            ).fetchone()[0]
        return {"generated_card_count": int(generated)}

    # ----- source roots ----------------------------------------------------------------------
    def register_source_roots(
        self, roots: Iterable[dict[str, Any]], *, conn: sqlite3.Connection | None = None
    ) -> None:
        """Record configured roots in _state and deactivate sources of removed roots."""
        roots = list(roots)
        active_keys = {str(r.get("source_root_key")) for r in roots if r.get("enabled", True)}
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_state (state_key, state_value, updated_at) "
                "VALUES ('source_roots', ?, ?) "
                "ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value, updated_at=excluded.updated_at",
                (json.dumps(sorted(active_keys)), _now()),
            )
            # Deactivate file sources whose root is no longer configured/enabled. W-2 membership is
            # evaluated against the CURRENT locator's source_root_key (not the parent's last-known), and
            # deactivation realizes as a P2 tombstone of each affected entity (ADR-003 R8 §5.1/§5.4).
            known = {
                row[0]
                for row in c.execute(
                    "SELECT DISTINCT l.source_root_key FROM source_index_locators l "
                    "WHERE l.is_current_locator=1 AND l.source_root_key IS NOT NULL"
                ).fetchall()
            }
            for stale_key in known - active_keys:
                stale_entities = [
                    r[0]
                    for r in c.execute(
                        "SELECT s.source_entity_id FROM source_intelligence_sources s "
                        "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                        "  AND l.is_current_locator = 1 "
                        "WHERE l.source_root_key=? AND s.deleted=0",
                        (stale_key,),
                    ).fetchall()
                ]
                for entity_id in stale_entities:
                    c.execute(
                        "UPDATE source_intelligence_sources SET active=0, updated_at=? "
                        "WHERE source_entity_id=?",
                        (_now(), entity_id),
                    )
                    self._tombstone_entity(c, entity_id)
            self._assert_lifecycle_oracle(c)

    # ----- idempotency lookups ---------------------------------------------------------------
    def lookup_by_path(
        self,
        source_kind: str,
        rel_path: str,
        *,
        source_root_key: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Existing row for a (kind, rel_path). Pass ``source_root_key`` to scope the lookup to a
        single root — required when the same rel_path may exist under multiple roots, so the
        change-detection sha/mtime and fts_rowid belong to the right root. Omitting it keeps the
        legacy root-blind match (safe only for single-root/single-vault callers)."""
        # CA: resolve (kind, rel_path[, root]) through the CURRENT locator (is_current_locator=1) to the
        # LIVE entity, then join metadata by entity. A tombstoned/deleted path has no current locator, so a
        # reappearance is a fresh P1 (direction-A) — the returned handle is the durable source_entity_id.
        sql = (
            "SELECT s.source_entity_id, m.content_sha256, m.mtime_ns, m.fts_rowid, s.deleted, m.size_bytes "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 "
            "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
            "WHERE s.source_kind=? AND l.rel_path=?"
        )
        params: list[Any] = [source_kind, rel_path]
        if source_root_key is not None:
            sql += " AND l.source_root_key=?"
            params.append(source_root_key)
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(sql, tuple(params)).fetchone()
        if row is None:
            return None
        return {
            "source_id": row[0],
            "content_sha256": row[1],
            "mtime_ns": row[2],
            "fts_rowid": row[3],
            "deleted": bool(row[4]),
            "size_bytes": row[5],
        }

    def active_rel_paths(
        self, source_root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> set[str]:
        with borrow_connection(conn, self.db_path) as c:
            return {
                row[0]
                for row in c.execute(
                    "SELECT l.rel_path FROM source_intelligence_sources s "
                    "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                    "  AND l.is_current_locator = 1 "
                    "WHERE l.source_root_key=? AND l.rel_path IS NOT NULL AND s.deleted=0",
                    (source_root_key,),
                ).fetchall()
            }

    def active_index_state(
        self, source_root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, tuple[int | None, int | None]]:
        """Preloaded change-detection state for all active files under a root:
        ``rel_path -> (mtime_ns, size_bytes)``.

        One query so a bounded/resumable rescan can mtime+size fast-skip unchanged files without a
        per-file DB lookup or a re-hash (the hot path for a 400k-file root). Deleted rows excluded.
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT l.rel_path, m.mtime_ns, m.size_bytes "
                "FROM source_intelligence_sources s "
                "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
                "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "WHERE s.source_kind='external_file' AND l.source_root_key=? "
                "AND l.rel_path IS NOT NULL AND s.deleted=0",
                (source_root_key,),
            ).fetchall()
        return {row[0]: (row[1], row[2]) for row in rows}

    def content_status_counts(
        self, source_root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, int]:
        """Index-scoped per-root extraction breakdown for health (no full-table scan).

        Filters by ``source_root_key`` via ``idx_si_sources_root`` and PK-joins metadata/text, so the
        cost is bounded by the root's own active-file count — not the whole table. ``content_searchable``
        requires NONEMPTY searchable text (an FTS/text row alone is not enough), so sensitive content
        (extracted-to-vault, ``text_excerpt`` NULL) counts as ``content_extracted`` but NOT searchable.
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                # CA: joins bind the entity; root scope + address come from the CURRENT locator. The
                # serving-trust gate (R8 §6.3) rides the locator's policy_validation_state (NULL ≡
                # validated, 'policy_stale' ≡ content unverified) with COUNT-EXCLUSIVITY: a policy-stale
                # locator is bucketed as policy_unverified and NEVER counts as content_searchable /
                # content_extracted. Disposition mapped read-time (no row-wide backfill).
                "SELECT COALESCE(m.extraction_disposition, CASE m.extraction_status "
                "   WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' "
                "   WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' "
                "   ELSE 'metadata_only' END) AS disp, "
                " m.extraction_status AS st, "
                " CASE WHEN l.policy_validation_state IS NULL THEN 0 ELSE 1 END AS policy_stale, "
                " SUM(CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 "
                "          THEN 1 ELSE 0 END) AS searchable, "
                " SUM(CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END) AS has_fts, "
                " COUNT(*) AS n "
                "FROM source_intelligence_sources s "
                "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 "
                "JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id "
                "WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 "
                "GROUP BY disp, st, policy_stale",
                (source_root_key,),
            ).fetchall()

        # Positional access (disp=0, st=1, policy_stale=2, searchable=3, has_fts=4, n=5).
        def _sum(pred: Any) -> int:
            return sum(int(r[5]) for r in rows if pred(r))

        def _valid(r: Any) -> bool:
            return int(r[2]) == 0  # policy-validated locator (NULL policy_validation_state)

        total = sum(int(r[5]) for r in rows)
        # Count-exclusivity: content_searchable / content_extracted exclude policy-stale locators.
        searchable = sum(int(r[3] or 0) for r in rows if _valid(r))
        metadata_searchable = sum(int(r[4] or 0) for r in rows)
        content_extracted = _sum(lambda r: r[1] == "ok" and _valid(r))
        content_eligible = _sum(lambda r: r[0] == "content")
        content_pending = _sum(lambda r: r[0] == "content" and r[1] == "pending")
        intentional_metadata_only = _sum(lambda r: r[0] == "metadata_only")
        policy_unverified = _sum(lambda r: not _valid(r))
        return {
            "metadata_indexed": total,
            "metadata_searchable": metadata_searchable,
            "content_extracted": content_extracted,
            "content_searchable": searchable,
            "content_eligible": content_eligible,
            "content_pending": content_pending,
            "intentional_metadata_only": intentional_metadata_only,
            # Back-compat key (was extraction_status='pending'); now the explicit metadata-only count.
            "metadata_only": intentional_metadata_only,
            # Serving-trust DEGRADE bucket (R8 §6.3): locators whose content is policy-unverified.
            "policy_unverified": policy_unverified,
            "failed": _sum(lambda r: r[1] == "failed"),
            "unsupported": _sum(lambda r: r[0] == "unsupported"),
            "too_large": _sum(lambda r: r[0] == "too_large"),
        }

    def list_root_file_sources(
        self, source_root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Active external_file sources under a root: (source_id, rel_path, project_number).

        Used by conservative, same-root referenced-sheet matching (never global cross-root).
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT s.source_entity_id, l.rel_path, s.project_number "
                "FROM source_intelligence_sources s "
                "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 "
                "WHERE s.source_kind='external_file' AND l.source_root_key=? AND l.rel_path IS NOT NULL "
                "AND s.deleted=0",
                (source_root_key,),
            ).fetchall()
        return [{"source_id": r[0], "rel_path": r[1], "project_number": r[2]} for r in rows]

    def _resolve_dst_ref_entity(self, c: sqlite3.Connection, dst_ref: str) -> str | None:
        """Fail-closed resolution of a relationship ``dst_ref`` (a 'source' target) to a
        ``source_entity_id`` (R11 §2a/§2b; F-002 R3B). Shared by the READ path (``list_relationships``)
        and the go-forward WRITE (``_dst_ref_for_write``, which passes a BARE entity id).

        * A PREFIXED ``hbsrc1_``/``hbsrc2_`` ref is classified via the codec (malformed → ``None``): a v2
          (``hbsrc2_``) entity ref resolves in the ENTITY domain; a v1 (``hbsrc1_``) decoded legacy ref via
          the DISTINCT resolver (0 and >=2 → ``None``; there is no entity competitor for a prefixed legacy
          ref, so the tri-state UNIQUE check is the exact fail-closed criterion).
        * A BARE value is FIRST canonically validated (F-023) via ``classify_source_ref(source_id=...)`` —
          a malformed length / non-canonical char / unknown ``hbsrc``-style prefix (e.g. ``hbsrc3_``) fails
          closed to ``None`` BEFORE any lookup; the returned classification establishes NO precedence. The
          validated value is then resolved INDEPENDENTLY in the entity domain and the legacy domain
          (tri-state) with the exact 7-outcome contract: legacy ``AMBIGUOUS`` → ``None`` regardless of the
          entity; entity none + ``NO_MATCH`` → ``None``; entity unique + ``NO_MATCH`` → the entity (the
          write-path compatibility case); entity none + ``UNIQUE`` → the legacy entity; both ``UNIQUE`` and
          equal → that entity; both ``UNIQUE`` and different → ``None`` (cross-domain collision). No
          precedence, no disjoint-domain assumption, and no path creates/rewrites/rebinds an entity."""
        ref = str(dst_ref or "")
        prefixed = ref.startswith("hbsrc1_") or ref.startswith("hbsrc2_")
        try:
            if prefixed:
                kind, value = classify_source_ref(source_ref=ref)
            else:
                kind, value = classify_source_ref(source_id=ref)  # F-023 canonical bare validation
        except SourceConnectorValidationError:
            return None
        # Single entity-domain lookup (the frozen dual-authority occurrence for this method).
        entity_row = c.execute(
            "SELECT source_entity_id FROM source_index_entities WHERE source_entity_id=?", (value,)
        ).fetchone()
        entity_id = entity_row[0] if entity_row is not None else None
        if prefixed and kind == "entity":
            return entity_id  # hbsrc2_ v2 entity ref → entity domain only
        state, legacy_id = self._resolve_entity_by_source_id(c, value)
        if prefixed:
            # hbsrc1_ decoded legacy ref → DISTINCT resolver only (0 and >=2 → None).
            return legacy_id if state == _LEGACY_UNIQUE else None
        # BARE — independent both-domain resolution, 7-outcome contract (no precedence).
        if state == _LEGACY_AMBIGUOUS:
            return None
        if state == _LEGACY_NO_MATCH:
            return entity_id
        if entity_id is None:
            return legacy_id
        return entity_id if entity_id == legacy_id else None

    def _dst_ref_for_write(
        self, c: sqlite3.Connection, dst_kind: str, dst_ref: Any
    ) -> str | None:
        """F-002 go-forward persistence: for a ``dst_kind=='source'`` relationship, resolve/validate the
        target as an ENTITY (via the fail-closed :meth:`_resolve_dst_ref_entity`) and return a **v2**
        entity ref (``encode_source_ref(entity_id)`` → ``hbsrc2_``). A non-'source' kind (e.g. ``project``)
        is returned unchanged. A 'source' target that cannot be validated as an entity returns ``None`` so
        the caller SKIPS the row — a source relationship is NEVER persisted with an unvalidated/bare/legacy
        ``dst_ref`` (invariant: every newly-written source relationship carries an ``hbsrc2_`` ``dst_ref``).
        Legacy + existing-bare-row compatibility stays in the READ resolver only (``list_relationships``)."""
        if dst_kind != "source":
            return dst_ref
        entity_id = self._resolve_dst_ref_entity(c, str(dst_ref or ""))
        if entity_id is None:
            return None
        return encode_source_ref(entity_id)

    def list_relationships(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Outgoing relationships for a source entity, with the target rel_path (from the target's CURRENT
        locator) resolved for 'source' kinds via the fail-closed resolver (R11 OCC-009)."""
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT r.dst_kind, r.dst_ref, r.relation, r.confidence, r.evidence_json "
                "FROM source_intelligence_relationships r "
                "WHERE r.src_source_entity_id=? ORDER BY r.created_at",
                (source_entity_id,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for dst_kind, dst_ref, relation, confidence, evidence_json in rows:
                dst_rel_path = None
                if dst_kind == "source" and dst_ref:
                    target = self._resolve_dst_ref_entity(c, dst_ref)
                    if target is not None:
                        loc = c.execute(
                            "SELECT rel_path FROM source_index_locators "
                            "WHERE source_entity_id=? AND is_current_locator=1",
                            (target,),
                        ).fetchone()
                        dst_rel_path = loc[0] if loc else None
                evidence = None
                if evidence_json:
                    with suppress(ValueError, TypeError):
                        evidence = json.loads(evidence_json)
                out.append(
                    {
                        "dst_kind": dst_kind,
                        "dst_ref": dst_ref,
                        "relation": relation,
                        "confidence": confidence,
                        "evidence": evidence,
                        "dst_rel_path": dst_rel_path,
                    }
                )
        return out

    def record_relationships(
        self,
        source_entity_id: str,
        relationships: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Upsert outgoing relationship rows for a source entity (UNIQUE guard dedupes). Additive."""
        if not relationships:
            return
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            for rel in relationships:
                # F-002: a 'source' target is persisted as a v2 entity ref (hbsrc2_); an unresolvable
                # source target is skipped (never a bare/legacy dst_ref). Non-'source' kinds unchanged.
                dst_ref = self._dst_ref_for_write(c, rel["dst_kind"], rel["dst_ref"])
                if dst_ref is None:
                    continue
                c.execute(
                    "INSERT INTO source_intelligence_relationships "
                    "(relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, "
                    " evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                    (
                        uuid.uuid4().hex,
                        source_entity_id,
                        rel["dst_kind"],
                        dst_ref,
                        rel["relation"],
                        rel.get("confidence"),
                        json.dumps(rel.get("evidence")) if rel.get("evidence") else None,
                        now,
                    ),
                )

    # ----- writes ----------------------------------------------------------------------------
    def upsert_source_file(
        self,
        record: dict[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
    ) -> str:
        """Write of one external file (sources+metadata+text+chunks+relationships+FTS).

        ``in_transaction=True`` (requires ``conn``) runs the write on the caller's already-open
        transaction WITHOUT opening/committing its own — so a whole metadata batch + its cursor
        checkpoint can commit atomically (V122). Standalone callers omit it and get the historical
        own-transaction behaviour. ``record["preserve_content"]`` performs a metadata/path-FTS REPAIR
        that leaves valid extracted content intact (see :meth:`_upsert_source_file_locked`)."""
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            return self._upsert_source_file_locked(conn, record)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            return self._upsert_source_file_locked(c, record)

    def _upsert_source_file_locked(self, c: sqlite3.Connection, record: dict[str, Any]) -> str:
        """Connection-scoped write body (NO transaction of its own — the caller owns the txn).

        Two content modes:

        * **replace** (default): a genuine change/transition — the excerpt/text/chunks/FTS are rewritten
          from ``record``; a metadata-only/unsupported/too-large/cleared write (no excerpt, no vault ref)
          INVALIDATES stale content (drops ``_text``/chunks) and the path-only FTS row keeps discoverability.
          Project relationships are REPLACED (obsolete ``belongs_to_project`` rows are cleared) so a
          reclassification never leaves an orphaned project edge.
        * **preserve** (``record["preserve_content"]``): the file is physically unchanged and its extracted
          CONTENT is still valid to keep, but the row's policy-DERIVED state may be stale (a fingerprint
          change, a legacy row, a project re-route with unchanged key/number, a root-path change). Preserve
          keeps the extracted text/chunks/digest but AUTHORITATIVELY rebuilds the derived state: it rebuilds
          the FTS row FROM the retained text (not an empty path-only row when content exists), refreshes
          ``abs_path_hash``/project fields/``belongs_to_project`` edges, and re-stamps disposition +
          fingerprint. It never moves ``updated_at`` (a pure "still present" observation must not read as a
          material change). Content is destroyed only in replace mode.
        """
        source_kind = record["source_kind"]
        rel_path = record["rel_path"]
        root = record.get("source_root_key")
        # Legacy deterministic handle — carried on the locator's ``source_id`` so a persisted legacy ref
        # still resolves via the DISTINCT resolver (PC-AC-ID-005).
        legacy_source_id = source_id_for(source_kind, source_root_key=root, rel_path=rel_path)
        now = _now()
        preserve = bool(record.get("preserve_content"))

        # CA address realization: resolve the CURRENT locator for this path → existing entity (update /
        # P3 reappearance), else mint a fresh P1 entity + current locator. A tombstoned path has no
        # current locator, so a reappearance mints a NEW entity (direction-A; TOMBSTONED terminal).
        loc = self._locator_for_path(c, source_kind, rel_path, source_root_key=root)
        if loc is not None:
            entity_id = loc[0]
        else:
            entity_id = self._mint_entity(c)
            self._insert_current_locator(
                c, entity_id=entity_id, source_id=legacy_source_id,
                source_root_key=root, rel_path=rel_path,
            )

        existing = c.execute(
            "SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_entity_id=?",
            (entity_id,),
        ).fetchone()
        old_fts_rowid = existing[0] if existing else None

        # OW (F-005 observation): last_seen_generation/last_seen_at/last_indexed_fingerprint live on the
        # CURRENT locator (V129), NOT the parent. A metadata observation stamps last_seen so
        # generation-based reconciliation can tell "seen this generation" from "gone"; a reprocess
        # re-stamps the policy fingerprint the row is now current under and, in the SAME write,
        # REVALIDATES serving-trust (policy_validation_state = NULL). COALESCE-preserve keeps a prior
        # value on a bare re-observe with no fingerprint context.
        gen = record.get("last_seen_generation")
        last_seen_at = now if gen is not None else None
        fingerprint = record.get("last_indexed_fingerprint")
        if gen is not None or fingerprint is not None:
            c.execute(
                "UPDATE source_index_locators SET "
                " last_seen_generation=COALESCE(?, last_seen_generation), "
                " last_seen_at=COALESCE(?, last_seen_at), "
                " last_indexed_fingerprint=COALESCE(?, last_indexed_fingerprint), "
                " policy_validation_state=CASE WHEN ? IS NOT NULL THEN NULL "
                "  ELSE policy_validation_state END "
                "WHERE source_entity_id=? AND is_current_locator=1",
                (gen, last_seen_at, fingerprint, fingerprint, entity_id),
            )

        # Parent row (entity-keyed; last-known root/rel_path — non-authoritative). Observation columns are
        # NOT parent columns post-V128. ``updated_at`` moves only on a material change (replace), never a
        # preserve REPAIR (which must not read as a change / re-stale notes).
        if preserve:
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_entity_id, source_kind, source_root_key, rel_path, abs_path_hash, "
                " project_key, project_number, active, deleted, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET "
                " source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, "
                " project_key=excluded.project_key, project_number=excluded.project_number, "
                " active=1, deleted=0",
                (
                    entity_id, source_kind, root, rel_path, record.get("abs_path_hash"),
                    record.get("project_key"), record.get("project_number"), now, now,
                ),
            )
        else:
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_entity_id, source_kind, source_root_key, rel_path, abs_path_hash, "
                " project_key, project_number, active, deleted, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET "
                " source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, "
                " project_key=excluded.project_key, project_number=excluded.project_number, "
                " active=1, deleted=0, updated_at=excluded.updated_at",
                (
                    entity_id, source_kind, root, rel_path, record.get("abs_path_hash"),
                    record.get("project_key"), record.get("project_number"), now, now,
                ),
            )

        aux = record.get("fts_aux") or record.get("project_key") or ""
        fts_table = (
            "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
        )
        if preserve:
            # AUTHORITATIVE derived-state rebuild that KEEPS content. Rebuild the FTS row FROM the retained
            # text so a content row stays body-searchable (a bare empty path-only row would break body search
            # while health still counts the retained text as content-searchable). Metadata-only rows (no
            # text) get an empty-excerpt path row. Extracted text/chunks/digest + extraction_status are left
            # intact (content is unchanged); only the DERIVED representation is refreshed.
            retained = c.execute(
                "SELECT text_excerpt FROM source_intelligence_text WHERE source_entity_id=?",
                (entity_id,),
            ).fetchone()
            retained_excerpt = retained[0] if retained and retained[0] else ""
            fts_rowid = old_fts_rowid
            if source_kind == "external_file" and self._fts_available(c):
                if old_fts_rowid is not None:
                    c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (old_fts_rowid,))
                cur = c.execute(
                    f"INSERT INTO {fts_table}(text_excerpt, rel_path, aux) VALUES (?,?,?)",
                    (retained_excerpt, rel_path, aux),
                )
                fts_rowid = cur.lastrowid
            c.execute(
                "INSERT INTO source_intelligence_metadata "
                "(source_entity_id, file_ext, size_bytes, mtime_ns, extraction_status, fts_rowid, "
                " indexed_at, extraction_disposition) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET "
                " file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
                # Authoritative: point at the rebuilt FTS row and re-stamp disposition to current policy
                # (extraction_status + content columns are deliberately NOT touched — content is unchanged).
                " fts_rowid=excluded.fts_rowid, "
                " extraction_disposition=excluded.extraction_disposition, "
                " indexed_at=excluded.indexed_at",
                (
                    entity_id,
                    record.get("file_ext"),
                    record.get("size_bytes"),
                    record.get("mtime_ns"),
                    record.get("extraction_status", "pending"),
                    fts_rowid,
                    now,
                    record.get("extraction_disposition"),
                ),
            )
            # Rebuild the belongs_to_project edge under CURRENT policy (a matcher change with unchanged
            # key/number can still change confidence/evidence) — replacement-based, never orphaned.
            c.execute(
                "DELETE FROM source_intelligence_relationships "
                "WHERE src_source_entity_id=? AND relation='belongs_to_project'",
                (entity_id,),
            )
            for rel in record.get("relationships") or []:
                # F-002: 'source' targets persist as a v2 entity ref (hbsrc2_); an unresolvable source
                # target is skipped. belongs_to_project rows (dst_kind='project') pass through unchanged.
                dst_ref = self._dst_ref_for_write(c, rel["dst_kind"], rel["dst_ref"])
                if dst_ref is None:
                    continue
                c.execute(
                    "INSERT INTO source_intelligence_relationships "
                    "(relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                    (
                        uuid.uuid4().hex,
                        entity_id,
                        rel["dst_kind"],
                        dst_ref,
                        rel["relation"],
                        rel.get("confidence"),
                        json.dumps(rel.get("evidence")) if rel.get("evidence") else None,
                        now,
                    ),
                )
            self._assert_lifecycle_oracle(c, entity_id)
            return entity_id

        # ---- replace mode (a genuine change / transition) ----
        # FTS sync (regular fts5; only bounded excerpt/rel_path/project_key indexed). Always drop any prior
        # row first, then maintain ONE row per source. PATH FTS INVARIANT (V122): every active external
        # source keeps a searchable row — metadata-only files carry an EMPTY text_excerpt plus rel_path +
        # project aux, content files additionally carry the bounded excerpt. content_searchable is measured
        # from NONEMPTY source_intelligence_text, so a path-only FTS row never overstates content coverage.
        fts_rowid = None
        if self._fts_available(c):
            if old_fts_rowid is not None:
                c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (old_fts_rowid,))
            excerpt = record.get("text_excerpt")
            if source_kind == "external_file":
                cur = c.execute(
                    f"INSERT INTO {fts_table}(text_excerpt, rel_path, aux) VALUES (?,?,?)",
                    (excerpt or "", rel_path, aux),
                )
                fts_rowid = cur.lastrowid
            elif excerpt:
                cur = c.execute(
                    f"INSERT INTO {fts_table}(text_excerpt, rel_path, aux) VALUES (?,?,?)",
                    (excerpt, rel_path, aux),
                )
                fts_rowid = cur.lastrowid

        # content_indexed_at reflects whether CURRENT VALID extracted content exists (finding 3). In
        # replace mode (a genuine change/transition) the write is AUTHORITATIVE: it is stamped ``now`` only
        # when this write actually carries extracted content (content disposition, status ok, a real
        # excerpt), and forced to NULL otherwise — so a content→metadata_only/unsupported/too_large/cleared
        # transition can never leave a stale "content indexed at" timestamp behind (the UPSERT below assigns
        # it directly, NOT via COALESCE, unlike the preserve path which never touches it).
        _disp = record.get("extraction_disposition")
        _status = record.get("extraction_status", "ok")
        # Valid extracted content exists when this content write actually carries indexed text — either a
        # plaintext excerpt or an encrypted-to-vault ref (sensitive roots). A metadata-only / cleared write
        # carries neither, so the stamp is NULL and no stale timestamp survives the transition.
        _has_content = bool(record.get("text_excerpt") or record.get("text_vault_ref"))
        content_indexed_at = (
            now if (_disp == "content" and _status == "ok" and _has_content) else None
        )
        c.execute(
            "INSERT INTO source_intelligence_metadata "
            "(source_entity_id, file_ext, size_bytes, mtime_ns, content_sha256, page_count, "
            " paragraph_count, sheet_count, extraction_status, extraction_failure_code, fts_rowid, "
            " indexed_at, extraction_disposition, content_indexed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_entity_id) DO UPDATE SET "
            " file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
            " content_sha256=excluded.content_sha256, page_count=excluded.page_count, "
            " paragraph_count=excluded.paragraph_count, sheet_count=excluded.sheet_count, "
            " extraction_status=excluded.extraction_status, extraction_failure_code=excluded.extraction_failure_code, "
            " fts_rowid=excluded.fts_rowid, indexed_at=excluded.indexed_at, "
            " extraction_disposition=excluded.extraction_disposition, "
            # Authoritative in replace mode: NULL clears a stale stamp when valid content no longer exists.
            " content_indexed_at=excluded.content_indexed_at",
            (
                entity_id,
                record.get("file_ext"),
                record.get("size_bytes"),
                record.get("mtime_ns"),
                record.get("content_sha256"),
                record.get("page_count"),
                record.get("paragraph_count"),
                record.get("sheet_count"),
                record.get("extraction_status", "ok"),
                record.get("extraction_failure_code"),
                fts_rowid,
                now,
                record.get("extraction_disposition"),
                content_indexed_at,
            ),
        )

        # _text (bounded excerpt; never raw body). A content write inserts/updates the row; a
        # metadata-only/unsupported/too-large/cleared write (no excerpt and no vault ref) DELETES any stale
        # prior text row so a content->metadata-only transition invalidates the old excerpt + full-text
        # hash + vault ref (chunks are replaced below). Unchanged files are fast-skipped upstream; a pure
        # repair takes the preserve branch above and never reaches this content-invalidating path.
        if record.get("text_excerpt") is not None or record.get("text_vault_ref") is not None:
            c.execute(
                "INSERT INTO source_intelligence_text "
                "(source_entity_id, text_excerpt, excerpt_char_count, excerpt_truncated, full_text_sha256, "
                " text_vault_ref, raw_body_persisted, redaction_applied, updated_at) "
                "VALUES (?,?,?,?,?,?,0,1,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET "
                " text_excerpt=excluded.text_excerpt, excerpt_char_count=excluded.excerpt_char_count, "
                " excerpt_truncated=excluded.excerpt_truncated, full_text_sha256=excluded.full_text_sha256, "
                " text_vault_ref=excluded.text_vault_ref, updated_at=excluded.updated_at",
                (
                    entity_id,
                    record.get("text_excerpt"),
                    record.get("excerpt_char_count", 0),
                    1 if record.get("excerpt_truncated") else 0,
                    record.get("full_text_sha256"),
                    record.get("text_vault_ref"),
                    now,
                ),
            )
        else:
            c.execute(
                "DELETE FROM source_intelligence_text WHERE source_entity_id=?", (entity_id,)
            )

        # chunks (replace set)
        c.execute("DELETE FROM source_intelligence_chunks WHERE source_entity_id=?", (entity_id,))
        for ordinal, chunk in enumerate(record.get("chunks") or []):
            c.execute(
                "INSERT INTO source_intelligence_chunks "
                "(chunk_id, source_entity_id, ordinal, chunk_text, char_count, raw_body_persisted, created_at) "
                "VALUES (?,?,?,?,?,0,?)",
                (f"{entity_id}:{ordinal}", entity_id, ordinal, chunk, len(chunk), now),
            )

        # relationships — REPLACEMENT-based for project edges: a reprocess/transition drops the source's
        # existing belongs_to_project rows before re-asserting the current set, so a reclassification never
        # leaves an obsolete project relationship attached (additive ON CONFLICT alone could not remove one).
        c.execute(
            "DELETE FROM source_intelligence_relationships "
            "WHERE src_source_entity_id=? AND relation='belongs_to_project'",
            (entity_id,),
        )
        for rel in record.get("relationships") or []:
            c.execute(
                "INSERT INTO source_intelligence_relationships "
                "(relationship_id, src_source_entity_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(src_source_entity_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                (
                    uuid.uuid4().hex,
                    entity_id,
                    rel["dst_kind"],
                    rel["dst_ref"],
                    rel["relation"],
                    rel.get("confidence"),
                    json.dumps(rel.get("evidence")) if rel.get("evidence") else None,
                    now,
                ),
            )
        self._assert_lifecycle_oracle(c, entity_id)
        return entity_id

    def link_domain_source(
        self,
        *,
        source_kind: str,
        domain_ref_table: str,
        domain_ref_id: str,
        project_key: str | None = None,
        project_number: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        """Create a LINK to an existing domain record (email/procore/schedule). No body re-ingest.

        R11-D2: mints through the P1 lifecycle (entity + a SYNTHETIC current locator) — never a raw parent
        ``source_id`` write. The synthetic address encodes the COMPLETE stable identity tuple so it is
        collision-free: ``source_root_key = f"domain::{source_kind}::{domain_ref_table}"`` and
        ``rel_path = domain_ref_id``. Path-uniqueness therefore gives domain sources idempotent re-link
        semantics identical to file sources; the deterministic domain-link handle stays on the locator's
        ``source_id`` for legacy resolution. Returns the durable ``source_entity_id``."""
        legacy_source_id = source_id_for(
            source_kind, domain_ref_table=domain_ref_table, domain_ref_id=domain_ref_id
        )
        synthetic_root = f"domain::{source_kind}::{domain_ref_table}"
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            loc = self._locator_for_path(
                c, source_kind, domain_ref_id, source_root_key=synthetic_root
            )
            if loc is not None:
                entity_id = loc[0]
            else:
                entity_id = self._mint_entity(c)
                self._insert_current_locator(
                    c, entity_id=entity_id, source_id=legacy_source_id,
                    source_root_key=synthetic_root, rel_path=domain_ref_id,
                )
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_entity_id, source_kind, domain_ref_table, domain_ref_id, project_key, "
                " project_number, active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET project_key=excluded.project_key, "
                " project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at",
                (
                    entity_id,
                    source_kind,
                    domain_ref_table,
                    domain_ref_id,
                    project_key,
                    project_number,
                    now,
                    now,
                ),
            )
            self._assert_lifecycle_oracle(c, entity_id)
        return entity_id

    def mark_deleted(
        self,
        source_kind: str,
        rel_path: str,
        *,
        source_root_key: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        # W-1: resolve the target via the CURRENT locator (a demoted path must never resolve a live
        # target), then P2-tombstone the entity.
        sql = (
            "SELECT s.source_entity_id, m.fts_rowid FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id=s.source_entity_id "
            "  AND l.is_current_locator=1 "
            "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id=s.source_entity_id "
            "WHERE s.source_kind=? AND l.rel_path=?"
        )
        params: list[Any] = [source_kind, rel_path]
        if source_root_key is not None:
            sql += " AND l.source_root_key=?"
            params.append(source_root_key)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(sql, tuple(params)).fetchone()
            if row is None:
                return
            entity_id, fts_rowid = row[0], row[1]
            if fts_rowid is not None and self._fts_available(c):
                fts_table = (
                    "source_intelligence_fts"
                    if source_kind == "external_file"
                    else "obsidian_note_fts"
                )
                c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
            c.execute(
                "UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? "
                "WHERE source_entity_id=?",
                (_now(), entity_id),
            )
            self._tombstone_entity(c, entity_id)
            self._mark_generated_notes_stale(c, entity_id)
            self._assert_lifecycle_oracle(c, entity_id)

    def mark_deleted_batch(
        self,
        source_kind: str,
        rel_paths: list[str],
        *,
        source_root_key: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Mark a whole CONFIRMED-GONE batch deleted in ONE transaction (A1 vault deletion safety).

        For each ``rel_path`` the source row is deactivated (``deleted=1, active=0``), its FTS row is
        removed, and any generated card is staled — atomically ACROSS the batch so a crash can never
        leave a certified reconciliation half-applied. Never touches a source FILE (index state only).
        Returns the number of rows actually deactivated (missing rel_paths are skipped)."""
        if not rel_paths:
            return 0
        fts_table = (
            "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
        )
        base_sql = (
            "SELECT s.source_entity_id, m.fts_rowid FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id=s.source_entity_id "
            "  AND l.is_current_locator=1 "
            "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id=s.source_entity_id "
            "WHERE s.source_kind=? AND l.rel_path=?"
        )
        deleted = 0
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            fts_ok = self._fts_available(c)
            for rel_path in rel_paths:
                sql = base_sql
                params: list[Any] = [source_kind, rel_path]
                if source_root_key is not None:
                    sql += " AND l.source_root_key=?"
                    params.append(source_root_key)
                row = c.execute(sql, tuple(params)).fetchone()
                if row is None:
                    continue
                entity_id, fts_rowid = row[0], row[1]
                if fts_rowid is not None and fts_ok:
                    c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
                c.execute(
                    "UPDATE source_intelligence_sources "
                    "SET deleted=1, active=0, updated_at=? WHERE source_entity_id=?",
                    (_now(), entity_id),
                )
                self._tombstone_entity(c, entity_id)
                self._mark_generated_notes_stale(c, entity_id)
                deleted += 1
            self._assert_lifecycle_oracle(c)
        return deleted

    def _mark_generated_notes_stale(self, c: sqlite3.Connection, source_entity_id: str) -> None:
        c.execute(
            "UPDATE source_intelligence_generated_notes SET generation_status='stale', updated_at=? "
            "WHERE source_entity_id=? AND generation_status='generated'",
            (_now(), source_entity_id),
        )

    def mark_generated_notes_stale(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._mark_generated_notes_stale(c, source_entity_id)

    # ----- V122 generation-aware batch reads/writes ------------------------------------------
    def load_metadata_state_batch(
        self, source_root_key: str, rel_paths: list[str], *, conn: sqlite3.Connection | None = None
    ) -> dict[str, dict[str, Any]]:
        """Fast-skip state for a BOUNDED batch of paths: ``rel_path -> {mtime, size, has_fts, disposition,
        project_key, project_number, content_mode, fingerprint}``.

        The metadata-first replacement for a full-root ``active_index_state`` preload — one query per
        batch keeps memory O(batch), never O(root). The walker fast-skips (or content-preserves) a file
        ONLY when its stat matches AND it is still fully consistent with CURRENT policy. Consistency needs
        more than stat: ``has_fts`` (a path/project FTS row exists), the read-time-mapped ``disposition``,
        the stored ``project_key``/``project_number`` (a project-matcher change that re-routes a file is NOT
        fast-skipped — stale project fields/relationships get replaced), ``content_mode`` (``plain`` = nonempty
        excerpt / ``vault`` = encrypted ref / ``none``) so a sensitivity flip in EITHER direction is detected
        and re-secured, and ``fingerprint`` (the policy fingerprint the row was last indexed under) so ANY
        metadata/search-affecting policy or code change forces reprocessing rather than a skip. Deleted rows
        excluded; V99 root-scoped identity.
        """
        if not rel_paths:
            return {}
        placeholders = ",".join("?" for _ in rel_paths)
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT l.rel_path, m.mtime_ns, m.size_bytes, "
                " CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END AS has_fts, "
                # Read-time legacy mapping (matches content_status_counts); NULL disposition is derived
                # from the legacy extraction_status so a fast-skip comparison sees the effective value.
                " COALESCE(m.extraction_disposition, CASE m.extraction_status "
                "   WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' "
                "   WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' "
                "   ELSE 'metadata_only' END) AS disp, "
                " s.project_key AS project_key, s.project_number AS project_number, "
                # F-005: the policy fingerprint the row was last indexed under is re-homed to the locator.
                " l.last_indexed_fingerprint AS fingerprint, "
                # Content storage mode: plaintext excerpt vs encrypted-to-vault ref vs none. Lets the walker
                # detect BOTH a sensitive root holding plaintext AND a plain root holding a vault ref.
                " COALESCE((SELECT CASE "
                "   WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 'plain' "
                "   WHEN t.text_vault_ref IS NOT NULL AND LENGTH(t.text_vault_ref) > 0 THEN 'vault' "
                "   ELSE 'none' END FROM source_intelligence_text t "
                "   WHERE t.source_entity_id = s.source_entity_id), 'none') AS content_mode "
                "FROM source_intelligence_sources s "
                "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
                "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 "
                f"AND l.rel_path IN ({placeholders})",
                (source_root_key, *rel_paths),
            ).fetchall()
        return {
            row[0]: {
                "mtime": row[1],
                "size": row[2],
                "has_fts": bool(row[3]),
                "disposition": row[4],
                "project_key": row[5],
                "project_number": row[6],
                "fingerprint": row[7],
                "content_mode": row[8],
            }
            for row in rows
        }

    def stamp_last_seen(
        self,
        source_root_key: str,
        rel_paths: list[str],
        generation_id: str,
        *,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
    ) -> None:
        """Stamp last_seen_generation/last_seen_at for a batch of UNCHANGED (fast-skipped) files.

        Sets ONLY the last-seen columns — never ``updated_at`` — so a pure "still present" observation
        cannot masquerade as a material change (which would wrongly mark generated notes stale or defeat
        the reconciliation ``updated_at`` guard). ``in_transaction=True`` (requires ``conn``) runs on the
        caller's open txn so the stamp commits atomically with the batch's metadata + cursor checkpoint."""
        if not rel_paths:
            return
        now = _now()
        placeholders = ",".join("?" for _ in rel_paths)
        # OW (observation-write): the last-seen columns are re-homed to the CURRENT locator (V129). Scope
        # by the locator's own current address; restrict to LIVE external_file entities. Writes ONLY the
        # two observation columns — never parent updated_at.
        sql = (
            "UPDATE source_index_locators SET last_seen_generation=?, last_seen_at=? "
            "WHERE is_current_locator=1 AND tombstoned_at IS NULL AND source_root_key=? "
            f"AND rel_path IN ({placeholders}) "
            "AND source_entity_id IN (SELECT source_entity_id FROM source_intelligence_sources "
            " WHERE source_kind='external_file' AND deleted=0)"
        )
        params = (generation_id, now, source_root_key, *rel_paths)
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            conn.execute(sql, params)
            return
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(sql, params)

    def stale_candidates_batch(
        self,
        source_root_key: str,
        generation_id: str,
        generation_started_at: str,
        *,
        after_source_id: str | None = None,
        limit: int = 500,
        conn: sqlite3.Connection | None = None,
    ) -> list[tuple[str, str]]:
        """One source_id-keyset page of deletion candidates for a COMPLETE generation.

        A candidate is an active external file NOT stamped with this generation whose ``updated_at`` is at
        or before the generation start (the guard that protects a legitimate targeted write made after the
        generation began). ``last_seen_generation IS NULL`` is included so legacy/never-stamped rows are
        considered. ``julianday`` comparison — never lexical. Keyset by ``source_id`` (never OFFSET) so a
        ``reconcile_pending`` generation resumes without rewalking. Returns ``[(source_id, rel_path), ...]``.
        """
        # CA: entity keyset/order/output; rel_path + the generation observation come from the CURRENT
        # locator (F-005). ``after_source_id`` is the prior page's entity-id keyset cursor.
        sql = (
            "SELECT s.source_entity_id, l.rel_path FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 "
            "WHERE s.source_kind='external_file' AND l.source_root_key=? AND s.deleted=0 "
            "AND (l.last_seen_generation IS NULL OR l.last_seen_generation != ?) "
            "AND julianday(s.updated_at) <= julianday(?) "
        )
        params: list[Any] = [source_root_key, generation_id, generation_started_at]
        if after_source_id is not None:
            sql += "AND s.source_entity_id > ? "
            params.append(after_source_id)
        sql += "ORDER BY s.source_entity_id LIMIT ?"
        params.append(int(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(sql, tuple(params)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def mark_deleted_by_source_id(
        self,
        source_entity_id: str,
        *,
        source_kind: str = "external_file",
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
    ) -> None:
        """Delete-reconcile a single confirmed-absent source ENTITY: drop its FTS row (path + content), P2
        tombstone it, and stale its generated notes. ``in_transaction=True`` (requires ``conn``) runs on the
        caller's open txn so a reconcile batch's deletes + cursor checkpoint commit atomically."""
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            self._mark_deleted_by_source_id_locked(conn, source_entity_id, source_kind)
            return
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._mark_deleted_by_source_id_locked(c, source_entity_id, source_kind)

    def _mark_deleted_by_source_id_locked(
        self, c: sqlite3.Connection, source_entity_id: str, source_kind: str
    ) -> None:
        row = c.execute(
            "SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_entity_id=?",
            (source_entity_id,),
        ).fetchone()
        fts_rowid = row[0] if row else None
        if fts_rowid is not None and self._fts_available(c):
            fts_table = (
                "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
            )
            c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
        c.execute(
            "UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? "
            "WHERE source_entity_id=?",
            (_now(), source_entity_id),
        )
        self._tombstone_entity(c, source_entity_id)
        self._mark_generated_notes_stale(c, source_entity_id)
        self._assert_lifecycle_oracle(c, source_entity_id)

    def _invalidate_content_locked(
        self, c: sqlite3.Connection, source_entity_id: str, source_kind: str
    ) -> None:
        """Fully invalidate a source's CONTENT representation IN PLACE (Phase B / B4 corrective) — WITHOUT
        deleting the source row — for a move that OVERWRITES an already-indexed destination. Clears every
        content-derived field the read/search paths consult, so no stale content is served or advertised
        complete while the destination awaits re-extraction:

          * drops the FTS row (via the CURRENT metadata.fts_rowid — read BEFORE it is nulled) so old body
            text is no longer searchable;
          * DELETEs the bounded text excerpt (text_excerpt/full_text_sha256/text_vault_ref) and the chunks;
          * nulls the metadata content columns (content_sha256/fts_rowid/page_count/paragraph_count/
            sheet_count/extraction_failure_code/extraction_disposition/content_indexed_at) and sets
            extraction_status='pending';
          * stales any generated notes (source cards) for this source (the dest's OWN pre-existing card,
            which the old→new relink's UNIQUE-collision IGNORE would otherwise leave 'generated').

        Mirrors replace-mode ``_upsert_source_file_locked`` (text/chunks/content_indexed_at) + the FTS drop
        in ``_mark_deleted_by_source_id_locked``. Idempotent / no-op when the source has no content."""
        row = c.execute(
            "SELECT fts_rowid FROM source_intelligence_metadata WHERE source_entity_id=?",
            (source_entity_id,),
        ).fetchone()
        fts_rowid = row[0] if row else None
        if fts_rowid is not None and self._fts_available(c):
            fts_table = (
                "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
            )
            c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
        c.execute("DELETE FROM source_intelligence_text WHERE source_entity_id=?", (source_entity_id,))
        c.execute(
            "DELETE FROM source_intelligence_chunks WHERE source_entity_id=?", (source_entity_id,)
        )
        c.execute(
            "UPDATE source_intelligence_metadata SET content_sha256='', fts_rowid=NULL, "
            " page_count=NULL, paragraph_count=NULL, sheet_count=NULL, extraction_failure_code=NULL, "
            " extraction_disposition=NULL, content_indexed_at=NULL, extraction_status='pending' "
            "WHERE source_entity_id=?",
            (source_entity_id,),
        )
        self._mark_generated_notes_stale(c, source_entity_id)

    def _confirmed_move_locked(
        self,
        c: sqlite3.Connection,
        root_key: str,
        old_rel_path: str,
        new_rel_path: str,
        dest_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Decomposed, per-event-idempotent same-root relocation on an OPEN transaction (ADR-003 R11-D3).

        A no-signal relocation is TWO independently-valid lifecycle observations, NOT one correlated
        identity-preserving move. This method realizes only the **source side**: source-gone ⇒ **P2
        tombstone the old entity** resolved via its CURRENT locator. The **destination side** (target-appears
        ⇒ P1 create-new) is established by the drain's own post-move ``index_source_file`` — it is NOT done
        here (no content/fingerprint/file-stat/generated-note/lineage carried; ``renamed_from_source_id``
        is never written; P-C/P-D). Destination-locator occupancy is an idempotent ACTION discriminator, NOT
        provenance. Returns ``{old_source_id, new_source_id, linked, result}`` — result strings are
        compatibility bindings for the frozen drain, never evidence of lineage or completion:

        | old current | dest occupied | action | result |
        |---|---|---|---|
        | yes | no  | P2-tombstone old | ``move_applied`` (drain indexes dest) |
        | yes | yes | conservative conflict — NO mutation | ``conflicting_successor`` (drain terminal-skips) |
        | no  | yes | P2 no-op | ``move_already_applied`` (drain resolves+updates dest) |
        | no  | no  | P2 no-op | ``source_missing`` (drain mints dest) |
        """
        old_sid = source_id_for("external_file", source_root_key=root_key, rel_path=old_rel_path)
        new_sid = source_id_for("external_file", source_root_key=root_key, rel_path=new_rel_path)
        _ = dest_metadata  # destination stat is applied by the drain's re-index, not here (R11-D3)
        old_loc = self._locator_for_path(c, "external_file", old_rel_path, source_root_key=root_key)
        dest_loc = self._locator_for_path(c, "external_file", new_rel_path, source_root_key=root_key)
        dest_occupied = dest_loc is not None
        if old_loc is not None:
            if dest_occupied:
                # Conservative conflict: old is still current AND a live entity already occupies the
                # destination — fail closed, no move mutation (cleanup left to authoritative reconciliation).
                return {"old_source_id": old_sid, "new_source_id": new_sid,
                        "linked": False, "result": "conflicting_successor"}
            # Source side only: P2 tombstone the old entity (idempotent by TOMBSTONED-terminal). The
            # destination P1 is the drain's fall-through re-index of the target.
            self._mark_deleted_by_source_id_locked(c, old_loc[0], "external_file")
            return {"old_source_id": old_sid, "new_source_id": new_sid,
                    "linked": True, "result": "move_applied"}
        # Old already absent/TOMBSTONED — P2 is a no-op; destination occupancy only distinguishes which
        # compatibility string the drain sees (both fall through to the idempotent destination re-index).
        result = "move_already_applied" if dest_occupied else "source_missing"
        return {"old_source_id": old_sid, "new_source_id": new_sid,
                "linked": False, "result": result}

    def apply_confirmed_same_root_move(
        self,
        root_key: str,
        old_rel_path: str,
        new_rel_path: str,
        dest_metadata: dict[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Open a transaction and run :meth:`_confirmed_move_locked` (unguarded — direct/test use)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            return self._confirmed_move_locked(c, root_key, old_rel_path, new_rel_path, dest_metadata)

    def apply_owned_confirmed_same_root_move(
        self,
        *,
        event_id: str,
        expected_attempt: int,
        root_key: str,
        old_relative_path: str,
        new_relative_path: str,
        destination_metadata: dict[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Ownership-guarded move (Phase B / B4 corrective, PLAN-C4-001). Ownership is proven by a **guarded
        WRITE as the first statement** — ``UPDATE … SET updated_at=? WHERE event_id=? AND status='processing'
        AND attempts=?`` — NOT a read-only ``SELECT``. This matters: the shared ``transaction()`` helper never
        emits ``BEGIN`` and the connection uses ``isolation_level=''`` (implicit ``BEGIN`` fires only before a
        DML), so a ``SELECT`` would hold no write lock and a reclaim could slip in before the first mutation.
        The guarded ``UPDATE`` acquires the RESERVED write lock at this first statement, so this connection
        holds it through ``_confirmed_move_locked`` and the commit — no concurrent reclaim can commit until it
        finishes — and ``rowcount`` reflects ownership at lock-acquisition time (0 → the event was already
        reclaimed → ``result='claim_conflict'``, **no source/lineage mutation**). The write also refreshes the
        stuck-event lease so the event can't be TTL-reclaimed between commit and re-indexing. SQLite
        BUSY/LOCKED on the guarded write → ``result='db_busy'`` (no lock acquired, no mutation; retryable);
        any other ``OperationalError`` propagates as a real error."""
        old_sid = source_id_for("external_file", source_root_key=root_key, rel_path=old_relative_path)
        new_sid = source_id_for("external_file", source_root_key=root_key, rel_path=new_relative_path)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            try:
                cur = c.execute(
                    "UPDATE source_intelligence_events SET updated_at=? "
                    "WHERE event_id=? AND status='processing' AND attempts=?",
                    (_now(), event_id, int(expected_attempt)),
                )
            except sqlite3.OperationalError as e:
                if is_sqlite_busy(e):
                    return {"old_source_id": old_sid, "new_source_id": new_sid,
                            "linked": False, "result": "db_busy"}
                raise
            if (cur.rowcount or 0) != 1:
                return {"old_source_id": old_sid, "new_source_id": new_sid,
                        "linked": False, "result": "claim_conflict"}
            return self._confirmed_move_locked(
                c, root_key, old_relative_path, new_relative_path, destination_metadata
            )

    def find_successor_source_id(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> str | None:
        """R11-D1: **always returns None** in 03a. The ``renamed_from_source_id`` lineage authority is
        removed from runtime (P-C): under the degraded model a relocation is delete+create with no
        identity-preserving successor, so answering a stale handle as a current successor is exactly the
        rebinding P-B forbids. A signalled-P4 moved answer (derived only from authoritative P4 continuity)
        is 03b — ``renamed_from_source_id`` is NOT reinstated. The content provider's ``_resolve_moved``
        already fails closed on None, so a deleted ref falls through to ordinary unavailable handling."""
        _ = (source_id, conn)  # signature preserved for the frozen content-provider caller
        return None

    # ----- source detail + generated-note tracking (source cards) ----------------------------
    def get_source_detail(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        """Joined sources+metadata+text row for rendering a source card (keyed by durable entity). The
        served ``source_id``/``source_root_key``/``rel_path`` come from the CURRENT locator (CA authority);
        a TOMBSTONED entity (no current locator) returns NULLs for those and ``deleted=True``. None if the
        entity is absent."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                # A domain-LINK source has a synthetic locator (root=domain::…, rel_path=domain_ref_id)
                # for identity/uniqueness only — its served file address is NULL (it is a domain ref, not a
                # path), so consumers that distinguish link-vs-file by rel_path stay correct.
                "SELECT s.source_entity_id, s.source_kind, "
                "  CASE WHEN s.domain_ref_table IS NOT NULL THEN NULL ELSE l.source_root_key END, "
                "  CASE WHEN s.domain_ref_table IS NOT NULL THEN NULL ELSE l.rel_path END, "
                "  s.domain_ref_table, s.domain_ref_id, s.project_key, s.project_number, s.deleted, "
                "  m.file_ext, m.size_bytes, m.mtime_ns, m.content_sha256, m.page_count, "
                "  m.paragraph_count, m.sheet_count, m.extraction_status, m.indexed_at, "
                "  t.text_excerpt, t.excerpt_char_count, t.excerpt_truncated, t.text_vault_ref "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 "
                "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id "
                "WHERE s.source_entity_id = ?",
                (source_entity_id,),
            ).fetchone()
        if row is None:
            return None
        keys = (
            "source_id",
            "source_kind",
            "source_root_key",
            "rel_path",
            "domain_ref_table",
            "domain_ref_id",
            "project_key",
            "project_number",
            "deleted",
            "file_ext",
            "size_bytes",
            "mtime_ns",
            "content_sha256",
            "page_count",
            "paragraph_count",
            "sheet_count",
            "extraction_status",
            "indexed_at",
            "text_excerpt",
            "excerpt_char_count",
            "excerpt_truncated",
            "text_vault_ref",
        )
        detail = dict(zip(keys, row, strict=True))
        detail["deleted"] = bool(detail["deleted"])
        return detail

    def record_generated_note(
        self,
        source_entity_id: str,
        note_rel_path: str,
        status: str,
        generated_at: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_generated_notes "
                "(generated_note_id, source_entity_id, note_rel_path, generation_status, generated_at, updated_at) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_entity_id, note_rel_path) DO UPDATE SET "
                " generation_status=excluded.generation_status, generated_at=excluded.generated_at, "
                " updated_at=excluded.updated_at",
                (uuid.uuid4().hex, source_entity_id, note_rel_path, status, generated_at, _now()),
            )
            if status == "generated":
                self._set_state(c, "last_note_at", _now())

    def has_generated_note(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> bool:
        """True if a card was ever generated for this source entity (status generated or stale)."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT 1 FROM source_intelligence_generated_notes "
                "WHERE source_entity_id=? AND generation_status IN ('generated','stale') LIMIT 1",
                (source_entity_id,),
            ).fetchone()
        return row is not None

    def list_stale_generated_notes(
        self, limit: int = 25, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT source_entity_id, note_rel_path FROM source_intelligence_generated_notes "
                "WHERE generation_status='stale' ORDER BY updated_at LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [{"source_id": r[0], "note_rel_path": r[1]} for r in rows]

    def list_recent_events(
        self,
        *,
        limit: int = 25,
        event_types: tuple[str, ...] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Most-recent indexer events (created/modified/deleted/reindex/rebuild), newest first.

        Read-only audit-trail reader for "what changed recently". ``event_types`` optionally narrows
        by bound parameters (no SQL interpolation). Returns event_id, source_id, rel_path,
        source_root_key, event_type, status, created_at.
        """
        params: list[Any] = []
        sql = (
            "SELECT event_id, source_id, rel_path, source_root_key, event_type, status, created_at "
            "FROM source_intelligence_events "
        )
        types = tuple(event_types) if event_types else ()
        if types:
            sql += "WHERE event_type IN (%s) " % ",".join("?" for _ in types)
            params.extend(types)
        sql += "ORDER BY created_at DESC, event_id DESC LIMIT ?"
        params.append(int(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(sql, params).fetchall()
        return [
            {
                "event_id": r[0],
                "source_id": r[1],
                "rel_path": r[2],
                "source_root_key": r[3],
                "event_type": r[4],
                "status": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    def list_generated_notes(
        self, *, statuses: tuple[str, ...] = ("generated",), conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Generated-note rows joined to their source (rel_path/kind) — for maintenance scans.

        Unlike ``list_stale_generated_notes`` this is not status-locked or row-capped; the caller
        filters by source path. Returns generated_note_id, source_id, note_rel_path,
        generation_status, source_rel_path, source_kind.
        """
        statuses = tuple(statuses) or ("generated",)
        placeholders = ",".join("?" for _ in statuses)
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT g.generated_note_id, g.source_entity_id, g.note_rel_path, g.generation_status, "
                "       l.rel_path, s.source_kind "
                "FROM source_intelligence_generated_notes g "
                "JOIN source_intelligence_sources s ON s.source_entity_id = g.source_entity_id "
                "LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 "
                f"WHERE g.generation_status IN ({placeholders}) ORDER BY g.updated_at",
                statuses,
            ).fetchall()
        return [
            {
                "generated_note_id": r[0],
                "source_id": r[1],
                "note_rel_path": r[2],
                "generation_status": r[3],
                "source_rel_path": r[4],
                "source_kind": r[5],
            }
            for r in rows
        ]

    def get_sources_for_note(
        self, note_rel_path: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Reverse lookup: source rows whose generated card lives at ``note_rel_path``.

        Returns a LIST (0, 1, or many) on purpose: there is no UNIQUE on ``note_rel_path`` alone, so
        two different ``source_id``s could point at the same card path. Callers MUST treat ``len > 1``
        as ambiguous rather than picking one arbitrarily. Read-only.
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT g.source_entity_id, g.generation_status, g.generated_at, "
                "       s.source_kind, l.rel_path, l.source_root_key, s.deleted, s.active "
                "FROM source_intelligence_generated_notes g "
                "JOIN source_intelligence_sources s ON s.source_entity_id = g.source_entity_id "
                "LEFT JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 "
                "WHERE g.note_rel_path=? ORDER BY g.updated_at",
                (note_rel_path,),
            ).fetchall()
        return [
            {
                "source_id": r[0],
                "generation_status": r[1],
                "generated_at": r[2],
                "source_kind": r[3],
                "source_rel_path": r[4],
                "source_root_key": r[5],
                "deleted": bool(r[6]),
                "active": bool(r[7]),
            }
            for r in rows
        ]

    def list_cards_for_source(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """All generated-note rows for a source entity (any status), oldest-updated first.

        Read-only; the basis for duplicate-card and card-state detection. One source SHOULD have one
        active (generated/stale) card row; more than one is a duplicate the caller flags.
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT generated_note_id, note_rel_path, generation_status, generated_at, updated_at "
                "FROM source_intelligence_generated_notes WHERE source_entity_id=? ORDER BY updated_at",
                (source_entity_id,),
            ).fetchall()
        return [
            {
                "generated_note_id": r[0],
                "note_rel_path": r[1],
                "generation_status": r[2],
                "generated_at": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    def set_generated_note_status(
        self, generated_note_id: str, status: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        """Set one generated-note row's status (legal: not_generated/generated/stale)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_intelligence_generated_notes SET generation_status=?, updated_at=? "
                "WHERE generated_note_id=?",
                (status, _now(), generated_note_id),
            )

    # ----- advisory model-summary receipts (V94) ---------------------------------------------
    def upsert_summary(
        self, source_entity_id: str, receipt: dict[str, Any], *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_summaries "
                "(source_entity_id, model_provider, model_name, prompt_version, prompt_sha256, "
                " summary_sha256, source_sha256, advisory, generated_at) "
                "VALUES (?,?,?,?,?,?,?,1,?) "
                "ON CONFLICT(source_entity_id) DO UPDATE SET model_provider=excluded.model_provider, "
                " model_name=excluded.model_name, prompt_version=excluded.prompt_version, "
                " prompt_sha256=excluded.prompt_sha256, summary_sha256=excluded.summary_sha256, "
                " source_sha256=excluded.source_sha256, generated_at=excluded.generated_at",
                (
                    source_entity_id,
                    receipt["model_provider"],
                    receipt.get("model_name"),
                    receipt["prompt_version"],
                    receipt.get("prompt_sha256"),
                    receipt.get("summary_sha256"),
                    receipt.get("source_sha256"),
                    _now(),
                ),
            )
            self._set_state(c, "last_summary_at", _now())

    def delete_summary(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "DELETE FROM source_intelligence_summaries WHERE source_entity_id=?",
                (source_entity_id,),
            )

    def get_summary(
        self, source_entity_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT model_provider, model_name, prompt_version, prompt_sha256, summary_sha256, "
                " source_sha256, generated_at FROM source_intelligence_summaries "
                "WHERE source_entity_id=?",
                (source_entity_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(
            zip(
                (
                    "model_provider",
                    "model_name",
                    "prompt_version",
                    "prompt_sha256",
                    "summary_sha256",
                    "source_sha256",
                    "generated_at",
                ),
                row,
                strict=True,
            )
        )

    def summary_counts(self, *, conn: sqlite3.Connection | None = None) -> dict[str, int]:
        """summarized_count + stale_summary_count (receipt source_sha drifted from current)."""
        with borrow_connection(conn, self.db_path) as c:
            total = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
            stale = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_summaries s "
                "JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "WHERE s.source_sha256 IS NOT m.content_sha256"
            ).fetchone()[0]
        return {"summarized_count": int(total), "stale_summary_count": int(stale)}

    # ----- durable queue ---------------------------------------------------------------------
    def enqueue_event(
        self,
        *,
        event_type: str,
        rel_path: str | None = None,
        source_root_key: str | None = None,
        source_id: str | None = None,
        dest_rel_path: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        event_id = uuid.uuid4().hex
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            # Coalesce: if an identical queued event exists, reuse it (debounce backstop).
            if event_type == "moved":
                # A move's queue identity is BOTH paths + root (source_root_key, rel_path, dest_rel_path):
                # distinct moves of the same source (A->B vs A->C) must NEVER collapse into one event.
                # ``IS`` (not ``=``) so a NULL component compares NULL-safe. Ordinary events keep the
                # (rel_path, event_type) identity below.
                existing = c.execute(
                    "SELECT event_id FROM source_intelligence_events "
                    "WHERE status='queued' AND event_type='moved' "
                    "AND source_root_key IS ? AND rel_path IS ? AND dest_rel_path IS ?",
                    (source_root_key, rel_path, dest_rel_path),
                ).fetchone()
                if existing is not None:
                    return str(existing[0])
            elif rel_path is not None:
                existing = c.execute(
                    "SELECT event_id FROM source_intelligence_events "
                    "WHERE status='queued' AND rel_path=? AND event_type=?",
                    (rel_path, event_type),
                ).fetchone()
                if existing is not None:
                    return str(existing[0])
            elif event_type == "rebuild" and source_root_key is not None:
                # Root-level rebuild events carry no rel_path, so the path-keyed coalesce above never
                # fires for them. Without this, a bounded rebuild pass that re-enqueues its remainder
                # every drain would grow the queue without bound. Coalesce on (event_type, root) so at
                # most one queued rebuild per root exists at a time.
                existing = c.execute(
                    "SELECT event_id FROM source_intelligence_events "
                    "WHERE status='queued' AND event_type='rebuild' AND source_root_key=? "
                    "AND rel_path IS NULL",
                    (source_root_key,),
                ).fetchone()
                if existing is not None:
                    return str(existing[0])
            c.execute(
                "INSERT INTO source_intelligence_events "
                "(event_id, source_id, rel_path, source_root_key, dest_rel_path, event_type, status, attempts, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,'queued',0,?,?)",
                (event_id, source_id, rel_path, source_root_key, dest_rel_path, event_type, now, now),
            )
        return event_id

    def claim_queued(
        self, limit: int = 50, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            # ``next_attempt_at`` gates bounded-backoff deferrals: a deferred event is re-eligible only once
            # its future timestamp has passed. Ordinary events have NULL → always eligible (behavior
            # unchanged). Lexical compare is sound because both columns use the same _now() ISO format.
            rows = c.execute(
                "SELECT event_id, source_id, rel_path, source_root_key, event_type, attempts, dest_rel_path "
                "FROM source_intelligence_events "
                "WHERE status='queued' AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
                "ORDER BY created_at LIMIT ?",
                (now, int(limit)),
            ).fetchall()
            claimed = []
            for r in rows:
                c.execute(
                    "UPDATE source_intelligence_events SET status='processing', attempts=attempts+1, updated_at=? "
                    "WHERE event_id=? AND status='queued'",
                    (now, r[0]),
                )
                claimed.append(
                    {
                        "event_id": r[0],
                        "source_id": r[1],
                        "rel_path": r[2],
                        "source_root_key": r[3],
                        "event_type": r[4],
                        # attempts AFTER this claim (the UPDATE above incremented it) — the drain uses this
                        # to decide defer-vs-exhausted for retryable 'moved' conditions.
                        "attempts": int(r[5] or 0) + 1,
                        "dest_rel_path": r[6],
                    }
                )
            return claimed

    def sample_queued_events(
        self, *, limit: int = 500, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Bounded read of queued events (rel_path) for the coarse queue-composition diagnostic.

        Read-only; does NOT claim/mutate. Single-file events only (rebuild/deleted have no rel_path).
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT rel_path, source_root_key, event_type FROM source_intelligence_events "
                "WHERE status='queued' AND rel_path IS NOT NULL ORDER BY created_at LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [{"rel_path": r[0], "source_root_key": r[1], "event_type": r[2]} for r in rows]

    def complete_event(
        self,
        event_id: str,
        status: str,
        *,
        error_code: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        # Skip-code normalization at the WRITE boundary: a NEW skip with no code is stamped
        # ``unspecified_skip`` (a regression signal) rather than NULL, so it never silently merges
        # into the legacy NULL→``unspecified`` read-time bucket. Non-skip statuses keep error_code
        # as-is (errors carry the raw exception name; done/processing/queued carry None).
        if status == "skipped":
            error_code = normalize_skip_code(error_code)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE source_intelligence_events SET status=?, error_code=?, updated_at=? WHERE event_id=?",
                (status, error_code, _now(), event_id),
            )

    def defer_event(
        self,
        event_id: str,
        *,
        error_code: str,
        expected_attempt: int,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        """Bounded, backoff-based retry for a CLAIMED event (Phase B / B4 corrective), guarded by the
        **claim generation**.

        ``expected_attempt`` is the ``attempts`` value ``claim_queued`` returned to THIS drain. The guard
        requires both ``status='processing'`` AND ``attempts=expected_attempt`` so a stale worker whose
        event was reclaimed (``requeue_stuck`` → another claim bumps ``attempts``) can never re-queue an
        event it no longer owns. Returns:
          * ``"deferred"`` — re-queued with a future ``next_attempt_at`` (retryable on a later drain);
          * ``"exhausted"`` — ``expected_attempt >= MOVED_MAX_ATTEMPTS``; no write, so the caller applies a
            guarded terminal disposition (a move never loops forever);
          * ``"conflict"`` — the guarded UPDATE matched 0 rows (not owned / not processing) → fail closed;
          * ``"db_busy"`` — SQLite BUSY/LOCKED on the guarded write (PLAN-C4-002/C4R5-001): the retry could
            not be written; the caller must leave the event ``processing`` for ``requeue_stuck`` (fail-closed,
            never a false terminal). Any other ``OperationalError`` propagates as a real error.
        """
        if expected_attempt >= MOVED_MAX_ATTEMPTS:
            return "exhausted"
        delay = min(
            MOVED_BACKOFF_CAP_S, MOVED_BACKOFF_BASE_S * (2 ** max(0, expected_attempt - 1))
        )
        try:
            with borrow_connection(conn, self.db_path) as c, transaction(c):
                cur = c.execute(
                    "UPDATE source_intelligence_events "
                    "SET status='queued', error_code=?, next_attempt_at=?, updated_at=? "
                    "WHERE event_id=? AND status='processing' AND attempts=?",
                    (error_code, _iso_after(delay), _now(), event_id, int(expected_attempt)),
                )
                if (cur.rowcount or 0) == 0:
                    return "conflict"
            return "deferred"
        except sqlite3.OperationalError as e:
            if is_sqlite_busy(e):
                return "db_busy"
            raise

    def complete_owned_event(
        self,
        event_id: str,
        status: str,
        *,
        expected_attempt: int,
        error_code: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> str:
        """Busy-aware terminal completion guarded by the claim generation (Phase B / B4 corrective,
        PLAN-C4R6-001). Only the drain that currently owns the claim (``status='processing'`` AND
        ``attempts=expected_attempt``) may finish it. Returns:
          * ``"completed"`` — the terminal transition was persisted;
          * ``"conflict"`` — a stale worker (reclaimed) → no-op;
          * ``"db_busy"`` — SQLite BUSY/LOCKED on the terminal write: the completion could not be written, so
            the event is left ``processing`` for ``requeue_stuck`` (fail-closed; NEVER a false terminal and
            NEVER an unguarded fallback). Any other ``OperationalError`` propagates as a real error."""
        if status == "skipped":
            error_code = normalize_skip_code(error_code)
        try:
            with borrow_connection(conn, self.db_path) as c, transaction(c):
                cur = c.execute(
                    "UPDATE source_intelligence_events SET status=?, error_code=?, updated_at=? "
                    "WHERE event_id=? AND status='processing' AND attempts=?",
                    (status, error_code, _now(), event_id, int(expected_attempt)),
                )
                return "completed" if (cur.rowcount or 0) > 0 else "conflict"
        except sqlite3.OperationalError as e:
            if is_sqlite_busy(e):
                return "db_busy"
            raise

    def event_is_owned(
        self, event_id: str, expected_attempt: int, *, conn: sqlite3.Connection | None = None
    ) -> bool:
        """True iff the event is still owned by this claim generation (processing + attempts match).
        Read-only; retained for test assertions. The DRAIN uses :meth:`heartbeat_owned_event` (a guarded
        WRITE) instead, so the ownership re-check also refreshes the lease and holds a write lock."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT 1 FROM source_intelligence_events "
                "WHERE event_id=? AND status='processing' AND attempts=?",
                (event_id, int(expected_attempt)),
            ).fetchone()
        return row is not None

    def heartbeat_owned_event(
        self, event_id: str, *, expected_attempt: int, conn: sqlite3.Connection | None = None
    ) -> str:
        """Guarded ownership heartbeat before EXPENSIVE re-indexing (Phase B / B4 corrective, PLAN-C4-001).
        A guarded WRITE (not a read-only SELECT) so it both re-proves ownership under the claim generation
        AND refreshes the stuck-event lease. Returns ``"ok"`` (rowcount==1 — owned, lease refreshed),
        ``"conflict"`` (reclaimed → the current owner is authoritative; do NOT index), or ``"db_busy"``
        (SQLite BUSY/LOCKED → leave the event ``processing`` for ``requeue_stuck``; retryable). Any other
        ``OperationalError`` propagates as a real error."""
        try:
            with borrow_connection(conn, self.db_path) as c, transaction(c):
                cur = c.execute(
                    "UPDATE source_intelligence_events SET updated_at=? "
                    "WHERE event_id=? AND status='processing' AND attempts=?",
                    (_now(), event_id, int(expected_attempt)),
                )
                return "ok" if (cur.rowcount or 0) == 1 else "conflict"
        except sqlite3.OperationalError as e:
            if is_sqlite_busy(e):
                return "db_busy"
            raise

    def requeue_stuck(
        self, ttl_seconds: int = 900, *, conn: sqlite3.Connection | None = None
    ) -> int:
        """Re-queue events stuck in 'processing' (e.g. across a crash). Returns count."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE source_intelligence_events SET status='queued', updated_at=? "
                "WHERE status='processing' AND (julianday('now') - julianday(updated_at)) * 86400 > ?",
                (_now(), int(ttl_seconds)),
            )
            return cur.rowcount or 0

    # ----- watcher single-owner lease --------------------------------------------------------
    # Two backend processes pointed at the same DB must not both run the watcher drain loop.
    # The lease is a pair of singleton k/v rows in the existing source_intelligence_state table
    # (NO schema change): ``watcher_owner`` (JSON owner_info incl. an opaque per-watcher
    # owner_token) and ``watcher_heartbeat_at`` (ISO timestamp). A live owner's heartbeat blocks a
    # competing acquire; a stale heartbeat (older than ttl, e.g. a crashed owner) is reclaimable.
    def _read_watcher_owner(self, c: sqlite3.Connection) -> dict[str, Any] | None:
        row = c.execute(
            "SELECT state_value FROM source_intelligence_state WHERE state_key='watcher_owner'"
        ).fetchone()
        if not row or not row[0]:
            return None
        try:
            owner = json.loads(row[0])
            return owner if isinstance(owner, dict) else None
        except Exception:
            return None

    def acquire_watcher_lease(
        self,
        *,
        owner_token: str,
        owner_info: dict[str, Any],
        ttl_seconds: int = 900,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Try to claim watcher ownership. Returns ``{acquired, took_over, owner}``.

        Acquires when there is no current owner, the current owner is *this* token (re-entry), or
        the current owner's heartbeat is stale (> ttl). Refuses (``acquired=False``) when a
        DIFFERENT owner has a fresh heartbeat — the caller must then run degraded (API only, no
        drain loop). ``took_over`` is True when a stale different owner was displaced.
        """
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            current = self._read_watcher_owner(c)
            hb = c.execute(
                "SELECT (julianday('now') - julianday(state_value)) * 86400 "
                "FROM source_intelligence_state WHERE state_key='watcher_heartbeat_at'"
            ).fetchone()
            age = float(hb[0]) if hb and hb[0] is not None else None
            same_owner = bool(current and current.get("owner_token") == owner_token)
            stale = current is None or age is None or age > float(ttl_seconds)
            if current is not None and not same_owner and not stale:
                return {"acquired": False, "took_over": False, "owner": current}
            took_over = bool(current is not None and not same_owner and stale)
            payload = dict(owner_info)
            payload["owner_token"] = owner_token
            payload["started_at"] = (
                current.get("started_at") if same_owner and current else None
            ) or now
            self._set_state(c, "watcher_owner", json.dumps(payload, sort_keys=True))
            self._set_state(c, "watcher_heartbeat_at", now)
            return {"acquired": True, "took_over": took_over, "owner": payload}

    def refresh_watcher_heartbeat(
        self, *, owner_token: str, conn: sqlite3.Connection | None = None
    ) -> bool:
        """Stamp a fresh heartbeat IFF this token still owns the lease. Returns False if not owner."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            current = self._read_watcher_owner(c)
            if not current or current.get("owner_token") != owner_token:
                return False
            self._set_state(c, "watcher_heartbeat_at", _now())
            return True

    def release_watcher_lease(
        self, *, owner_token: str, conn: sqlite3.Connection | None = None
    ) -> bool:
        """Release the lease IFF this token owns it (so a non-owner stop never clears it)."""
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            current = self._read_watcher_owner(c)
            if not current or current.get("owner_token") != owner_token:
                return False
            c.execute(
                "DELETE FROM source_intelligence_state "
                "WHERE state_key IN ('watcher_owner', 'watcher_heartbeat_at')"
            )
            return True

    def get_watcher_owner(
        self, *, ttl_seconds: int = 900, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        """Current owner info + heartbeat age + staleness, or None if unowned (status diagnostic)."""
        with borrow_connection(conn, self.db_path) as c:
            owner = self._read_watcher_owner(c)
            if owner is None:
                return None
            hb = c.execute(
                "SELECT state_value, (julianday('now') - julianday(state_value)) * 86400 "
                "FROM source_intelligence_state WHERE state_key='watcher_heartbeat_at'"
            ).fetchone()
        age = round(float(hb[1]), 1) if hb and hb[1] is not None else None
        owner = dict(owner)
        owner["heartbeat_at"] = hb[0] if hb else None
        owner["heartbeat_age_seconds"] = age
        owner["stale"] = age is None or age > float(ttl_seconds)
        return owner

    # ----- search ----------------------------------------------------------------------------
    def search_sources(
        self,
        query: str,
        *,
        limit: int = 20,
        project_key: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            if not self._fts_available(c):
                return []
            match_query = sanitize_fts_query(query)
            if not match_query:
                return []
            sql = (
                # Weighted BM25 (text_excerpt:1, rel_path:8, aux/project:12) so filename/project matches
                # rank above deep body-frequency matches — critical now that metadata-only files are
                # searchable by path alone. Weights are locked by ranking tests. Per-column snippets +
                # text presence + disposition drive match_basis/indexed_text_available shaping (V122).
                # CA: the FTS/content join binds the entity; the displayed path + returned handle come
                # from the CURRENT locator. Serving-trust EXCLUDE (R8 §6.3): policy-stale locators are
                # filtered out of search (l.policy_validation_state IS NULL).
                "SELECT l.rel_path, f.aux, bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, "
                " snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, "
                " snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, "
                " snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, "
                " s.source_entity_id, m.extraction_status, m.extraction_disposition, "
                " CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text "
                # CROSS JOIN fixes the selective FTS-first loop order. Ordinary INNER JOIN lets SQLite
                # start at a root-scoped locator index, then probe the FTS virtual table once per locator
                # (~seconds at 100k / unbounded at NAS scale). FTS → metadata.fts_rowid → entity → current
                # locator is deterministic and sub-millisecond for a selective path token (Phase D).
                "FROM source_intelligence_fts f "
                "CROSS JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
                "CROSS JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id "
                "CROSS JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
                "  AND l.policy_validation_state IS NULL "
                "LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id "
                "WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' "
            )
            params: list[Any] = [match_query]
            if project_key:
                sql += "AND f.aux = ? "
                params.append(project_key)
            sql += "ORDER BY rank LIMIT ?"
            params.append(int(limit))
            rows = c.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            has_text = bool(r[9])
            match_basis, snippet = _derive_match(
                snip_text=r[3], snip_path=r[4], snip_aux=r[5], has_text=has_text
            )
            out.append(
                {
                    "result_type": "source",
                    "source_id": r[6],
                    "path": r[0],
                    "project_key": r[1] or None,
                    "score": float(r[2]),
                    "snippet": snippet,
                    "match_basis": match_basis,
                    "indexed_text_available": has_text,
                    "extraction_status": r[7],
                    "extraction_disposition": _map_disposition(r[8], r[7]),
                }
            )
        return out

    def search_notes(
        self,
        query: str,
        *,
        limit: int = 20,
        path_prefix: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            if not self._fts_available(c):
                return []
            match_query = sanitize_fts_query(query)
            if not match_query:
                return []
            sql = (
                # CA: entity-bound join; returned handle = source_entity_id. Serving-trust EXCLUDE (§6.3).
                "SELECT n.rel_path, n.aux, bm25(obsidian_note_fts) AS rank, "
                " snippet(obsidian_note_fts, 0, '[', ']', '…', 12) AS snip, s.source_entity_id "
                "FROM obsidian_note_fts n "
                "JOIN source_intelligence_metadata m ON m.fts_rowid = n.rowid "
                "JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id "
                "  AND s.source_kind='obsidian_note' "
                "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "  AND l.is_current_locator = 1 AND l.policy_validation_state IS NULL "
                "WHERE obsidian_note_fts MATCH ? AND s.deleted=0 "
            )
            params: list[Any] = [match_query]
            if path_prefix:
                sql += "AND n.rel_path LIKE ? "
                params.append(f"{path_prefix}%")
            sql += "ORDER BY rank LIMIT ?"
            params.append(int(limit))
            rows = c.execute(sql, params).fetchall()
        return [
            {
                "result_type": "obsidian_note",
                "source_id": r[4],
                "path": r[0],
                "tags": r[1] or None,
                "score": float(r[2]),
                "snippet": r[3],
            }
            for r in rows
        ]

    # ----- N8C-12 source-root connector reads (root-aware, keyset-paged) ----------------------
    def search_source_files(
        self,
        query: str,
        *,
        source_root_key: str | None = None,
        file_ext: str | None = None,
        limit: int = 25,
        after: tuple[float, str, str, str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """FTS search over indexed external source files, root-aware and keyset-pageable.

        Unlike ``search_sources`` (N8C-3) this ALWAYS returns ``source_root_key`` + ``file_ext`` in each
        row and supports deterministic keyset continuation. Order is ``bm25 rank`` ascending (best first),
        tie-broken by ``(source_root_key, rel_path, source_id)`` so equal-rank rows have a total order.
        ``after`` is the prior page's last ``(rank, source_root_key, rel_path, source_id)`` tuple; the
        caller fetches ``limit+1`` to detect more pages. Read-only.
        """
        with borrow_connection(conn, self.db_path) as c:
            if not self._fts_available(c):
                return []
            match_query = sanitize_fts_query(query)
            if not match_query:
                return []
            sql = (
                "SELECT src_root, rel, sid, ext, rank, snip_text, snip_path, snip_aux, "
                "       est, disp, has_text FROM ("
                # CA: entity-bound join; displayed root/path from the CURRENT locator; keyset + public
                # `after` tuple key on the entity. Serving-trust EXCLUDE (§6.3): policy-stale filtered out.
                " SELECT COALESCE(l.source_root_key,'') AS src_root, COALESCE(l.rel_path,'') AS rel, "
                "  s.source_entity_id AS sid, m.file_ext AS ext, "
                "  bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, "
                "  snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, "
                "  snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, "
                "  snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, "
                "  m.extraction_status AS est, m.extraction_disposition AS disp, "
                "  CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text "
                # CROSS JOIN is intentional: preserve the selective FTS-first loop order. With ordinary
                # INNER JOIN, SQLite may start at all root locators and probe FTS once per file.
                " FROM source_intelligence_fts f "
                " CROSS JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
                " CROSS JOIN source_intelligence_sources s ON s.source_entity_id = m.source_entity_id "
                " CROSS JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
                "   AND l.is_current_locator = 1 AND l.tombstoned_at IS NULL "
                "   AND l.policy_validation_state IS NULL "
                " LEFT JOIN source_intelligence_text t ON t.source_entity_id = s.source_entity_id "
                " WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' "
            )
            params: list[Any] = [match_query]
            if source_root_key is not None:
                sql += " AND l.source_root_key = ? "
                params.append(source_root_key)
            if file_ext:
                sql += " AND m.file_ext = ? "
                params.append(str(file_ext).lower().lstrip("."))
            sql += ")"
            if after is not None:
                ar, aroot, arel, asid = after
                sql += (
                    " WHERE rank > ? OR (rank = ? AND src_root > ?) "
                    " OR (rank = ? AND src_root = ? AND rel > ?) "
                    " OR (rank = ? AND src_root = ? AND rel = ? AND sid > ?)"
                )
                params += [ar, ar, aroot, ar, aroot, arel, ar, aroot, arel, asid]
            sql += " ORDER BY rank, src_root, rel, sid LIMIT ?"
            params.append(int(limit))
            rows = c.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            has_text = bool(r[10])
            match_basis, snippet = _derive_match(
                snip_text=r[5], snip_path=r[6], snip_aux=r[7], has_text=has_text
            )
            out.append(
                {
                    "source_root_key": r[0],
                    "rel_path": r[1],
                    "source_id": r[2],
                    "file_ext": r[3],
                    "score": float(r[4]),
                    "snippet": snippet,
                    "match_basis": match_basis,
                    "indexed_text_available": has_text,
                    "extraction_status": r[8],
                    "extraction_disposition": _map_disposition(r[9], r[8]),
                }
            )
        return out

    def list_source_files(
        self,
        source_root_key: str,
        *,
        prefix: str | None = None,
        limit: int = 25,
        after: tuple[str, str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Index-backed listing of external source files under one root (optionally a rel_path prefix).

        Stable order ``(rel_path, source_id)`` with keyset ``after`` = the prior page's last
        ``(rel_path, source_id)``. NOT a filesystem scan — reads only indexed rows. Read-only.
        """
        # CA: address/scope/keyset via the CURRENT locator; handle = entity. Serving-trust DEGRADE (§6.3):
        # policy-stale rows are NOT excluded here — they are returned and MARKED (policy_unverified) so a
        # listing degrades rather than hides.
        sql = (
            "SELECT l.source_root_key, l.rel_path, s.source_entity_id, m.file_ext, "
            "       l.policy_validation_state "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 "
            "LEFT JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
            "WHERE s.source_kind='external_file' AND s.deleted=0 AND l.source_root_key = ? "
            "AND l.rel_path IS NOT NULL "
        )
        params: list[Any] = [source_root_key]
        if prefix:
            escaped = str(prefix).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sql += "AND l.rel_path LIKE ? ESCAPE '\\' "
            params.append(f"{escaped}%")
        if after is not None:
            arel, asid = after
            sql += "AND (l.rel_path > ? OR (l.rel_path = ? AND s.source_entity_id > ?)) "
            params += [arel, arel, asid]
        sql += "ORDER BY l.rel_path, s.source_entity_id LIMIT ?"
        params.append(int(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(sql, params).fetchall()
        return [
            {
                "source_root_key": r[0],
                "rel_path": r[1],
                "source_id": r[2],
                "file_ext": r[3],
                "policy_unverified": r[4] is not None,
            }
            for r in rows
        ]

    def distinct_indexed_root_keys(self, *, conn: sqlite3.Connection | None = None) -> list[str]:
        """Distinct, non-null root keys carried by active indexed source rows — the index-recorded
        root truth. Used when the runtime config has no ``external_sources`` configured (e.g. the
        internet-facing serve profile) so roots_list/status still reflect reality. Path-free."""
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                # R8 §5.2 exact form: distinct CURRENT-locator roots (authoritative), never a demoted one.
                "SELECT DISTINCT l.source_root_key FROM source_index_locators l "
                "WHERE l.is_current_locator=1 AND l.tombstoned_at IS NULL "
                "AND l.source_root_key IS NOT NULL ORDER BY l.source_root_key"
            ).fetchall()
        return [str(r[0]) for r in rows]

    def count_source_files(
        self, source_root_key: str | None = None, *, conn: sqlite3.Connection | None = None
    ) -> int:
        """Count of active indexed external source files (optionally scoped to one root)."""
        # CA: scope by the CURRENT locator's root (high-fanout cost NOT_VERIFIED → PC-WI-06A).
        sql = (
            "SELECT COUNT(*) FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "  AND l.is_current_locator = 1 "
            "WHERE s.source_kind='external_file' AND s.deleted=0"
        )
        params: list[Any] = []
        if source_root_key is not None:
            sql += " AND l.source_root_key = ?"
            params.append(source_root_key)
        with borrow_connection(conn, self.db_path) as c:
            return int(c.execute(sql, params).fetchone()[0])

    # ----- status ----------------------------------------------------------------------------
    def index_status(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        with borrow_connection(conn, self.db_path) as c:
            fts = self._fts_available(c)
            by_kind = {
                row[0]: row[1]
                for row in c.execute(
                    "SELECT source_kind, COUNT(*) FROM source_intelligence_sources "
                    "WHERE deleted=0 GROUP BY source_kind"
                ).fetchall()
            }
            total = sum(by_kind.values())
            queued = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='queued'"
            ).fetchone()[0]
            processing = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='processing'"
            ).fetchone()[0]
            errors = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='error'"
            ).fetchone()[0]
            skipped = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_events WHERE status='skipped'"
            ).fetchone()[0]
            skipped_by_code = {
                (row[0] or "unspecified"): row[1]
                for row in c.execute(
                    "SELECT error_code, COUNT(*) FROM source_intelligence_events "
                    "WHERE status='skipped' GROUP BY error_code"
                ).fetchall()
            }
            last_indexed = c.execute(
                "SELECT MAX(indexed_at) FROM source_intelligence_metadata"
            ).fetchone()[0]
            stale_notes = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_generated_notes WHERE generation_status='stale'"
            ).fetchone()[0]
            roots_row = c.execute(
                "SELECT state_value FROM source_intelligence_state WHERE state_key='source_roots'"
            ).fetchone()
            summarized = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[
                0
            ]
            stale_summaries = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_summaries s "
                "JOIN source_intelligence_metadata m ON m.source_entity_id = s.source_entity_id "
                "WHERE s.source_sha256 IS NOT m.content_sha256"
            ).fetchone()[0]
            generated_cards = c.execute(
                "SELECT COUNT(*) FROM source_intelligence_generated_notes "
                "WHERE generation_status='generated'"
            ).fetchone()[0]
            gen_state = {
                row[0]: row[1]
                for row in c.execute(
                    "SELECT state_key, state_value FROM source_intelligence_state "
                    "WHERE state_key IN "
                    "('last_generation_at','last_generation_cards','last_generation_summaries')"
                ).fetchall()
            }
        roots = json.loads(roots_row[0]) if roots_row and roots_row[0] else []
        return {
            "fts_available": fts,
            "sources_total": total,
            "by_kind": by_kind,
            "queued_count": queued,
            "processing_count": processing,
            "error_count": errors,
            "skipped_count": int(skipped),
            "skipped_by_code": skipped_by_code,
            "stale_note_count": stale_notes,
            "summarized_count": int(summarized),
            "stale_summary_count": int(stale_summaries),
            "generated_card_count": int(generated_cards),
            "last_generation_at": gen_state.get("last_generation_at"),
            "last_generation_cards": gen_state.get("last_generation_cards"),
            "last_generation_summaries": gen_state.get("last_generation_summaries"),
            "last_indexed_at": last_indexed,
            "configured_roots": roots,
        }

    def queue_health(self, *, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Operator queue-health signals: stuck-event age + recent-activity timestamps.

        Reads only existing tables (events + the source_intelligence_state k/v rows stamped by
        drain/note/summary); no schema change. ``oldest_processing_age_seconds`` is None when
        nothing is in-flight.
        """
        with borrow_connection(conn, self.db_path) as c:
            counts = {
                status: c.execute(
                    "SELECT COUNT(*) FROM source_intelligence_events WHERE status=?", (status,)
                ).fetchone()[0]
                for status in ("queued", "processing", "error", "done")
            }
            oldest_age = c.execute(
                "SELECT (julianday('now') - julianday(MIN(updated_at))) * 86400 "
                "FROM source_intelligence_events WHERE status='processing'"
            ).fetchone()[0]
            last_event_at = c.execute(
                "SELECT MAX(created_at) FROM source_intelligence_events"
            ).fetchone()[0]
            state = {
                row[0]: row[1]
                for row in c.execute(
                    "SELECT state_key, state_value FROM source_intelligence_state "
                    "WHERE state_key IN ('last_drain_at','last_note_at','last_summary_at')"
                ).fetchall()
            }
        return {
            "queued_count": counts["queued"],
            "processing_count": counts["processing"],
            "error_count": counts["error"],
            "done_count": counts["done"],
            "oldest_processing_age_seconds": (
                round(float(oldest_age), 1) if oldest_age is not None else None
            ),
            "last_event_at": last_event_at,
            "last_drain_at": state.get("last_drain_at"),
            "last_note_at": state.get("last_note_at"),
            "last_summary_at": state.get("last_summary_at"),
        }
