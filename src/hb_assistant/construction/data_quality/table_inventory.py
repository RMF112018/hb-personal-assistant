"""Table lifecycle inventory and reconciliation (Phase 07B Prompt 01).

Operationalizes the previously-manual Phase 07A table lifecycle inventory
(docs/evidence/.../01-table-lifecycle-inventory.json) as a read-only CLI report.

It introspects the live SQLite schema (authoritative current truth) and
reconciles it against the canonical lifecycle contract
(resources/json/table_lifecycle_status_contract.json). Tables present in the DB
but absent from the contract are classified ``unknown_requires_audit``; contract
tables absent from the DB are surfaced separately.

Read-only: no --apply, no writes, no external calls, no raw content. Safe to run
against an empty (migrated-only) store.

Public entry point: build_table_inventory_report(db_path=None) -> dict
CLI surface: hb-assistant construction-agent data-quality table-inventory --json
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any, Optional

from hb_assistant.store.connection import get_connection

_CONTRACT_PKG = "hb_assistant.resources.json"
_CONTRACT_FILENAME = "table_lifecycle_status_contract.json"

_UNKNOWN_STATUS = "unknown_requires_audit"

# The reconciliation fields surfaced per table (contract-sourced where known).
_CONTRACT_FIELDS = (
    "table_family",
    "lifecycle_status",
    "expected_population_status",
    "phase_owner",
    "blocking_for_phase",
    "v",
    "notes",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_git_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[4]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _get_schema_version(db_path: Optional[str | Path] = None) -> int:
    try:
        conn = get_connection(db_path)
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _load_contract() -> dict[str, Any]:
    """Load the canonical lifecycle contract. importlib -> filesystem -> empty."""
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_CONTRACT_PKG) / _CONTRACT_FILENAME).read_text(
                encoding="utf-8"
            )
        else:  # pragma: no cover - legacy importlib path
            text = importlib_resources.read_text(
                _CONTRACT_PKG, _CONTRACT_FILENAME, encoding="utf-8"
            )
        return json.loads(text)
    except Exception:
        candidate = (
            Path(__file__).resolve().parents[4]
            / "src"
            / "hb_assistant"
            / "resources"
            / "json"
            / _CONTRACT_FILENAME
        )
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        return {"statuses": [], "required_fields": [], "tables": {}}


def _live_user_tables(conn: Any) -> list[str]:
    """User tables and views from sqlite_master (excludes indexes and sqlite_* internals).

    Views are included so reconciliation against a contract that catalogues views
    (e.g. v_procore_*) does not report them as missing.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def build_table_inventory_report(db_path: Optional[str | Path] = None) -> dict[str, Any]:
    """Build the live-schema-vs-contract table lifecycle inventory (read-only)."""
    conn = get_connection(db_path)
    contract = _load_contract()
    contract_tables: dict[str, Any] = contract.get("tables", {}) or {}

    live = _live_user_tables(conn)
    live_set = set(live)
    contract_set = set(contract_tables.keys())

    tables: list[dict[str, Any]] = []
    for name in live:
        entry: dict[str, Any] = {"table_name": name, "present_in_db": True}
        spec = contract_tables.get(name)
        if spec:
            for field in _CONTRACT_FIELDS:
                if field in spec:
                    entry[field] = spec[field]
            entry["source"] = "contract"
        else:
            entry["lifecycle_status"] = _UNKNOWN_STATUS
            entry["source"] = "unmapped"
        tables.append(entry)

    summary_by_status = dict(Counter(t.get("lifecycle_status", _UNKNOWN_STATUS) for t in tables))

    return {
        "command": "construction-agent data-quality table-inventory",
        "generated_utc": _now(),
        "repo_sha": _get_git_sha(),
        "schema_version": _get_schema_version(db_path),
        "contract_source": contract.get("source"),
        "contract_table_count": len(contract_set),
        "live_table_count": len(live_set),
        "tables": tables,
        "summary_by_status": summary_by_status,
        "reconciliation": {
            "in_db_not_in_contract": sorted(live_set - contract_set),
            "in_contract_not_in_db": sorted(contract_set - live_set),
        },
        "read_only": True,
    }
