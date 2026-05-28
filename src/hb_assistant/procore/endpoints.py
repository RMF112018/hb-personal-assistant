"""Phase 04A canonical endpoint adapter registry.

The 14 IDs listed in ``12_Endpoint_Command_Matrix.md`` are the canonical
command-surface scheme. Each row carries everything the live sync orchestrator
needs to honor the contract (path template, pagination shape, parent/child
routing, review-required hint, SQLite target, and live-verified gate).

Existing pre-04A keys (``list-rfis``, ``list-submittals``, ...) remain valid
input via the ``legacy_endpoint_alias`` field so backward-compatible callers
keep working without a rename pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class EndpointAdapter:
    """One row of the canonical endpoint matrix."""

    endpoint_id: str
    family: str
    legacy_endpoint_alias: Optional[str]
    path_template: str
    parent_path_template: Optional[str]  # for child endpoints, the parent list path
    required_path_params: Tuple[str, ...]  # path parameters supplied at call time
    pagination: str  # "page+per_page" | "none"
    record_id_field: str
    parent_record_id_field: Optional[str]
    review_required_default: bool
    sensitivity: str  # "low" | "medium" | "high" | "critical"
    sqlite_target: str  # canonical table name (procore_live_records)
    live_verified: bool
    verification_reason: str


# Canonical 14-row registry. Live-verified status mirrors the Phase 04A
# command matrix: the 5 rows marked True are docs-verified for live GET;
# the other 9 are command-visible but fail-closed at orchestration time.
_ENDPOINTS: Tuple[EndpointAdapter, ...] = (
    EndpointAdapter(
        endpoint_id="projects",
        family="foundation",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects",
        parent_path_template=None,
        required_path_params=(),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="low",
        sqlite_target="procore_live_records",
        live_verified=True,
        verification_reason="live_smoke_passed_2026-05-28:7703b766",
    ),
    EndpointAdapter(
        endpoint_id="rfis",
        family="rfis",
        legacy_endpoint_alias="list-rfis",
        path_template="/rest/v1.0/projects/{project_id}/rfis",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=True,
        verification_reason="live_smoke_passed_2026-05-28:09113b6d",
    ),
    EndpointAdapter(
        endpoint_id="rfi-responses",
        family="rfis",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/rfis/{rfi_id}/replies",
        parent_path_template="/rest/v1.0/projects/{project_id}/rfis",
        required_path_params=("project_id", "rfi_id"),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field="rfi_id",
        review_required_default=True,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="populated_via_rfis_parent_fetch_2026-05-28",
    ),
    EndpointAdapter(
        endpoint_id="submittals",
        family="submittals",
        legacy_endpoint_alias="list-submittals",
        path_template="/rest/v1.0/projects/{project_id}/submittals",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=True,
        verification_reason="live_smoke_passed_2026-05-28:d9506311",
    ),
    EndpointAdapter(
        endpoint_id="submittal-responses",
        family="submittals",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses",
        parent_path_template="/rest/v1.0/projects/{project_id}/submittals",
        required_path_params=("project_id", "submittal_id"),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field="submittal_id",
        review_required_default=True,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="live_apply_child_fetch_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses",
    ),
    EndpointAdapter(
        endpoint_id="submittal-packages",
        family="submittals",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/submittals/packages",
        parent_path_template="/rest/v1.0/projects/{project_id}/submittals",
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="live_smoke_failed_2026-05-28:http_404_at_/rest/v1.0/projects/{project_id}/submittals/packages",
    ),
    EndpointAdapter(
        endpoint_id="observations",
        family="observations",
        legacy_endpoint_alias="list-observations",
        path_template="/rest/v1.0/projects/{project_id}/observations/items",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=True,
        sensitivity="high",
        sqlite_target="procore_live_records",
        live_verified=True,
        verification_reason="live_smoke_passed_2026-05-28:2d0a091f",
    ),
    EndpointAdapter(
        endpoint_id="meetings",
        family="meetings",
        legacy_endpoint_alias="list-meetings",
        path_template="/rest/v1.1/projects/{project_id}/meetings",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="phase_04a_prompt_07:v1.1_path_resolves_10_records_but_normalize_meeting_v1.0_schema_mismatch_pending_normalizer_update",
    ),
    EndpointAdapter(
        endpoint_id="meeting-topics",
        family="meetings",
        legacy_endpoint_alias="list-meeting-topics",
        path_template="/rest/v1.0/projects/{project_id}/meetings/{meeting_id}/topics",
        parent_path_template="/rest/v1.0/projects/{project_id}/meetings",
        required_path_params=("project_id", "meeting_id"),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field="meeting_id",
        review_required_default=True,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="child_endpoint_pending_docs_verification",
    ),
    EndpointAdapter(
        endpoint_id="daily-log-weather",
        family="daily_logs",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/weather_logs",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="low",
        sqlite_target="procore_live_records",
        live_verified=True,
        verification_reason="live_smoke_passed_2026-05-28:e4d9f384",
    ),
    EndpointAdapter(
        endpoint_id="daily-log-manpower",
        family="daily_logs",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/manpower_logs",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="low",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="daily_log_section_pending_docs_verification",
    ),
    EndpointAdapter(
        endpoint_id="daily-log-notes",
        family="daily_logs",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/notes_logs",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=True,
        sensitivity="high",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="daily_log_section_pending_docs_verification",
    ),
    EndpointAdapter(
        endpoint_id="daily-log-deliveries",
        family="daily_logs",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/delivery_logs",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=False,
        sensitivity="medium",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="daily_log_section_pending_docs_verification",
    ),
    EndpointAdapter(
        endpoint_id="daily-log-delays-review-routed",
        family="daily_logs",
        legacy_endpoint_alias=None,
        path_template="/rest/v1.0/projects/{project_id}/delay_logs",
        parent_path_template=None,
        required_path_params=("project_id",),
        pagination="page+per_page",
        record_id_field="id",
        parent_record_id_field=None,
        review_required_default=True,
        sensitivity="critical",
        sqlite_target="procore_live_records",
        live_verified=False,
        verification_reason="daily_log_safety_section_pending_docs_verification",
    ),
)

_BY_ID: Dict[str, EndpointAdapter] = {ep.endpoint_id: ep for ep in _ENDPOINTS}
_BY_LEGACY: Dict[str, EndpointAdapter] = {
    ep.legacy_endpoint_alias: ep
    for ep in _ENDPOINTS
    if ep.legacy_endpoint_alias is not None
}


def get(endpoint_id: str) -> Optional[EndpointAdapter]:
    """Resolve by canonical id; fall back to legacy alias for backward compatibility."""
    if endpoint_id in _BY_ID:
        return _BY_ID[endpoint_id]
    return _BY_LEGACY.get(endpoint_id)


def list_all() -> List[EndpointAdapter]:
    """Return the canonical 14-row registry in declaration order."""
    return list(_ENDPOINTS)


def list_verified() -> List[EndpointAdapter]:
    """Return only the live-verified adapters."""
    return [ep for ep in _ENDPOINTS if ep.live_verified]


def is_known(endpoint_id: str) -> bool:
    return endpoint_id in _BY_ID or endpoint_id in _BY_LEGACY


__all__ = [
    "EndpointAdapter",
    "get",
    "is_known",
    "list_all",
    "list_verified",
]
