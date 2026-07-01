"""PM-safe analytics trust ledger for schedule import and hub surfaces."""

from __future__ import annotations

from typing import Any, Literal

from hb_assistant.construction.analytics.schedule_cpm_trust import (
    map_cpm_trust_status,
    public_cpm_trust_fields,
    redact_cpm_failure_message,
)
from hb_assistant.store.project_schedule_hub_repository import MEMBERSHIP_EXCLUDED

AnalyticsTrustStatus = Literal["ready", "degraded", "blocked"]
TrustPhase = Literal["preview", "committed", "hub"]

# Gate rules (normative):
#
# blocked — PM analytics must not be treated as review-ready.
#   preview: parse/assembly failed; duplicate supersede required without confirmation
#   committed/hub: CPM recompute failed; quality evaluation failed; identity membership excluded
#
# degraded — analytics may be used with explicit limitations.
#   preview: trust warnings (identity overlap, new series, ignored package files)
#   committed/hub: CPM partial/pending/unavailable; quality pending/running/partial;
#                  identity partial; capability/readiness limitations (not defects)
#
# ready — analytics are sufficiently trustworthy for PM review at current maturity.
#   preview: parse complete, no blocking trust warnings, commit path clear
#   committed/hub: CPM complete or partial with outputs; quality complete or partial (not failed);
#                identity accepted/complete; no blocking trust reasons

_CAPABILITY_OUT_OF_SEQUENCE = (
    "Out-of-sequence progress analysis is not implemented in this release; "
    "do not treat schedule movement as entitlement or causation."
)


def normalize_quality_status(status: str | None, *, committed: bool) -> str:
    if not committed:
        return "not_started"
    if not status:
        return "pending"
    normalized = str(status)
    if normalized == "completed":
        return "complete"
    if normalized in {"pending", "running", "complete", "partial", "failed"}:
        return normalized
    return "pending"


def resolve_analytics_trust_status(
    *,
    phase: TrustPhase,
    parse_status: str = "complete",
    quality_status: str = "not_started",
    cpm_status: str = "not_started",
    identity_status: str = "not_started",
    identity_membership_status: str | None = None,
    trust_warnings: list[dict[str, Any]] | None = None,
    capability_limitations: list[str] | None = None,
    supersede_blocked: bool = False,
) -> AnalyticsTrustStatus:
    warnings = trust_warnings or []
    limitations = capability_limitations or []

    if parse_status == "failed":
        return "blocked"
    if supersede_blocked:
        return "blocked"

    if phase in {"committed", "hub"}:
        if cpm_status == "failed":
            return "blocked"
        if quality_status == "failed":
            return "blocked"
        if identity_membership_status == MEMBERSHIP_EXCLUDED:
            return "blocked"

    blocking_warning_codes = {
        "duplicate_schedule_version",
    }
    if phase == "preview" and any(str(w.get("code") or "") in blocking_warning_codes for w in warnings):
        if supersede_blocked:
            return "blocked"

    degraded = False
    if warnings:
        degraded = True
    if limitations:
        degraded = True
    if phase == "preview":
        if parse_status != "complete":
            degraded = True
        elif warnings:
            degraded = True
        else:
            return "ready"
        return "degraded"

    if cpm_status in {"partial", "pending", "unavailable", "not_started"}:
        degraded = True
    if quality_status in {"pending", "running", "partial"}:
        degraded = True
    if identity_status == "partial":
        degraded = True
    if identity_membership_status and identity_membership_status not in {MEMBERSHIP_EXCLUDED, "accepted"}:
        if identity_membership_status != "accepted":
            degraded = True

    if degraded:
        return "degraded"

    if cpm_status in {"complete", "partial"} and quality_status in {"complete", "partial"}:
        if identity_status in {"complete", "not_applicable"} or identity_membership_status == "accepted":
            return "ready"
        if identity_status == "pending" and phase == "hub":
            return "degraded"

    return "degraded"


def build_trust_reasons(
    *,
    phase: TrustPhase,
    analytics_trust_status: AnalyticsTrustStatus,
    trust_warnings: list[dict[str, Any]] | None = None,
    quality_status: str = "not_started",
    cpm_status: str = "not_started",
    identity_status: str = "not_started",
    ignored_companion_files: list[dict[str, str]] | None = None,
    capability_limitations: list[str] | None = None,
    cpm_failure_code: str | None = None,
    cpm_failed_step: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    for warning in trust_warnings or []:
        message = str(warning.get("message") or "").strip()
        if message:
            reasons.append(message)
    for row in ignored_companion_files or []:
        label = str(row.get("filename") or row.get("label") or "Companion file")
        detail = str(row.get("reason") or row.get("message") or "ignored during package assembly")
        reasons.append(f"{label}: {detail}")
    for item in capability_limitations or []:
        if item and item not in reasons:
            reasons.append(item)

    if analytics_trust_status == "blocked":
        if cpm_status == "failed":
            redacted = redact_cpm_failure_message(
                failure_code=cpm_failure_code,
                failed_step=cpm_failed_step,
            )
            if redacted:
                reasons.append(redacted)
        if quality_status == "failed":
            reasons.append("Schedule quality evaluation failed for this version.")
        if identity_status == "partial":
            reasons.append("Schedule identity review is incomplete for this project.")
    elif analytics_trust_status == "degraded":
        if cpm_status == "partial":
            reasons.append("Computed CPM finished partially; some chain outputs may be missing.")
        if cpm_status in {"pending", "unavailable"}:
            reasons.append("Computed CPM is not yet available for this schedule version.")
        if quality_status in {"pending", "running"}:
            reasons.append("Schedule quality evaluation is still running.")
        if quality_status == "partial":
            reasons.append("Schedule quality evaluation completed with review findings.")

    return reasons


def default_capability_limitations() -> list[str]:
    return [_CAPABILITY_OUT_OF_SEQUENCE]


def build_analytics_trust_ledger(
    *,
    phase: TrustPhase,
    parse_status: str = "complete",
    quality_status: str = "not_started",
    cpm_status: str = "not_started",
    identity_status: str = "not_started",
    identity_membership_status: str | None = None,
    trust_warnings: list[dict[str, Any]] | None = None,
    source_formats_detected: list[str] | None = None,
    source_formats_used: list[str] | None = None,
    ignored_companion_files: list[dict[str, str]] | None = None,
    merge_status: str | None = None,
    equivalence_status: str | None = None,
    canonical_activity_count: int | None = None,
    canonical_relationship_count: int | None = None,
    baseline_project_count: int | None = None,
    cpm_observability: dict[str, Any] | None = None,
    cpm_trigger_source: str | None = None,
    supersede_blocked: bool = False,
    capability_limitations: list[str] | None = None,
) -> dict[str, Any]:
    quality_status = normalize_quality_status(quality_status, committed=phase != "preview")
    limitations = list(capability_limitations or [])
    if phase in {"committed", "hub"}:
        for item in default_capability_limitations():
            if item not in limitations:
                limitations.append(item)

    analytics_trust_status = resolve_analytics_trust_status(
        phase=phase,
        parse_status=parse_status,
        quality_status=quality_status,
        cpm_status=cpm_status,
        identity_status=identity_status,
        identity_membership_status=identity_membership_status,
        trust_warnings=trust_warnings,
        capability_limitations=limitations,
        supersede_blocked=supersede_blocked,
    )
    cpm_trust = public_cpm_trust_fields(
        observability=cpm_observability,
        cpm_recompute_status=cpm_status,
        trigger_source=cpm_trigger_source,
    )
    trust_reasons = build_trust_reasons(
        phase=phase,
        analytics_trust_status=analytics_trust_status,
        trust_warnings=trust_warnings,
        quality_status=quality_status,
        cpm_status=cpm_status,
        identity_status=identity_status,
        ignored_companion_files=ignored_companion_files,
        capability_limitations=limitations,
        cpm_failure_code=str(cpm_observability.get("failure_code") or "") or None if cpm_observability else None,
        cpm_failed_step=str(cpm_observability.get("failed_step") or "") or None if cpm_observability else None,
    )
    return {
        "analytics_trust_status": analytics_trust_status,
        "trust_reasons": trust_reasons,
        "source_formats_detected": list(source_formats_detected or []),
        "source_formats_used": list(source_formats_used or []),
        "ignored_companion_files": list(ignored_companion_files or []),
        "merge_status": merge_status,
        "equivalence_status": equivalence_status,
        "canonical_activity_count": canonical_activity_count,
        "canonical_relationship_count": canonical_relationship_count,
        "baseline_project_count": baseline_project_count,
        "quality_status": quality_status,
        "cpm_status": cpm_status,
        "cpm_trust": cpm_trust,
        "capability_limitations": limitations,
    }


def map_committed_cpm_status(
    summary: dict[str, Any],
    *,
    observability: dict[str, Any] | None = None,
) -> str:
    if observability and str(observability.get("status") or "") == "failed":
        return "failed"
    runs = summary.get("runs") or {}
    kinds = (
        "graph_diagnostics",
        "forward_pass",
        "backward_pass",
        "float",
        "longest_path",
        "criticality",
    )
    if not any((runs.get(kind) or {}).get("available") for kind in kinds):
        return "pending"
    required = ("forward_pass", "backward_pass", "float", "longest_path", "criticality")
    if all((runs.get(kind) or {}).get("available") for kind in required):
        return "complete"
    if any((runs.get(kind) or {}).get("available") for kind in required):
        return "partial"
    return "unavailable"


def map_committed_identity_status(membership: dict[str, Any] | None) -> str:
    if not membership:
        return "pending"
    status = str(membership.get("membership_status") or "")
    if status == "accepted":
        return "complete"
    if status:
        return "partial"
    return "pending"


def extract_ignored_companion_files(preview: dict[str, Any]) -> list[dict[str, str]]:
    ignored: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(filename: str, reason: str) -> None:
        key = f"{filename}:{reason}"
        if key in seen:
            return
        seen.add(key)
        ignored.append({"filename": filename, "reason": reason})

    for warning in preview.get("warnings") or []:
        if str(warning.get("code") or "") != "unsupported_package_file_ignored":
            continue
        add(
            str(warning.get("filename") or "companion"),
            str(warning.get("message") or "unsupported companion ignored"),
        )
    for file_row in preview.get("files") or []:
        for warning in file_row.get("warnings") or []:
            if str(warning.get("code") or "") != "unsupported_package_file_ignored":
                continue
            add(
                str(file_row.get("filename") or warning.get("filename") or "companion"),
                str(warning.get("message") or "unsupported companion ignored"),
            )
    return ignored


def ledger_from_import_preview(
    preview: dict[str, Any],
    *,
    trust_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trust = trust_preview or {}
    warnings = list(trust.get("warnings") or [])
    supersede_blocked = trust.get("posture") == "supersede_required" and any(
        str(warning.get("code") or "") == "duplicate_schedule_version" for warning in warnings
    )
    equivalence = preview.get("equivalence_report") or {}
    formats = sorted(
        {
            str(file_row.get("source_format"))
            for file_row in preview.get("files") or []
            if file_row.get("source_format")
        }
    )
    ledger = build_analytics_trust_ledger(
        phase="preview",
        trust_warnings=warnings,
        ignored_companion_files=extract_ignored_companion_files(preview),
        source_formats_detected=formats,
        source_formats_used=formats,
        merge_status=str(equivalence.get("status") or "") or None,
        equivalence_status=str(equivalence.get("status") or "") or None,
        canonical_activity_count=preview.get("activity_count"),
        canonical_relationship_count=preview.get("relationship_count"),
        baseline_project_count=len(preview.get("baseline_project_candidates") or []),
        supersede_blocked=supersede_blocked,
    )
    return pm_analytics_trust_payload(ledger)


def ledger_from_pipeline_status(pipeline: dict[str, Any]) -> dict[str, Any]:
    cpm = pipeline.get("cpm") or {}
    observability = {
        "status": cpm.get("cpm_recompute_status"),
        "failure_code": cpm.get("failure_code"),
        "failed_step": cpm.get("failed_step"),
        "trigger_source": cpm.get("trigger_source"),
        "canonical_input_activity_count": cpm.get("canonical_input_activity_count"),
        "canonical_input_relationship_count": cpm.get("canonical_input_relationship_count"),
        "graph_node_count": cpm.get("graph_node_count"),
        "graph_edge_count": cpm.get("graph_edge_count"),
        "duration_ms": cpm.get("duration_ms"),
    }
    ledger = build_analytics_trust_ledger(
        phase="committed",
        quality_status=str(pipeline.get("quality_evaluation_status") or "not_started"),
        cpm_status=str(cpm.get("cpm_recompute_status") or "not_started"),
        identity_status=map_committed_identity_status(
            {"membership_status": pipeline.get("identity_membership_status")}
            if pipeline.get("identity_membership_status")
            else None
        ),
        identity_membership_status=pipeline.get("identity_membership_status"),
        cpm_observability=observability,
        cpm_trigger_source=cpm.get("trigger_source"),
    )
    return pm_analytics_trust_payload(ledger)


def ledger_for_hub_version(
    *,
    quality_status: str,
    cpm_status: str,
    identity_status: str,
    identity_membership_status: str | None,
    cpm_observability: dict[str, Any] | None,
    canonical_activity_count: int | None = None,
    canonical_relationship_count: int | None = None,
    source_format: str | None = None,
) -> dict[str, Any]:
    formats = [source_format] if source_format else []
    ledger = build_analytics_trust_ledger(
        phase="hub",
        quality_status=quality_status,
        cpm_status=cpm_status,
        identity_status=identity_status,
        identity_membership_status=identity_membership_status,
        cpm_observability=cpm_observability,
        cpm_trigger_source=(cpm_observability or {}).get("trigger_source"),
        canonical_activity_count=canonical_activity_count,
        canonical_relationship_count=canonical_relationship_count,
        source_formats_detected=formats,
        source_formats_used=formats,
    )
    return pm_analytics_trust_payload(ledger)


def pm_analytics_trust_payload(ledger: dict[str, Any]) -> dict[str, Any]:
    """Default PM payload without operator diagnostics."""
    out = dict(ledger)
    cpm_trust = dict(out.get("cpm_trust") or {})
    out["cpm_trust_status"] = cpm_trust.get("cpm_trust_status")
    out["cpm_recompute_status"] = cpm_trust.get("cpm_recompute_status")
    out["trigger_source"] = cpm_trust.get("trigger_source")
    out["failed_step"] = cpm_trust.get("failed_step")
    out["failure_code"] = cpm_trust.get("failure_code")
    out["failure_message_redacted"] = cpm_trust.get("failure_message_redacted")
    out["canonical_input_activity_count"] = cpm_trust.get("canonical_input_activity_count")
    out["canonical_input_relationship_count"] = cpm_trust.get("canonical_input_relationship_count")
    out["graph_node_count"] = cpm_trust.get("graph_node_count")
    out["graph_edge_count"] = cpm_trust.get("graph_edge_count")
    out["duration_ms"] = cpm_trust.get("duration_ms")
    return out
