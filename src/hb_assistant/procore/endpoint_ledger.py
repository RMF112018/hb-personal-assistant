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
    "resolve the authoritative API path (do not guess); remains fail-closed until verified"
)
_NEXT_STEP_HELD_PENDING = (
    "operator-run bounded live smoke to verify before promotion; "
    "remains fail-closed until verified"
)

# Phase 06B Prompt 04 — explicit per-endpoint disposition for held (live_verified=False)
# endpoints. Each remaining blocker maps to a stop condition (no path guessing, no permission
# bypass, no live evidence available), so all three are explicitly preserved fail-closed with
# the human action required to unblock. `evidence` cites the (historical) Phase 05 closeout.
# A test guards that this map's keys exactly equal the registry's held set.
_PHASE05_CLOSEOUT_EVIDENCE = (
    "docs/evidence/construction-intelligence-phase-05-financials/"
    "12-final-validation-coverage-evidence-and-closeout.md"
)
_HELD_DISPOSITION: Dict[str, Dict[str, str]] = {
    "purchase-order-detail-line-items": {
        "disposition": "fail_closed_pending_live_smoke",
        "blocker": (
            "per-PO 404 data condition: the line_item_contract_details path 404s for the "
            "sampled POs (their /line_items sibling succeeds), i.e. those POs carry no detail "
            "items — a data condition, not a path bug"
        ),
        "operator_action": (
            "run a bounded live smoke against a PO known to have contract-detail items (or an "
            "operator-supplied real payload), then re-probe and promote on a clean projection"
        ),
        "evidence": _PHASE05_CLOSEOUT_EVIDENCE,
    },
    "budget-change-line-items": {
        "disposition": "fail_closed_permission_blocked",
        "blocker": (
            "live 403 FORBIDDEN — the Procore token/role lacks budget-changes "
            "adjustment-line-items access"
        ),
        "operator_action": (
            "a Procore administrator must grant the integration user's role access to budget "
            "changes (adjustment line items) for the company/project, then re-probe; this tool "
            "does not modify Procore permissions"
        ),
        "evidence": _PHASE05_CLOSEOUT_EVIDENCE,
    },
    "budget-details": {
        "disposition": "fail_closed_unresolved_path",
        "blocker": (
            "no resolved REST path in the source reference (Prompt 00 §3.2); registered with a "
            "non-routable 'unresolved:budget-details' sentinel and no normalizer"
        ),
        "operator_action": (
            "obtain the authoritative budget-details path from Procore (likely a merge into "
            "budget-detail-rows) with an operator-supplied real path — the path will NOT be guessed"
        ),
        "evidence": _PHASE05_CLOSEOUT_EVIDENCE,
    },
}


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
        held_entry = None if adapter.live_verified else _HELD_DISPOSITION.get(adapter.endpoint_id)
        if adapter.live_verified:
            disposition = "promoted"
        elif held_entry is not None:
            disposition = held_entry["disposition"]
        else:
            disposition = "fail_closed_pending_verification"
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
                "disposition": disposition,
                "held_detail": (
                    {
                        "blocker": held_entry["blocker"],
                        "operator_action": held_entry["operator_action"],
                        "evidence": held_entry["evidence"],
                    }
                    if held_entry is not None
                    else None
                ),
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
