"""Targeted tests for actions CLI (Phase 14 Prompt 02).

- CLI grammar (--help)
- JSON shape/contract for extract/list
- Redaction (no full content/PII/bodies in outputs)
- Dry-run safety: before/after row counts on action_items + source_links identical (direct SQL seeding per project patterns)

Uses CliRunner + existing store connection patterns. No full email/file bodies in code or asserts.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app as cli_app
from hb_assistant.store import get_connection, transaction
from hb_assistant.store.errors import StoreReadinessError


runner = CliRunner()


def test_actions_cli_grammar_help():
    """Group and subcommands respond to --help (grammar check)."""
    res = runner.invoke(cli_app, ["actions", "--help"])
    assert res.exit_code == 0
    assert "extract" in res.output or "Action intelligence" in res.output

    res2 = runner.invoke(cli_app, ["actions", "extract", "--help"])
    assert res2.exit_code == 0
    assert "--dry-run" in res2.output

    res3 = runner.invoke(cli_app, ["actions", "list", "--help"])
    assert res3.exit_code == 0


def test_actions_extract_dry_run_json_shape_and_redaction():
    """--dry-run --json produces expected contract + redacted output (no full content)."""
    res = runner.invoke(cli_app, ["actions", "extract", "--dry-run", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["command"] == "actions extract"
    assert data["dry_run"] is True
    assert "results" in data
    assert "would_persist" in data
    assert "note" in data
    assert "dry-run" in data["note"].lower()
    # Redaction / no full content
    out_str = res.output
    assert "full body" not in out_str.lower()
    assert "secret" not in out_str.lower()  # no PII leakage


def test_actions_list_json_shape():
    """list --json produces contract (redacted)."""
    res = runner.invoke(cli_app, ["actions", "list", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["command"] == "actions list"
    assert "results" in data
    assert "note" in data
    assert "open actions" in data.get("note", "").lower() or "open" in str(data.get("results", [])).lower()


def test_actions_extract_dry_run_no_mutation_via_direct_sql():
    """Provable dry-run safety using direct SQL seeding + before/after counts (per project test patterns)."""
    conn = get_connection()
    # Ensure minimal schema for isolated test conn (action_items + source_links)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stable_key TEXT NOT NULL UNIQUE,
            action_type TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            title TEXT NOT NULL,
            due_date TEXT,
            confidence REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_source_record_id INTEGER,
            to_source_record_id INTEGER,
            action_item_id INTEGER,
            link_type TEXT NOT NULL,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Seed minimal via direct SQL (as used in existing tests for action_items + source_links)
    with transaction(conn):
        conn.execute(
            "INSERT OR IGNORE INTO action_items (stable_key, action_type, title, confidence, status) VALUES (?, ?, ?, ?, ?)",
            ("test:seed:001", "task", "Test seed item for dry-run safety", 0.7, "open"),
        )
    before_ai = conn.execute("SELECT COUNT(*) FROM action_items").fetchone()[0]
    before_sl = conn.execute("SELECT COUNT(*) FROM source_links").fetchone()[0]

    # Run the CLI in dry-run (default) — must not change counts
    res = runner.invoke(cli_app, ["actions", "extract", "--dry-run", "--json"])
    assert res.exit_code == 0

    after_ai = conn.execute("SELECT COUNT(*) FROM action_items").fetchone()[0]
    after_sl = conn.execute("SELECT COUNT(*) FROM source_links").fetchone()[0]

    assert after_ai == before_ai, "Dry-run must not insert action_items"
    assert after_sl == before_sl, "Dry-run must not insert source_links"
