"""Operator-only, LOCAL poison-file quarantine operations (list / inspect / bounded retry).

``list`` / ``inspect`` are READ-ONLY. ``retry`` is a local DB mutation (quarantine resolution only — never a
source-file write) gated by explicit confirmation and a bounded item count. There is NO remote MCP write
surface and NO blanket "ignore"/waiver: a quarantine is cleared only by a TRUSTWORTHY observation.

Confirmed-absence contract (a retry that cannot find the path is NOT automatically success): a quarantine
resolves to ``confirmed_absent`` only when the root is available, the parent directory is trustworthily
listable, and the absence is not a permission / mount-loss / race / indeterminate-I/O artifact — otherwise the
unresolved quarantine is RETAINED.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..store.source_index_scan_quarantine_repository import (
    SourceIndexScanQuarantineRepository,
)
from ..store.source_index_scan_quarantine_tables import (
    RESOLUTION_CONFIRMED_ABSENT,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED,
)
from .config import ObsidianMcpConfig


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_quarantine(
    db_path: str,
    *,
    root_key: str | None = None,
    resolution_state: str | None = "unresolved",
    limit: int = 100,
) -> dict[str, Any]:
    """READ-ONLY: sanitized listing of quarantine records (rel_path only; no absolute paths)."""
    repo = SourceIndexScanQuarantineRepository(db_path)
    items = repo.list_quarantine(root_key, resolution_state=resolution_state, limit=limit)
    return {"ok": True, "count": len(items), "items": items}


def inspect_quarantine(db_path: str, quarantine_id: str) -> dict[str, Any]:
    """READ-ONLY: one quarantine record's sanitized detail."""
    repo = SourceIndexScanQuarantineRepository(db_path)
    rec = repo.get(quarantine_id)
    if rec is None:
        return {"ok": False, "error": "quarantine_not_found", "quarantine_id": quarantine_id}
    return {"ok": True, "quarantine": rec}


def _observe(root_dir: Path, rel_path: str) -> tuple[str, str | None]:
    """Observe one quarantined path and decide its resolution WITHOUT trusting a bare "not found".

    Returns ``(outcome, retain_reason)`` where outcome ∈ ``resolved`` | ``confirmed_absent`` | ``retain``."""
    if not root_dir.is_dir():
        return "retain", "root_unavailable"
    abs_path = root_dir / rel_path
    try:
        abs_path.stat()
    except FileNotFoundError:
        # A retry that cannot find the path is NOT automatically success. Confirm the absence is trustworthy:
        # the parent must be listable (not a permission/mount artifact) and the entry genuinely gone.
        parent = abs_path.parent
        try:
            with os.scandir(parent) as it:
                names = {e.name for e in it}
        except OSError:
            return "retain", "parent_untrustworthy"
        if abs_path.name in names:
            return "retain", "reappeared_during_retry"  # a race — do not resolve
        return "confirmed_absent", None
    except OSError:
        return "retain", "path_unreadable"  # permission / stale handle / mount loss — indeterminate
    if not os.access(abs_path, os.R_OK):
        return "retain", "path_unreadable"
    # Statable AND readable → observable again. Resolve; the next normal generation re-indexes + finalizes.
    return "resolved", None


def retry_quarantine(
    db_path: str,
    config: ObsidianMcpConfig,
    *,
    root_key: str,
    quarantine_id: str | None = None,
    max_items: int = 1,
) -> dict[str, Any]:
    """Operator-only bounded retry. Re-observes each targeted quarantine and resolves it ONLY on a
    trustworthy observation (readable → ``resolved``; trustworthily absent → ``confirmed_absent``); otherwise
    RETAINS it. Resolution is a single atomic UPDATE per item. Never writes a source file. Bounded by
    ``max_items``; resolving the LAST quarantine does not itself complete any generation — a fresh pass must
    verify the walk and reconcile before the root is authoritative again."""
    repo = SourceIndexScanQuarantineRepository(db_path)
    root = next(
        (r for r in getattr(config, "external_sources", []) if r.source_root_key == root_key), None
    )
    if root is None:
        return {"ok": False, "error": "unknown_root", "root_key": root_key}
    root_dir = Path(root.path)

    if quarantine_id is not None:
        rec = repo.get(quarantine_id)
        # Only an UNRESOLVED record is a retry target — retrying an already-resolved record is an idempotent
        # no-op (never a second mutation, never a double-counted resolution).
        targets = (
            [rec]
            if rec is not None
            and rec["source_root_key"] == root_key
            and rec["resolution_state"] == RESOLUTION_UNRESOLVED
            else []
        )
    else:
        targets = repo.list_quarantine(
            root_key, resolution_state="unresolved", limit=max(1, int(max_items))
        )

    outcomes: list[dict[str, Any]] = []
    resolved = confirmed_absent = retained = 0
    for rec in targets:
        if rec is None:
            continue
        outcome, reason = _observe(root_dir, rec["rel_path"])
        # ``resolve`` returns False if the record was already resolved by a concurrent retry — count only the
        # mutation THIS call actually performed (idempotent; never double-counts a resolution).
        if outcome == "resolved":
            if repo.resolve(
                quarantine_id=rec["quarantine_id"],
                resolution_state=RESOLUTION_RESOLVED,
                last_successful_observation_at=_now(),
            ):
                resolved += 1
            else:
                outcome, reason = "retain", "already_resolved"
                retained += 1
        elif outcome == "confirmed_absent":
            if repo.resolve(
                quarantine_id=rec["quarantine_id"],
                resolution_state=RESOLUTION_CONFIRMED_ABSENT,
            ):
                confirmed_absent += 1
            else:
                outcome, reason = "retain", "already_resolved"
                retained += 1
        else:
            retained += 1
        outcomes.append(
            {
                "quarantine_id": rec["quarantine_id"],
                "rel_path": rec["rel_path"],
                "outcome": outcome,
                "retain_reason": reason,
            }
        )
    return {
        "ok": True,
        "root_key": root_key,
        "attempted": len(outcomes),
        "resolved": resolved,
        "confirmed_absent": confirmed_absent,
        "retained": retained,
        "remaining_blocking": repo.blocking_count(root_key),
        "outcomes": outcomes,
    }
