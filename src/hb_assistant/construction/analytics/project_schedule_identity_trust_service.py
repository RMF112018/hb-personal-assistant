"""PM-safe schedule identity trust read model for Project Schedule Hub."""

from __future__ import annotations

from typing import Any, Literal

from hb_assistant.store.project_schedule_hub_repository import (
    MEMBERSHIP_ACCEPTED,
    MEMBERSHIP_EXCLUDED,
    MEMBERSHIP_PENDING,
)

IdentityTrustStatus = Literal[
    "trusted",
    "review_required",
    "ambiguous",
    "mismatch",
    "blocked",
    "unavailable",
]
IdentityGate = Literal["ready", "degraded", "blocked"]

_REASON_MESSAGES: dict[str, str] = {
    "duplicate_schedule_version": "This schedule version already exists and requires supersede confirmation.",
    "likely_new_schedule_series": "No accepted schedule series exists yet for this project.",
    "low_activity_overlap": "Activity overlap with the accepted schedule is weak.",
    "identity_requires_review": "This file may belong to a different schedule series.",
    "data_date_out_of_sequence": "Data date appears earlier than the accepted schedule update.",
    "source_project_mismatch": "Source project in the file does not match the linked project record.",
    "source_project_unknown": "Source project ID was not detected in the uploaded schedule.",
    "requires_review_match": "Identity resolution requires operator review.",
    "low_activity_overlap_membership": "Series membership is pending due to weak activity overlap.",
    "count_scale_delta": "Activity or relationship counts changed substantially versus the accepted schedule.",
    "excluded_from_series": "This schedule version is excluded from the trusted series.",
    "multiple_identity_candidates": "Multiple schedule identity candidates were detected.",
    "ambiguous_match": "Schedule identity match is ambiguous.",
    "no_prior_identity_version": "No prior identity version is available for comparison.",
    "no_identity_match": "No schedule identity match is available.",
}

_RECOMMENDED_ACTIONS: dict[str, list[str]] = {
    "trusted": [],
    "review_required": [
        "Open identity review and confirm the schedule belongs to the correct project series.",
        "Do not rely on comparison metrics until identity is accepted.",
    ],
    "ambiguous": [
        "Review candidate schedule identities before accepting analytics.",
        "Assign or split identity in the operator review surface.",
    ],
    "mismatch": [
        "Confirm the uploaded file belongs to this project before proceeding.",
        "Do not treat schedule analytics as reliable until the mismatch is resolved.",
    ],
    "blocked": [
        "Resolve series exclusion or project mismatch in identity review.",
        "Analytics remain blocked until an operator accepts the correct series membership.",
    ],
    "unavailable": [
        "Import and commit the schedule, then revisit identity review.",
    ],
}

_FORBIDDEN_PM_KEYS = frozenset(
    {
        "schedule_version_key",
        "schedule_identity_key",
        "import_id",
        "package_id",
        "cpm_run_id",
        "source_export_proxy",
        "matched_prior_schedule_version_key",
        "winning_candidate_schedule_version_key",
        "accepted_schedule_version_key",
        "preview_schedule_version_key",
        "procore_project_id",
    }
)


def _humanize_reason(code: str | None) -> str | None:
    if not code:
        return None
    normalized = str(code).strip()
    if not normalized:
        return None
    if normalized in _REASON_MESSAGES:
        return _REASON_MESSAGES[normalized]
    return normalized.replace("_", " ").strip().capitalize() + "."


def _safe_label(*parts: Any, fallback: str = "Schedule update") -> str:
    for part in parts:
        text = str(part or "").strip()
        if text:
            return text
    return fallback


def map_identity_gate(*, identity_trust_status: IdentityTrustStatus) -> IdentityGate:
    if identity_trust_status in {"mismatch", "blocked"}:
        return "blocked"
    if identity_trust_status in {"review_required", "ambiguous", "unavailable"}:
        return "degraded"
    return "ready"


def build_identity_trust_from_preview(
    *,
    preview: dict[str, Any],
    trust_preview: dict[str, Any] | None,
    project_display_name: str | None = None,
) -> dict[str, Any]:
    trust = trust_preview or {}
    warnings = list(trust.get("warnings") or [])
    codes = [str(w.get("code") or "") for w in warnings]
    safe_reasons = [_humanize_reason(c) for c in codes if _humanize_reason(c)]
    safe_reasons = [r for r in safe_reasons if r]

    status: IdentityTrustStatus = "trusted"
    if "source_project_mismatch" in codes:
        status = "mismatch"
    elif "duplicate_schedule_version" in codes and trust.get("posture") == "supersede_required":
        status = "review_required"
    elif any(
        c in codes
        for c in (
            "identity_requires_review",
            "low_activity_overlap",
            "likely_new_schedule_series",
            "data_date_out_of_sequence",
            "source_project_unknown",
        )
    ):
        status = "review_required"
    elif warnings:
        status = "review_required"

    schedule_label = _safe_label(
        preview.get("schedule_name"),
        preview.get("source_filename"),
        preview.get("display_label"),
    )
    data_date = preview.get("data_date")
    if data_date:
        schedule_label = f"{schedule_label} ({str(data_date)[:10]})"

    gate = map_identity_gate(identity_trust_status=status)
    pm_message = _pm_message(status=status, gate=gate)
    return pm_identity_trust_payload(
        identity_trust_status=status,
        identity_gate=gate,
        review_required=status != "trusted",
        operator_action_required=status in {"review_required", "ambiguous", "mismatch", "blocked"},
        safe_project_label=_safe_label(project_display_name, preview.get("project_display_name"), fallback="Project"),
        safe_schedule_label=schedule_label,
        safe_reasons=safe_reasons,
        recommended_operator_actions=_RECOMMENDED_ACTIONS.get(status, []),
        pm_message=pm_message,
        technical_identity={
            "preview_posture": trust.get("posture"),
            "warning_codes": codes,
        },
    )


def build_identity_trust_from_committed(
    *,
    project_key: str,
    project_display_name: str | None,
    schedule_label: str | None,
    identity_match: dict[str, Any] | None,
    membership: dict[str, Any] | None,
    trust_preview_warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    del project_key
    match = identity_match or {}
    membership_status = str((membership or {}).get("membership_status") or "")
    match_status = str(match.get("match_status") or "")
    requires_review = bool(int(match.get("requires_review") or 0))
    candidate_count = int(match.get("candidate_count") or 0)

    codes: list[str] = []
    if membership and membership.get("review_reason"):
        codes.extend(str(membership["review_reason"]).split(","))
    if match.get("no_match_reason"):
        codes.append(str(match["no_match_reason"]))
    for warning in trust_preview_warnings or []:
        code = str(warning.get("code") or "")
        if code:
            codes.append(code)

    status: IdentityTrustStatus = "trusted"
    if membership_status == MEMBERSHIP_EXCLUDED:
        status = "blocked"
        codes.append("excluded_from_series")
    elif match_status == "ambiguous" or candidate_count > 1:
        status = "ambiguous"
        codes.append("ambiguous_match")
    elif requires_review or membership_status == MEMBERSHIP_PENDING:
        status = "review_required"
        if requires_review:
            codes.append("requires_review_match")
    elif not match and not membership:
        status = "unavailable"
        codes.append("no_identity_match")
    elif membership_status and membership_status != MEMBERSHIP_ACCEPTED:
        status = "review_required"

    safe_reasons = sorted({_humanize_reason(c) for c in codes if _humanize_reason(c)})
    gate = map_identity_gate(identity_trust_status=status)
    label = _safe_label(schedule_label, match.get("source_filename_redacted"))
    return pm_identity_trust_payload(
        identity_trust_status=status,
        identity_gate=gate,
        review_required=status != "trusted",
        operator_action_required=status in {"review_required", "ambiguous", "mismatch", "blocked"},
        safe_project_label=_safe_label(project_display_name, fallback="Project"),
        safe_schedule_label=label,
        safe_reasons=list(safe_reasons),
        recommended_operator_actions=_RECOMMENDED_ACTIONS.get(status, []),
        pm_message=_pm_message(status=status, gate=gate),
        technical_identity={
            "membership_status": membership_status or None,
            "match_status": match_status or None,
            "requires_review": requires_review,
            "candidate_count": candidate_count or None,
            "confidence_score": match.get("confidence_score"),
            "match_type": match.get("match_type"),
            "match_rule": match.get("match_rule"),
        },
    )


def build_identity_trust_from_hub(
    *,
    project_display_name: str | None,
    schedule_trust: dict[str, Any] | None,
    identity_review: dict[str, Any] | None,
    current_schedule: dict[str, Any] | None,
    identity_match: dict[str, Any] | None,
    membership: dict[str, Any] | None,
) -> dict[str, Any]:
    trust_status = str((schedule_trust or {}).get("status") or (identity_review or {}).get("status") or "")
    codes = list(schedule_trust.get("review_reasons") or []) if schedule_trust else []
    membership_status = str((membership or {}).get("membership_status") or (schedule_trust or {}).get("current_membership_status") or "")

    status: IdentityTrustStatus = "unavailable"
    if trust_status == "trusted" and membership_status in {"", MEMBERSHIP_ACCEPTED}:
        status = "trusted"
    elif trust_status == "excluded" or membership_status == MEMBERSHIP_EXCLUDED:
        status = "blocked"
        codes.append("excluded_from_series")
    elif trust_status == "review_required" or membership_status == MEMBERSHIP_PENDING:
        match = identity_match or {}
        if str(match.get("match_status") or "") == "ambiguous" or int(match.get("candidate_count") or 0) > 1:
            status = "ambiguous"
        else:
            status = "review_required"
    elif trust_status == "trusted":
        status = "trusted"
    elif membership_status == MEMBERSHIP_ACCEPTED:
        status = "trusted"

    if "source_project_mismatch" in codes:
        status = "mismatch"

    current = current_schedule or {}
    schedule_label = _safe_label(
        current.get("friendly_label"),
        current.get("source_filename"),
    )
    data_date = current.get("data_date")
    if data_date:
        schedule_label = f"{schedule_label} ({str(data_date)[:10]})"

    safe_reasons = sorted({_humanize_reason(c) for c in codes if _humanize_reason(c)})
    gate = map_identity_gate(identity_trust_status=status)
    return pm_identity_trust_payload(
        identity_trust_status=status,
        identity_gate=gate,
        review_required=status != "trusted",
        operator_action_required=status in {"review_required", "ambiguous", "mismatch", "blocked"},
        safe_project_label=_safe_label(project_display_name, fallback="Project"),
        safe_schedule_label=schedule_label,
        safe_reasons=list(safe_reasons),
        recommended_operator_actions=_RECOMMENDED_ACTIONS.get(status, []),
        pm_message=_pm_message(status=status, gate=gate),
        technical_identity={
            "schedule_trust_status": trust_status or None,
            "membership_status": membership_status or None,
            "identity_match_status": (identity_match or {}).get("match_status"),
            "requires_review": bool(int((identity_match or {}).get("requires_review") or 0)),
            "candidate_count": (identity_match or {}).get("candidate_count"),
            "confidence_score": (identity_match or {}).get("confidence_score"),
        },
    )


def _pm_message(*, status: IdentityTrustStatus, gate: IdentityGate) -> str:
    if status == "trusted":
        return "Schedule identity is trusted for PM review at the current project context."
    if status == "mismatch":
        return "Schedule identity does not match the linked project. Analytics are blocked."
    if status == "blocked":
        return "Schedule identity is blocked for this project series. Analytics are blocked."
    if status == "ambiguous":
        return "Schedule identity is ambiguous. Treat analytics as degraded until an operator resolves identity."
    if status == "review_required":
        return "Schedule identity review is required before relying on comparison analytics."
    return "Schedule identity evidence is unavailable for this context."


def pm_identity_trust_payload(
    *,
    identity_trust_status: IdentityTrustStatus,
    identity_gate: IdentityGate,
    review_required: bool,
    operator_action_required: bool,
    safe_project_label: str,
    safe_schedule_label: str,
    safe_reasons: list[str],
    recommended_operator_actions: list[str],
    pm_message: str,
    technical_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "identity_trust_status": identity_trust_status,
        "identity_gate": identity_gate,
        "review_required": review_required,
        "operator_action_required": operator_action_required,
        "safe_project_label": safe_project_label,
        "safe_schedule_label": safe_schedule_label,
        "safe_reasons": safe_reasons,
        "recommended_operator_actions": recommended_operator_actions,
        "pm_message": pm_message,
    }
    if technical_identity:
        out["technical_identity"] = technical_identity
    return out


def assert_pm_identity_payload_redacted(payload: dict[str, Any]) -> list[str]:
    """Return forbidden keys present at top level of a PM identity payload."""
    leaks: list[str] = []
    for key in payload:
        if key in _FORBIDDEN_PM_KEYS:
            leaks.append(key)
    return leaks
