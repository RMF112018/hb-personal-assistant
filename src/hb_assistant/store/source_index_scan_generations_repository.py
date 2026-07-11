"""Reader/writer for the V122 ``source_index_scan_generations`` table — the SOLE generation-lifecycle
authority.

A *scan generation* spans many bounded V119 passes over one root. This repository owns every piece of
generation state: the ownership lease (``active_run_id`` + ``owner_heartbeat_at``), the traversal cursor
(``cursor_json``), the reconciliation checkpoint (``reconcile_cursor_json``), the ``policy_fingerprint``,
and every status transition. No generation lifecycle logic lives in ``SourceIndexRepository`` or the
bootstrap repository; the only cross-repo coupling is the connection-aware ``insert_pass_row`` primitive
(imported from ``source_index_bootstrap_repository``) which links each V119 pass to its generation inside
this module's ``BEGIN IMMEDIATE`` pass-start transaction.

Key invariants (approved plan):

* **Stale-lease recovery preserves progress.** A stale owner (``active_run_id`` set + ``owner_heartbeat_at``
  older than the lease) is *released* — the generation reverts to ``partial``/``reconcile_pending`` with its
  committed cursor preserved, never ``abandoned``. An idle ``partial``/``reconcile_pending`` (``active_run_id``
  NULL) is NEVER stale-reaped. ``abandoned`` is reserved for invalid cursor/fingerprint/root state.
* **One active generation per root** is an atomic DB invariant (partial-unique index) enforced under
  ``BEGIN IMMEDIATE`` so two processes cannot resume the same partial and a killed process cannot
  permanently block the root.
* **No false completeness.** ``completed`` requires the metadata walk AND deletion reconciliation to have
  finished; a survivor that was only refreshed-but-unresolved leaves the generation ``reconcile_pending``.
* **No infinite partial loops.** A no-forward-progress condition (high-fanout / generation ceiling) is
  ``failed`` (bounded error code, no reconciliation), never a reopened ``partial``.

No absolute host paths: ``root_key`` is opaque, ``root_path_hash`` is a hash.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from hb_assistant.store.connection import borrow_connection, transaction
from hb_assistant.store.source_index_bootstrap_repository import insert_pass_row

# Counter columns a caller may set (absolute running totals, not deltas).
_GEN_COUNTER_COLUMNS: frozenset[str] = frozenset(
    {"files_observed", "metadata_upserted", "files_unchanged", "errors_count", "deleted_count"}
)

# Terminal ``failed`` error codes that signal NO FORWARD PROGRESS under the current config: the plan's
# lifecycle contract requires a relevant policy/configuration change or an explicit operator restart before
# a new generation may start — an unchanged high-fanout directory or generation ceiling must NOT silently
# create + fail a fresh generation on every scheduled pass. ``empty_root_guard`` (the lost-mount blast-radius
# sentinel) is documented as requiring operator confirmation, so it belongs here too: a vanished mount must
# not spawn a fresh failed generation every scheduled scan — recovery is an explicit restart (or a real
# policy change). Any OTHER failure code auto-retries normally.
_NO_PROGRESS_ERROR_CODES: frozenset[str] = frozenset(
    {"directory_fanout_limit", "generation_ceiling", "empty_root_guard"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _immediate_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run an explicit ``BEGIN IMMEDIATE`` transaction on a borrowed connection.

    Acquires the write lock up front so the atomic pass-start claim races correctly under WAL. Toggles
    the connection to autocommit for explicit BEGIN/COMMIT control and restores the prior isolation
    level on exit. The connection is never closed here (lifecycle belongs to the caller).
    """
    prev = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.isolation_level = prev


class SourceIndexScanGenerationsRepository:
    """Durable per-root scan-generation lifecycle: leases, cursor, reconcile checkpoint, status."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else None

    # ----- reads -----------------------------------------------------------------------------
    def get_generation(
        self, generation_id: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_scan_generations WHERE generation_id=?",
                (generation_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_active_generation(
        self, root_key: str, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, Any] | None:
        """Return the single active (running|partial|reconcile_pending) generation for a root, if any."""
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_scan_generations WHERE root_key=? AND "
                "status IN ('running','partial','reconcile_pending') "
                "ORDER BY started_at DESC, rowid DESC LIMIT 1",
                (root_key,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_generations(
        self,
        root_key: str | None = None,
        *,
        limit: int = 50,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            if root_key is None:
                rows = c.execute(
                    "SELECT * FROM source_index_scan_generations "
                    "ORDER BY started_at DESC, rowid DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM source_index_scan_generations WHERE root_key=? "
                    "ORDER BY started_at DESC, rowid DESC LIMIT ?",
                    (root_key, int(limit)),
                ).fetchall()
        return [dict(r) for r in rows]

    def latest_generations(
        self, *, conn: sqlite3.Connection | None = None
    ) -> dict[str, dict[str, Any]]:
        """Return the NEWEST generation per root, keyed by ``root_key`` — one row per root, uncapped.

        Health/readiness must derive from EACH root's own latest generation. A global ``list_generations``
        cap could evict a root's latest row when other roots have many generations, so this uses a
        per-root correlated ``MAX`` (started_at, rowid) instead of a bounded newest-first scan (finding 5)."""
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT g.* FROM source_index_scan_generations g "
                "WHERE g.rowid = ("
                "  SELECT g2.rowid FROM source_index_scan_generations g2 "
                "  WHERE g2.root_key = g.root_key "
                "  ORDER BY g2.started_at DESC, g2.rowid DESC LIMIT 1)"
            ).fetchall()
        return {r["root_key"]: dict(r) for r in rows}

    def prune_generations(
        self,
        root_key: str | None = None,
        *,
        keep: int = 20,
        dry_run: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Bounded, FAIL-CLOSED retention: keep at most ``keep`` most-recent generation rows PER ROOT,
        pruning older terminal rows so ``source_index_scan_generations`` never grows unbounded.

        Two rows are ALWAYS retained regardless of ``keep`` (so trust/lifecycle can never be pruned):

        * the ACTIVE generation (``running`` / ``partial`` / ``reconcile_pending``) — a live pass owns it;
        * the latest COMPLETED generation — the authoritative row health + watcher readiness derive from,
          and the one current source rows reference via ``last_seen_generation``.

        ``keep`` floors at 1. ``root_key=None`` prunes every root. ``dry_run`` reports counts without
        deleting. Older ``failed``/``abandoned``/superseded-``completed`` rows beyond the window are removed;
        their linked V119 pass rows keep their (now-dangling, soft) ``generation_id`` — no FK, no cascade."""
        keep = max(1, int(keep))
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.row_factory = sqlite3.Row
            if root_key is None:
                roots = [
                    r[0]
                    for r in c.execute(
                        "SELECT DISTINCT root_key FROM source_index_scan_generations"
                    ).fetchall()
                ]
            else:
                roots = [root_key]
            pruned_by_root: dict[str, int] = {}
            for rk in roots:
                rows = c.execute(
                    "SELECT generation_id, status FROM source_index_scan_generations "
                    "WHERE root_key=? ORDER BY started_at DESC, rowid DESC",
                    (rk,),
                ).fetchall()
                keep_ids = {r["generation_id"] for r in rows[:keep]}
                # ALWAYS retain the active generation (there is at most one per root by the partial index).
                keep_ids.update(
                    r["generation_id"]
                    for r in rows
                    if r["status"] in ("running", "partial", "reconcile_pending")
                )
                # ALWAYS retain the latest COMPLETED generation (rows are newest-first).
                for r in rows:
                    if r["status"] == "completed":
                        keep_ids.add(r["generation_id"])
                        break
                delete_ids = [r["generation_id"] for r in rows if r["generation_id"] not in keep_ids]
                if delete_ids and not dry_run:
                    c.executemany(
                        "DELETE FROM source_index_scan_generations WHERE generation_id=?",
                        [(g,) for g in delete_ids],
                    )
                pruned_by_root[rk] = len(delete_ids)
        return {
            "keep": keep,
            "dry_run": dry_run,
            "pruned_by_root": pruned_by_root,
            "total_pruned": sum(pruned_by_root.values()),
        }

    # ----- atomic pass-start -----------------------------------------------------------------
    def begin_generation_pass(
        self,
        root_key: str,
        run_id: str,
        *,
        policy_fingerprint: str,
        root_path_hash: str,
        traversal_version: int = 1,
        mode: str = "bootstrap",
        stale_lease_seconds: float = 120.0,
        restart: bool = False,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim/resume-or-create a generation for ``root_key`` and link a new V119 pass.

        Returns a dict describing the claimed generation (``generation_id``, ``status='running'``,
        ``resumed``, ``cursor_json``, ``reconcile_cursor_json``, ``metadata_walk_completed_at``), or a
        BLOCKED sentinel ``{"blocked": True, "generation_id", "status": "failed", "last_error_code"}`` when
        the latest generation ``failed`` with a no-forward-progress code under the SAME policy (see below),
        or ``None`` if a LIVE pass (fresh lease) already owns the root — a retryable conflict, not fatal.

        No-forward-progress suppression (plan lifecycle contract): if there is no resumable generation and
        the latest ``failed`` generation for this root has the SAME ``root_path_hash`` + ``traversal_version``
        + ``policy_fingerprint`` and a no-forward-progress ``last_error_code`` (high-fanout / generation
        ceiling), a new generation is NOT created — recovery requires a policy/configuration change (which
        changes the fingerprint and lifts the block automatically) or an explicit ``restart=True`` operator
        action. Otherwise an unchanged pathological root would create + fail a fresh generation every pass.

        Runs under ``BEGIN IMMEDIATE`` so the claim is mutually exclusive across processes.
        """
        with borrow_connection(conn, self.db_path) as c, _immediate_transaction(c):
            c.row_factory = sqlite3.Row
            now = _now()
            active = c.execute(
                "SELECT * FROM source_index_scan_generations WHERE root_key=? AND "
                "status IN ('running','partial','reconcile_pending') "
                "ORDER BY started_at DESC, rowid DESC LIMIT 1",
                (root_key,),
            ).fetchone()

            generation_id: str
            resumed = False
            if active is not None:
                active = dict(active)
                has_live_owner = bool(active["active_run_id"]) and not self._lease_stale(
                    c, active["owner_heartbeat_at"], now, stale_lease_seconds
                )
                if has_live_owner:
                    # A live pass owns this generation. Do not touch it; caller retries later.
                    return None
                if active["active_run_id"]:
                    # Stale owner: RELEASE ownership, preserving cursor/progress (never abandon here).
                    self._release_owner_row(c, active, now)
                # Fingerprint / traversal / root validation.
                if (
                    active["policy_fingerprint"] != policy_fingerprint
                    or int(active["traversal_version"]) != int(traversal_version)
                    or active["root_path_hash"] != root_path_hash
                ):
                    # Invalid / incompatible generation → abandon (no reconciliation), then create fresh.
                    c.execute(
                        "UPDATE source_index_scan_generations SET status='abandoned', "
                        "active_run_id=NULL, finished_at=?, updated_at=?, "
                        "last_error_code='fingerprint_changed' WHERE generation_id=?",
                        (now, now, active["generation_id"]),
                    )
                    active = None
                else:
                    generation_id = active["generation_id"]
                    resumed = True
                    c.execute(
                        "UPDATE source_index_scan_generations SET status='running', "
                        "active_run_id=?, owner_heartbeat_at=?, updated_at=? WHERE generation_id=?",
                        (run_id, now, now, generation_id),
                    )

            if active is None:
                # No resumable generation. Before creating a fresh one, honor a no-forward-progress
                # terminal failure: an unchanged high-fanout / generation-ceiling failure must not be
                # silently retried every pass. A matching failed generation (same root/traversal/fingerprint
                # + no-progress code) BLOCKS restart unless the operator forced ``restart=True``. A policy
                # change makes the fingerprint differ → not matched → a fresh generation starts (recovery).
                if not restart:
                    # Block on the AUTHORITATIVE LATEST generation overall, never the latest *failed* row:
                    # a newer ``completed`` (explicit-restart recovery) or ``abandoned`` (fingerprint-changed
                    # recovery) after a no-progress failure must LIFT the block. Filtering to status='failed'
                    # would skip past that newer row and resurrect a stale failure forever (round-7 blocker 1).
                    # (Reached only when ``active is None``, so the latest row here is always terminal.)
                    latest = c.execute(
                        "SELECT * FROM source_index_scan_generations WHERE root_key=? "
                        "ORDER BY started_at DESC, rowid DESC LIMIT 1",
                        (root_key,),
                    ).fetchone()
                    if latest is not None:
                        latest = dict(latest)
                        same_policy = (
                            latest["status"] == "failed"
                            and latest["policy_fingerprint"] == policy_fingerprint
                            and int(latest["traversal_version"]) == int(traversal_version)
                            and latest["root_path_hash"] == root_path_hash
                        )
                        if same_policy and latest["last_error_code"] in _NO_PROGRESS_ERROR_CODES:
                            return {
                                "blocked": True,
                                "generation_id": latest["generation_id"],
                                "status": "failed",
                                "last_error_code": latest["last_error_code"],
                            }
                generation_id = uuid.uuid4().hex
                c.execute(
                    "INSERT INTO source_index_scan_generations "
                    "(generation_id, root_key, status, traversal_version, root_path_hash, "
                    " policy_fingerprint, active_run_id, owner_heartbeat_at, started_at, updated_at) "
                    "VALUES (?,?,'running',?,?,?,?,?,?,?)",
                    (
                        generation_id,
                        root_key,
                        int(traversal_version),
                        root_path_hash,
                        policy_fingerprint,
                        run_id,
                        now,
                        now,
                        now,
                    ),
                )

            # Close any orphaned still-'running' V119 pass rows for this root so the partial-unique
            # "one active run per root" slot is free, then insert the linked pass in the SAME txn.
            c.execute(
                "UPDATE source_index_bootstrap_runs SET status='interrupted', finished_at=? "
                "WHERE root_key=? AND status='running'",
                (now, root_key),
            )
            insert_pass_row(
                c,
                run_id=run_id,
                root_key=root_key,
                mode=mode,
                generation_id=generation_id,
                now=now,
            )
            gen = dict(
                c.execute(
                    "SELECT * FROM source_index_scan_generations WHERE generation_id=?",
                    (generation_id,),
                ).fetchone()
            )
        gen["resumed"] = resumed
        gen["run_id"] = run_id
        return gen

    @staticmethod
    def _lease_stale(
        c: sqlite3.Connection, heartbeat_at: str | None, now: str, stale_seconds: float
    ) -> bool:
        if not heartbeat_at:
            return True
        row = c.execute(
            "SELECT (julianday(?) - julianday(?)) * 86400 > ?",
            (now, heartbeat_at, float(stale_seconds)),
        ).fetchone()
        return bool(row[0])

    @staticmethod
    def _release_owner_row(c: sqlite3.Connection, active: dict[str, Any], now: str) -> None:
        """Release a stale owner: revert running→partial/reconcile_pending, preserve cursor, clear lease.

        The old owning V119 pass (if still ``running``) is marked ``interrupted``.
        """
        status = active["status"]
        if status == "running":
            status = "reconcile_pending" if active["metadata_walk_completed_at"] else "partial"
        c.execute(
            "UPDATE source_index_scan_generations SET status=?, active_run_id=NULL, updated_at=? "
            "WHERE generation_id=?",
            (status, now, active["generation_id"]),
        )
        if active["active_run_id"]:
            c.execute(
                "UPDATE source_index_bootstrap_runs SET status='interrupted', finished_at=? "
                "WHERE run_id=? AND status='running'",
                (now, active["active_run_id"]),
            )

    # ----- cursor / reconcile checkpoints -----------------------------------------------------
    def advance_cursor(
        self,
        generation_id: str,
        run_id: str,
        *,
        cursor_json: str | None,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
        **counters: int,
    ) -> int:
        """Checkpoint the traversal cursor + absolute counters + heartbeat. Returns the affected rowcount.

        Called AFTER (or, with ``in_transaction=True``, WITHIN the same txn AS) the batch's metadata writes,
        so the cursor never advances past uncommitted metadata (a crash merely re-processes the batch —
        idempotent — never skips it). The lease guard (``active_run_id=run_id AND status='running'``) means
        a rowcount of **0** signals this run LOST ownership (stale-lease takeover) — the caller must abort
        the pass rather than keep writing under a lease it no longer holds. ``in_transaction=True`` (requires
        ``conn``) runs on the caller's open txn so the checkpoint commits atomically with the batch."""
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            return self._apply_advance(conn, generation_id, run_id, "cursor_json", cursor_json, counters)
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            return self._apply_advance(c, generation_id, run_id, "cursor_json", cursor_json, counters)

    def advance_reconcile_cursor(
        self,
        generation_id: str,
        run_id: str,
        *,
        reconcile_cursor_json: str | None,
        conn: sqlite3.Connection | None = None,
        in_transaction: bool = False,
        **counters: int,
    ) -> int:
        """Checkpoint the reconciliation keyset position + counters. Returns the affected rowcount (0 =
        lease lost; abort). ``in_transaction=True`` runs on the caller's open txn."""
        if in_transaction:
            if conn is None:
                raise ValueError("in_transaction=True requires an open conn")
            return self._apply_advance(
                conn, generation_id, run_id, "reconcile_cursor_json", reconcile_cursor_json, counters
            )
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            return self._apply_advance(
                c, generation_id, run_id, "reconcile_cursor_json", reconcile_cursor_json, counters
            )

    @staticmethod
    def _apply_advance(
        c: sqlite3.Connection,
        generation_id: str,
        run_id: str,
        cursor_col: str,
        cursor_val: str | None,
        counters: dict[str, int],
    ) -> int:
        unknown = set(counters) - _GEN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown generation counter columns: {sorted(unknown)}")
        sets = [f"{cursor_col}=?", "owner_heartbeat_at=?", "updated_at=?"]
        now = _now()
        vals: list[Any] = [cursor_val, now, now]
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        cur = c.execute(
            f"UPDATE source_index_scan_generations SET {', '.join(sets)} "
            "WHERE generation_id=? AND active_run_id=? AND status='running'",
            (*vals, generation_id, run_id),
        )
        return cur.rowcount or 0

    # ----- standalone heartbeat (best-effort, own txn) ----------------------------------------
    def heartbeat(
        self,
        generation_id: str,
        run_id: str,
        *,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> None:
        unknown = set(counters) - _GEN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown generation counter columns: {sorted(unknown)}")
        sets = ["owner_heartbeat_at=?", "updated_at=?"]
        now = _now()
        vals: list[Any] = [now, now]
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            c.execute(
                f"UPDATE source_index_scan_generations SET {', '.join(sets)} "
                "WHERE generation_id=? AND active_run_id=? AND status='running'",
                (*vals, generation_id, run_id),
            )

    # ----- terminal / phase transitions -------------------------------------------------------
    def mark_metadata_walk_complete(
        self,
        generation_id: str,
        run_id: str,
        *,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> int:
        """Metadata walk finished (status stays ``running``); reconciliation runs next.

        Lease-fenced: the ``active_run_id=run_id AND status='running'`` guard means a rowcount of **0**
        signals this run LOST ownership before it could mark the walk complete (a stale-lease takeover). The
        caller MUST treat 0 as a conflict and abort — otherwise it would proceed to reconcile/complete a
        generation whose walk-completion write never landed (finding 6)."""
        unknown = set(counters) - _GEN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown generation counter columns: {sorted(unknown)}")
        now = _now()
        sets = ["metadata_walk_completed_at=?", "owner_heartbeat_at=?", "updated_at=?"]
        vals: list[Any] = [now, now, now]
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                f"UPDATE source_index_scan_generations SET {', '.join(sets)} "
                "WHERE generation_id=? AND active_run_id=? AND status='running'",
                (*vals, generation_id, run_id),
            )
            return cur.rowcount or 0

    def mark_partial(
        self,
        generation_id: str,
        run_id: str,
        *,
        cursor_json: str | None = None,
        last_error_code: str | None = None,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> int:
        """A per-pass bound (or a suspend on an unresolved file / unreadable directory) stopped the walk:
        status→``partial``, lease released, cursor preserved. ``last_error_code`` records the suspend
        reason (e.g. ``directory_read_error`` / ``metadata_walk_error``) without failing the generation.

        Ownership-guarded (``active_run_id=run_id``): a rowcount of **0** means a stale-lease takeover
        already claimed this generation, so the caller MUST treat it as a lost-lease conflict rather than
        reporting an authoritative ``partial`` the new owner never wrote (round-7 blocker 3)."""
        return self._terminate(
            generation_id,
            run_id,
            status="partial",
            cursor_json=cursor_json,
            last_error_code=last_error_code,
            conn=conn,
            counters=counters,
        )

    def mark_reconcile_pending(
        self,
        generation_id: str,
        run_id: str,
        *,
        reconcile_cursor_json: str | None = None,
        last_error_code: str | None = None,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> int:
        """Metadata walk done but reconciliation not finished: status→``reconcile_pending`` (resumable
        without re-walking), lease released, reconcile checkpoint preserved.

        Ownership-guarded: a rowcount of **0** means the lease was taken over — the caller must treat it as
        a lost-lease conflict, not an authoritative ``reconcile_pending`` (round-7 blocker 3)."""
        return self._terminate(
            generation_id,
            run_id,
            status="reconcile_pending",
            reconcile_cursor_json=reconcile_cursor_json,
            last_error_code=last_error_code,
            conn=conn,
            counters=counters,
        )

    def finish_completed(
        self,
        generation_id: str,
        run_id: str,
        *,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> int:
        """Metadata walk + reconciliation both finished: status→``completed``.

        Lease-fenced (``require_running``): only a still-``running`` generation this run still owns can be
        completed, and the affected rowcount is returned. A rowcount of **0** means the lease was lost after
        the final batch — the caller MUST NOT report completion (finding 6)."""
        return self._terminate(
            generation_id,
            run_id,
            status="completed",
            set_reconciliation_completed=True,
            set_finished=True,
            require_running=True,
            conn=conn,
            counters=counters,
        )

    def fail_generation(
        self,
        generation_id: str,
        run_id: str,
        *,
        last_error_code: str,
        conn: sqlite3.Connection | None = None,
        **counters: int,
    ) -> int:
        """No-forward-progress / unrecoverable: status→``failed`` (NO reconciliation, requires a
        config/fingerprint change or explicit restart — never silently reopened as ``partial``).

        Ownership-guarded: a rowcount of **0** means the lease was taken over — the caller must treat it as
        a lost-lease conflict, not an authoritative ``failed`` (round-7 blocker 3)."""
        return self._terminate(
            generation_id,
            run_id,
            status="failed",
            last_error_code=last_error_code,
            set_finished=True,
            conn=conn,
            counters=counters,
        )

    def abandon_generation(
        self,
        generation_id: str,
        run_id: str,
        *,
        last_error_code: str = "abandoned",
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Invalid/unvalidatable cursor/fingerprint/root: status→``abandoned`` (NO reconciliation).

        Lease-fenced (``active_run_id=run_id AND status='running'``), returns the affected rowcount. Cursor
        validation performs filesystem operations, so a lease can expire and be taken over WHILE it runs;
        without this fence the old worker could abandon the NEW owner's generation. A rowcount of 0 means the
        lease was lost — the caller must treat it as a conflict, not an abandonment."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                "UPDATE source_index_scan_generations SET status='abandoned', active_run_id=NULL, "
                "finished_at=?, updated_at=?, last_error_code=? "
                "WHERE generation_id=? AND active_run_id=? AND status='running'",
                (now, now, last_error_code, generation_id, run_id),
            )
            return cur.rowcount or 0

    def release_owner(
        self, generation_id: str, run_id: str, *, conn: sqlite3.Connection | None = None
    ) -> None:
        """Interrupt backstop: if this run still owns a ``running`` generation, revert to
        ``partial``/``reconcile_pending`` (preserving cursor) and clear the lease."""
        now = _now()
        with borrow_connection(conn, self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM source_index_scan_generations WHERE generation_id=? "
                "AND active_run_id=? AND status='running'",
                (generation_id, run_id),
            ).fetchone()
            if row is None:
                return
            status = "reconcile_pending" if row["metadata_walk_completed_at"] else "partial"
            with transaction(c):
                c.execute(
                    "UPDATE source_index_scan_generations SET status=?, active_run_id=NULL, "
                    "updated_at=? WHERE generation_id=? AND active_run_id=?",
                    (status, now, generation_id, run_id),
                )

    def _terminate(
        self,
        generation_id: str,
        run_id: str,
        *,
        status: str,
        cursor_json: str | None = None,
        reconcile_cursor_json: str | None = None,
        last_error_code: str | None = None,
        set_reconciliation_completed: bool = False,
        set_finished: bool = False,
        require_running: bool = False,
        conn: sqlite3.Connection | None = None,
        counters: dict[str, int] | None = None,
    ) -> int:
        """Apply a terminal/phase transition; returns the affected rowcount.

        ``require_running`` adds ``AND status='running'`` to the lease guard so a state that certifies
        forward progress (completion) can only be written by the run that still owns a live generation — a
        rowcount of 0 then signals a lost lease. The give-up transitions (partial / reconcile_pending /
        failed) omit the ``status='running'`` predicate (a resumed generation may already be partial), but
        are still ownership-guarded by ``active_run_id`` and now RETURN the rowcount: a 0 there is a
        stale-lease takeover the caller must report as a conflict, not silently no-op (round-7 blocker 3)."""
        counters = counters or {}
        unknown = set(counters) - _GEN_COUNTER_COLUMNS
        if unknown:
            raise ValueError(f"unknown generation counter columns: {sorted(unknown)}")
        now = _now()
        sets = ["status=?", "active_run_id=NULL", "updated_at=?"]
        vals: list[Any] = [status, now]
        if cursor_json is not None:
            sets.append("cursor_json=?")
            vals.append(cursor_json)
        if reconcile_cursor_json is not None:
            sets.append("reconcile_cursor_json=?")
            vals.append(reconcile_cursor_json)
        if last_error_code is not None:
            sets.append("last_error_code=?")
            vals.append(last_error_code)
        if set_reconciliation_completed:
            sets.append("reconciliation_completed_at=?")
            vals.append(now)
        if set_finished:
            sets.append("finished_at=?")
            vals.append(now)
        for col, val in counters.items():
            sets.append(f"{col}=?")
            vals.append(int(val))
        where = "WHERE generation_id=? AND active_run_id=?"
        if require_running:
            where += " AND status='running'"
        with borrow_connection(conn, self.db_path) as c, transaction(c):
            cur = c.execute(
                f"UPDATE source_index_scan_generations SET {', '.join(sets)} {where}",
                (*vals, generation_id, run_id),
            )
            return cur.rowcount or 0
