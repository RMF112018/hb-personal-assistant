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


def write_mcp_resource_registry_snapshot(
    *,
    resource_count: int,
    registry_hash: str,
    policy_version: str,
    db_path: str | None = None,
) -> str:
    """Insert one MCP resource-registry snapshot; returns the ``snapshot_id``.

    Local-only, additive, metadata-only (count + hash + versions). All guard columns 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    snapshot_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_resource_registry_snapshots
                (snapshot_id, created_at, resource_count, registry_hash, policy_version,
                 schema_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                _now(),
                int(resource_count),
                registry_hash,
                policy_version,
                LATEST_SCHEMA_VERSION,
            ),
        )
    return snapshot_id


def write_mcp_tool_registry_snapshot(
    *,
    allowed_tool_count: int,
    denied_action_count: int,
    registry_hash: str,
    policy_version: str,
    db_path: str | None = None,
) -> str:
    """Insert one MCP tool-registry snapshot; returns the ``snapshot_id``.

    Local-only, additive, metadata-only (counts + hash + versions). All guard columns 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    snapshot_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_tool_registry_snapshots
                (snapshot_id, created_at, allowed_tool_count, denied_action_count,
                 registry_hash, policy_version, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                _now(),
                int(allowed_tool_count),
                int(denied_action_count),
                registry_hash,
                policy_version,
                LATEST_SCHEMA_VERSION,
            ),
        )
    return snapshot_id


def write_mcp_permission_audit_run(
    *,
    status: str,
    checks_json: str,
    finding_count: int,
    policy_version: str,
    evidence_path: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one MCP permission-audit run; returns the ``audit_run_id``.

    ``checks_json`` is the metadata-only check report (names/booleans/short reason codes) —
    never raw content. All guard columns 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    audit_run_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_permission_audit_runs
                (audit_run_id, created_at, status, checks_json, finding_count, policy_version,
                 schema_version, evidence_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_run_id,
                _now(),
                status,
                checks_json,
                int(finding_count),
                policy_version,
                LATEST_SCHEMA_VERSION,
                evidence_path,
            ),
        )
    return audit_run_id


def write_mcp_prompt_registry_snapshot(
    *,
    prompt_count: int,
    registry_hash: str,
    policy_version: str,
    db_path: str | None = None,
) -> str:
    """Insert one MCP prompt-registry snapshot; returns the ``snapshot_id``.

    Local-only, additive, metadata-only (count + hash + versions). All guard columns 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    snapshot_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_prompt_registry_snapshots
                (snapshot_id, created_at, prompt_count, registry_hash, policy_version,
                 schema_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                _now(),
                int(prompt_count),
                registry_hash,
                policy_version,
                LATEST_SCHEMA_VERSION,
            ),
        )
    return snapshot_id


def write_mcp_tool_call_receipt(
    *,
    tool_name: str,
    decision: str,
    workflow_wrapper: str | None,
    policy_version: str,
    output_classification: str | None,
    source_count: int,
    result_count: int,
    args_hash: str | None,
    result_hash: str | None,
    client_name: str | None = None,
    correlation_id: str | None = None,
    evidence_path: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only MCP tool-call receipt; returns the ``receipt_id``.

    Persists hashes/counts/classification only — never raw arguments or results. All
    twenty guard columns stay at 0 (DB CHECK enforced).
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_tool_call_receipts
                (receipt_id, created_at, client_name, tool_name, decision, workflow_wrapper,
                 policy_version, schema_version, output_classification, source_count,
                 result_count, evidence_path, correlation_id, args_hash, result_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                _now(),
                client_name,
                tool_name,
                decision,
                workflow_wrapper,
                policy_version,
                LATEST_SCHEMA_VERSION,
                output_classification,
                int(source_count),
                int(result_count),
                evidence_path,
                correlation_id,
                args_hash,
                result_hash,
            ),
        )
    return receipt_id


def write_mcp_denial_receipt(
    *,
    requested_action: str,
    denial_reason_code: str,
    policy_version: str,
    client_name: str | None = None,
    correlation_id: str | None = None,
    request_hash: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only MCP denial receipt; returns the ``receipt_id``.

    Stores the action name, reason code, hashes, and versions only — never the raw
    requested content. ``decision`` is pinned to ``denied`` (DB CHECK). All twenty guard
    columns stay at 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V37 table exists (idempotent)

    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_mcp_denial_receipts
                (receipt_id, created_at, client_name, requested_action, decision,
                 denial_reason_code, policy_version, schema_version, correlation_id,
                 request_hash)
            VALUES (?, ?, ?, ?, 'denied', ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                _now(),
                client_name,
                requested_action,
                denial_reason_code,
                policy_version,
                LATEST_SCHEMA_VERSION,
                correlation_id,
                request_hash,
            ),
        )
    return receipt_id


def _sha256(payload: Any) -> str:
    import hashlib

    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
