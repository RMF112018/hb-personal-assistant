"""Phase 09 Prompt 08 — automation / delivery receipt proof (read-only).

Verifies that a controlled automation run has persisted **metadata-only** delivery /
notification / HTML-render / open / agent-run / launchd receipts with **no external
delivery**: every no-raw / no-writeback ``CHECK(... = 0)`` guard column sums to zero, the
delivery / notification channels are pinned to local artifacts (``obsidian_vault`` /
``local_macos``), the launchd schedule mode is ``dry_run``, and ``external_writeback_performed``
is zero across every receipt table.

Read-only — opens the database read-only and never writes. Database-path agnostic so it can
run over a controlled proof DB or a temporary test DB.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

# Receipt tables + their local-only channel/mode pinning (None = no such column).
_RECEIPT_TABLES: tuple[dict[str, Any], ...] = (
    {
        "table": "daily_brief_delivery_receipts",
        "channel_col": "delivery_channel",
        "channel_allowed": {"obsidian_vault"},
        "mode_col": "mode",
        "mode_allowed": {"dry_run", "apply"},
    },
    {
        "table": "daily_brief_notification_receipts",
        "channel_col": "channel",
        "channel_allowed": {"local_macos"},
        "mode_col": "mode",
        "mode_allowed": {"dry_run", "apply"},
    },
    {
        "table": "daily_brief_html_render_receipts",
        "channel_col": None,
        "channel_allowed": set(),
        "mode_col": "mode",
        "mode_allowed": {"dry_run", "apply"},
    },
    {
        "table": "daily_brief_open_receipts",
        "channel_col": "open_target",
        "channel_allowed": {"vault", "html"},
        "mode_col": "mode",
        "mode_allowed": {"dry_run", "apply"},
    },
    {
        "table": "second_brain_agent_run_receipts",
        "channel_col": None,
        "channel_allowed": set(),
        "mode_col": None,
        "mode_allowed": set(),
    },
    {
        "table": "second_brain_run_registry",
        "channel_col": None,
        "channel_allowed": set(),
        "mode_col": None,
        "mode_allowed": set(),
    },
    {
        "table": "launchd_schedule_previews",
        "channel_col": None,
        "channel_allowed": set(),
        "mode_col": "mode",
        "mode_allowed": {"dry_run"},
    },
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        c
        for c in (r[1] for r in conn.execute(f"PRAGMA table_info({table})"))
        if c.endswith("_persisted") or c.endswith("_performed")
    ]


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def build_automation_delivery_proof(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only automation / delivery receipt proof.

    Returns per-table receipt counts, guard-column sums (all must be 0), channel/mode pinning
    results, an ``external_writeback_performed`` sum (must be 0), and the ``populated`` /
    ``proof_passed`` verdicts. Never writes.
    """
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        tables: dict[str, Any] = {}
        guard_violation = False
        channel_violation = False
        external_writeback_total = 0
        delivery_count = 0
        agent_run_count = 0
        total_receipts = 0

        for spec in _RECEIPT_TABLES:
            table = spec["table"]
            if not _table_exists(conn, table):
                tables[table] = {"present": False}
                continue
            cols = _columns(conn, table)
            count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            total_receipts += count

            guards = _guard_columns(conn, table)
            guard_sum = 0
            if guards and count:
                expr = "+".join(f"COALESCE(SUM({c}),0)" for c in guards)
                guard_sum = int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
            if guard_sum != 0:
                guard_violation = True
            if "external_writeback_performed" in cols and count:
                external_writeback_total += int(
                    conn.execute(
                        f"SELECT COALESCE(SUM(external_writeback_performed),0) FROM {table}"
                    ).fetchone()[0]
                )

            # Channel / mode pinning (local-only).
            channels: list[str] = []
            ch_col = spec["channel_col"]
            if ch_col and ch_col in cols and count:
                channels = [
                    str(r[0]) for r in conn.execute(f"SELECT DISTINCT {ch_col} FROM {table}")
                ]
                if not set(channels) <= spec["channel_allowed"]:
                    channel_violation = True
            modes: list[str] = []
            mode_col = spec["mode_col"]
            if mode_col and mode_col in cols and count:
                modes = [
                    str(r[0]) for r in conn.execute(f"SELECT DISTINCT {mode_col} FROM {table}")
                ]
                if spec["mode_allowed"] and not set(modes) <= spec["mode_allowed"]:
                    channel_violation = True

            tables[table] = {
                "present": True,
                "count": count,
                "guard_columns": len(guards),
                "guard_sum": guard_sum,
                "channels": channels,
                "modes": modes,
            }
            if table == "daily_brief_delivery_receipts":
                delivery_count = count
            if table == "second_brain_agent_run_receipts":
                agent_run_count = count

        populated = delivery_count >= 1 and agent_run_count >= 1
        no_external = external_writeback_total == 0
        proof_passed = (
            populated
            and not guard_violation
            and not channel_violation
            and no_external
            and schema_version == LATEST_SCHEMA_VERSION
        )
        return {
            "proof": "phase_09_automation_delivery",
            "schema_version": schema_version,
            "schema_version_expected": LATEST_SCHEMA_VERSION,
            "populated": populated,
            "proof_passed": proof_passed,
            "total_receipts": total_receipts,
            "delivery_receipt_count": delivery_count,
            "agent_run_receipt_count": agent_run_count,
            "guard_violation": guard_violation,
            "channel_or_mode_violation": channel_violation,
            "external_writeback_total": external_writeback_total,
            "no_external_delivery": no_external,
            "tables": tables,
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "no_external_delivery": no_external,
                "local_channels_only": not channel_violation,
            },
        }
    finally:
        conn.close()
