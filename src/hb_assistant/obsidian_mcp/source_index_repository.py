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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction
from hb_assistant.store.source_intelligence_tables import fts5_available

from .source_connector_models import sanitize_fts_query
from .source_skip_codes import normalize_skip_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            # Deactivate file sources whose root is no longer configured/enabled.
            known = {
                row[0]
                for row in c.execute(
                    "SELECT DISTINCT source_root_key FROM source_intelligence_sources "
                    "WHERE source_root_key IS NOT NULL"
                ).fetchall()
            }
            for stale_key in known - active_keys:
                c.execute(
                    "UPDATE source_intelligence_sources SET active=0, updated_at=? WHERE source_root_key=?",
                    (_now(), stale_key),
                )

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
        sql = (
            "SELECT s.source_id, m.content_sha256, m.mtime_ns, m.fts_rowid, s.deleted, m.size_bytes "
            "FROM source_intelligence_sources s "
            "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
            "WHERE s.source_kind=? AND s.rel_path=?"
        )
        params: list[Any] = [source_kind, rel_path]
        if source_root_key is not None:
            sql += " AND s.source_root_key=?"
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
                    "SELECT rel_path FROM source_intelligence_sources "
                    "WHERE source_root_key=? AND rel_path IS NOT NULL AND deleted=0",
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
                "SELECT s.rel_path, m.mtime_ns, m.size_bytes "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "WHERE s.source_kind='external_file' AND s.source_root_key=? "
                "AND s.rel_path IS NOT NULL AND s.deleted=0",
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
                # Disposition is the explicit V122 column when present, else mapped from the legacy
                # extraction_status (NO row-wide backfill — mapped at read time). metadata_searchable =
                # has a path/project FTS row; content_searchable = has NONEMPTY indexed text.
                "SELECT COALESCE(m.extraction_disposition, CASE m.extraction_status "
                "   WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' "
                "   WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' "
                "   ELSE 'metadata_only' END) AS disp, "
                " m.extraction_status AS st, "
                " SUM(CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 "
                "          THEN 1 ELSE 0 END) AS searchable, "
                " SUM(CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END) AS has_fts, "
                " COUNT(*) AS n "
                "FROM source_intelligence_sources s "
                "JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "LEFT JOIN source_intelligence_text t ON t.source_id = s.source_id "
                "WHERE s.source_kind='external_file' AND s.source_root_key=? AND s.deleted=0 "
                "GROUP BY disp, st",
                (source_root_key,),
            ).fetchall()

        # Positional access (disp=0, st=1, searchable=2, has_fts=3, n=4) — independent of row_factory.
        def _sum(pred: Any) -> int:
            return sum(int(r[4]) for r in rows if pred(r))

        total = sum(int(r[4]) for r in rows)
        searchable = sum(int(r[2] or 0) for r in rows)
        metadata_searchable = sum(int(r[3] or 0) for r in rows)
        content_extracted = _sum(lambda r: r[1] == "ok")
        content_eligible = _sum(lambda r: r[0] == "content")
        content_pending = _sum(lambda r: r[0] == "content" and r[1] == "pending")
        intentional_metadata_only = _sum(lambda r: r[0] == "metadata_only")
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
            "failed": _sum(lambda r: r["st"] == "failed"),
            "unsupported": _sum(lambda r: r["disp"] == "unsupported"),
            "too_large": _sum(lambda r: r["disp"] == "too_large"),
        }

    def list_root_file_sources(
        self, source_root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Active external_file sources under a root: (source_id, rel_path, project_number).

        Used by conservative, same-root referenced-sheet matching (never global cross-root).
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT source_id, rel_path, project_number FROM source_intelligence_sources "
                "WHERE source_kind='external_file' AND source_root_key=? AND rel_path IS NOT NULL "
                "AND deleted=0",
                (source_root_key,),
            ).fetchall()
        return [{"source_id": r[0], "rel_path": r[1], "project_number": r[2]} for r in rows]

    def list_relationships(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """Outgoing relationships for a source, with the target rel_path resolved for 'source' kinds."""
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT r.dst_kind, r.dst_ref, r.relation, r.confidence, r.evidence_json, s.rel_path "
                "FROM source_intelligence_relationships r "
                "LEFT JOIN source_intelligence_sources s "
                "  ON r.dst_kind='source' AND s.source_id = r.dst_ref "
                "WHERE r.src_source_id=? ORDER BY r.created_at",
                (source_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for dst_kind, dst_ref, relation, confidence, evidence_json, dst_rel_path in rows:
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
        source_id: str,
        relationships: list[dict[str, Any]],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Upsert outgoing relationship rows for a source (UNIQUE guard dedupes). Additive."""
        if not relationships:
            return
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            for rel in relationships:
                c.execute(
                    "INSERT INTO source_intelligence_relationships "
                    "(relationship_id, src_source_id, dst_kind, dst_ref, relation, confidence, "
                    " evidence_json, created_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(src_source_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                    (
                        uuid.uuid4().hex,
                        source_id,
                        rel["dst_kind"],
                        rel["dst_ref"],
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
        source_id = source_id_for(
            source_kind, source_root_key=record.get("source_root_key"), rel_path=rel_path
        )
        now = _now()
        preserve = bool(record.get("preserve_content"))
        existing = c.execute(
            "SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_id=?",
            (source_id,),
        ).fetchone()
        old_fts_rowid = existing[0] if existing else None

        # Generation stamp (V122): a metadata observation stamps last_seen_generation/last_seen_at so
        # generation-based reconciliation can tell "seen this generation" from "gone". A CHANGED file
        # moves updated_at (material change); a preserve REPAIR of an unchanged file must NOT move
        # updated_at (it would defeat the reconciliation guard / needlessly re-stale notes).
        gen = record.get("last_seen_generation")
        last_seen_at = now if gen is not None else None
        # The policy fingerprint the row is now current under (V122): written in BOTH modes so the next
        # generation can fast-skip only when the row is current for CURRENT policy. COALESCE-preserve on a
        # NULL keeps a legacy row's prior value untouched (a bare re-observe with no fingerprint context).
        fingerprint = record.get("last_indexed_fingerprint")
        if preserve:
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, source_root_key, rel_path, abs_path_hash, "
                " project_key, project_number, active, deleted, created_at, updated_at, "
                " last_seen_generation, last_seen_at, last_indexed_fingerprint) "
                "VALUES (?,?,?,?,?,?,?,1,0,?,?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                # Authoritatively refresh derived identity fields (abs_path_hash after a root-path change,
                # project routing after a matcher change) — but NEVER updated_at (a preserve is not a
                # material change). Content columns are untouched below.
                " source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, "
                " project_key=excluded.project_key, project_number=excluded.project_number, "
                " active=1, deleted=0, "
                " last_seen_generation=COALESCE(excluded.last_seen_generation, source_intelligence_sources.last_seen_generation), "
                " last_seen_at=COALESCE(excluded.last_seen_at, source_intelligence_sources.last_seen_at), "
                " last_indexed_fingerprint=COALESCE(excluded.last_indexed_fingerprint, source_intelligence_sources.last_indexed_fingerprint)",
                (
                    source_id,
                    source_kind,
                    record.get("source_root_key"),
                    rel_path,
                    record.get("abs_path_hash"),
                    record.get("project_key"),
                    record.get("project_number"),
                    now,
                    now,
                    gen,
                    last_seen_at,
                    fingerprint,
                ),
            )
        else:
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, source_root_key, rel_path, abs_path_hash, "
                " project_key, project_number, active, deleted, created_at, updated_at, "
                " last_seen_generation, last_seen_at, last_indexed_fingerprint) "
                "VALUES (?,?,?,?,?,?,?,1,0,?,?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                " source_root_key=excluded.source_root_key, abs_path_hash=excluded.abs_path_hash, "
                " project_key=excluded.project_key, "
                " project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at, "
                " last_seen_generation=COALESCE(excluded.last_seen_generation, source_intelligence_sources.last_seen_generation), "
                " last_seen_at=COALESCE(excluded.last_seen_at, source_intelligence_sources.last_seen_at), "
                # Authoritative in replace mode: a reprocess re-stamps the fingerprint the row is now current under.
                " last_indexed_fingerprint=COALESCE(excluded.last_indexed_fingerprint, source_intelligence_sources.last_indexed_fingerprint)",
                (
                    source_id,
                    source_kind,
                    record.get("source_root_key"),
                    rel_path,
                    record.get("abs_path_hash"),
                    record.get("project_key"),
                    record.get("project_number"),
                    now,
                    now,
                    gen,
                    last_seen_at,
                    fingerprint,
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
                "SELECT text_excerpt FROM source_intelligence_text WHERE source_id=?", (source_id,)
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
                "(source_id, file_ext, size_bytes, mtime_ns, extraction_status, fts_rowid, "
                " indexed_at, extraction_disposition) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                " file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
                # Authoritative: point at the rebuilt FTS row and re-stamp disposition to current policy
                # (extraction_status + content columns are deliberately NOT touched — content is unchanged).
                " fts_rowid=excluded.fts_rowid, "
                " extraction_disposition=excluded.extraction_disposition, "
                " indexed_at=excluded.indexed_at",
                (
                    source_id,
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
                "WHERE src_source_id=? AND relation='belongs_to_project'",
                (source_id,),
            )
            for rel in record.get("relationships") or []:
                c.execute(
                    "INSERT INTO source_intelligence_relationships "
                    "(relationship_id, src_source_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(src_source_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                    " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                    (
                        uuid.uuid4().hex,
                        source_id,
                        rel["dst_kind"],
                        rel["dst_ref"],
                        rel["relation"],
                        rel.get("confidence"),
                        json.dumps(rel.get("evidence")) if rel.get("evidence") else None,
                        now,
                    ),
                )
            return source_id

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
            "(source_id, file_ext, size_bytes, mtime_ns, content_sha256, page_count, "
            " paragraph_count, sheet_count, extraction_status, extraction_failure_code, fts_rowid, "
            " indexed_at, extraction_disposition, content_indexed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(source_id) DO UPDATE SET "
            " file_ext=excluded.file_ext, size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
            " content_sha256=excluded.content_sha256, page_count=excluded.page_count, "
            " paragraph_count=excluded.paragraph_count, sheet_count=excluded.sheet_count, "
            " extraction_status=excluded.extraction_status, extraction_failure_code=excluded.extraction_failure_code, "
            " fts_rowid=excluded.fts_rowid, indexed_at=excluded.indexed_at, "
            " extraction_disposition=excluded.extraction_disposition, "
            # Authoritative in replace mode: NULL clears a stale stamp when valid content no longer exists.
            " content_indexed_at=excluded.content_indexed_at",
            (
                source_id,
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
                "(source_id, text_excerpt, excerpt_char_count, excerpt_truncated, full_text_sha256, "
                " text_vault_ref, raw_body_persisted, redaction_applied, updated_at) "
                "VALUES (?,?,?,?,?,?,0,1,?) "
                "ON CONFLICT(source_id) DO UPDATE SET "
                " text_excerpt=excluded.text_excerpt, excerpt_char_count=excluded.excerpt_char_count, "
                " excerpt_truncated=excluded.excerpt_truncated, full_text_sha256=excluded.full_text_sha256, "
                " text_vault_ref=excluded.text_vault_ref, updated_at=excluded.updated_at",
                (
                    source_id,
                    record.get("text_excerpt"),
                    record.get("excerpt_char_count", 0),
                    1 if record.get("excerpt_truncated") else 0,
                    record.get("full_text_sha256"),
                    record.get("text_vault_ref"),
                    now,
                ),
            )
        else:
            c.execute("DELETE FROM source_intelligence_text WHERE source_id=?", (source_id,))

        # chunks (replace set)
        c.execute("DELETE FROM source_intelligence_chunks WHERE source_id=?", (source_id,))
        for ordinal, chunk in enumerate(record.get("chunks") or []):
            c.execute(
                "INSERT INTO source_intelligence_chunks "
                "(chunk_id, source_id, ordinal, chunk_text, char_count, raw_body_persisted, created_at) "
                "VALUES (?,?,?,?,?,0,?)",
                (f"{source_id}:{ordinal}", source_id, ordinal, chunk, len(chunk), now),
            )

        # relationships — REPLACEMENT-based for project edges: a reprocess/transition drops the source's
        # existing belongs_to_project rows before re-asserting the current set, so a reclassification never
        # leaves an obsolete project relationship attached (additive ON CONFLICT alone could not remove one).
        c.execute(
            "DELETE FROM source_intelligence_relationships "
            "WHERE src_source_id=? AND relation='belongs_to_project'",
            (source_id,),
        )
        for rel in record.get("relationships") or []:
            c.execute(
                "INSERT INTO source_intelligence_relationships "
                "(relationship_id, src_source_id, dst_kind, dst_ref, relation, confidence, evidence_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(src_source_id, dst_kind, dst_ref, relation) DO UPDATE SET "
                " confidence=excluded.confidence, evidence_json=excluded.evidence_json",
                (
                    uuid.uuid4().hex,
                    source_id,
                    rel["dst_kind"],
                    rel["dst_ref"],
                    rel["relation"],
                    rel.get("confidence"),
                    json.dumps(rel.get("evidence")) if rel.get("evidence") else None,
                    now,
                ),
            )
        return source_id

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
        """Create a LINK row to an existing domain record (email/procore/schedule). No body re-ingest."""
        source_id = source_id_for(
            source_kind, domain_ref_table=domain_ref_table, domain_ref_id=domain_ref_id
        )
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_sources "
                "(source_id, source_kind, domain_ref_table, domain_ref_id, project_key, project_number, "
                " active, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,1,0,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET project_key=excluded.project_key, "
                " project_number=excluded.project_number, active=1, deleted=0, updated_at=excluded.updated_at",
                (
                    source_id,
                    source_kind,
                    domain_ref_table,
                    domain_ref_id,
                    project_key,
                    project_number,
                    now,
                    now,
                ),
            )
        return source_id

    def mark_deleted(
        self,
        source_kind: str,
        rel_path: str,
        *,
        source_root_key: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        sql = (
            "SELECT s.source_id, m.fts_rowid FROM source_intelligence_sources s "
            "LEFT JOIN source_intelligence_metadata m ON m.source_id=s.source_id "
            "WHERE s.source_kind=? AND s.rel_path=?"
        )
        params: list[Any] = [source_kind, rel_path]
        if source_root_key is not None:
            sql += " AND s.source_root_key=?"
            params.append(source_root_key)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            row = c.execute(sql, tuple(params)).fetchone()
            if row is None:
                return
            source_id, fts_rowid = row[0], row[1]
            if fts_rowid is not None and self._fts_available(c):
                fts_table = (
                    "source_intelligence_fts"
                    if source_kind == "external_file"
                    else "obsidian_note_fts"
                )
                c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
            c.execute(
                "UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_id=?",
                (_now(), source_id),
            )
            self._mark_generated_notes_stale(c, source_id)

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
            "SELECT s.source_id, m.fts_rowid FROM source_intelligence_sources s "
            "LEFT JOIN source_intelligence_metadata m ON m.source_id=s.source_id "
            "WHERE s.source_kind=? AND s.rel_path=?"
        )
        deleted = 0
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            fts_ok = self._fts_available(c)
            for rel_path in rel_paths:
                sql = base_sql
                params: list[Any] = [source_kind, rel_path]
                if source_root_key is not None:
                    sql += " AND s.source_root_key=?"
                    params.append(source_root_key)
                row = c.execute(sql, tuple(params)).fetchone()
                if row is None:
                    continue
                source_id, fts_rowid = row[0], row[1]
                if fts_rowid is not None and fts_ok:
                    c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
                c.execute(
                    "UPDATE source_intelligence_sources "
                    "SET deleted=1, active=0, updated_at=? WHERE source_id=?",
                    (_now(), source_id),
                )
                self._mark_generated_notes_stale(c, source_id)
                deleted += 1
        return deleted

    def _mark_generated_notes_stale(self, c: sqlite3.Connection, source_id: str) -> None:
        c.execute(
            "UPDATE source_intelligence_generated_notes SET generation_status='stale', updated_at=? "
            "WHERE source_id=? AND generation_status='generated'",
            (_now(), source_id),
        )

    def mark_generated_notes_stale(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._mark_generated_notes_stale(c, source_id)

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
                "SELECT s.rel_path, m.mtime_ns, m.size_bytes, "
                " CASE WHEN m.fts_rowid IS NOT NULL THEN 1 ELSE 0 END AS has_fts, "
                # Read-time legacy mapping (matches content_status_counts); NULL disposition is derived
                # from the legacy extraction_status so a fast-skip comparison sees the effective value.
                " COALESCE(m.extraction_disposition, CASE m.extraction_status "
                "   WHEN 'ok' THEN 'content' WHEN 'failed' THEN 'content' "
                "   WHEN 'unsupported' THEN 'unsupported' WHEN 'skipped_too_large' THEN 'too_large' "
                "   ELSE 'metadata_only' END) AS disp, "
                " s.project_key AS project_key, s.project_number AS project_number, "
                " s.last_indexed_fingerprint AS fingerprint, "
                # Content storage mode: plaintext excerpt vs encrypted-to-vault ref vs none. Lets the walker
                # detect BOTH a sensitive root holding plaintext AND a plain root holding a vault ref.
                " COALESCE((SELECT CASE "
                "   WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 'plain' "
                "   WHEN t.text_vault_ref IS NOT NULL AND LENGTH(t.text_vault_ref) > 0 THEN 'vault' "
                "   ELSE 'none' END FROM source_intelligence_text t "
                "   WHERE t.source_id = s.source_id), 'none') AS content_mode "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "WHERE s.source_kind='external_file' AND s.source_root_key=? AND s.deleted=0 "
                f"AND s.rel_path IN ({placeholders})",
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
        sql = (
            "UPDATE source_intelligence_sources SET last_seen_generation=?, last_seen_at=? "
            "WHERE source_kind='external_file' AND source_root_key=? AND deleted=0 "
            f"AND rel_path IN ({placeholders})"
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
        sql = (
            "SELECT source_id, rel_path FROM source_intelligence_sources "
            "WHERE source_kind='external_file' AND source_root_key=? AND deleted=0 "
            "AND (last_seen_generation IS NULL OR last_seen_generation != ?) "
            "AND julianday(updated_at) <= julianday(?) "
        )
        params: list[Any] = [source_root_key, generation_id, generation_started_at]
        if after_source_id is not None:
            sql += "AND source_id > ? "
            params.append(after_source_id)
        sql += "ORDER BY source_id LIMIT ?"
        params.append(int(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(sql, tuple(params)).fetchall()
        return [(r[0], r[1]) for r in rows]

    def mark_deleted_by_source_id(
        self,
        source_id: str,
        *,
        source_kind: str = "external_file",
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
    ) -> None:
        """Delete-reconcile a single confirmed-absent source: drop its FTS row (path + content), mark it
        deleted/inactive, and mark generated notes stale. ``in_transaction=True`` (requires ``conn``) runs
        on the caller's open txn so a reconcile batch's deletes + cursor checkpoint commit atomically."""
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            self._mark_deleted_by_source_id_locked(conn, source_id, source_kind)
            return
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            self._mark_deleted_by_source_id_locked(c, source_id, source_kind)

    def _mark_deleted_by_source_id_locked(
        self, c: sqlite3.Connection, source_id: str, source_kind: str
    ) -> None:
        row = c.execute(
            "SELECT m.fts_rowid FROM source_intelligence_metadata m WHERE m.source_id=?",
            (source_id,),
        ).fetchone()
        fts_rowid = row[0] if row else None
        if fts_rowid is not None and self._fts_available(c):
            fts_table = (
                "source_intelligence_fts" if source_kind == "external_file" else "obsidian_note_fts"
            )
            c.execute(f"DELETE FROM {fts_table} WHERE rowid=?", (fts_rowid,))
        c.execute(
            "UPDATE source_intelligence_sources SET deleted=1, active=0, updated_at=? WHERE source_id=?",
            (_now(), source_id),
        )
        self._mark_generated_notes_stale(c, source_id)

    def apply_confirmed_same_root_move(
        self,
        root_key: str,
        old_rel_path: str,
        new_rel_path: str,
        dest_metadata: dict[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Transactionally record a CONFIRMED same-root file rename/move (Phase B / B4).

        Invariant: the old row cannot become non-current unless the destination row + lineage are durably
        persisted in the SAME transaction — on any failure the whole move rolls back and the old row stays
        current. The move carries ONLY lineage (``renamed_from_source_id``): extraction/content trust is
        NOT carried forward (a filesystem move does not prove byte identity), so the destination row is
        (re)written with the current dest metadata and ``extraction_status='pending'`` and its inherited
        generated-note links are marked ``stale`` (inherited-but-unverified) pending re-extraction. The
        caller is responsible for confirming the destination is present first and for enqueuing
        re-extraction of ``new_rel_path``.

        Returns ``{old_source_id, new_source_id, linked}`` — ``linked`` is False when no current old row
        existed (then this is a plain create with no predecessor)."""
        old_sid = source_id_for("external_file", source_root_key=root_key, rel_path=old_rel_path)
        new_sid = source_id_for("external_file", source_root_key=root_key, rel_path=new_rel_path)
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            old_present = c.execute(
                "SELECT 1 FROM source_intelligence_sources WHERE source_id=? AND deleted=0",
                (old_sid,),
            ).fetchone() is not None
            lineage = old_sid if old_present else None
            # Destination row + lineage first — if this fails the txn rolls back and the old row is intact.
            c.execute(
                "INSERT INTO source_intelligence_sources"
                "(source_id, source_kind, source_root_key, rel_path, active, deleted, "
                " renamed_from_source_id, created_at, updated_at) VALUES(?,?,?,?,1,0,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET active=1, deleted=0, "
                " renamed_from_source_id=excluded.renamed_from_source_id, updated_at=excluded.updated_at",
                (new_sid, "external_file", root_key, new_rel_path, lineage, now, now),
            )
            # Destination metadata = current dest stat; content trust invalidated (extraction pending).
            c.execute(
                "INSERT INTO source_intelligence_metadata"
                "(source_id, file_ext, size_bytes, mtime_ns, content_sha256, extraction_status, "
                " fts_rowid, indexed_at) VALUES(?,?,?,?,?, 'pending', NULL, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET file_ext=excluded.file_ext, "
                " size_bytes=excluded.size_bytes, mtime_ns=excluded.mtime_ns, "
                " extraction_status='pending', indexed_at=excluded.indexed_at",
                (new_sid, dest_metadata.get("file_ext"), dest_metadata.get("size_bytes"),
                 dest_metadata.get("mtime_ns"), "", now),
            )
            if old_present:
                # Inherited-but-unverified: relink the old row's generated notes to the new row as 'stale'
                # (an explicit status, not an implied null) so they are not advertised as current content.
                c.execute(
                    "UPDATE OR IGNORE source_intelligence_generated_notes "
                    "SET source_id=?, generation_status='stale', updated_at=? WHERE source_id=?",
                    (new_sid, now, old_sid),
                )
                # Old row becomes non-current only now that the destination + lineage are persisted.
                self._mark_deleted_by_source_id_locked(c, old_sid, "external_file")
        return {"old_source_id": old_sid, "new_source_id": new_sid, "linked": old_present}

    def find_successor_source_id(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> str | None:
        """Return the current successor of a renamed/moved source (the active row whose
        ``renamed_from_source_id`` is ``source_id``), or None. Used to answer an old source_ref as
        ``moved`` rather than a bare deleted/unavailable."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT source_id FROM source_intelligence_sources "
                "WHERE renamed_from_source_id=? AND deleted=0 AND active=1 LIMIT 1",
                (source_id,),
            ).fetchone()
        return row[0] if row else None

    # ----- source detail + generated-note tracking (source cards) ----------------------------
    def get_source_detail(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        """Joined sources+metadata+text row for rendering a source card. None if absent."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT s.source_id, s.source_kind, s.source_root_key, s.rel_path, s.domain_ref_table, "
                "  s.domain_ref_id, s.project_key, s.project_number, s.deleted, "
                "  m.file_ext, m.size_bytes, m.mtime_ns, m.content_sha256, m.page_count, "
                "  m.paragraph_count, m.sheet_count, m.extraction_status, m.indexed_at, "
                "  t.text_excerpt, t.excerpt_char_count, t.excerpt_truncated, t.text_vault_ref "
                "FROM source_intelligence_sources s "
                "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
                "LEFT JOIN source_intelligence_text t ON t.source_id = s.source_id "
                "WHERE s.source_id = ?",
                (source_id,),
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
        source_id: str,
        note_rel_path: str,
        status: str,
        generated_at: str,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_generated_notes "
                "(generated_note_id, source_id, note_rel_path, generation_status, generated_at, updated_at) "
                "VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_id, note_rel_path) DO UPDATE SET "
                " generation_status=excluded.generation_status, generated_at=excluded.generated_at, "
                " updated_at=excluded.updated_at",
                (uuid.uuid4().hex, source_id, note_rel_path, status, generated_at, _now()),
            )
            if status == "generated":
                self._set_state(c, "last_note_at", _now())

    def has_generated_note(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> bool:
        """True if a card was ever generated for this source (status generated or stale)."""
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT 1 FROM source_intelligence_generated_notes "
                "WHERE source_id=? AND generation_status IN ('generated','stale') LIMIT 1",
                (source_id,),
            ).fetchone()
        return row is not None

    def list_stale_generated_notes(
        self, limit: int = 25, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT source_id, note_rel_path FROM source_intelligence_generated_notes "
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
                "SELECT g.generated_note_id, g.source_id, g.note_rel_path, g.generation_status, "
                "       s.rel_path, s.source_kind "
                "FROM source_intelligence_generated_notes g "
                "JOIN source_intelligence_sources s ON s.source_id = g.source_id "
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
                "SELECT g.source_id, g.generation_status, g.generated_at, "
                "       s.source_kind, s.rel_path, s.source_root_key, s.deleted, s.active "
                "FROM source_intelligence_generated_notes g "
                "JOIN source_intelligence_sources s ON s.source_id = g.source_id "
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
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        """All generated-note rows for a ``source_id`` (any status), oldest-updated first.

        Read-only; the basis for duplicate-card and card-state detection. One source SHOULD have one
        active (generated/stale) card row; more than one is a duplicate the caller flags.
        """
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT generated_note_id, note_rel_path, generation_status, generated_at, updated_at "
                "FROM source_intelligence_generated_notes WHERE source_id=? ORDER BY updated_at",
                (source_id,),
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
        self, source_id: str, receipt: dict[str, Any], *, conn: sqlite3.Connection | None = None
    ) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                "INSERT INTO source_intelligence_summaries "
                "(source_id, model_provider, model_name, prompt_version, prompt_sha256, "
                " summary_sha256, source_sha256, advisory, generated_at) "
                "VALUES (?,?,?,?,?,?,?,1,?) "
                "ON CONFLICT(source_id) DO UPDATE SET model_provider=excluded.model_provider, "
                " model_name=excluded.model_name, prompt_version=excluded.prompt_version, "
                " prompt_sha256=excluded.prompt_sha256, summary_sha256=excluded.summary_sha256, "
                " source_sha256=excluded.source_sha256, generated_at=excluded.generated_at",
                (
                    source_id,
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

    def delete_summary(self, source_id: str, *, conn: sqlite3.Connection | None = None) -> None:
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute("DELETE FROM source_intelligence_summaries WHERE source_id=?", (source_id,))

    def get_summary(
        self, source_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            row = c.execute(
                "SELECT model_provider, model_name, prompt_version, prompt_sha256, summary_sha256, "
                " source_sha256, generated_at FROM source_intelligence_summaries WHERE source_id=?",
                (source_id,),
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
                "JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
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
        conn: sqlite3.Connection | None = None,
    ) -> str:
        event_id = uuid.uuid4().hex
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            # Coalesce: if an identical queued event for this path exists, reuse it (debounce backstop).
            if rel_path is not None:
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
                "(event_id, source_id, rel_path, source_root_key, event_type, status, attempts, created_at, updated_at) "
                "VALUES (?,?,?,?,?,'queued',0,?,?)",
                (event_id, source_id, rel_path, source_root_key, event_type, now, now),
            )
        return event_id

    def claim_queued(
        self, limit: int = 50, *, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            rows = c.execute(
                "SELECT event_id, source_id, rel_path, source_root_key, event_type FROM source_intelligence_events "
                "WHERE status='queued' ORDER BY created_at LIMIT ?",
                (int(limit),),
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
                "SELECT f.rel_path, f.aux, bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, "
                " snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, "
                " snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, "
                " snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, "
                " s.source_id, m.extraction_status, m.extraction_disposition, "
                " CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text "
                "FROM source_intelligence_fts f "
                "JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
                "JOIN source_intelligence_sources s ON s.source_id = m.source_id "
                "LEFT JOIN source_intelligence_text t ON t.source_id = s.source_id "
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
                "SELECT n.rel_path, n.aux, bm25(obsidian_note_fts) AS rank, "
                " snippet(obsidian_note_fts, 0, '[', ']', '…', 12) AS snip, s.source_id "
                "FROM obsidian_note_fts n "
                "JOIN source_intelligence_metadata m ON m.fts_rowid = n.rowid "
                "JOIN source_intelligence_sources s ON s.source_id = m.source_id AND s.source_kind='obsidian_note' "
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
                " SELECT COALESCE(s.source_root_key,'') AS src_root, COALESCE(s.rel_path,'') AS rel, "
                "  s.source_id AS sid, m.file_ext AS ext, "
                "  bm25(source_intelligence_fts, 1.0, 8.0, 12.0) AS rank, "
                "  snippet(source_intelligence_fts, 0, '[', ']', '…', 12) AS snip_text, "
                "  snippet(source_intelligence_fts, 1, '[', ']', '…', 12) AS snip_path, "
                "  snippet(source_intelligence_fts, 2, '[', ']', '…', 12) AS snip_aux, "
                "  m.extraction_status AS est, m.extraction_disposition AS disp, "
                "  CASE WHEN t.text_excerpt IS NOT NULL AND LENGTH(t.text_excerpt) > 0 THEN 1 ELSE 0 END AS has_text "
                " FROM source_intelligence_fts f "
                " JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
                " JOIN source_intelligence_sources s ON s.source_id = m.source_id "
                " LEFT JOIN source_intelligence_text t ON t.source_id = s.source_id "
                " WHERE source_intelligence_fts MATCH ? AND s.deleted=0 AND s.source_kind='external_file' "
            )
            params: list[Any] = [match_query]
            if source_root_key is not None:
                sql += " AND s.source_root_key = ? "
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
        sql = (
            "SELECT s.source_root_key, s.rel_path, s.source_id, m.file_ext "
            "FROM source_intelligence_sources s "
            "LEFT JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
            "WHERE s.source_kind='external_file' AND s.deleted=0 AND s.source_root_key = ? "
            "AND s.rel_path IS NOT NULL "
        )
        params: list[Any] = [source_root_key]
        if prefix:
            escaped = str(prefix).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            sql += "AND s.rel_path LIKE ? ESCAPE '\\' "
            params.append(f"{escaped}%")
        if after is not None:
            arel, asid = after
            sql += "AND (s.rel_path > ? OR (s.rel_path = ? AND s.source_id > ?)) "
            params += [arel, arel, asid]
        sql += "ORDER BY s.rel_path, s.source_id LIMIT ?"
        params.append(int(limit))
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(sql, params).fetchall()
        return [
            {"source_root_key": r[0], "rel_path": r[1], "source_id": r[2], "file_ext": r[3]}
            for r in rows
        ]

    def distinct_indexed_root_keys(self, *, conn: sqlite3.Connection | None = None) -> list[str]:
        """Distinct, non-null root keys carried by active indexed source rows — the index-recorded
        root truth. Used when the runtime config has no ``external_sources`` configured (e.g. the
        internet-facing serve profile) so roots_list/status still reflect reality. Path-free."""
        with borrow_connection(conn, self.db_path) as c:
            rows = c.execute(
                "SELECT DISTINCT source_root_key FROM source_intelligence_sources "
                "WHERE source_root_key IS NOT NULL AND deleted=0 ORDER BY source_root_key"
            ).fetchall()
        return [str(r[0]) for r in rows]

    def count_source_files(
        self, source_root_key: str | None = None, *, conn: sqlite3.Connection | None = None
    ) -> int:
        """Count of active indexed external source files (optionally scoped to one root)."""
        sql = (
            "SELECT COUNT(*) FROM source_intelligence_sources "
            "WHERE source_kind='external_file' AND deleted=0"
        )
        params: list[Any] = []
        if source_root_key is not None:
            sql += " AND source_root_key = ?"
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
                "JOIN source_intelligence_metadata m ON m.source_id = s.source_id "
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
