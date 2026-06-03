"""Phase 08D MCP-bridge metadata-only writers (Prompt 03).

Writes audit rows into two V37 tables — ``second_brain_mcp_server_config_snapshots``
and ``second_brain_mcp_claude_desktop_config_previews``. Both tables enforce the full
twenty ``CHECK(col = 0)`` no-raw / no-writeback / no-direct-api / no-determination guard
columns at the DB layer; these writers leave every guard at 0 and persist only metadata
(hashes, counts, transport, redacted command, policy/schema version, evidence path).

Reuses the canonical store idiom (``SQLiteMigrator().apply()`` + ``get_connection`` +
``transaction``), mirroring ``second_brain/store.py``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_mcp_server_config_snapshot(
    *,
    transport: str,
    config_hash: str,
    policy_version: str,
    db_path: str | None = None,
) -> str:
    """Insert one MCP server-config snapshot; returns the ``snapshot_id``.

    Local-only, additive, metadata-only. All guard columns stay at 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    snapshot_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_server_config_snapshots
                (snapshot_id, created_at, transport, config_hash, policy_version, schema_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (snapshot_id, _now(), transport, config_hash, policy_version, LATEST_SCHEMA_VERSION),
        )
    return snapshot_id


def write_mcp_claude_desktop_config_preview(
    *,
    client_name: str,
    safe: bool,
    transport: str,
    command_redacted: str,
    args: list[str],
    env_keys: list[str],
    config_hash: str,
    policy_version: str,
    evidence_path: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one Claude Desktop config-preview snapshot; returns the ``preview_id``.

    Persists only the redacted command, the argv list, and the env *key names* (never
    env values) plus a content hash. Local-only, additive, metadata-only.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    preview_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_claude_desktop_config_previews
                (preview_id, created_at, client_name, safe, transport, command_redacted,
                 args_json, env_keys_json, config_hash, policy_version, schema_version,
                 evidence_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preview_id,
                _now(),
                client_name,
                1 if safe else 0,
                transport,
                command_redacted,
                json.dumps(list(args)),
                json.dumps(list(env_keys)),
                config_hash,
                policy_version,
                LATEST_SCHEMA_VERSION,
                evidence_path,
            ),
        )
    return preview_id


def _sha256(payload: Any) -> str:
    import hashlib

    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
