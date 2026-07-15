"""Migration-ownership authorization for the managed database (NF-F-001 / NF-F-011).

Enforced-issuer capability model (NF-AUD-004): a managed-database migration authorization can be minted
ONLY from a :class:`MigrationCapability`, and a capability can be obtained ONLY from an acquirer that
verifies its own governing control:

- ``acquire_startup_capability()`` — verifies the operator flag (``HB_ALLOW_STARTUP_MIGRATIONS``) and,
  for a managed-production target, a validated backup receipt.
- ``acquire_admin_capability(role)`` — verifies the admin RBAC role.
- ``acquire_local_bootstrap_capability()`` — scoped to the canonical MANAGED_LOCAL target only.

There is NO public factory that mints a managed authorization from caller-asserted actor/route/operation.
Operation, actor, and route come from the capability, not the caller. So incidental in-process code
cannot mint a valid managed authorization merely by importing a function and supplying plausible fields
— it must first satisfy the governing gate inside an acquirer.

Integrity + FD-stable identity (NF-AUD-005): each authorization carries an HMAC(process-local secret)
tag over its canonical fields INCLUDING the opened-target device/inode when available, is validated
against the identity of the database ACTUALLY opened (derived from a retained read-only guard FD)
before any DDL, and is revalidated at the migration boundary. Device/inode mismatch fails closed.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from hb_assistant.config.db_storage_guard import DatabaseStorageClass, classify_storage_class

from .errors import (
    MigrationAuthorizationExpired,
    MigrationAuthorizationInvalid,
    MigrationAuthorizationRequired,
    MigrationBackupReceiptRequired,
    MigrationStorageClassDenied,
    MigrationTargetMismatch,
    MigrationVersionMismatch,
)

# Process-local integrity secret. Regenerated every process start; never persisted or logged.
_PROCESS_SECRET = os.urandom(32)

# Process-local sentinel proving a MigrationCapability was constructed in-module by an acquirer.
_CAP_KEY = object()

_MANAGED = (DatabaseStorageClass.MANAGED_PRODUCTION, DatabaseStorageClass.MANAGED_LOCAL)


class MigrationOperation(str, Enum):
    STARTUP = "startup"
    ADMIN = "admin"
    LOCAL_REFRESH = "local_refresh"
    LIVE_REFRESH = "live_refresh"
    LOCAL_APP_BOOTSTRAP = "local_app_bootstrap"
    WORKSPACE_INITIALIZE = "workspace_initialize"
    REHEARSAL = "rehearsal"
    DEVELOPMENT = "development"


# Storage classes whose migration is the managed-database ownership boundary (NF-F-001 Invariant #3):
# a migration of one REQUIRES a validated authorization — a ``None`` authorization is a hard failure.
# Non-managed classes keep ambient self-heal; snapshot/blocked are always denied.
_MIGRATION_REQUIRES_AUTHORIZATION: frozenset[DatabaseStorageClass] = frozenset(_MANAGED)


# Operations permitted per managed storage class.
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
}


def migration_requires_authorization(storage_class: DatabaseStorageClass) -> bool:
    """True when *migrating* ``storage_class`` requires a validated authorization (managed boundary)."""
    return storage_class in _MIGRATION_REQUIRES_AUTHORIZATION


@dataclass(frozen=True)
class ValidatedBackupReceipt:
    """A backup receipt already validated by ``startup_schema_policy`` (metadata only)."""

    schema_version: int
    generated_utc: str
    backup_digest: str


@dataclass(frozen=True)
class AuthorizedTargetIdentity:
    """The database target an authorization is bound to.

    ``device``/``inode`` are captured at mint time when the target file exists (NF-AUD-005), binding
    the authorization to the strongest-supported opened-target identity; ``None`` for a target that
    does not yet exist (a fresh DB), in which case the migrator's retained-FD revalidation stabilizes
    identity from creation through the migration boundary.
    """

    resolved_path: str
    storage_class: DatabaseStorageClass
    device: int | None = None
    inode: int | None = None


@dataclass(frozen=True)
class OpenedDatabaseIdentity:
    """Identity of the database SQLite ACTUALLY opened (see database_identity.py).

    ``guard_fd`` is a retained read-only file descriptor pinned to the opened file's inode; the
    migrator revalidates device/inode through it at the migration boundary and closes it.
    """

    effective_path: str
    resolved_path: str
    device: int | None
    inode: int | None
    pragma_database_name: str
    storage_class: DatabaseStorageClass
    guard_fd: int | None = None


@dataclass(frozen=True)
class MigrationCapability:
    """Proof that a governing gate was satisfied. Constructible ONLY by the acquirers below (each of
    which verifies its own control); direct construction is rejected. Carries the authoritative
    operation/actor/route — a caller cannot self-assert these (NF-AUD-004)."""

    operation: MigrationOperation
    actor_class: str
    route_class: str
    allowed_storage_classes: frozenset[DatabaseStorageClass]
    backup_receipt: ValidatedBackupReceipt | None
    require_production_receipt: bool = False
    _key: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._key is not _CAP_KEY:
            raise MigrationAuthorizationInvalid(
                "MigrationCapability must be obtained from an acquirer, not constructed directly"
            )


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


# --- Capability acquirers (each verifies its governing control) ------------------------------------


def acquire_startup_capability() -> MigrationCapability:
    """Acquire the STARTUP capability. Verifies the operator flag itself; validates and carries the
    backup receipt when one is configured. Raises if the operator control is not satisfied."""
    from .startup_schema_policy import (  # noqa: PLC0415
        _allow_startup_migrations,
        _startup_migration_backup_receipt_path,
        validate_startup_migration_backup_receipt,
    )

    if not _allow_startup_migrations():
        raise MigrationAuthorizationRequired(
            "startup migration not enabled (operator must set HB_ALLOW_STARTUP_MIGRATIONS=1)"
        )
    receipt: ValidatedBackupReceipt | None = None
    receipt_path = _startup_migration_backup_receipt_path()
    if receipt_path is not None:
        payload = validate_startup_migration_backup_receipt(receipt_path)
        receipt = ValidatedBackupReceipt(
            schema_version=int(payload.get("schema_version", 0) or 0),
            generated_utc=str(payload.get("generated_utc", "")),
            backup_digest=str(payload.get("backup_digest") or payload.get("backup_path") or ""),
        )
    return MigrationCapability(
        operation=MigrationOperation.STARTUP,
        actor_class="startup",
        route_class="startup_schema_policy",
        allowed_storage_classes=frozenset(_MANAGED),
        backup_receipt=receipt,
        require_production_receipt=True,
        _key=_CAP_KEY,
    )


def acquire_admin_capability(role: dict[str, str]) -> MigrationCapability:
    """Acquire the ADMIN capability. Verifies the admin RBAC role itself (raises if not admin)."""
    if not isinstance(role, dict) or role.get("role") != "admin":
        raise MigrationAuthorizationRequired("admin role required to authorize a managed migration")
    return MigrationCapability(
        operation=MigrationOperation.ADMIN,
        actor_class="admin",
        route_class="admin_schema_migrate",
        allowed_storage_classes=frozenset(_MANAGED),
        backup_receipt=None,
        _key=_CAP_KEY,
    )


def acquire_local_bootstrap_capability() -> MigrationCapability:
    """Acquire the automatic local app/CLI-entry bootstrap capability, scoped to MANAGED_LOCAL only —
    it can never target the NAS managed-production DB, a snapshot, a workspace, or an unknown path."""
    return MigrationCapability(
        operation=MigrationOperation.LOCAL_APP_BOOTSTRAP,
        actor_class="local_app",
        route_class="app_entry_bootstrap",
        allowed_storage_classes=frozenset({DatabaseStorageClass.MANAGED_LOCAL}),
        backup_receipt=None,
        _key=_CAP_KEY,
    )


# --- Minting (capability-gated) -------------------------------------------------------------------


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
        # NF-AUD-005: device/inode are part of the signed identity.
        str(target_identity.device) if target_identity.device is not None else "none",
        str(target_identity.inode) if target_identity.inode is not None else "none",
        receipt,
        issued_at.astimezone(timezone.utc).isoformat(),
        expires_at.astimezone(timezone.utc).isoformat() if expires_at else "none",
    ]
    return "\x1f".join(parts).encode("utf-8")


def _integrity_tag(payload: bytes) -> str:
    return hmac.new(_PROCESS_SECRET, payload, hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{os.urandom(8).hex()}"


def execution_id_default() -> str:
    return _new_id("exec")


def _stat_identity(resolved_path: str) -> tuple[int | None, int | None]:
    """Return (device, inode) for ``resolved_path`` if it exists, else (None, None)."""
    try:
        st = os.stat(resolved_path)
    except OSError:
        return None, None
    return st.st_dev, st.st_ino


def authorize_migration(
    capability: MigrationCapability,
    *,
    resolved_path: str,
    expected_origin_version: int,
    target_version: int,
    execution_id: str | None = None,
    expires_at: datetime | None = None,
) -> MigrationAuthorization | None:
    """Mint a managed-migration authorization from a verified ``capability``, bound to the resolved
    target and its strongest-supported identity (device/inode when the file exists).

    Returns ``None`` for a NON-managed target (the migrator handles those: snapshot/blocked denied,
    workspace/rehearsal/dev self-heal) — so authorized callers can pass the result straight to
    ``apply(authorization=...)`` regardless of the resolved class. Raises when the capability does not
    cover the resolved managed class, when a required production backup receipt is absent, or when the
    capability's operation is not permitted for the class.
    """
    if not isinstance(capability, MigrationCapability):
        raise MigrationAuthorizationInvalid("a MigrationCapability is required to authorize a migration")

    resolved = str(Path(resolved_path).resolve())
    storage_class = classify_storage_class(resolved)

    if storage_class not in _MANAGED:
        return None  # migrator handles non-managed / snapshot / blocked

    if storage_class not in capability.allowed_storage_classes:
        raise MigrationStorageClassDenied(
            f"capability for {capability.operation.value} may not target {storage_class.value}"
        )
    if capability.operation not in _ALLOWED_OPERATIONS.get(storage_class, frozenset()):
        raise MigrationStorageClassDenied(
            f"operation {capability.operation.value} not permitted for {storage_class.value}"
        )
    if (
        storage_class is DatabaseStorageClass.MANAGED_PRODUCTION
        and capability.require_production_receipt
        and capability.backup_receipt is None
    ):
        raise MigrationBackupReceiptRequired(
            "a validated backup receipt is required to migrate the managed-production database"
        )

    device, inode = _stat_identity(resolved)
    target_identity = AuthorizedTargetIdentity(
        resolved_path=resolved, storage_class=storage_class, device=device, inode=inode
    )
    issued_at = _now()
    authorization_id = _new_id("mauth")
    exec_id = execution_id or execution_id_default()
    payload = _canonical_payload(
        authorization_id=authorization_id,
        execution_id=exec_id,
        actor_class=capability.actor_class,
        route_class=capability.route_class,
        operation=capability.operation,
        storage_class=storage_class,
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        target_identity=target_identity,
        backup_receipt=capability.backup_receipt,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return MigrationAuthorization(
        authorization_id=authorization_id,
        execution_id=exec_id,
        actor_class=capability.actor_class,
        route_class=capability.route_class,
        operation=capability.operation,
        storage_class=storage_class,
        expected_origin_version=expected_origin_version,
        target_version=target_version,
        target_identity=target_identity,
        backup_receipt=capability.backup_receipt,
        issued_at=issued_at,
        expires_at=expires_at,
        integrity_tag=_integrity_tag(payload),
    )


# --- Validation (called by the migrator before any DDL) -------------------------------------------


def validate_authorization(
    authorization: MigrationAuthorization | None,
    opened: OpenedDatabaseIdentity,
    *,
    require_backup_receipt: bool = False,
) -> None:
    """Validate ``authorization`` against the ACTUAL opened database identity. Raises a typed error
    before any migration DDL when invalid.

    A ``None`` authorization for a MANAGED target is a hard failure; snapshot/blocked are always
    denied. Non-managed targets permit ``None`` (ambient self-heal). When an authorization is
    supplied it must be integrity-valid, unexpired, class/operation/path-matched, and — when its
    target identity carries device/inode — device/inode must match the opened file (NF-AUD-005).
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
        return  # non-managed target: ambient self-heal permitted

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

    if authorization.expires_at is not None and _now() > authorization.expires_at:
        raise MigrationAuthorizationExpired("authorization has expired")

    if authorization.storage_class is not storage_class:
        raise MigrationStorageClassDenied(
            f"authorization storage class {authorization.storage_class.value} != opened {storage_class.value}"
        )
    if authorization.target_identity.storage_class is not storage_class:
        raise MigrationStorageClassDenied("authorization target storage class mismatch")

    if authorization.operation not in _ALLOWED_OPERATIONS.get(storage_class, frozenset()):
        raise MigrationStorageClassDenied(
            f"operation {authorization.operation.value} not permitted for {storage_class.value}"
        )

    if authorization.target_identity.resolved_path != opened.resolved_path:
        raise MigrationTargetMismatch("authorization target does not match the opened database")

    # NF-AUD-005: FD-stable identity. When the authorization bound a device/inode (the target existed
    # at mint), the opened file MUST present the same device/inode; a rename/replace/inode-drift is a
    # hard failure. Fail closed if the bound identity cannot be confirmed against the opened file.
    auth_dev = authorization.target_identity.device
    auth_ino = authorization.target_identity.inode
    if auth_dev is not None or auth_ino is not None:
        if opened.device is None or opened.inode is None:
            raise MigrationTargetMismatch(
                "opened database identity (device/inode) unavailable to confirm authorized target"
            )
        if opened.device != auth_dev or opened.inode != auth_ino:
            raise MigrationTargetMismatch(
                "opened database device/inode does not match the authorized target (substitution)"
            )

    if (
        require_backup_receipt
        and storage_class is DatabaseStorageClass.MANAGED_PRODUCTION
        and authorization.backup_receipt is None
    ):
        raise MigrationBackupReceiptRequired("a validated backup receipt is required for this migration")


def assert_origin_version(authorization: MigrationAuthorization, actual_origin: int) -> None:
    """Bind the declared origin to the DB's actual current version (called by the migrator)."""
    if (
        authorization.expected_origin_version >= 0
        and actual_origin != authorization.expected_origin_version
    ):
        raise MigrationVersionMismatch(
            f"actual origin {actual_origin} != authorized origin {authorization.expected_origin_version}"
        )


def revalidate_opened_identity(opened: OpenedDatabaseIdentity) -> None:
    """Critical-boundary revalidation (NF-AUD-005), run just before the migration transaction commits.

    The retained guard FD pins the migrated inode (SQLite's own descriptor writes to the same inode),
    so both operate on the file we validated regardless of path renames. This confirms (a) the guard FD
    is still valid and consistent, and (b) the resolved target path still points to that same inode — a
    path swapped to a *different* inode during migration is a hard failure. Fail closed when a managed
    target has no retained guard FD to pin."""
    if opened.guard_fd is None:
        # Fresh in-memory / unstattable target: nothing to pin. Only acceptable for non-managed.
        if opened.storage_class in _MIGRATION_REQUIRES_AUTHORIZATION:
            raise MigrationTargetMismatch(
                "no retained guard FD to revalidate the managed migration target"
            )
        return
    try:
        st_fd = os.fstat(opened.guard_fd)
    except OSError as exc:
        raise MigrationTargetMismatch("retained guard FD could not be revalidated") from exc
    if opened.device is not None and (st_fd.st_dev != opened.device or st_fd.st_ino != opened.inode):
        raise MigrationTargetMismatch(
            "opened database device/inode drifted during migration (TOCTOU substitution)"
        )
    # Detect a path swap during migration: the resolved target path must still resolve to the same
    # inode we migrated. (SQLite committed to the pinned inode; a path now pointing elsewhere means a
    # concurrent replace — fail closed and roll back.)
    if opened.resolved_path and opened.device is not None:
        try:
            st_path = os.stat(opened.resolved_path)
        except OSError as exc:
            raise MigrationTargetMismatch(
                "migrated target path no longer resolvable at commit boundary"
            ) from exc
        if st_path.st_dev != opened.device or st_path.st_ino != opened.inode:
            raise MigrationTargetMismatch(
                "target path was swapped to a different inode during migration"
            )
