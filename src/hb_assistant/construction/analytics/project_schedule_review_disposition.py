"""Phase 17 schedule review disposition taxonomy, normalization, and PM-safe labels."""

from __future__ import annotations

from typing import Any

DISPOSITION_NEEDS_REVIEW = "needs_review"
DISPOSITION_ACCEPTED_FOR_FOLLOW_UP = "accepted_for_follow_up"
DISPOSITION_DISMISSED_NOT_MATERIAL = "dismissed_not_material"
DISPOSITION_SUPERSEDED = "superseded"
DISPOSITION_DUPLICATE = "duplicate"
DISPOSITION_RESOLVED = "resolved"
DISPOSITION_BLOCKED_BY_IDENTITY = "blocked_by_identity"
DISPOSITION_BLOCKED_BY_TRUST = "blocked_by_trust"

CANONICAL_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_NEEDS_REVIEW,
        DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
        DISPOSITION_DISMISSED_NOT_MATERIAL,
        DISPOSITION_SUPERSEDED,
        DISPOSITION_DUPLICATE,
        DISPOSITION_RESOLVED,
        DISPOSITION_BLOCKED_BY_IDENTITY,
        DISPOSITION_BLOCKED_BY_TRUST,
    }
)

OPERATOR_SELECTABLE_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_NEEDS_REVIEW,
        DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
        DISPOSITION_DISMISSED_NOT_MATERIAL,
        DISPOSITION_SUPERSEDED,
        DISPOSITION_DUPLICATE,
        DISPOSITION_RESOLVED,
    }
)

SYSTEM_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_BLOCKED_BY_IDENTITY,
        DISPOSITION_BLOCKED_BY_TRUST,
    }
)

LEGACY_DISPOSITION_ALIASES: dict[str, str] = {
    "open": DISPOSITION_NEEDS_REVIEW,
    "watching": DISPOSITION_NEEDS_REVIEW,
    "reviewed": DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
    "dismissed": DISPOSITION_DISMISSED_NOT_MATERIAL,
}

REASON_REQUIRED_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_DISMISSED_NOT_MATERIAL,
        DISPOSITION_SUPERSEDED,
        DISPOSITION_DUPLICATE,
        DISPOSITION_RESOLVED,
    }
)

READY_DISPOSITIONS: frozenset[str] = frozenset(
    {
        DISPOSITION_NEEDS_REVIEW,
        DISPOSITION_ACCEPTED_FOR_FOLLOW_UP,
        DISPOSITION_RESOLVED,
    }
)

DISPOSITION_PM_LABELS: dict[str, dict[str, str]] = {
    DISPOSITION_NEEDS_REVIEW: {
        "label": "Needs review",
        "pm_description": "This item is queued for operator or project-team review.",
    },
    DISPOSITION_ACCEPTED_FOR_FOLLOW_UP: {
        "label": "Accepted for PM follow-up",
        "pm_description": "An operator marked this item for project-team review.",
    },
    DISPOSITION_DISMISSED_NOT_MATERIAL: {
        "label": "Dismissed as not material",
        "pm_description": "An operator dismissed this item as not material for PM follow-up.",
    },
    DISPOSITION_SUPERSEDED: {
        "label": "Superseded",
        "pm_description": "This item was superseded by a newer schedule update or review item.",
    },
    DISPOSITION_DUPLICATE: {
        "label": "Duplicate",
        "pm_description": "This item duplicates another review cue already tracked.",
    },
    DISPOSITION_RESOLVED: {
        "label": "Resolved",
        "pm_description": "An operator marked this item resolved after review.",
    },
    DISPOSITION_BLOCKED_BY_IDENTITY: {
        "label": "Blocked by identity trust",
        "pm_description": "Schedule identity trust must be resolved before this item can proceed.",
    },
    DISPOSITION_BLOCKED_BY_TRUST: {
        "label": "Blocked by analytics trust",
        "pm_description": "Analytics trust must be restored before this item can proceed.",
    },
}


def normalize_disposition(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in LEGACY_DISPOSITION_ALIASES:
        return LEGACY_DISPOSITION_ALIASES[raw]
    if raw in CANONICAL_DISPOSITIONS:
        return raw
    raise ValueError("invalid_review_status")


def is_open_disposition(disposition: str | None) -> bool:
    normalized = normalize_disposition(disposition)
    return normalized == DISPOSITION_NEEDS_REVIEW


def is_terminal_disposition(disposition: str | None) -> bool:
    normalized = normalize_disposition(disposition)
    return normalized in {
        DISPOSITION_DISMISSED_NOT_MATERIAL,
        DISPOSITION_SUPERSEDED,
        DISPOSITION_DUPLICATE,
        DISPOSITION_RESOLVED,
    }


def pm_disposition_view(disposition: str | None) -> dict[str, str]:
    normalized = normalize_disposition(disposition) or DISPOSITION_NEEDS_REVIEW
    meta = DISPOSITION_PM_LABELS.get(normalized, DISPOSITION_PM_LABELS[DISPOSITION_NEEDS_REVIEW])
    return {
        "disposition": normalized,
        "label": meta["label"],
        "pm_description": meta["pm_description"],
    }


def validate_disposition_change(
    *,
    prior_disposition: str | None,
    new_disposition: str,
    disposition_reason: str | None,
    operator_selectable_only: bool = True,
    trust_blocked: bool = False,
    identity_gate_blocked: bool = False,
    analytics_gate_blocked: bool = False,
) -> None:
    normalized_new = normalize_disposition(new_disposition)
    if normalized_new is None:
        raise ValueError("invalid_review_status")
    if operator_selectable_only and normalized_new not in OPERATOR_SELECTABLE_DISPOSITIONS:
        raise ValueError("operator_disposition_not_allowed")
    if normalized_new in REASON_REQUIRED_DISPOSITIONS and not str(disposition_reason or "").strip():
        raise ValueError("disposition_reason_required")
    prior = normalize_disposition(prior_disposition)
    if prior in SYSTEM_DISPOSITIONS and normalized_new in READY_DISPOSITIONS:
        if trust_blocked or identity_gate_blocked or analytics_gate_blocked:
            raise ValueError("blocked_disposition_cannot_be_cleared")
    if prior in SYSTEM_DISPOSITIONS and normalized_new in OPERATOR_SELECTABLE_DISPOSITIONS:
        if trust_blocked:
            raise ValueError("trust_blocked_disposition_change")


def system_disposition_for_trust(
    *,
    identity_gate_blocked: bool,
    analytics_gate_blocked: bool,
) -> str | None:
    if identity_gate_blocked:
        return DISPOSITION_BLOCKED_BY_IDENTITY
    if analytics_gate_blocked:
        return DISPOSITION_BLOCKED_BY_TRUST
    return None


def enrich_item_disposition_pm_fields(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    disposition = normalize_disposition(str(item.get("review_status") or "")) or DISPOSITION_NEEDS_REVIEW
    out["review_status"] = disposition
    pm = pm_disposition_view(disposition)
    out["disposition_label"] = pm["label"]
    out["disposition_pm_description"] = pm["pm_description"]
    out["is_preview"] = not bool(item.get("review_item_id"))
    out["is_persisted"] = bool(item.get("review_item_id"))
    return out
