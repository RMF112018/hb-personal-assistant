"""Startup schema policy: prevent silent production migrations on container restart."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hb_assistant.config.db_storage_guard import is_nas_runtime
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


class StartupSchemaPolicyError(Exception):
    """Raised when startup schema policy blocks service start."""

    def __init__(self, message: str, *, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.details = details or {}


@dataclass(frozen=True)
class StartupSchemaDecision:
    action: str  # allow | migrate | fail
    reason: str
    current_version: int
    expected_version: int = LATEST_SCHEMA_VERSION
    migration_performed: bool = False


def _allow_startup_migrations() -> bool:
    return os.environ.get("HB_ALLOW_STARTUP_MIGRATIONS", "").strip() == "1"


def _startup_migration_backup_receipt_path() -> Path | None:
    raw = os.environ.get("HB_STARTUP_MIGRATION_BACKUP_RECEIPT", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def validate_startup_migration_backup_receipt(receipt_path: Path) -> dict[str, Any]:
    """Require a metadata-only backup receipt before startup migrations."""
    if not receipt_path.is_file():
        raise StartupSchemaPolicyError(
            "startup migration backup receipt missing",
            reason="backup_receipt_missing",
            details={"receipt_path": str(receipt_path)},
        )
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StartupSchemaPolicyError(
            "startup migration backup receipt is not valid JSON",
            reason="backup_receipt_invalid",
            details={"receipt_path": str(receipt_path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise StartupSchemaPolicyError(
            "startup migration backup receipt must be a JSON object",
            reason="backup_receipt_invalid",
        )
    for key in ("generated_utc", "schema_version", "backup_path"):
        if key not in payload:
            raise StartupSchemaPolicyError(
                f"startup migration backup receipt missing required field: {key}",
                reason="backup_receipt_incomplete",
                details={"receipt_path": str(receipt_path), "missing_field": key},
            )
    return payload


def evaluate_startup_schema(db_path: str | Path) -> StartupSchemaDecision:
    """Evaluate whether startup may proceed without or with migration."""
    path = Path(db_path)
    nas = is_nas_runtime()
    expected = LATEST_SCHEMA_VERSION

    if not path.is_file():
        if nas:
            return StartupSchemaDecision(
                action="fail",
                reason="db_missing_nas_runtime",
                current_version=0,
                expected_version=expected,
            )
        return StartupSchemaDecision(
            action="migrate",
            reason="db_missing_dev_bootstrap",
            current_version=0,
            expected_version=expected,
            migration_performed=True,
        )

    current = int(SQLiteMigrator(db_path=str(path)).current_version())

    if current > expected:
        return StartupSchemaDecision(
            action="fail",
            reason="schema_ahead_of_code",
            current_version=current,
            expected_version=expected,
        )

    if current == expected:
        return StartupSchemaDecision(
            action="allow",
            reason="schema_at_head",
            current_version=current,
            expected_version=expected,
        )

    if not _allow_startup_migrations():
        return StartupSchemaDecision(
            action="fail",
            reason="schema_behind_requires_operator_flag",
            current_version=current,
            expected_version=expected,
        )

    receipt = _startup_migration_backup_receipt_path()
    if receipt is None:
        return StartupSchemaDecision(
            action="fail",
            reason="schema_behind_requires_backup_receipt",
            current_version=current,
            expected_version=expected,
        )

    validate_startup_migration_backup_receipt(receipt)
    return StartupSchemaDecision(
        action="migrate",
        reason="schema_behind_operator_authorized",
        current_version=current,
        expected_version=expected,
        migration_performed=True,
    )


def apply_startup_schema_policy(db_path: str | Path) -> dict[str, Any]:
    """Apply startup schema policy for the managed DB path."""
    path = Path(db_path)
    decision = evaluate_startup_schema(path)

    if decision.action == "fail":
        raise StartupSchemaPolicyError(
            f"startup schema policy blocked service start ({decision.reason})",
            reason=decision.reason,
            details={
                "current_version": decision.current_version,
                "expected_version": decision.expected_version,
            },
        )

    if decision.action == "allow":
        return {
            "managed": True,
            "migrated": False,
            "migration_performed": False,
            "schema_version": decision.current_version,
            "policy_reason": decision.reason,
        }

    version = int(SQLiteMigrator(db_path=str(path)).apply())
    return {
        "managed": True,
        "migrated": True,
        "migration_performed": True,
        "schema_version": version,
        "policy_reason": decision.reason,
    }
