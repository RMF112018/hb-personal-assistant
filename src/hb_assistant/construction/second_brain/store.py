"""Phase 08A second-brain config-receipt store (Prompt 03).

Writes a metadata-only audit row into the V26
``second_brain_runtime_config_receipts`` table recording the resolved runtime
posture (mode, config status, dependency availability, policy version). The table
enforces ten ``CHECK(col = 0)`` no-raw / no-writeback guard columns at the DB
layer; this writer leaves them all at 0 and never persists secrets, raw content,
prompts, responses, or URLs.

Reuses the canonical store idiom (``get_connection`` / ``transaction``) and runs
the migrator to guarantee the V26 table exists, mirroring ``ConstructionStore``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

from .config import SecondBrainConfig
from .contracts import load_phase_08a_contract

if TYPE_CHECKING:
    from .reasoning import AgentRunReceipt, ModelCallReceipt


def _runtime_policy_version() -> str:
    contract = load_phase_08a_contract("second_brain_runtime_contract")
    version = contract.get("version")
    return version if isinstance(version, str) else "unknown"


def write_config_receipt(
    *,
    config: SecondBrainConfig,
    db_path: str | None = None,
) -> str:
    """Insert one config receipt; returns the generated ``config_receipt_id``.

    Local-only, additive, metadata-only. All guard columns stay at 0.
    """
    SQLiteMigrator(db_path).apply()  # ensure V26 table exists (idempotent)

    receipt_id = uuid.uuid4().hex
    dependency_status_json = json.dumps(config.dependency_status(), sort_keys=True)
    policy_version = _runtime_policy_version()

    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_runtime_config_receipts
                (config_receipt_id, mode, config_status, dependency_status_json,
                 policy_version, generated_utc)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                config.mode,
                config.config_status,
                dependency_status_json,
                policy_version,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return receipt_id


def write_agent_run_receipt(
    receipt: AgentRunReceipt,
    *,
    db_path: str | None = None,
) -> str:
    """Insert one agent-run receipt (V28); returns the ``agent_run_id``.

    Local-only, additive, metadata-only (status + structured reason code + counts). The nine
    no-raw / no-writeback guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V28 table exists (idempotent)
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_agent_run_receipts
                (agent_run_id, agent_id, run_kind, status, reason_code, review_tier,
                 degradation_mode, model_receipt_count, started_utc, finished_utc, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.agent_run_id,
                receipt.agent_id,
                receipt.run_kind,
                receipt.status,
                receipt.reason_code,
                receipt.review_tier,
                receipt.degradation_mode,
                receipt.model_receipt_count,
                receipt.started_utc,
                receipt.finished_utc,
                receipt.created_utc,
            ),
        )
    return receipt.agent_run_id


def write_agent_model_receipt(
    receipt: ModelCallReceipt,
    *,
    db_path: str | None = None,
) -> str:
    """Insert one model-call receipt (V28); returns the ``model_receipt_id``.

    Local-only, additive, metadata-only (content hashes + token counts + reason code; never the
    raw prompt/response). The nine no-raw / no-writeback guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V28 table exists (idempotent)
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO second_brain_agent_model_receipts
                (model_receipt_id, agent_run_id, model_profile_id, model_id, input_context_hash,
                 output_hash, input_token_count, output_token_count, temperature, effort,
                 review_tier_reason_code, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.model_receipt_id,
                receipt.agent_run_id,
                receipt.model_profile_id,
                receipt.model_id,
                receipt.input_context_hash,
                receipt.output_hash,
                receipt.input_token_count,
                receipt.output_token_count,
                receipt.temperature,
                receipt.effort,
                receipt.review_tier_reason_code,
                receipt.created_utc,
            ),
        )
    return receipt.model_receipt_id


def read_latest_config_receipt(*, db_path: str | None = None) -> dict[str, Any] | None:
    """Return the most recent config receipt row as a dict, or None if empty."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        """
        SELECT config_receipt_id, mode, config_status, dependency_status_json,
               policy_version, generated_utc
        FROM second_brain_runtime_config_receipts
        ORDER BY generated_utc DESC, config_receipt_id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return dict(row) if row is not None else None
