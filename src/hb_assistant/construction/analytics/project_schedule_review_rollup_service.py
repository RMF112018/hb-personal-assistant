"""PM-safe schedule review status rollups for hub, controls, workbench, driver, and export."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hb_assistant.construction.analytics.project_schedule_review_disposition import (
    DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
    DISPOSITION_BLOCKED_BY_IDENTITY,
    DISPOSITION_BLOCKED_BY_TRUST,
    DISPOSITION_DISMISSED_NOT_MATERIAL,
    DISPOSITION_NEEDS_REVIEW,
    DISPOSITION_RESOLVED,
    SYSTEM_DISPOSITIONS,
    enrich_item_disposition_pm_fields,
    is_open_disposition,
    normalize_disposition,
)


def _max_reviewed_at(items: list[dict[str, Any]]) -> str | None:
    timestamps = [str(item.get("reviewed_at")) for item in items if item.get("reviewed_at")]
    if not timestamps:
        return None
    return max(timestamps)


def build_review_status_rollup(
    *,
    items: list[dict[str, Any]],
    preview_items: list[dict[str, Any]] | None = None,
    analytics_trust_status: str | None = None,
    identity_gate: str | None = None,
) -> dict[str, Any]:
    preview = list(preview_items or [])
    persisted = [item for item in items if item.get("review_item_id")]
    preview_only = [
        item
        for item in preview
        if not item.get("review_item_id")
        and str(item.get("stable_item_key") or "") not in {
            str(row.get("stable_item_key") or "") for row in persisted
        }
    ]

    counts = {
        "needs_review": 0,
        "accepted_for_follow_up": 0,
        "dismissed_not_material": 0,
        "resolved": 0,
        "blocked": 0,
        "superseded": 0,
        "duplicate": 0,
    }
    for item in persisted:
        disposition = normalize_disposition(str(item.get("review_status") or "")) or DISPOSITION_NEEDS_REVIEW
        if disposition == DISPOSITION_NEEDS_REVIEW:
            counts["needs_review"] += 1
        elif disposition == DISPOSITION_ACCEPTED_FOR_FOLLOW_UP:
            counts["accepted_for_follow_up"] += 1
        elif disposition == DISPOSITION_DISMISSED_NOT_MATERIAL:
            counts["dismissed_not_material"] += 1
        elif disposition == DISPOSITION_RESOLVED:
            counts["resolved"] += 1
        elif disposition in SYSTEM_DISPOSITIONS:
            counts["blocked"] += 1
        elif disposition == "superseded":
            counts["superseded"] += 1
        elif disposition == "duplicate":
            counts["duplicate"] += 1

    trust_blocked = analytics_trust_status == "blocked" or identity_gate == "blocked"
    if trust_blocked:
        recommended = "Resolve schedule identity and analytics trust before advancing review dispositions."
        pm_summary = "Schedule review is blocked or degraded by trust gates. Operator trust review is recommended first."
    elif counts["needs_review"] > 0 or preview_only:
        recommended = "Review preview cues and persisted items, then record operator dispositions."
        pm_summary = "Schedule review items are queued for operator review."
    elif counts["accepted_for_follow_up"] > 0:
        recommended = "Follow up with the project team on accepted review items."
        pm_summary = "Some review items are accepted for PM follow-up."
    else:
        recommended = "No open review items require immediate operator action."
        pm_summary = "Schedule review queue has no open operator actions."

    return {
        "total_items": len(persisted),
        "preview_cue_count": len(preview_only),
        "persisted_item_count": len(persisted),
        "needs_review": counts["needs_review"],
        "accepted_for_follow_up": counts["accepted_for_follow_up"],
        "dismissed_not_material": counts["dismissed_not_material"],
        "resolved": counts["resolved"],
        "blocked": counts["blocked"],
        "superseded": counts["superseded"],
        "duplicate": counts["duplicate"],
        "last_reviewed_at": _max_reviewed_at(persisted),
        "pm_summary": pm_summary,
        "recommended_next_action": recommended,
        # Legacy summary keys for gradual UI migration.
        "open_count": counts["needs_review"],
        "watching_count": 0,
        "reviewed_count": counts["accepted_for_follow_up"] + counts["resolved"],
        "dismissed_count": counts["dismissed_not_material"],
        "total_count": len(persisted) + len(preview_only),
    }


def split_preview_and_persisted(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    persisted: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    persisted_keys: set[str] = set()
    for item in items:
        enriched = enrich_item_disposition_pm_fields(item)
        if enriched.get("review_item_id"):
            persisted.append(enriched)
            key = str(enriched.get("stable_item_key") or "")
            if key:
                persisted_keys.add(key)
        else:
            preview.append(enriched)
    preview_only = [
        item
        for item in preview
        if str(item.get("stable_item_key") or "") not in persisted_keys
    ]
    return preview_only, persisted


def prioritize_preview_items(items: list[dict[str, Any]], *, limit: int = 12) -> list[dict[str, Any]]:
    open_items = [item for item in items if is_open_disposition(str(item.get("review_status") or ""))]
    prioritized = sorted(
        open_items,
        key=lambda row: (-int(row.get("priority") or 0), str(row.get("item_title") or "")),
    )
    return prioritized[:limit]
