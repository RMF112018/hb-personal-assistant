"""Store-specific structured runtime errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StoreReadinessError(RuntimeError):
    status: str
    message: str
    db_path: str
    report: dict[str, Any]

    def __str__(self) -> str:
        return self.message


# --- NF-F-001 migration-ownership error hierarchy -------------------------------------------------
# Typed, actionable errors for the read-only readiness boundary and the migration-authorization
# guard. They carry operator guidance in the message but NEVER raw secrets, authorization material,
# or untrusted absolute paths (callers sanitize the target before including it).


class SchemaReadinessError(RuntimeError):
    """Base: a read-only readiness check found the DB not usable for the requested operation.

    Raised on ordinary (unauthorized) request paths instead of migrating. Carries a normalized
    reason code and optional operator guidance; performs no mutation.
    """

    reason = "schema_not_ready"

    def __init__(self, message: str, *, guidance: str | None = None) -> None:
        super().__init__(message)
        self.guidance = guidance


class SchemaVersionBehind(SchemaReadinessError):
    reason = "schema_version_behind"


class SchemaStructureInvalid(SchemaReadinessError):
    reason = "schema_structure_invalid"


class MigrationAuthorizationError(RuntimeError):
    """Base for authorization-guard failures. Every subclass MUST be raised before any migration
    DDL, ledger write, or write-transaction mutation."""

    reason = "migration_authorization_error"


class MigrationAuthorizationRequired(MigrationAuthorizationError):
    reason = "migration_authorization_required"


class MigrationAuthorizationInvalid(MigrationAuthorizationError):
    reason = "migration_authorization_invalid"


class MigrationAuthorizationExpired(MigrationAuthorizationError):
    reason = "migration_authorization_expired"


class MigrationTargetMismatch(MigrationAuthorizationError):
    reason = "migration_target_mismatch"


class MigrationStorageClassDenied(MigrationAuthorizationError):
    reason = "migration_storage_class_denied"


class MigrationVersionMismatch(MigrationAuthorizationError):
    reason = "migration_version_mismatch"


class MigrationBackupReceiptRequired(MigrationAuthorizationError):
    reason = "migration_backup_receipt_required"


class OpenedDatabaseIdentityUnavailable(MigrationAuthorizationError):
    """The strongest-supported opened-target identity could not be established; fail closed rather
    than silently downgrade the target-binding guarantee (plan §12)."""

    reason = "opened_database_identity_unavailable"
