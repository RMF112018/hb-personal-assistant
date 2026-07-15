"""Migration-ownership authorization for the managed database (NF-F-001).

The architecture (`TARGETED_CALLER_CORRECTION + MANDATORY MIGRATOR AUTHORIZATION GUARD`) requires
that every *managed-production* ``SQLiteMigrator.apply()`` be gated by an explicit, typed, scoped
authorization that is bound to the **actual opened database target** and validated **before** any
migration DDL or write transaction.

Trust model (plan §11, risk NF001-R-01):

- Authorizations are ONLY minted by the trusted factory functions in this module, which run in
  server/operator code AFTER the existing RBAC / operator-flag / backup-receipt controls succeed.
- Each authorization carries an ``integrity_tag`` = HMAC(process-local secret, canonical fields).
  The secret is generated once per process from ``os.urandom`` and never leaves the process, so an
  authorization deserialized from an untrusted request (or a hand-constructed dataclass) cannot
  carry a valid tag — ``validate_authorization`` rejects it. A boolean / unchecked request field /
  env bypass is explicitly NOT accepted as proof.
- Workspace-init authority is a DISTINCT capability that cannot target managed or snapshot storage.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from hb_assistant.config.db_storage_guard import DatabaseStorageClass

from .errors import (
    MigrationAuthorizationExpired,
    MigrationAuthorizationInvalid,
    MigrationAuthorizationRequired,
    MigrationStorageClassDenied,
    MigrationTargetMismatch,
    MigrationVersionMismatch,
)

# Process-local integrity secret. Regenerated every process start; never persisted or logged. A
# forged/deserialized authorization cannot reproduce the HMAC without it.
_PROCESS_SECRET = os.urandom(32)


class MigrationOperation(str, Enum):
    STARTUP = "startup"
    ADMIN = "admin"
    LOCAL_REFRESH = "local_refresh"
    LIVE_REFRESH = "live_refresh"
    LOCAL_APP_BOOTSTRAP = "local_app_bootstrap"
    WORKSPACE_INITIALIZE = "workspace_initialize"
    REHEARSAL = "rehearsal"
    DEVELOPMENT = "development"


# Storage classes whose migration is the *managed*-database ownership boundary (NF-F-001 Invariant
# #3, scoped per RC-1 + the operator MANAGED_LOCAL decision): a migration of one of these REQUIRES an
# explicit, target-bound authorization — a ``None`` authorization is a hard failure. Non-managed
# classes (isolated workspace / disposable rehearsal / explicit development) retain ambient self-heal
# (``None`` authorization permitted) so dev/CLI/test call sites are unaffected; read-only snapshot and
# blocked are always denied regardless of authorization.
_MIGRATION_REQUIRES_AUTHORIZATION: frozenset[DatabaseStorageClass] = frozenset(
    {DatabaseStorageClass.MANAGED_PRODUCTION, DatabaseStorageClass.MANAGED_LOCAL}
)


# Operations permitted per storage class. Managed production is reachable only by genuine migration
# operations; managed-local by the automatic app/CLI-entry bootstrap; workspace-init can ONLY target
# isolated workspace; snapshot never migrates.
_ALLOWED_OPERATIONS: dict[DatabaseStorageClass, frozenset[MigrationOperation]] = {
    DatabaseStorageClass.MANAGED_PRODUCTION: frozenset(
        {
            MigrationOperation.STARTUP,
            MigrationOperation.ADMIN,
            MigrationOperation.LOCAL_REFRESH,
            MigrationOperation.LIVE_REFRESH,
        }
    ),
    DatabaseStorageClass.MANAGED_LOCAL: frozenset(
        {MigrationOperation.LOCAL_APP_BOOTSTRAP, MigrationOperation.ADMIN}
    ),
    DatabaseStorageClass.ISOLATED_WORKSPACE: frozenset({MigrationOperation.WORKSPACE_INITIALIZE}),
    DatabaseStorageClass.DISPOSABLE_REHEARSAL: frozenset({MigrationOperation.REHEARSAL}),
    DatabaseStorageClass.EXPLICIT_DEVELOPMENT: frozenset({MigrationOperation.DEVELOPMENT}),
    # READ_ONLY_SNAPSHOT and BLOCKED intentionally absent -> migration always denied.
}


@dataclass(frozen=True)
class ValidatedBackupReceipt:
    """A backup receipt already validated by ``startup_schema_policy`` (metadata only)."""

    schema_version: int
    generated_utc: str
    backup_digest: str


@dataclass(frozen=True)
class AuthorizedTargetIdentity:
    """The database target an authorization is bound to (resolved before opening)."""

    resolved_path: str
    storage_class: DatabaseStorageClass


@dataclass(frozen=True)
class OpenedDatabaseIdentity:
    """Identity of the database SQLite ACTUALLY opened (see database_identity.py)."""

    effective_path: str
    resolved_path: str
    device: int | None
    inode: int | None
    pragma_database_name: str
    storage_class: DatabaseStorageClass


@dataclass(frozen=True)
class MigrationAuthorization:
    authorization_id: str
    execution_id: str
    actor_class: str
    route_class: str
    operation: MigrationOperation
    storage_class: DatabaseStorageClass
    expected_origin_version: int
    target_version: int
    target_identity: AuthorizedTargetIdentity
    backup_receipt: ValidatedBackupReceipt | None
    issued_at: datetime
    expires_at: datetime | None
    integrity_tag: str


def _canonical_payload(
    *,
    authorization_id: str,
    execution_id: str,
    actor_class: str,
    route_class: str,
    operation: MigrationOperation,
    storage_class: DatabaseStorageClass,
    expected_origin_version: int,
    target_version: int,
    target_identity: AuthorizedTargetIdentity,
    backup_receipt: ValidatedBackupReceipt | None,
    issued_at: datetime,
    expires_at: datetime | None,
) -> bytes:
    receipt = (
        f"{backup_receipt.schema_version}|{backup_receipt.generated_utc}|{backup_receipt.backup_digest}"
        if backup_receipt is not None
        else "none"
    )
    parts = [
        authorization_id,
        execution_id,
        actor_class,
        route_class,
        operation.value,
        storage_class.value,
        str(expected_origin_version),
        str(target_version),
        target_identity.resolved_path,
        target_identity.storage_class.value,
        receipt,
        issued_at.astimezone(timezone.utc).isoformat(),
        expires_at.astimezone(timezone.utc).isoformat() if expires_at else "none",
    ]
    return "\x1f".join(parts).encode("utf-8")


def _integrity_tag(payload: bytes) -> str:
    return hmac.new(_PROCESS_SECRET, payload, hashlib.sha256).hexdigest()


def _issue(
    *,
    authorization_id: str,
    execution_id: str,
    actor_class: str,
    route_class: str,
    operation: MigrationOperation,
    target_identity: AuthorizedTargetIdentity,
    expected_origin_version: int,
    target_version: int,
    backup_receipt: ValidatedBackupReceipt | None,
    issued_at: datetime,
    expires_at: datetime | None,
) -> MigrationAuthorization:
    """Internal trusted minting: computes the integrity tag over the canonical payload."""
    payload = _canonical_payload(
        authorization_id=authorization_id,
        execution_id=execution_id,
        actor_class=actor_class,
        route_class=route_class,
        operation=operation,
        storage_class=target_identity.storage_class,
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        target_identity=target_identity,
        backup_receipt=backup_receipt,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return MigrationAuthorization(
        authorization_id=authorization_id,
        execution_id=execution_id,
        actor_class=actor_class,
        route_class=route_class,
        operation=operation,
        storage_class=target_identity.storage_class,
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        target_identity=target_identity,
        backup_receipt=backup_receipt,
        issued_at=issued_at,
        expires_at=expires_at,
        integrity_tag=_integrity_tag(payload),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{os.urandom(8).hex()}"


def _target_for(resolved_path: str, storage_class: DatabaseStorageClass) -> AuthorizedTargetIdentity:
    return AuthorizedTargetIdentity(resolved_path=str(Path(resolved_path).resolve()), storage_class=storage_class)


# --- Trusted factories (server/operator code only, AFTER existing gates) --------------------------


def issue_managed_authorization(
    *,
    operation: MigrationOperation,
    resolved_path: str,
    actor_class: str,
    route_class: str,
    execution_id: str,
    expected_origin_version: int,
    target_version: int,
    backup_receipt: ValidatedBackupReceipt | None = None,
) -> MigrationAuthorization:
    """Mint authorization for the MANAGED PRODUCTION database. Callers must have already passed the
    existing controls (startup flag+receipt / admin RBAC / operator gates)."""
    if operation not in _ALLOWED_OPERATIONS[DatabaseStorageClass.MANAGED_PRODUCTION]:
        raise MigrationStorageClassDenied(
            f"operation {operation.value} not permitted for managed production"
        )
    return _issue(
        authorization_id=_new_id("mauth"),
        execution_id=execution_id,
        actor_class=actor_class,
        route_class=route_class,
        operation=operation,
        target_identity=_target_for(resolved_path, DatabaseStorageClass.MANAGED_PRODUCTION),
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        backup_receipt=backup_receipt,
        issued_at=_now(),
        expires_at=None,
    )


def issue_local_app_bootstrap_authorization(
    *, resolved_path: str, execution_id: str, expected_origin_version: int, target_version: int
) -> MigrationAuthorization:
    """Mint the automatic app/CLI-entry bootstrap authorization for the MANAGED_LOCAL (Mac
    app-support canonical) DB. Fails closed unless the path classifies EXACTLY as MANAGED_LOCAL — it
    can never authorize the NAS managed DB, a snapshot, a workspace DB, or an unknown/blocked path.
    """
    from hb_assistant.config.db_storage_guard import classify_storage_class  # noqa: PLC0415

    if classify_storage_class(resolved_path) is not DatabaseStorageClass.MANAGED_LOCAL:
        raise MigrationStorageClassDenied(
            "local-app bootstrap authorization refused: target is not the canonical local app DB"
        )
    return _issue(
        authorization_id=_new_id("lauth"),
        execution_id=execution_id,
        actor_class="local_app",
        route_class="app_entry_bootstrap",
        operation=MigrationOperation.LOCAL_APP_BOOTSTRAP,
        target_identity=_target_for(resolved_path, DatabaseStorageClass.MANAGED_LOCAL),
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        backup_receipt=None,
        issued_at=_now(),
        expires_at=None,
    )


def issue_workspace_init_authorization(
    *, resolved_path: str, execution_id: str, target_version: int
) -> MigrationAuthorization:
    """Mint workspace-initialize authorization. CANNOT target managed/snapshot storage."""
    return _issue(
        authorization_id=_new_id("wauth"),
        execution_id=execution_id,
        actor_class="workspace",
        route_class="workspace_init",
        operation=MigrationOperation.WORKSPACE_INITIALIZE,
        target_identity=_target_for(resolved_path, DatabaseStorageClass.ISOLATED_WORKSPACE),
        expected_origin_version=0,
        target_version=target_version,
        backup_receipt=None,
        issued_at=_now(),
        expires_at=None,
    )


def issue_non_managed_bootstrap_authorization(
    *, resolved_path: str, storage_class: DatabaseStorageClass, target_version: int
) -> MigrationAuthorization:
    """Mint bootstrap authorization for an EXPLICITLY non-managed dev/rehearsal DB (RC-1).

    Preserves current CLI/dev self-heal UX without an implicit managed bypass: this factory refuses
    any managed/snapshot/blocked storage class, so it can never authorize the managed DB.
    """
    if storage_class not in (
        DatabaseStorageClass.EXPLICIT_DEVELOPMENT,
        DatabaseStorageClass.DISPOSABLE_REHEARSAL,
    ):
        raise MigrationStorageClassDenied(
            f"bootstrap authorization refused for storage class {storage_class.value}"
        )
    operation = (
        MigrationOperation.DEVELOPMENT
        if storage_class is DatabaseStorageClass.EXPLICIT_DEVELOPMENT
        else MigrationOperation.REHEARSAL
    )
    return _issue(
        authorization_id=_new_id("dauth"),
        execution_id=execution_id_default(),
        actor_class="local",
        route_class="cli_or_dev",
        operation=operation,
        target_identity=_target_for(resolved_path, storage_class),
        expected_origin_version=0,
        target_version=target_version,
        backup_receipt=None,
        issued_at=_now(),
        expires_at=None,
    )


def execution_id_default() -> str:
    return _new_id("exec")


# --- Validation (called by the migrator before any DDL) -------------------------------------------


def validate_authorization(
    authorization: MigrationAuthorization | None,
    opened: OpenedDatabaseIdentity,
    *,
    require_backup_receipt: bool = False,
) -> None:
    """Validate ``authorization`` against the ACTUAL opened database identity. Raises a typed error
    (all subclasses of the store error hierarchy) before any migration DDL when invalid.

    A ``None`` authorization for a MANAGED target (production or local) is a hard failure; read-only
    snapshot and blocked are always denied. Non-managed targets (isolated workspace / disposable
    rehearsal / explicit development) permit a ``None`` authorization (ambient self-heal preserved);
    when an authorization IS supplied it must be valid and match the opened target's class.
    """
    storage_class = opened.storage_class

    if storage_class is DatabaseStorageClass.READ_ONLY_SNAPSHOT:
        raise MigrationStorageClassDenied("migration is never permitted against a read-only snapshot")
    if storage_class is DatabaseStorageClass.BLOCKED:
        raise MigrationStorageClassDenied("migration target is a blocked/unclassified storage location")

    if authorization is None:
        if storage_class in _MIGRATION_REQUIRES_AUTHORIZATION:
            raise MigrationAuthorizationRequired(
                f"migration of {storage_class.value} storage requires a validated authorization"
            )
        # Non-managed target: ambient self-heal permitted with no authorization.
        return

    # Integrity: recompute the HMAC; a forged/deserialized auth cannot match the process secret.
    payload = _canonical_payload(
        authorization_id=authorization.authorization_id,
        execution_id=authorization.execution_id,
        actor_class=authorization.actor_class,
        route_class=authorization.route_class,
        operation=authorization.operation,
        storage_class=authorization.storage_class,
        expected_origin_version=authorization.expected_origin_version,
        target_version=authorization.target_version,
        target_identity=authorization.target_identity,
        backup_receipt=authorization.backup_receipt,
        issued_at=authorization.issued_at,
        expires_at=authorization.expires_at,
    )
    if not hmac.compare_digest(_integrity_tag(payload), authorization.integrity_tag):
        raise MigrationAuthorizationInvalid("authorization integrity check failed (forged or altered)")

    # Expiry.
    if authorization.expires_at is not None and _now() > authorization.expires_at:
        raise MigrationAuthorizationExpired("authorization has expired")

    # Storage-class agreement between authorization, its bound target, and the opened DB.
    if authorization.storage_class is not storage_class:
        raise MigrationStorageClassDenied(
            f"authorization storage class {authorization.storage_class.value} != opened {storage_class.value}"
        )
    if authorization.target_identity.storage_class is not storage_class:
        raise MigrationStorageClassDenied("authorization target storage class mismatch")

    # Operation must be permitted for this storage class.
    if authorization.operation not in _ALLOWED_OPERATIONS.get(storage_class, frozenset()):
        raise MigrationStorageClassDenied(
            f"operation {authorization.operation.value} not permitted for {storage_class.value}"
        )

    # Target identity: the authorization must be bound to the SAME resolved path SQLite opened.
    if authorization.target_identity.resolved_path != opened.resolved_path:
        raise MigrationTargetMismatch("authorization target does not match the opened database")

    # Version binding: refuse migrating a DB that is not at the expected origin, or to a wrong head.
    # expected_origin_version < 0 means "any origin" (used by workspace/dev bootstrap).
    if authorization.expected_origin_version >= 0:
        # actual origin is checked by the migrator against current_version(); here we only bind the
        # declared origin/target so the migrator can compare (see migrator.apply()).
        pass

    # Backup receipt requirement (managed startup/live-refresh).
    if require_backup_receipt and authorization.backup_receipt is None:
        from .errors import MigrationBackupReceiptRequired  # noqa: PLC0415

        raise MigrationBackupReceiptRequired("a validated backup receipt is required for this migration")


def assert_origin_version(authorization: MigrationAuthorization, actual_origin: int) -> None:
    """Bind the declared origin to the DB's actual current version (called by the migrator)."""
    if authorization.expected_origin_version >= 0 and actual_origin != authorization.expected_origin_version:
        raise MigrationVersionMismatch(
            f"actual origin {actual_origin} != authorized origin {authorization.expected_origin_version}"
        )
