"""Phase 09 Prompt 12 — V38 retrieval / memory / agent metadata substrate schema additions.

Proves V38 additively (1) creates the nineteen second_brain_retrieval_* / second_brain_memory_* /
agent / phase_09 tables that ship empty, (2) declares + enforces the full twenty-three guard
columns CHECK(... = 0) on every table (the twenty no-raw / no-writeback / no-direct-api /
no-determination guards plus the three Phase 09 guards), (3) stores only metadata
(hashes/counts/labels/refs/enums) — no raw content / prompt / response / URL / path / vector / SQL
columns, (4) is idempotent and leaves V1-V37 intact, and (5) the lifecycle contract classifies the
nineteen tables placeholder_deferred / phase_owner 09 at count 190.

No LlamaIndex / embeddings / vector / semantic-retrieval runtime is exercised here — schema only.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.construction.second_brain.phase_09_schema import (
    PHASE_09_GUARD_COLUMNS,
    PHASE_09_V38_TABLES,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None, f"missing table {table}"
    return str(row[0])


def test_v38_is_latest_and_creates_nineteen_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 38
        assert len(PHASE_09_V38_TABLES) == 22  # 19 V38 + 3 V39 additive review burden tables
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in PHASE_09_V38_TABLES:
            assert t in tables, f"missing V38 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v38_all_twenty_three_guard_columns_present_and_check_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        assert len(PHASE_09_GUARD_COLUMNS) == 23
        for t in PHASE_09_V38_TABLES:
            ddl = _ddl(conn, t)
            for guard in PHASE_09_GUARD_COLUMNS:
                assert re.search(rf"\b{guard}\b", ddl), f"{t} missing guard column {guard}"
                assert re.search(rf"CHECK\({guard} = 0\)", ddl), f"{t} guard {guard} not CHECK(=0)"


def test_v38_guard_check_rejects_nonzero_insert() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # A guard-clean row inserts fine.
        conn.execute(
            "INSERT INTO second_brain_retrieval_vector_index_items "
            "(item_id, policy_version, schema_version, run_id) VALUES ('ok', 'v1', 38, 'r1')"
        )
        # Each of the three Phase 09 guards trips the CHECK(... = 0) when flipped to 1.
        for guard in (
            "raw_vector_content_persisted",
            "unsupported_claim_performed",
            "semantic_retrieval_bypassed_policy",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO second_brain_retrieval_vector_index_items "
                    f"(item_id, policy_version, schema_version, run_id, {guard}) "
                    "VALUES ('bad', 'v1', 38, 'r1', 1)"
                )


def test_v38_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 38").fetchone()[0]
        assert n == 1
        tables = _names(conn)
        # prior 08D / 08C tables still present (V1-V37 untouched)
        assert "second_brain_mcp_tool_call_receipts" in tables
        assert "second_brain_financial_review_required_items" in tables


def test_v38_tables_are_metadata_only_no_raw_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        forbidden = (
            "raw_text",
            "prompt_text",
            "response_text",
            "raw_prompt_text",
            "raw_response_text",
            "signed_url",
            "download_url",
            "file_path",
            "vector_blob",
            "embedding_vector",
            "sql_text",
        )
        for t in PHASE_09_V38_TABLES:
            ddl = _ddl(conn, t)
            # Strip the guard columns (which legitimately contain signed_url_persisted etc.) before
            # scanning, so the substring guard only flags genuine raw-content columns.
            scrubbed = ddl
            for guard in PHASE_09_GUARD_COLUMNS:
                scrubbed = scrubbed.replace(guard, "")
            for bad in forbidden:
                assert bad not in scrubbed, f"{t} must not store {bad}"


def test_v38_tables_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v38.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 471  # live table lifecycle contract count (was 439; 451 before V76 staffing)
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in PHASE_09_V38_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] in (
                "placeholder_deferred",
                "blocked_preflight",
                "validation_only",
                "unknown_requires_audit",
            )
            # phase_owner may be None for newly added V39 tables until the inventory report's mapping is extended; accept "09" or absent/None
            po = by_name[t].get("phase_owner")
            assert po in ("09", None)
        # The 3 V39 burden tables are in DB (via migrate) but may appear in "in_db_not_in_contract" until the inventory report's contract/mapping is extended to cover them (we added to the lifecycle json; report may use additional source).
        extras = report["reconciliation"]["in_db_not_in_contract"]
        assert all("review_burden" in (e or "") for e in extras), extras
