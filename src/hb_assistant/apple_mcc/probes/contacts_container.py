"""Contacts container allowlist resolution."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from hb_assistant.apple_mcc.probes.status import ProbeResult, ProbeState

# Default live capture targets iCloud CN container (primary).
# BF-Personal is included when present as a Contacts container name.
DEFAULT_CONTACTS_CONTAINER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "iCloud",
        "BF-Personal",
    }
)


def resolve_contacts_containers(
    *,
    containers: Sequence[dict[str, Any]],
    allowlist: frozenset[str] | set[str] | None = None,
    enabled: bool = True,
) -> ProbeResult:
    """Resolve allowlisted Contacts containers. Fail closed when none match."""
    if not enabled:
        return ProbeResult(
            domain="contacts",
            state=ProbeState.DISABLED,
            detail="contacts_capture_disabled",
        )
    allowed = frozenset(allowlist) if allowlist is not None else DEFAULT_CONTACTS_CONTAINER_ALLOWLIST
    names = [str(c.get("name", c.get("title", ""))) for c in containers]
    matched = [n for n in names if n in allowed]
    if not names:
        return ProbeResult(
            domain="contacts",
            state=ProbeState.MISSING,
            detail="no_containers_enumerated",
            candidates=(),
            metadata={"allowlist": sorted(allowed)},
        )
    if not matched:
        return ProbeResult(
            domain="contacts",
            state=ProbeState.MISSING,
            detail="no_allowlisted_containers",
            candidates=tuple(names),
            metadata={"allowlist": sorted(allowed)},
        )
    return ProbeResult(
        domain="contacts",
        state=ProbeState.OK,
        detail="containers_bound",
        selected=",".join(matched),
        candidates=tuple(names),
        metadata={"matched": matched, "allowlist": sorted(allowed)},
    )
