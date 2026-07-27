"""Deterministic kill-mid-``apply()`` child harness for the PC-WI-03 atomicity proof (PCR-005).

Run as a subprocess in a **fresh interpreter** (never imported into the parent test process). It opens
a validated legacy source-index fixture and begins the migrator's *single* atomic-transaction
``apply()``. A ``sqlite3`` trace-callback provides the **deterministic barrier**: when the
``schema_migrations`` ledger INSERT for ``--barrier-version`` is about to execute — a version strictly
above the fixture origin, so it genuinely runs inside the open, uncommitted transaction with earlier
post-origin migrations already applied-but-uncommitted — the harness atomically publishes an IPC signal
file and then blocks in ``signal.pause()``, holding the transaction open until the parent process
SIGKILLs it mid-transaction.

The barrier is the IPC file (an inter-process signal), **never a timing sleep**: the parent waits for
the file, then terminates the child; the child's post-signal ``pause()`` merely holds the open
transaction until that termination. If the barrier version is never reached, ``apply()`` runs to
completion and the process exits 0 — which the parent's harness self-test treats as a vacuous proof
(the migration finished before interruption), failing the test rather than passing it.

This module performs no migration of a managed/production database, no backup/restore, and no network
access. It only migrates the caller-supplied rehearsal fixture it is pointed at.
"""

from __future__ import annotations

import argparse
import os
import signal
import sqlite3


def _run(db: str, signal_path: str, barrier_version: int) -> int:
    from hb_assistant.store.migrator import SQLiteMigrator

    conn = sqlite3.connect(db)
    marker = f"VALUES ({barrier_version},"
    state = {"fired": False}

    def _trace(statement: str) -> None:
        # The trace callback fires *before* each statement executes. The ledger INSERT
        # ``... VALUES (<barrier_version>, '...', ?)`` is unique to that version's migration and only
        # runs when the version is above the fixture origin (idempotent apply() skips already-present
        # versions), so matching it means the transaction is open with earlier post-origin migrations
        # already applied but not yet committed.
        if not state["fired"] and marker in statement:
            state["fired"] = True
            tmp = signal_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write("barrier-reached\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, signal_path)  # atomic publish of the IPC barrier signal
            signal.pause()  # hold the open transaction until the parent SIGKILLs this process

    conn.set_trace_callback(_trace)
    # Completes only if the barrier version was never reached (a vacuous proof the parent rejects).
    SQLiteMigrator(db_path=db).apply(conn=conn)
    conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC-WI-03 kill-mid-apply atomicity child harness")
    parser.add_argument("--db", required=True, help="rehearsal fixture database path")
    parser.add_argument("--signal", required=True, help="IPC barrier signal file to publish")
    parser.add_argument(
        "--barrier-version",
        type=int,
        required=True,
        help="ledger version whose INSERT triggers the barrier (must exceed the fixture origin)",
    )
    args = parser.parse_args(argv)
    return _run(args.db, args.signal, args.barrier_version)


if __name__ == "__main__":
    raise SystemExit(main())
