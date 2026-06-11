"""Phase 10 V45 — email follow-up raw enrichment **readiness / eligibility** (read-only, raw-free).

Makes the V45 enrichment no-op conditions explicit and actionable. Walks the accepted task/commitment
funnel and reports, by reason code, why each unit is or is not eligible for raw enrichment — WITHOUT
loading or printing any raw email body. Raw existence is determined only from the already-safe
window-builder metadata (``RawFollowupWindow.available`` / message counts) and from source refs /
hashes; the sanitized window text is never read here.

This module performs no model call (it only checks route availability), no persistence, and no
writeback. Output carries counts, reason codes, route metadata, and a bounded sample of safe
candidate ids only — never raw content.
"""

from __future__ import annotations

from typing import Any, Optional

from .email_followup_enrichment import (
    _EMAIL_FAMILIES,
    _TERMINAL_STATUSES,
    _watch_index,
)
from .email_followup_route import route_email_followup
from .raw_followup_window import RawWindowCaps, build_raw_followup_window

#: Final (non-pending) review statuses — a unit already carrying one is not re-enriched.
_FINAL_REVIEW_STATUSES = frozenset({"accepted", "rejected", "superseded"})

#: Fixed skip-reason vocabulary (every key always present in the report, even when zero).
_SKIP_REASONS: tuple[str, ...] = (
    "no_candidate_id",
    "no_candidate_source_refs",
    "no_email_source_ref",
    "no_raw_email_content",
    "already_pending",
    "already_final_review_status",
    "local_model_unavailable",
    "raw_policy_disabled",
    "source_link_invalid",
    "unsupported_candidate_type",
)

_GUARDRAILS = {
    "read_only": True,
    "raw_free": True,
    "no_raw_body_loaded": True,
    "existence_by_hash_or_window_metadata_only": True,
    "no_model_call": True,
    "no_persistence": True,
    "no_writeback": True,
    "local_only": True,
}


def _enrichment_status_index(store: Any) -> dict[str, set[str]]:
    """Map source_candidate_id → set of existing enrichment review_status values (raw-free)."""
    idx: dict[str, set[str]] = {}
    try:
        rows = store.list_email_followup_enrichments(limit=100000)
    except Exception:
        return idx
    for r in rows:
        cid = str(r.get("source_candidate_id") or "")
        if not cid:
            continue
        idx.setdefault(cid, set()).add(str(r.get("review_status") or "pending"))
    return idx


def _has_citeable_email_ref(email_refs: list[dict[str, Any]]) -> bool:
    """True when at least one email ref carries a citeable hash (ref or primary-key hash)."""
    return any(
        (r.get("source_ref_hash") or r.get("source_primary_key_hash")) for r in email_refs
    )


def build_email_followup_enrichment_readiness(
    *,
    store: Any,
    candidate_id: Optional[str] = None,
    include_closed: bool = False,
    limit: int = 200,
    present_models: set[str] | None = None,
    caps: Optional[RawWindowCaps] = None,
    sample_limit: int = 10,
    raw_policy_enabled: bool = True,
) -> dict[str, Any]:
    """Build the raw-free V45 enrichment readiness/eligibility report (read-only).

    Walks accepted tasks + commitments, applies the same gates as the enrichment engine, and counts
    each outcome by reason code. ``present_models`` (installed local model names; ``None`` ⇒ daemon
    unreachable) is used only to check route availability. ``raw_policy_enabled=False`` reports every
    otherwise-eligible unit under ``raw_policy_disabled`` (there is no persistent raw-policy gate in
    the engine today; this is the contract hook). Never loads or returns raw email content.
    """
    caps = caps or RawWindowCaps()
    watch_idx = _watch_index(store)
    enrich_idx = _enrichment_status_index(store)

    # Route availability (local-only; fail-closed). One probe; no generation.
    route = route_email_followup(present_models=present_models)
    local_model_available = bool(route.available and not route.blocked)

    accepted_task_count = 0
    accepted_commitment_count = 0
    accepted_with_candidate_id = 0
    accepted_with_source_refs = 0
    accepted_with_email_source_refs = 0
    accepted_with_raw_email_content = 0
    eligible = 0
    closed_excluded = 0
    already_enriched_pending = 0
    already_enriched_final = 0
    skipped: dict[str, int] = dict.fromkeys(_SKIP_REASONS, 0)
    sample_eligible: list[str] = []

    units: list[tuple[str, dict[str, Any]]] = []
    for row in store.list_accepted_tasks(limit=limit):
        accepted_task_count += 1
        units.append(("task", row))
    for row in store.list_accepted_commitments(limit=limit):
        accepted_commitment_count += 1
        units.append(("commitment", row))

    for kind, row in units:
        cid = str(row.get("candidate_id") or "")
        accepted_id = str(
            row.get("accepted_task_id") or row.get("accepted_commitment_id") or ""
        )
        if candidate_id is not None and candidate_id not in (cid, accepted_id):
            continue
        if not cid:
            skipped["no_candidate_id"] += 1
            continue
        accepted_with_candidate_id += 1

        # Closed gate (out of scope unless include_closed) — tracked separately, not a skip reason.
        watch = watch_idx.get(accepted_id) or {}
        status = (row.get("status") or "").strip().lower()
        watch_status = str(watch.get("watch_status") or "").strip().lower()
        is_closed = (
            bool(row.get("completed_utc"))
            or status in _TERMINAL_STATUSES
            or watch_status == "closed"
        )
        if is_closed and not include_closed:
            closed_excluded += 1
            continue

        try:
            refs = store.list_candidate_source_refs(
                candidate_id=cid, candidate_type=kind, limit=1000
            )
        except Exception:
            refs = []
        if not refs:
            skipped["no_candidate_source_refs"] += 1
            continue
        accepted_with_source_refs += 1

        email_refs = [r for r in refs if str(r.get("source_family") or "") in _EMAIL_FAMILIES]
        if not email_refs:
            skipped["no_email_source_ref"] += 1
            continue
        accepted_with_email_source_refs += 1

        if not _has_citeable_email_ref(email_refs):
            skipped["source_link_invalid"] += 1
            continue

        # Already-enriched gate (raw-free: status only).
        statuses = enrich_idx.get(cid, set())
        if "pending" in statuses:
            already_enriched_pending += 1
            skipped["already_pending"] += 1
            continue
        if statuses & _FINAL_REVIEW_STATUSES:
            already_enriched_final += 1
            skipped["already_final_review_status"] += 1
            continue

        # Raw availability — ONLY the window's safe metadata is read (never window_text).
        try:
            window = build_raw_followup_window(
                candidate_id=cid,
                candidate_type=kind,
                source_refs=email_refs,
                store=store,
                caps=caps,
            )
            raw_available = bool(window.available)
        except Exception:
            raw_available = False
        if not raw_available:
            skipped["no_raw_email_content"] += 1
            continue
        accepted_with_raw_email_content += 1

        if not raw_policy_enabled:
            skipped["raw_policy_disabled"] += 1
            continue

        # Passed every per-candidate gate. If the local model is down it is still NOT runnable now.
        if not local_model_available:
            skipped["local_model_unavailable"] += 1
            continue

        eligible += 1
        if len(sample_eligible) < max(0, sample_limit):
            sample_eligible.append(cid)

    accepted_total = accepted_task_count + accepted_commitment_count

    return {
        "command": "second-brain follow-up-watch enrich-readiness",
        "ok": True,
        "accepted_task_count": accepted_task_count,
        "accepted_commitment_count": accepted_commitment_count,
        "accepted_total": accepted_total,
        "accepted_with_candidate_id": accepted_with_candidate_id,
        "accepted_with_source_refs": accepted_with_source_refs,
        "accepted_with_email_source_refs": accepted_with_email_source_refs,
        "accepted_with_raw_email_content": accepted_with_raw_email_content,
        "eligible_for_raw_enrichment": eligible,
        "closed_excluded": closed_excluded,
        "already_enriched_pending": already_enriched_pending,
        "already_enriched_final": already_enriched_final,
        "skipped_by_reason": skipped,
        "local_model_available": local_model_available,
        "route": {
            "task_family": route.task_family,
            "selected_profile": route.selected_profile,
            "model_name": route.model_name,
            "available": route.available,
            "reason_code": route.reason_code,
            "no_cloud": route.no_cloud,
        },
        "raw_policy_enabled": bool(raw_policy_enabled),
        "sample_eligible_candidate_ids": sample_eligible,
        "guardrails": dict(_GUARDRAILS),
    }


#: Data-gap readiness statuses (the email-substrate-vs-follow-up-layers view, distinct from the
#: per-candidate enrichment-eligibility funnel above).
DATA_GAP_STATUS_POPULATED = "populated"
DATA_GAP_STATUS_DATA_GAP = "data_gap"
DATA_GAP_STATUS_NO_SOURCE = "no_source"
DATA_GAP_STATUS_NOT_CONFIGURED = "not_configured"

_DATA_GAP_REASON = "email raw content available but follow-up projection not yet populated"


def classify_email_followup_data_gap(counts: dict[str, int]) -> dict[str, Any]:
    """Classify raw-free readiness counts into a data-gap status + card. Pure function.

    The honest data-gap case: email raw/structured rows EXIST but every follow-up layer
    (watch items / task / commitment / enrichment) is empty — the email -> follow-up projection
    has not been populated. This must surface as a card, never as a silent "nothing to do".
    ``source_rows`` is the usefulness-gate contradiction-(c) input.
    """
    email_substrate = int(counts.get("email_message_raw_content", 0)) + int(
        counts.get("email_thread_raw_context", 0)
    )
    email_structured = int(counts.get("email_raw_message_structured", 0)) + int(
        counts.get("email_raw_thread_structured", 0)
    )
    followup_rows = (
        int(counts.get("follow_up_watch_items", 0))
        + int(counts.get("task_candidates", 0))
        + int(counts.get("commitment_candidates", 0))
        + int(counts.get("email_followup_enrichments", 0))
    )
    source_rows = email_substrate + email_structured

    if followup_rows > 0:
        status = DATA_GAP_STATUS_POPULATED
    elif source_rows > 0:
        status = DATA_GAP_STATUS_DATA_GAP
    elif email_substrate == 0 and email_structured == 0:
        status = DATA_GAP_STATUS_NOT_CONFIGURED
    else:
        status = DATA_GAP_STATUS_NO_SOURCE

    card = None
    if status == DATA_GAP_STATUS_DATA_GAP:
        card = {"section": "email_followup", "status": status, "reason": _DATA_GAP_REASON}

    return {
        "section": "email_followup",
        "status": status,
        "source_rows": source_rows,
        "raw_available": email_substrate > 0,
        "structured_available": email_structured > 0,
        "followup_rows": followup_rows,
        "counts": {k: int(v) for k, v in counts.items()},
        "data_gap_card": card,
    }


def build_email_followup_data_gap(store: Any) -> dict[str, Any]:
    """Compute the email/follow-up data-gap readiness surface from the store (read-only, raw-free)."""
    try:
        counts = store.email_followup_readiness_counts()
    except Exception as exc:  # advisory only — never fail the run
        return {
            "section": "email_followup",
            "status": DATA_GAP_STATUS_NOT_CONFIGURED,
            "source_rows": 0,
            "raw_available": False,
            "structured_available": False,
            "followup_rows": 0,
            "counts": {},
            "data_gap_card": None,
            "degraded_reason": f"readiness_error:{type(exc).__name__}",
        }
    return classify_email_followup_data_gap(counts)


__all__ = [
    "DATA_GAP_STATUS_DATA_GAP",
    "DATA_GAP_STATUS_NOT_CONFIGURED",
    "DATA_GAP_STATUS_NO_SOURCE",
    "DATA_GAP_STATUS_POPULATED",
    "build_email_followup_data_gap",
    "build_email_followup_enrichment_readiness",
    "classify_email_followup_data_gap",
]
