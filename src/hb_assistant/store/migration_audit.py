"""Sanitized structured audit for migration-ownership decisions (NF-F-001, plan §6).

Emits one structured logging record per migration-guard decision so an operator can see WHY a managed
migration was allowed, rejected, or skipped — WITHOUT ever recording sensitive material. Records carry
only: a fixed event name, the storage-class / operation / actor / route *labels*, an outcome, and
integer schema versions. They NEVER carry the process secret, an ``integrity_tag``, a backup digest,
or an absolute database path (only the coarse storage class). Emission is best-effort and must never
affect the migration outcome (a logging failure is swallowed).
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger("hb_assistant.store.migration_audit")

# Field names that must never appear in an audit record (defense-in-depth for callers/tests).
_FORBIDDEN_FIELDS = frozenset(
    {"integrity_tag", "secret", "process_secret", "backup_digest", "resolved_path", "path", "db_path"}
)


def emit_migration_event(
    event: str,
    *,
    storage_class: str | None = None,
    operation: str | None = None,
    actor_class: str | None = None,
    route_class: str | None = None,
    outcome: str | None = None,
    origin_version: int | None = None,
    target_version: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Emit (and return) a sanitized migration-guard audit record.

    Only enum/label strings, an outcome, a reason code, and integer versions are recorded — no path,
    secret, tag, or digest. Returns the record dict for tests/callers; never raises.
    """
    record: dict[str, Any] = {"event": str(event)}
    for key, value in (
        ("storage_class", storage_class),
        ("operation", operation),
        ("actor_class", actor_class),
        ("route_class", route_class),
        ("outcome", outcome),
        ("reason", reason),
    ):
        if value is not None:
            record[key] = str(value)
    if origin_version is not None:
        record["origin_version"] = int(origin_version)
    if target_version is not None:
        record["target_version"] = int(target_version)

    # Defense-in-depth: strip any forbidden field a future caller might add.
    for forbidden in _FORBIDDEN_FIELDS:
        record.pop(forbidden, None)

    try:
        _LOGGER.info("migration_guard", extra={"migration_audit": record})
    except Exception:  # noqa: BLE001 — audit must never affect the migration outcome
        pass
    return record
