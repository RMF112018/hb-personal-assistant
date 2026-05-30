"""Phase 06B machine-readable Procore endpoint promotion ledger.

A pure, deterministic derivation layer over the canonical endpoint registry
(``procore/endpoints.py``). It projects each ``EndpointAdapter`` row into a
ledger record carrying promotion status, evidence path, last-verified date, and
the next step — making endpoint status machine-readable without mutating the
registry (which is repo truth) and without any live Procore call.

Status is mirrored from the registry's ``live_verified`` gate only; this module
never probes Procore, so a non-verified endpoint is reported ``held``
(fail-closed) rather than silently promoted.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from hb_assistant.procore import endpoints as ep_registry

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Evidence bundle directories the ledger points at (derived from the
# endpoint's verification_reason phase token). Both directories exist in-repo.
_PHASE05_EVIDENCE = "docs/evidence/construction-intelligence-phase-05-financials/"
_PHASE04A_EVIDENCE = "docs/evidence/construction-intelligence-phase-04a/"

_NEXT_STEP_PROMOTED = "none — live-verified; monitor for drift"
_NEXT_STEP_HELD_UNRESOLVED = (
    "resolve API path and obtain permission grant before any live smoke; "
    "remains fail-closed until verified"
)
_NEXT_STEP_HELD_PENDING = (
    "operator-run bounded live smoke to verify before promotion; "
    "remains fail-closed until verified"
)


def _last_verified_date(verification_reason: str) -> str | None:
    """First ISO date embedded in the verification_reason, else None."""
    match = _DATE_RE.search(verification_reason)
    return match.group(0) if match else None


def _evidence_path(verification_reason: str) -> str:
    """Map an endpoint to the evidence bundle that established its status."""
    return _PHASE05_EVIDENCE if verification_reason.startswith("phase05") else _PHASE04A_EVIDENCE


def _next_step(*, live_verified: bool, verification_reason: str) -> str:
    if live_verified:
        return _NEXT_STEP_PROMOTED
    if "unresolved_path" in verification_reason:
        return _NEXT_STEP_HELD_UNRESOLVED
    return _NEXT_STEP_HELD_PENDING


def _ledger_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for adapter in ep_registry.list_all():
        reason = adapter.verification_reason
        rows.append(
            {
                "endpoint_id": adapter.endpoint_id,
                "family": adapter.family,
                "live_verified": adapter.live_verified,
                "promotion_status": "promoted" if adapter.live_verified else "held",
                "verification_reason": reason,
                "evidence_path": _evidence_path(reason),
                "last_verified_date": _last_verified_date(reason),
                "next_step": _next_step(live_verified=adapter.live_verified, verification_reason=reason),
            }
        )
    rows.sort(key=lambda r: r["endpoint_id"])
    return rows


def build_promotion_ledger() -> Dict[str, Any]:
    """Build the deterministic endpoint promotion ledger payload.

    ``ledger_row_count`` always equals ``registry_endpoint_count`` — the ledger
    is a one-to-one projection of the registry, never a filtered view.
    """
    rows = _ledger_rows()
    registry_count = len(ep_registry.list_all())
    promoted = [r for r in rows if r["promotion_status"] == "promoted"]
    held = [r for r in rows if r["promotion_status"] == "held"]
    return {
        "command": "hb-assistant procore live endpoints ledger",
        "ok": True,
        "phase": "Phase 06B Prompt 01",
        "registry_endpoint_count": registry_count,
        "ledger_row_count": len(rows),
        "promoted_count": len(promoted),
        "held_count": len(held),
        "ledger": rows,
    }
