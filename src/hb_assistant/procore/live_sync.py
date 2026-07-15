"""Phase 04A per-endpoint live sync orchestrator.

Single entry point :func:`run_live_sync` assembles the full chain for one
endpoint id: gate checks -> adapter lookup -> verified-or-fail-closed ->
token fetch -> GET pagination -> per-item normalization -> SQLite upsert ->
watermark update -> redacted receipt.

The orchestrator never raises raw exception strings into the receipt or logs;
all error paths flow through :mod:`hb_assistant.procore.redaction`. Unverified
endpoints return a structured ``not_live_verified`` receipt with
``no_live_call_performed=True`` and zero counts — the transport is never
touched and no DB row is written.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hb_assistant.procore.endpoints import EndpointAdapter
from hb_assistant.procore.endpoints import get as get_adapter
from hb_assistant.procore.errors import (
    ProcoreAPIError,
    ProcoreAuthRequired,
    ProcoreRateLimitError,
)
from hb_assistant.procore.live_gate import (
    direct_live_project_eligibility,
    live_env_active,
)
from hb_assistant.procore.loader import load_procore_projects
from hb_assistant.procore.normalizers import (
    daily_log_live,
    extract_topics_from_categories,
    normalize_activity,
    normalize_inspection,
    normalize_inspection_item,
    normalize_inspection_section,
    normalize_meeting,
    normalize_meeting_detail,
    normalize_meeting_topic,
    normalize_observation,
    normalize_punch_item,
    normalize_rfi,
    normalize_rfi_reply,
    normalize_schedule,
    normalize_submittal,
    normalize_submittal_package,
    normalize_submittal_response,
)
from hb_assistant.procore.normalizers.budget import (
    normalize_budget_change_history,
    normalize_budget_change_line_item,
    normalize_budget_detail_column,
    normalize_budget_detail_row,
    normalize_budget_modification,
    normalize_budget_view,
)
from hb_assistant.procore.normalizers.commitment_contract import (
    normalize_commitment_attachment,
    normalize_commitment_change_order,
    normalize_commitment_change_order_line_item,
    normalize_commitment_compliance,
    normalize_commitment_contract,
    normalize_commitment_line_item,
    normalize_purchase_order_contract,
    normalize_purchase_order_detail_line_item,
    normalize_purchase_order_line_item,
)
from hb_assistant.procore.normalizers.owner_contract import (
    normalize_payment_application,
    normalize_prime_change_order,
    normalize_prime_change_order_line_item,
    normalize_prime_contract,
    normalize_prime_contract_attachment,
    normalize_prime_contract_line_item,
)
from hb_assistant.procore.normalizers.rfq_change_event import (
    normalize_change_event,
    normalize_change_event_comment,
    normalize_rfq,
    normalize_rfq_quote,
    normalize_rfq_response,
)
from hb_assistant.procore.normalizers.subcontractor_invoice import (
    normalize_billing_period,
    normalize_subcontractor_invoice,
    normalize_subcontractor_invoice_change_order_item,
    normalize_subcontractor_invoice_contract_detail_item,
    normalize_subcontractor_invoice_contract_item,
)
from hb_assistant.procore.pagination import RetryPolicy
from hb_assistant.procore.redaction import redact_source_url
from hb_assistant.procore.structured_analytics import (
    SOURCE_QUALITY_LIVE_FULL,
    upsert_full_raw_payload_and_structured,
)
from hb_assistant.procore.token_provider import default_procore_token_provider
from hb_assistant.store.procore_budget_projection import (
    BUDGET_ENDPOINTS,
    project_budget_family,
)
from hb_assistant.store.procore_commitment_projection import (
    COMMITMENT_ENDPOINTS,
    project_commitment_family,
)
from hb_assistant.store.procore_history import record_procore_history_for_record
from hb_assistant.store.procore_inspection_projection import project_inspection
from hb_assistant.store.procore_invoice_projection import (
    INVOICE_ENDPOINTS,
    project_invoice_family,
)
from hb_assistant.store.procore_meeting_projection import project_meeting_family
from hb_assistant.store.procore_observation_projection import project_observation
from hb_assistant.store.procore_owner_projection import (
    OWNER_ENDPOINTS,
    project_owner_contract_family,
)
from hb_assistant.store.procore_punch_projection import project_punch_item
from hb_assistant.store.procore_repositories import (
    count_procore_live_child_records_for_parent,
    count_procore_live_records,
    record_sync_run_complete,
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)
from hb_assistant.store.procore_rfi_projection import project_rfi
from hb_assistant.store.procore_rfq_change_event_projection import (
    RFQ_ENDPOINTS,
    project_rfq_change_event_family,
)
from hb_assistant.store.procore_schedule_projection import project_activity
from hb_assistant.store.procore_submittal_projection import project_submittal

COMPANY_ID = "5280"
EVIDENCE_DIR_REL = "docs/evidence/construction-intelligence-phase-04a"

# High default bounds keep live sync in "full unfiltered endpoint" posture while
# still allowing operators/tests to pass lower caps for diagnostics.
DEFAULT_MAX_PAGES = 1000
DEFAULT_MAX_ITEMS = 100000
DEFAULT_MAX_CHILD_REQUESTS = 100000
DEFAULT_CHILD_REQUEST_DELAY_SECONDS = 0.0
CHILD_REFRESH_LOOKBACK_HOURS = 26
_ENDPOINT_PER_PAGE_LIMITS = {
    # Live smoke evidence: Procore returns HTTP 500 for this endpoint at
    # per_page=100, while per_page=10 succeeds.
    "meeting-topics": 10,
}
_COMMITMENT_COMPLIANCE_COMPATIBLE_PARENT_TYPES = {"WorkOrderContract"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_procore_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _should_fetch_child_records(
    *,
    project_key: str,
    child_endpoint_id: str,
    parent_id: str,
    parent_summary: Dict[str, Any],
    now_utc: datetime,
    db_path: Optional[Path],
) -> bool:
    """Daily-sync child fanout gate.

    Fetch when children are not yet populated for this parent. Once children
    exist, fetch only if the parent was updated in the prior 26 hours. Missing
    or unparseable parent timestamps fail open so we do not miss updates.
    """
    existing_children = count_procore_live_child_records_for_parent(
        project_key=project_key,
        endpoint_id=child_endpoint_id,
        parent_procore_id=str(parent_id),
        db_path=db_path,
    )
    if existing_children == 0:
        return True

    parent_updated_at = _parse_procore_datetime(parent_summary.get("updated_at"))
    if parent_updated_at is None:
        return True
    return parent_updated_at >= now_utc - timedelta(hours=CHILD_REFRESH_LOOKBACK_HOURS)


def _per_page_for_endpoint(endpoint_id: str, max_items: int) -> int:
    if endpoint_id in _ENDPOINT_PER_PAGE_LIMITS:
        return _ENDPOINT_PER_PAGE_LIMITS[endpoint_id]
    return min(max_items, 100)


def _is_compatible_n1_parent(endpoint_id: str, parent_summary: Dict[str, Any]) -> bool:
    if endpoint_id != "commitment-compliance":
        return True
    parent_type = parent_summary.get("type")
    if parent_type is None:
        # Older fixtures and defensive live payloads may not carry type; do not
        # silently drop potentially compatible parents unless Procore identified
        # them as an incompatible commitment class.
        return True
    return str(parent_type) in _COMMITMENT_COMPLIANCE_COMPATIBLE_PARENT_TYPES


def _normalize_project(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Minimal projects normalizer (parent-only, low sensitivity)."""
    if not isinstance(raw, dict):
        raise TypeError("normalize_project requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_project requires raw['id']")
    canonical: Dict[str, Any] = {}
    for key in ("id", "name", "display_name", "project_number", "stage", "active", "updated_at"):
        if key in raw and raw[key] is not None:
            canonical[key] = raw[key]
    return {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "projects",
        "review_required": False,
        "routing_reason": "projects_low_sensitivity",
        "canonical_fields": canonical,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
    }


def _normalize_submittal_package_top_level(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Standalone /submittals/packages normalizer.

    Packages at this endpoint are sibling resources to submittals, not
    children of a specific submittal — there is no parent submittal id, so
    the synthetic parent key ``standalone`` is used.
    """
    return normalize_submittal_package(
        raw,
        parent_procore_id="standalone",
        project_key=project_key,
        endpoint_id=endpoint_id,
        correlation_id=correlation_id,
        fetched_at=fetched_at,
    )


# Canonical-id -> child normalizer fn. Children share a uniform kwarg signature
# (parent_procore_id) so the generic dispatch can call them through a single
# lookup keyed on the child adapter's endpoint_id.
_CHILD_NORMALIZER_BY_ID: Dict[str, Callable[..., Dict[str, Any]]] = {
    "rfi-responses": normalize_rfi_reply,
    "submittal-responses": normalize_submittal_response,
    "meeting-topics": normalize_meeting_topic,
}


# Parent endpoint_id -> field name carrying inline children in the parent
# list payload. Procore's list endpoints already embed children (RFI
# replies, submittal responses); reading them inline avoids the N+1 GET
# pattern that triggered rate-limit storms in prior probes.
_INLINE_CHILD_FIELD_BY_PARENT_ID: Dict[str, str] = {
    "rfis": "replies",
    "submittals": "responses",
    "meetings": "topics",
}


def _resolve_child_adapter(parent_adapter: EndpointAdapter) -> Optional[EndpointAdapter]:
    """Find the registry's child adapter for a given parent, if any.

    A child adapter belongs to the same ``family`` as the parent AND has
    ``parent_record_id_field`` set (i.e., it expects a parent record id in
    its path_template). Path matching by ``parent_path_template`` is
    intentionally avoided because parent path_templates evolve (e.g.,
    meetings moved from v1.0 to v1.1 in the Prompt 07 backlog) while child
    adapters keep their original parent_path_template values.
    """
    from hb_assistant.procore.endpoints import list_all

    for candidate in list_all():
        if candidate.parent_record_id_field is None:
            continue
        if candidate.family != parent_adapter.family:
            continue
        if candidate.endpoint_id == parent_adapter.endpoint_id:
            continue
        return candidate
    return None


# Canonical-id -> normalizer fn for the 5 live-verified endpoints. Unverified
# endpoints intentionally have no entry: they fail closed before normalization.
_NORMALIZER_BY_ID: Dict[str, Callable[..., Dict[str, Any]]] = {
    "projects": _normalize_project,
    "rfis": normalize_rfi,
    "submittals": normalize_submittal,
    "submittal-packages": _normalize_submittal_package_top_level,
    "meetings": normalize_meeting,
    # daily-log-* live normalizers (Phase 04B): real Procore field contracts +
    # PII hashing + entity/edge/action-signal projection. Covers the 7 prior
    # sections plus accident / dumpster / safety-violation / visitor.
    **daily_log_live.NORMALIZER_BY_ENDPOINT,
    # meeting-topics is also a standalone top-level v1.1 endpoint
    # (/meeting_topics root noun). The same normalize_meeting_topic function
    # used in _CHILD_NORMALIZER_BY_ID handles both contexts because its
    # parent_procore_id kwarg defaults to None.
    "meeting-topics": normalize_meeting_topic,
    # meeting-detail is a per-meeting rich fetch with PII-bearing fields;
    # the orchestrator's meeting-detail branch fetches the list first then
    # iterates one detail GET per meeting.
    "meeting-detail": normalize_meeting_detail,
    # Convenience: observations is not docs-verified in the matrix, but its
    # normalizer is already exercised in dry-run tests. Future promotion can
    # flip endpoints.live_verified=True without code changes here.
    "observations": normalize_observation,
    # punch-items is a top-level list endpoint with project_id as a query
    # param (no path placeholder). PII (people refs, assignment login info)
    # and free-text (description, schedule_risk_reason, comments) are
    # reduced to hash-only summaries inside the normalizer.
    "punch-items": normalize_punch_item,
    # v2.0 company-scoped scheduling endpoints. data envelope is unwrapped
    # by http_client.paginate. activities is the child of schedules and
    # fetched via per-schedule N+1 when operator selects --endpoint activities.
    "schedules": normalize_schedule,
    "activities": normalize_activity,
    # Inspections: list at /rest/v1.0/projects/{project_id}/checklist/lists.
    # Heavy PII (inspectors, signature_requests, point_of_contact) +
    # attachments + custom_fields; review_required heuristic mirrors the
    # observation safety/status fragment scan.
    "inspections": normalize_inspection,
    # inspection-sections is a project-wide flat list of checklist
    # template sections at
    # /rest/v1.0/projects/{project_id}/checklist/list_sections.
    # Structural only — id, name, position, template_section_id,
    # updated_at — no PII, no parent.
    "inspection-sections": normalize_inspection_section,
    # inspection-items is a project-wide flat list of checklist items
    # at /rest/v1.1/projects/{project_id}/checklist/list_items. Each
    # item payload carries list_id + section_id directly; the upsert
    # step derives parent_procore_id from raw["list_id"] the same way
    # activities derives schedule_id. Always review_required=True due
    # to per-item PII (responder), free-text bodies, and nested
    # observation refs.
    "inspection-items": normalize_inspection_item,
    # Phase 05 owner-side financial endpoints. Registered so the live chain can
    # normalize + project them once promoted; they remain live_verified=False in
    # the registry, so the orchestrator still fail-closes before this lookup.
    "prime-contracts": normalize_prime_contract,
    "prime-contract-line-items": normalize_prime_contract_line_item,
    "prime-contract-attachments": normalize_prime_contract_attachment,
    "prime-change-orders": normalize_prime_change_order,
    "prime-change-order-line-items": normalize_prime_change_order_line_item,
    "payment-applications": normalize_payment_application,
    # Phase 05 vendor-side financial endpoints (commitments + PO compatibility).
    # Same fail-closed posture: registered but live_verified=False in the registry.
    "commitment-contracts": normalize_commitment_contract,
    "commitment-line-items": normalize_commitment_line_item,
    "commitment-change-orders": normalize_commitment_change_order,
    "commitment-change-order-line-items": normalize_commitment_change_order_line_item,
    "commitment-attachments": normalize_commitment_attachment,
    "commitment-compliance": normalize_commitment_compliance,
    "purchase-order-contracts": normalize_purchase_order_contract,
    "purchase-order-line-items": normalize_purchase_order_line_item,
    "purchase-order-detail-line-items": normalize_purchase_order_detail_line_item,
    # Phase 05 subcontractor billing surface (billing periods + requisitions +
    # invoice items). Same fail-closed posture: registered but live_verified=False.
    "billing-periods": normalize_billing_period,
    "subcontractor-invoices": normalize_subcontractor_invoice,
    "subcontractor-invoice-contract-items": normalize_subcontractor_invoice_contract_item,
    "subcontractor-invoice-contract-detail-items": normalize_subcontractor_invoice_contract_detail_item,
    "subcontractor-invoice-change-order-items": normalize_subcontractor_invoice_change_order_item,
    # Phase 05 change-management surface (RFQs + responses/quotes + change events
    # + comments). Same fail-closed posture: registered but live_verified=False.
    "rfqs": normalize_rfq,
    "rfq-responses": normalize_rfq_response,
    "rfq-quotes": normalize_rfq_quote,
    "change-events": normalize_change_event,
    "change-event-comments": normalize_change_event_comment,
    # Phase 05 budget surface (views / detail-columns / detail-rows / change-history
    # / change-line-items / modifications). budget-details is a non-routable sentinel
    # and is intentionally NOT registered. live_verified=False (fail-closed).
    "budget-views": normalize_budget_view,
    "budget-detail-columns": normalize_budget_detail_column,
    "budget-detail-rows": normalize_budget_detail_row,
    "budget-change-history": normalize_budget_change_history,
    "budget-change-line-items": normalize_budget_change_line_item,
    "budget-modifications": normalize_budget_modification,
}


def resolve_normalizer(endpoint_id: str) -> Optional[Callable[..., Dict[str, Any]]]:
    """Return the normalizer callable for an endpoint id (parent map, then child
    map). Read-only lookup used by the local coverage tooling — no I/O."""
    return _NORMALIZER_BY_ID.get(endpoint_id) or _CHILD_NORMALIZER_BY_ID.get(endpoint_id)


# Endpoints whose records carry no natural id field. budget-change-history is an
# append-only change log keyed by (budget_code, column, when, before/after) rather than
# an id; derive a deterministic synthetic id so latest-state upsert + history stay
# idempotent (same change -> same id).
_SYNTHETIC_RECORD_ID_FIELDS: Dict[str, tuple[str, ...]] = {
    "budget-change-history": ("budget_code", "column", "created_at", "old_value", "new_value"),
    # The work-order-contract compliance blob is id-less (one per commitment); key it
    # by the parent contract id tagged onto each child during the N+1 fetch.
    "commitment-compliance": ("_hb_parent_procore_id",),
}


def _record_id_of(adapter: EndpointAdapter, raw: Dict[str, Any]) -> Optional[str]:
    value = raw.get(adapter.record_id_field)
    if value is None or value == "":
        fields = _SYNTHETIC_RECORD_ID_FIELDS.get(adapter.endpoint_id)
        if fields and isinstance(raw, dict):
            import hashlib

            key = "|".join("" if raw.get(f) is None else str(raw.get(f)) for f in fields)
            if key.strip("|"):
                return "h:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return None
    return str(value)


def _parent_id_for_upsert(adapter: EndpointAdapter, raw: Dict[str, Any]) -> Optional[str]:
    """Resolve the parent record id for a child/N+1 endpoint item, else None.

    activities link to their schedule (``schedule_id``); inspection-items link to
    their list (``list_id``); generalized N+1 children carry the parent id tagged
    under ``_PARENT_ID_KEY`` during the fetch. All other endpoints have no parent.
    """
    if not isinstance(raw, dict):
        return None
    if adapter.endpoint_id == "activities":
        value = raw.get("schedule_id")
    elif adapter.endpoint_id == "inspection-items":
        value = raw.get("list_id")
    elif adapter.endpoint_id in _N1_CHILD_ENDPOINTS:
        value = raw.get(_PARENT_ID_KEY)
    else:
        return None
    return str(value) if value not in (None, "") else None


def _resolve_procore_project_id(project_key: str) -> Optional[str]:
    try:
        registry = load_procore_projects()
    except Exception:  # noqa: BLE001 -- registry errors surface as fail-closed receipt
        return None
    for project in registry.projects:
        if project.hb_project_key == project_key:
            value = (project.procore_project_id or "").strip()
            return value or None
    return None


def _safe_count_procore_live_records(
    *, project_key: str, endpoint_id: str, db_path: Optional[Path]
) -> int:
    try:
        return count_procore_live_records(
            project_key=project_key,
            endpoint_id=endpoint_id,
            db_path=db_path,
        )
    except Exception:  # noqa: BLE001 -- fail-closed receipts must not open transport
        return 0


def _resolve_path(adapter: EndpointAdapter, procore_project_id: str) -> str:
    """Substitute the project_id and company_id parameters.

    Phase 04A v2.0 endpoints (e.g., /companies/{company_id}/projects/.../schedules)
    require both. v1.x endpoints typically have only {project_id}. Path placeholders
    that don't appear in the template are no-ops.
    """
    path = adapter.path_template
    path = path.replace("{project_id}", procore_project_id)
    path = path.replace("{company_id}", COMPANY_ID)
    return path


# Phase 05 financial child endpoints whose path carries a parent record-id token
# (``parent_record_id_field``). They are fetched via a generalized N+1: list the parent
# at ``parent_path_template``, then issue one child GET per parent with the parent id
# substituted into the child token. budget-change-line-items is intentionally excluded
# (its path is a flat project-scoped list — no parent token, synced like a top-level
# endpoint). The 04A inline children (rfi-responses / submittal-responses / meeting-topics)
# are excluded — they are extracted inline from the parent payload, not fetched per-parent.
_N1_CHILD_ENDPOINTS = frozenset(
    {
        "prime-contract-line-items",
        "prime-contract-attachments",
        "prime-change-order-line-items",
        "commitment-line-items",
        "commitment-attachments",
        "commitment-compliance",
        "commitment-change-order-line-items",
        "purchase-order-line-items",
        "purchase-order-detail-line-items",
        "subcontractor-invoice-contract-items",
        "subcontractor-invoice-contract-detail-items",
        "subcontractor-invoice-change-order-items",
        "rfq-responses",
        "rfq-quotes",
        "change-event-comments",
        "budget-detail-columns",
        "budget-detail-rows",
    }
)

# Reserved key used to carry the parent procore record id on each fetched child record
# (mirrors how `activities` reuses `schedule_id`); read by the per-item parent-id
# derivation so the financial projection receives the correct `parent_procore_id`.
_PARENT_ID_KEY = "_hb_parent_procore_id"
_LIVE_SYNC_RETRY_POLICY = RetryPolicy(max_retries=0, jitter=False)

# N+1 children that need an extra query param sourced from the parent record. RFQ
# responses/quotes require `contract_id` (= the rfq's commitment_contract_id) in addition
# to project_id, else Procore 404s ("Contract not found"). Map: child -> (query_param, parent_field).
_N1_CHILD_EXTRA_PARENT_PARAMS: Dict[str, tuple[str, str]] = {
    "rfq-responses": ("contract_id", "commitment_contract_id"),
    "rfq-quotes": ("contract_id", "commitment_contract_id"),
}


def _resolve_child_path(adapter: EndpointAdapter, procore_project_id: str, parent_id: str) -> str:
    """Build an N+1 child path: substitute project_id + company_id + the parent token
    (``parent_record_id_field``) with the parent's procore record id."""
    path = _resolve_path(adapter, procore_project_id)
    if adapter.parent_record_id_field:
        path = path.replace("{" + adapter.parent_record_id_field + "}", str(parent_id))
    return path


def _project_id_query_params(path_template: str, procore_project_id: str) -> Dict[str, str]:
    """project_id as a query param iff it is NOT a path segment in the *template*.

    The decision keys off the original template, never the resolved path: once the
    placeholder is substituted the literal ``{project_id}`` is gone, so checking the
    resolved path would always (wrongly) add a redundant query param to path-scoped
    endpoints. Flat lists (e.g. ``/punch_items``, ``/payment_applications``) keep
    project_id as a query param; path-scoped (``/projects/{project_id}/...``) and v2.0
    company/project endpoints carry it in the path.
    """
    if "{project_id}" in path_template:
        return {}
    return {"project_id": str(procore_project_id)}


def _child_query_params(
    adapter: EndpointAdapter, procore_project_id: str, parent_summary: Dict[str, Any]
) -> Optional[Dict[str, str]]:
    """Query params for an N+1 child GET: project_id (when the child template is flat)
    plus any extra parent-derived param (e.g. rfq children need the parent's contract_id,
    else Procore 404s)."""
    params: Dict[str, str] = _project_id_query_params(adapter.path_template, procore_project_id)
    extra = _N1_CHILD_EXTRA_PARENT_PARAMS.get(adapter.endpoint_id)
    if extra:
        qname, pfield = extra
        pval = parent_summary.get(pfield)
        if pval is not None and pval != "":
            params[qname] = str(pval)
    return params or None


def _api_version(path_template: str) -> str:
    """Procore REST API version embedded in the path template (v1.0 / v1.1 / v2.0)."""
    if path_template.startswith("unresolved:"):
        return "unresolved"
    match = re.match(r"/rest/(v\d+\.\d+)/", path_template)
    return match.group(1) if match else "unknown"


def _request_classification(adapter: Optional[EndpointAdapter]) -> Optional[Dict[str, Any]]:
    """Redacted, secret-free request classification for the run receipt.

    Derived from the endpoint template only — no resolved ids, tokens, query values, or
    response bodies. ``project_id_param`` mirrors the actual query-construction rule:
    project_id travels in the path when the template contains ``{project_id}``, otherwise
    it is sent as a query param.
    """
    if adapter is None:
        return None
    template = adapter.path_template
    has_company = "{company_id}" in template
    has_project = "{project_id}" in template
    if has_company and has_project:
        path_scope = "company_project"
    elif has_project:
        path_scope = "project"
    else:
        path_scope = "flat"
    return {
        "api_version": _api_version(template),
        "path_scope": path_scope,
        "project_id_param": "path" if has_project else "query",
        "n_plus_1": adapter.endpoint_id in _N1_CHILD_ENDPOINTS,
        "path_template_redacted": redact_source_url(template),
    }


def _build_receipt(
    *,
    receipt_id: str,
    sync_run_id: str,
    mode: str,
    adapter: Optional[EndpointAdapter],
    command_endpoint: str,
    endpoint_id_resolved: Optional[str],
    legacy_alias: Optional[str],
    project_key: str,
    procore_project_id: Optional[str],
    state: str,
    status: str,
    reason_codes: List[str],
    request_count: int,
    attempt_count: int = 0,
    retry_count: int = 0,
    last_retry_after: Optional[int] = None,
    retrieved_count: int,
    normalized_count: int,
    sqlite_upserted_count: int,
    sqlite_total_count_after: int,
    no_live_call_performed: bool,
    started_at: str,
    completed_at: str,
    evidence_path: Optional[str],
    redacted_errors: List[Dict[str, Any]],
    parent_retrieved_count: int = 0,
    parent_normalized_count: int = 0,
    parent_upserted_count: int = 0,
    child_endpoint_id: Optional[str] = None,
    child_retrieved_count: int = 0,
    child_normalized_count: int = 0,
    child_upserted_count: int = 0,
    child_errors_count: int = 0,
    projection_error_count: int = 0,
    n1_fanout: Optional[Dict[str, Any]] = None,
    wait_on_rate_limit: bool = False,
    rate_limit_wait_count: int = 0,
    rate_limit_sleep_seconds_total: float = 0.0,
    max_rate_limit_wait_cycles: int = 0,
    raw_payload_rows_written: int = 0,
    structured_rows_written: int = 0,
    raw_persist_error_count: int = 0,
    raw_persist_skipped_higher_quality: int = 0,
    full_raw_persistence_enabled: bool = False,
) -> Dict[str, Any]:
    operator_failed_reasons = {
        "live_env_not_set",
        "confirm_live_get_required",
        "apply_required",
        "sqlite_only_required",
    }
    project_failed_reasons = {
        "project_not_mapped",
        "project_missing_procore_project_id",
        "project_mapping_registry_unavailable",
    }
    endpoint_failed_reasons = {
        "endpoint_contract_missing",
        "endpoint_not_live_eligible",
        "endpoint_alias_unknown",
        "endpoint_unverified_for_live",
    }
    reason_set = set(reason_codes)
    return {
        "receipt_id": receipt_id,
        "sync_run_id": sync_run_id,
        "phase": "phase04a",
        "mode": mode,
        "command_endpoint": command_endpoint,
        "endpoint_id": endpoint_id_resolved,
        "legacy_endpoint_alias": legacy_alias,
        "company_id": COMPANY_ID,
        "project_key": project_key,
        "procore_project_id": procore_project_id,
        "endpoint_family": adapter.family if adapter else None,
        "http_method": "GET",
        "request_classification": _request_classification(adapter),
        "request_count": request_count,
        "attempt_count": attempt_count,
        "retry_count": retry_count,
        "last_retry_after": last_retry_after,
        "wait_on_rate_limit": wait_on_rate_limit,
        "rate_limit_wait_count": rate_limit_wait_count,
        "rate_limit_sleep_seconds_total": rate_limit_sleep_seconds_total,
        "max_rate_limit_wait_cycles": max_rate_limit_wait_cycles,
        "retrieved_count": retrieved_count,
        "normalized_count": normalized_count,
        "sqlite_upserted_count": sqlite_upserted_count,
        "sqlite_total_count_after": sqlite_total_count_after,
        "raw_body_persisted": False,
        "secrets_redacted": True,
        # Full Procore business payloads are persisted to the private local DB (system
        # of record); transport/auth secrets are stripped. No payload body is ever
        # placed in this receipt or written to stdout.
        "full_raw_persistence_enabled": full_raw_persistence_enabled,
        "raw_payload_rows_written": raw_payload_rows_written,
        "structured_rows_written": structured_rows_written,
        "raw_persist_error_count": raw_persist_error_count,
        "raw_persist_skipped_due_to_higher_quality": raw_persist_skipped_higher_quality,
        "raw_payload_body_emitted_to_stdout": False,
        "operator_live_authorization": (
            "failed" if reason_set & operator_failed_reasons else "ok"
        ),
        "project_eligibility": "failed" if reason_set & project_failed_reasons else "ok",
        "endpoint_eligibility": "failed" if reason_set & endpoint_failed_reasons else "ok",
        "transport_attempted": not no_live_call_performed,
        "ok": status == "success" and raw_persist_error_count == 0,
        "state": state,
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "no_live_call_performed": no_live_call_performed,
        "redacted_errors": redacted_errors,
        "started_at": started_at,
        "completed_at": completed_at,
        "evidence_path": evidence_path,
        "parent_retrieved_count": parent_retrieved_count,
        "parent_normalized_count": parent_normalized_count,
        "parent_upserted_count": parent_upserted_count,
        "child_endpoint_id": child_endpoint_id,
        "child_retrieved_count": child_retrieved_count,
        "child_normalized_count": child_normalized_count,
        "child_upserted_count": child_upserted_count,
        "child_errors_count": child_errors_count,
        "projection_error_count": projection_error_count,
        "n1_fanout": n1_fanout,
    }


def run_live_sync(
    *,
    project_key: str,
    endpoint: str,
    apply: bool,
    sqlite_only: bool,
    confirm_live_get: bool,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_items: int = DEFAULT_MAX_ITEMS,
    max_child_requests: int = DEFAULT_MAX_CHILD_REQUESTS,
    child_request_delay_seconds: float = DEFAULT_CHILD_REQUEST_DELAY_SECONDS,
    wait_on_rate_limit: bool = False,
    rate_limit_fallback_sleep_seconds: float = 3660.0,
    max_rate_limit_wait_cycles: int = 1,
    sleep_fn: Callable[[float], None] = time.sleep,
    parent_id: Optional[str] = None,
    mode_hint: Optional[str] = None,
    db_path: Optional[Path] = None,
    transport: Optional[Any] = None,
    evidence_path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one endpoint's live sync chain and return a redacted receipt.

    ``mode_hint`` is ``"live_smoke"`` for the smoke subcommand (no SQLite
    writes), ``"live_apply"`` for full apply, and defaults to ``"live_apply"``
    when ``apply`` is True. The orchestrator never writes to SQLite in smoke
    mode regardless of the apply flag.
    """

    started_dt = datetime.now(timezone.utc)
    started_at = started_dt.isoformat()
    receipt_id = str(uuid.uuid4())
    sync_run_id = receipt_id
    correlation_id = str(uuid.uuid4())
    reason_codes: List[str] = []
    redacted_errors: List[Dict[str, Any]] = []
    request_count = 0
    attempt_count = 0
    retry_count = 0
    last_retry_after: Optional[int] = None
    rate_limit_wait_count = 0
    rate_limit_sleep_seconds_total = 0.0
    retrieved_count = 0
    normalized_count = 0
    sqlite_upserted_count = 0

    def _sleep_for_rate_limit(exc: ProcoreRateLimitError, reason: str) -> bool:
        nonlocal last_retry_after, rate_limit_wait_count, rate_limit_sleep_seconds_total
        if not wait_on_rate_limit:
            return False
        if rate_limit_wait_count >= max_rate_limit_wait_cycles:
            return False
        last_retry_after = exc.retry_after
        delay = (
            float(exc.retry_after)
            if exc.retry_after is not None
            else float(rate_limit_fallback_sleep_seconds)
        )
        if delay < 0:
            delay = 0.0
        reason_codes.append(reason)
        rate_limit_wait_count += 1
        rate_limit_sleep_seconds_total += delay
        sleep_fn(delay)
        return True

    # 1. Resolve adapter (canonical id or legacy alias)
    adapter = get_adapter(endpoint)
    endpoint_id_resolved = adapter.endpoint_id if adapter else None
    legacy_alias = adapter.legacy_endpoint_alias if adapter else None
    if adapter is None:
        reason_codes.append("endpoint_contract_missing")
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode_hint or "live_apply",
            adapter=None,
            command_endpoint=endpoint,
            endpoint_id_resolved=None,
            legacy_alias=None,
            project_key=project_key,
            procore_project_id=None,
            state="fail_closed_unsupported",
            status="error",
            reason_codes=reason_codes,
            request_count=0,
            retrieved_count=0,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=0,
            no_live_call_performed=True,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
        )

    direct_parent_id = str(parent_id).strip() if parent_id is not None else None
    if direct_parent_id == "":
        direct_parent_id = None
    supports_direct_parent = (
        adapter.endpoint_id == "activities" or adapter.endpoint_id in _N1_CHILD_ENDPOINTS
    )
    if direct_parent_id and not supports_direct_parent:
        reason_codes.append("parent_id_not_supported_for_endpoint")
    if direct_parent_id and adapter.endpoint_id in _N1_CHILD_EXTRA_PARENT_PARAMS:
        reason_codes.append("parent_id_requires_parent_metadata")

    # 2. Determine mode and enforce write-path guardrails
    mode = mode_hint or ("live_apply" if apply else "live_dry_run")
    if mode == "live_apply":
        if not apply:
            reason_codes.append("apply_required")
        if not sqlite_only:
            reason_codes.append("sqlite_only_required")

    # 3. Gate: HB_PROCORE_LIVE + --confirm-live-get
    if not live_env_active():
        reason_codes.append("live_env_not_set")
    if not confirm_live_get:
        reason_codes.append("confirm_live_get_required")

    # 4. Gate: configured/mapped project + non-empty Procore project id.
    # Scheduled/all-mapped refresh remains stricter via assert_live_mapping_strict;
    # direct endpoint sync only requires a configured mapping and explicit operator gates.
    procore_project_id: Optional[str] = None
    try:
        registry = load_procore_projects()
        project_gate = direct_live_project_eligibility(registry, project_key)
        procore_project_id = project_gate.procore_project_id
        if not project_gate.ok and project_gate.reason_code:
            reason_codes.append(project_gate.reason_code)
    except Exception:  # noqa: BLE001
        reason_codes.append("project_mapping_registry_unavailable")

    # 5. If any gate failed, fail-closed before transport/normalization.
    if reason_codes:
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode,
            adapter=adapter,
            command_endpoint=endpoint,
            endpoint_id_resolved=endpoint_id_resolved,
            legacy_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=procore_project_id,
            state="gate_blocked",
            status="error",
            reason_codes=reason_codes,
            request_count=0,
            retrieved_count=0,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=0,
            no_live_call_performed=True,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
        )

    # 6. Unverified endpoint -> structured fail-closed receipt (no API call).
    if not adapter.live_verified:
        reason_codes.append("endpoint_not_live_eligible")
        reason_codes.append("endpoint_unverified_for_live")
        if adapter.verification_reason:
            reason_codes.append(adapter.verification_reason)
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode,
            adapter=adapter,
            command_endpoint=endpoint,
            endpoint_id_resolved=endpoint_id_resolved,
            legacy_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=procore_project_id,
            state="not_live_verified",
            status="fail_closed",
            reason_codes=reason_codes,
            request_count=0,
            retrieved_count=0,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=_safe_count_procore_live_records(
                project_key=project_key,
                endpoint_id=adapter.endpoint_id,
                db_path=db_path,
            ),
            no_live_call_performed=True,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
        )

    # 7. Verified endpoint -> full live chain.
    normalizer = _NORMALIZER_BY_ID.get(adapter.endpoint_id)
    if normalizer is None:
        reason_codes.append("normalizer_missing")
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode,
            adapter=adapter,
            command_endpoint=endpoint,
            endpoint_id_resolved=endpoint_id_resolved,
            legacy_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=procore_project_id,
            state="fail_closed_unsupported",
            status="error",
            reason_codes=reason_codes,
            request_count=0,
            retrieved_count=0,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=0,
            no_live_call_performed=True,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
        )

    # Record sync-run start row only for apply mode (smoke mode does no DB writes).
    will_write_db = (mode == "live_apply") and apply and sqlite_only
    if will_write_db:
        # Apply schema only on the local-write path. Dry-run/live-read mode must
        # perform zero SQLite writes.
        from hb_assistant.store.migrator import ensure_schema_ready

        ensure_schema_ready(str(db_path) if db_path is not None else None)
        record_sync_run_start(
            sync_run_id=sync_run_id,
            endpoint_id=adapter.endpoint_id,
            command_endpoint=endpoint,
            legacy_endpoint_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=str(procore_project_id),
            company_id=COMPANY_ID,
            mode=mode,
            started_at_utc=started_at,
            db_path=db_path,
        )

    # Build client + transport.
    from hb_assistant.procore.http_client import ProcoreHTTPClient

    transport_calls = {"count": 0}
    base_transport = transport
    live_transport_client: Optional[ProcoreHTTPClient] = None
    if base_transport is None:
        live_transport_client = ProcoreHTTPClient(
            environment="production",
            transport=None,
            access_token_provider=default_procore_token_provider(),
            live_enabled=True,
        )

    def _counting_transport(
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        transport_calls["count"] += 1
        if base_transport is not None:
            return base_transport(method, url, headers, params)
        assert live_transport_client is not None
        return live_transport_client._default_live_transport(method, url, headers, params)

    client = ProcoreHTTPClient(
        environment="production",
        transport=_counting_transport,
        access_token_provider=default_procore_token_provider(),
        live_enabled=True,
    )

    # meeting-detail and activities are list+N+1 flows: the operator-facing
    # endpoint_id resolves to a per-item URL, but the orchestrator first
    # fetches the parent list at parent_path_template to get the iteration
    # ids.
    if (
        adapter.endpoint_id in ("meeting-detail", "activities")
        or adapter.endpoint_id in _N1_CHILD_ENDPOINTS
    ) and adapter.parent_path_template:
        path_template_used = adapter.parent_path_template
        path = path_template_used.replace("{project_id}", str(procore_project_id)).replace(
            "{company_id}", COMPANY_ID
        )
    else:
        path_template_used = adapter.path_template
        path = _resolve_path(adapter, str(procore_project_id))

    # Build query params: project_id (only when it is NOT a path segment in the
    # template — see _project_id_query_params) plus an optional date window (daily-log
    # endpoints default to a narrow/empty window and need a date filter to return
    # historical rows).
    get_params: Dict[str, str] = _project_id_query_params(
        path_template_used, str(procore_project_id)
    )
    if start_date:
        get_params["start_date"] = str(start_date)
    if end_date:
        get_params["end_date"] = str(end_date)

    items: List[Dict[str, Any]] = []
    if direct_parent_id and adapter.endpoint_id == "activities":
        items = [{"schedule_id": direct_parent_id}]
    elif direct_parent_id and adapter.endpoint_id in _N1_CHILD_ENDPOINTS:
        items = [{"id": direct_parent_id}]
    try:
        if not direct_parent_id:
            while True:
                candidate_items: List[Dict[str, Any]] = []
                candidate_retrieved_count = 0
                try:
                    items_iter = client.paginate(
                        path=path,
                        params=get_params or None,
                        per_page=_per_page_for_endpoint(adapter.endpoint_id, max_items),
                        max_pages=max_pages,
                        max_items=max_items,
                        retry_policy=_LIVE_SYNC_RETRY_POLICY,
                    )
                    for item in items_iter:
                        request_count = max(request_count, 1)
                        candidate_items.append(item)
                        candidate_retrieved_count += 1
                        if candidate_retrieved_count >= max_items:
                            break
                    items = candidate_items
                    retrieved_count = candidate_retrieved_count
                    break
                except ProcoreRateLimitError as exc:
                    if _sleep_for_rate_limit(exc, "parent_list_rate_limit_waited"):
                        continue
                    raise
    except ProcoreAuthRequired:
        reason_codes.append("token_provider_unavailable")
        attempt_count = transport_calls["count"]
        request_count = max(request_count, attempt_count)
        retry_count = 0
        if will_write_db:
            record_sync_run_complete(
                sync_run_id=sync_run_id,
                status="error",
                state="gate_blocked",
                reason_codes=reason_codes,
                request_count=request_count,
                retrieved_count=retrieved_count,
                normalized_count=0,
                sqlite_upserted_count=0,
                evidence_path=evidence_path,
                completed_at_utc=_now_utc(),
                no_live_call_performed=True,
                db_path=db_path,
            )
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode,
            adapter=adapter,
            command_endpoint=endpoint,
            endpoint_id_resolved=endpoint_id_resolved,
            legacy_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=procore_project_id,
            state="gate_blocked",
            status="error",
            reason_codes=reason_codes,
            request_count=request_count,
            attempt_count=attempt_count,
            retry_count=retry_count,
            last_retry_after=last_retry_after,
            retrieved_count=retrieved_count,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=count_procore_live_records(
                project_key=project_key,
                endpoint_id=adapter.endpoint_id,
                db_path=db_path,
            ),
            no_live_call_performed=True,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
            wait_on_rate_limit=wait_on_rate_limit,
            rate_limit_wait_count=rate_limit_wait_count,
            rate_limit_sleep_seconds_total=rate_limit_sleep_seconds_total,
            max_rate_limit_wait_cycles=max_rate_limit_wait_cycles,
        )
    except ProcoreAPIError as exc:
        attempt_count = transport_calls["count"]
        request_count = max(request_count, attempt_count)
        retry_count = 0
        if isinstance(exc, ProcoreRateLimitError):
            last_retry_after = exc.retry_after
            reason_codes.append("transport_error:429_rate_limited")
        else:
            reason_codes.append(f"transport_error:{exc.status or exc.code or 'unknown'}")
        redacted_errors.append({"code": exc.code, "status": exc.status})
        if will_write_db:
            record_sync_run_complete(
                sync_run_id=sync_run_id,
                status="error",
                state="transport_error",
                reason_codes=reason_codes,
                request_count=request_count,
                retrieved_count=retrieved_count,
                normalized_count=0,
                sqlite_upserted_count=0,
                evidence_path=evidence_path,
                completed_at_utc=_now_utc(),
                no_live_call_performed=False,
                db_path=db_path,
            )
        return _build_receipt(
            receipt_id=receipt_id,
            sync_run_id=sync_run_id,
            mode=mode,
            adapter=adapter,
            command_endpoint=endpoint,
            endpoint_id_resolved=endpoint_id_resolved,
            legacy_alias=legacy_alias,
            project_key=project_key,
            procore_project_id=procore_project_id,
            state="transport_error",
            status="error",
            reason_codes=reason_codes,
            request_count=request_count,
            attempt_count=attempt_count,
            retry_count=retry_count,
            last_retry_after=last_retry_after,
            retrieved_count=retrieved_count,
            normalized_count=0,
            sqlite_upserted_count=0,
            sqlite_total_count_after=count_procore_live_records(
                project_key=project_key,
                endpoint_id=adapter.endpoint_id,
                db_path=db_path,
            ),
            no_live_call_performed=False,
            started_at=started_at,
            completed_at=_now_utc(),
            evidence_path=evidence_path,
            redacted_errors=redacted_errors,
            wait_on_rate_limit=wait_on_rate_limit,
            rate_limit_wait_count=rate_limit_wait_count,
            rate_limit_sleep_seconds_total=rate_limit_sleep_seconds_total,
            max_rate_limit_wait_cycles=max_rate_limit_wait_cycles,
        )

    # Procore's v1.1 meetings endpoint returns GROUPED responses:
    # [{"group_title": "...", "meetings": [...]}, ...]. The orchestrator's
    # per-row upsert loop expects one canonical record per raw item, so
    # flatten any grouped meetings before normalization. v1.0 (flat list of
    # meeting dicts) is detected by absence of the "meetings" wrapper key
    # and passes through unchanged. Truncation honors the operator's
    # --max-items cap at the meeting-row level (not the group level).
    if adapter.endpoint_id in ("meetings", "meeting-detail") and items:
        flattened: List[Dict[str, Any]] = []
        grouped = False
        for raw in items:
            if isinstance(raw, dict) and isinstance(raw.get("meetings"), list):
                grouped = True
                for inner in raw["meetings"]:
                    if isinstance(inner, dict):
                        flattened.append(inner)
            elif isinstance(raw, dict):
                flattened.append(raw)
        if grouped:
            items = flattened[:max_items]
            retrieved_count = len(items)

    # activities per-schedule N+1 fetch (v2.0 list+detail flow). The
    # orchestrator already has the schedules list (`items`); for each schedule
    # it issues one activities GET (data envelope unwrapped by http_client),
    # then REPLACES items with the flat list of all activities across all
    # schedules. Each activity carries schedule_id in its payload so the
    # parent_procore_id can be derived at upsert time without a kwarg.
    if adapter.endpoint_id == "activities" and items:
        activity_items: List[Dict[str, Any]] = []
        for idx, schedule_summary in enumerate(items):
            if not isinstance(schedule_summary, dict):
                continue
            schedule_id = schedule_summary.get("schedule_id")
            if schedule_id is None or schedule_id == "":
                continue
            if not _should_fetch_child_records(
                project_key=project_key,
                child_endpoint_id=adapter.endpoint_id,
                parent_id=str(schedule_id),
                parent_summary=schedule_summary,
                now_utc=started_dt,
                db_path=db_path,
            ):
                continue
            activities_path = (
                f"/rest/v2.0/companies/{COMPANY_ID}/projects/{procore_project_id}"
                f"/schedules/{schedule_id}/activities"
            )
            if child_request_delay_seconds > 0 and idx > 0:
                sleep_fn(child_request_delay_seconds)
            while True:
                try:
                    activity_iter = list(
                        client.paginate(
                            activities_path,
                            per_page=100,
                            max_pages=max_pages,
                            max_items=max_items,
                            retry_policy=_LIVE_SYNC_RETRY_POLICY,
                        )
                    )
                    break
                except ProcoreRateLimitError as exc:
                    if _sleep_for_rate_limit(exc, "activities_rate_limit_waited"):
                        continue
                    last_retry_after = exc.retry_after
                    reason_codes.append("activities_rate_limited")
                    redacted_errors.append(
                        {
                            "detail_transport_error": exc.code or "rate_limited",
                            "status": exc.status,
                            "schedule_id": schedule_id,
                        }
                    )
                    break
                except ProcoreAPIError as exc:
                    redacted_errors.append(
                        {
                            "detail_transport_error": exc.code,
                            "status": exc.status,
                            "schedule_id": schedule_id,
                        }
                    )
                    break
                except Exception:  # noqa: BLE001
                    redacted_errors.append(
                        {"detail_transport_error": "unexpected", "schedule_id": schedule_id}
                    )
                    break
            if redacted_errors and redacted_errors[-1].get("schedule_id") == schedule_id:
                if redacted_errors[-1].get("status") == 429:
                    break
                continue
            for activity_raw in activity_iter:
                if isinstance(activity_raw, dict):
                    # Ensure schedule_id is set even if the payload omits it
                    # (so parent_procore_id can be derived at upsert time).
                    activity_raw.setdefault("schedule_id", schedule_id)
                    activity_items.append(activity_raw)
        items = activity_items[:max_items]
        retrieved_count = len(items)

    # meeting-detail per-meeting N+1 detail fetch. The orchestrator already
    # has the meetings list (`items`); now issue one detail GET per meeting
    # and REPLACE items with the rich detail payloads. Rate-limit / 5xx on
    # non-rate-limit detail errors are recorded in redacted_errors and the loop
    # continues to the next meeting. A 429 stops the loop immediately so one
    # endpoint run cannot turn a saturated rate window into a burst of failing
    # detail calls.
    if adapter.endpoint_id == "meeting-detail" and items:
        detail_items: List[Dict[str, Any]] = []
        for idx, meeting_summary in enumerate(items):
            if not isinstance(meeting_summary, dict):
                continue
            meeting_id = meeting_summary.get("id")
            if meeting_id is None or meeting_id == "":
                continue
            detail_path = f"/rest/v1.1/projects/{procore_project_id}/meetings/{meeting_id}"
            if child_request_delay_seconds > 0 and idx > 0:
                sleep_fn(child_request_delay_seconds)
            while True:
                try:
                    detail_iter = list(
                        client.paginate(
                            detail_path,
                            per_page=1,
                            max_pages=1,
                            max_items=1,
                            retry_policy=_LIVE_SYNC_RETRY_POLICY,
                        )
                    )
                    break
                except ProcoreRateLimitError as exc:
                    if _sleep_for_rate_limit(exc, "meeting_detail_rate_limit_waited"):
                        continue
                    last_retry_after = exc.retry_after
                    reason_codes.append("meeting_detail_rate_limited")
                    redacted_errors.append(
                        {
                            "detail_transport_error": exc.code or "rate_limited",
                            "status": exc.status,
                            "meeting_id": meeting_id,
                        }
                    )
                    break
                except ProcoreAPIError as exc:
                    redacted_errors.append(
                        {
                            "detail_transport_error": exc.code,
                            "status": exc.status,
                            "meeting_id": meeting_id,
                        }
                    )
                    break
                except Exception:  # noqa: BLE001
                    redacted_errors.append(
                        {"detail_transport_error": "unexpected", "meeting_id": meeting_id}
                    )
                    break
            if redacted_errors and redacted_errors[-1].get("meeting_id") == meeting_id:
                if redacted_errors[-1].get("status") == 429:
                    break
                continue
            if detail_iter:
                detail_items.append(detail_iter[0])
        items = detail_items
        retrieved_count = len(items)

    # Phase 05 generalized N+1: `items` currently holds the PARENT list (fetched via
    # parent_path_template above). For each parent, issue one child GET with the parent
    # id substituted into the child token, tag each child with the parent id (so the
    # financial projection receives parent_procore_id), and REPLACE items with the flat
    # child list. Per-parent transport errors are recorded and the loop continues.
    n1_fanout: Optional[Dict[str, Any]] = None
    if adapter.endpoint_id in _N1_CHILD_ENDPOINTS and items:
        token = adapter.parent_record_id_field or "id"
        parent_count = len(items)
        child_records: List[Dict[str, Any]] = []
        child_request_count = 0
        child_skipped_count = 0
        child_incompatible_parent_skipped_count = 0
        child_error_count = 0
        cap_reached = False
        rate_limit_stopped = False
        rate_limit_parent_id: Optional[str] = None
        for idx, parent_summary in enumerate(items):
            if not isinstance(parent_summary, dict):
                child_skipped_count += 1
                continue
            parent_id = parent_summary.get("id")
            if parent_id is None or parent_id == "":
                child_skipped_count += 1
                continue
            if not _is_compatible_n1_parent(adapter.endpoint_id, parent_summary):
                child_skipped_count += 1
                child_incompatible_parent_skipped_count += 1
                continue
            if will_write_db and not _should_fetch_child_records(
                project_key=project_key,
                child_endpoint_id=adapter.endpoint_id,
                parent_id=str(parent_id),
                parent_summary=parent_summary,
                now_utc=started_dt,
                db_path=db_path,
            ):
                child_skipped_count += 1
                continue
            # Bounded fan-out: cap the number of child GETs to limit rate-limit /
            # long-run exposure. When the cap is hit the remaining parents are counted
            # as skipped and the loop stops; a later run (or a higher --max-child-requests)
            # backfills idempotently — no upsert key or parent/child linkage changes.
            if child_request_count >= max_child_requests:
                cap_reached = True
                child_skipped_count += parent_count - idx
                break
            child_path = _resolve_child_path(adapter, str(procore_project_id), str(parent_id))
            # v1.0 child endpoints (e.g. /rest/v1.0/requisitions/{id}/contract_items) carry
            # no {project_id} path segment and require it as a query param; v2.0 children
            # already embed /projects/{project_id}/ in the path. RFQ children also need the
            # parent-derived contract_id (see _child_query_params).
            child_params = _child_query_params(adapter, str(procore_project_id), parent_summary)
            if child_request_delay_seconds > 0 and child_request_count > 0:
                sleep_fn(child_request_delay_seconds)
            while True:
                child_request_count += 1  # counted even on error (a GET was attempted)
                try:
                    child_iter = list(
                        client.paginate(
                            child_path,
                            params=child_params,
                            per_page=_per_page_for_endpoint(adapter.endpoint_id, max_items),
                            max_pages=max_pages,
                            max_items=max_items,
                            retry_policy=_LIVE_SYNC_RETRY_POLICY,
                        )
                    )
                    break
                except ProcoreRateLimitError as exc:
                    if _sleep_for_rate_limit(exc, "n1_child_rate_limit_waited"):
                        continue
                    child_error_count += 1
                    rate_limit_stopped = True
                    rate_limit_parent_id = str(parent_id)
                    last_retry_after = exc.retry_after
                    reason_codes.append("n1_child_rate_limited")
                    child_skipped_count += parent_count - idx - 1
                    redacted_errors.append(
                        {
                            "detail_transport_error": exc.code or "rate_limited",
                            "status": exc.status,
                            token: parent_id,
                        }
                    )
                    break
                except ProcoreAPIError as exc:
                    child_error_count += 1
                    redacted_errors.append(
                        {"detail_transport_error": exc.code, "status": exc.status, token: parent_id}
                    )
                    break
                except Exception:  # noqa: BLE001
                    child_error_count += 1
                    redacted_errors.append(
                        {"detail_transport_error": "unexpected", token: parent_id}
                    )
                    break
            if redacted_errors and redacted_errors[-1].get(token) == parent_id:
                if redacted_errors[-1].get("status") == 429:
                    break
                continue
            for child_raw in child_iter:
                if isinstance(child_raw, dict):
                    child_raw[_PARENT_ID_KEY] = str(parent_id)
                    child_records.append(child_raw)
            if len(child_records) >= max_items:
                # Record cap hit: remaining unvisited parents are skipped this run.
                child_skipped_count += parent_count - idx - 1
                break
        items = child_records[:max_items]
        retrieved_count = len(items)
        if cap_reached:
            reason_codes.append("n1_child_cap_reached")
        n1_fanout = {
            "is_n1": True,
            "parent_count": parent_count,
            "child_request_count": child_request_count,
            "child_skipped_count": child_skipped_count,
            "child_incompatible_parent_skipped_count": child_incompatible_parent_skipped_count,
            "child_error_count": child_error_count,
            "cap": max_child_requests,
            "cap_reached": cap_reached,
            "rate_limit_stopped": rate_limit_stopped,
            "rate_limit_parent_id": rate_limit_parent_id,
            "child_request_delay_seconds": child_request_delay_seconds,
            "rate_limit_wait_count": rate_limit_wait_count,
            "rate_limit_sleep_seconds_total": rate_limit_sleep_seconds_total,
        }

    # Normalize + upsert. After each parent upsert, perform an N+1 child GET if
    # the registry contains a child adapter for this parent (its
    # parent_path_template matches the parent's path_template, and it has a
    # parent_record_id_field set). The child path comes from the child
    # adapter's own path_template, with {project_id} + the
    # parent_record_id_field placeholder substituted. The child normalizer is
    # looked up in _CHILD_NORMALIZER_BY_ID by canonical endpoint_id.
    fetched_at = _now_utc()
    parent_retrieved_count = len(items)
    parent_normalized_count = 0
    parent_upserted_count = 0
    # Full raw payload persistence accumulators (raw-first private-DB system of record).
    raw_payload_rows_written = 0
    structured_rows_written = 0
    raw_persist_skipped_higher_quality = 0
    raw_persist_error_count = 0
    child_endpoint_id: Optional[str] = None
    child_retrieved_count = 0
    child_normalized_count = 0
    child_upserted_count = 0
    child_errors_count = 0
    child_adapter: Optional[EndpointAdapter] = (
        _resolve_child_adapter(adapter) if will_write_db else None
    )
    # meeting-detail: hardcode the child dispatch to meeting-topics. The
    # generic family-based resolver does not match here because
    # meeting-topics' parent_record_id_field is None (it's a standalone
    # /meeting_topics endpoint), yet the detail payload still embeds topics
    # under meeting_categories[].meeting_topic[] that we want to upsert as
    # meeting-topics rows.
    if child_adapter is None and adapter.endpoint_id == "meeting-detail" and will_write_db:
        from hb_assistant.procore.endpoints import get as _ep_get

        child_adapter = _ep_get("meeting-topics")
    child_normalizer: Optional[Callable[..., Dict[str, Any]]] = None
    if child_adapter is not None:
        child_normalizer = _CHILD_NORMALIZER_BY_ID.get(child_adapter.endpoint_id)
        if child_normalizer is None:
            child_adapter = None  # no normalizer registered -> skip N+1
        else:
            child_endpoint_id = child_adapter.endpoint_id

    for raw in items:
        # Raw-first: resolve a stable record id + parent id and persist the FULL
        # endpoint payload (transport secrets removed) BEFORE any lossy/normalized
        # projection, so a normalize/projection failure cannot lose business fields.
        # parent_procore_id: activities -> schedule_id, inspection-items -> list_id,
        # N+1 children -> tagged _PARENT_ID_KEY; all other endpoints have no parent.
        record_id = _record_id_of(adapter, raw) if will_write_db else None
        parent_id_for_upsert: Optional[str] = (
            _parent_id_for_upsert(adapter, raw) if will_write_db else None
        )
        if will_write_db:
            if record_id is None:
                raw_persist_error_count += 1
                redacted_errors.append({"raw_persist_error": "missing_record_id"})
            else:
                try:
                    full_raw = upsert_full_raw_payload_and_structured(
                        db_path=db_path,
                        endpoint_id=adapter.endpoint_id,
                        project_key=project_key,
                        procore_project_id=str(procore_project_id),
                        raw_item=raw,
                        parent_procore_id=parent_id_for_upsert,
                        record_id=record_id,
                        fetched_at_utc=fetched_at,
                        source_quality=SOURCE_QUALITY_LIVE_FULL,
                        capture_run_id=sync_run_id,
                    )
                    raw_payload_rows_written += full_raw["raw_payload_rows_written"]
                    structured_rows_written += full_raw["structured_rows_written"]
                    raw_persist_skipped_higher_quality += full_raw["skipped_due_to_higher_quality"]
                except Exception:  # noqa: BLE001 -- isolate per-item; verdict downgraded below
                    raw_persist_error_count += 1
                    redacted_errors.append({"raw_persist_error": "full_raw_persist_failed"})

        try:
            record = normalizer(
                raw,
                project_key=project_key,
                endpoint_id=adapter.endpoint_id,
                correlation_id=correlation_id,
                fetched_at=fetched_at,
            )
        except (TypeError, ValueError) as exc:
            redacted_errors.append({"normalize_error": type(exc).__name__})
            continue
        parent_normalized_count += 1
        normalized_count += 1

        if not will_write_db:
            continue

        if record_id is None:
            redacted_errors.append({"normalize_error": "missing_record_id"})
            continue
        source_url = (
            record["canonical_fields"].get("source_url")
            if isinstance(record.get("canonical_fields"), dict)
            else None
        )
        try:
            upsert_procore_live_record(
                project_key=project_key,
                procore_project_id=str(procore_project_id),
                endpoint_id=adapter.endpoint_id,
                procore_record_id=record_id,
                parent_procore_id=parent_id_for_upsert,
                normalized_fields=record["canonical_fields"],
                review_required=bool(record.get("review_required")),
                sensitive_reason=record.get("routing_reason"),
                source_url_redacted=redact_source_url(source_url) if source_url else None,
                last_sync_run_id=sync_run_id,
                now_utc=fetched_at,
                db_path=db_path,
            )
            parent_upserted_count += 1
            sqlite_upserted_count += 1
        except Exception:  # noqa: BLE001
            redacted_errors.append({"upsert_error": "sqlite_upsert_failed"})
            continue

        # Phase 04B historical memory: snapshot + field-level change events +
        # timeline events alongside the latest-state row above. Guarded so a
        # history failure never breaks the latest-state upsert.
        try:
            record_procore_history_for_record(
                project_key=project_key,
                endpoint_id=adapter.endpoint_id,
                parent_procore_id=parent_id_for_upsert,
                procore_record_id=record_id,
                normalized_fields=record["canonical_fields"],
                sync_run_id=sync_run_id,
                now_utc=fetched_at,
                source_updated_at=record["canonical_fields"].get("updated_at")
                if isinstance(record.get("canonical_fields"), dict)
                else None,
                normalizer_version=record.get("normalization_schema_version"),
                db_path=db_path,
            )
        except Exception:  # noqa: BLE001
            redacted_errors.append({"history_error": "history_record_failed"})

        # Phase 04B inspection enrichment: project the inspection-family payloads
        # into the dedicated V7 inspection tables (records / sections / items +
        # response sets/options + evidence rules) and emit action signals + edges.
        # Reads structural fields from raw; guarded so it never breaks the sync.
        if adapter.endpoint_id in ("inspections", "inspection-sections", "inspection-items"):
            try:
                project_inspection(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"inspection_projection_error": "projection_failed"})

        # Phase 04B meeting enrichment: project meetings / meeting-detail into the
        # cross-cutting enrichment tables (attendees, categories, topics, minutes,
        # attachments, mentioned records, action signals, series chain). Guarded.
        if adapter.endpoint_id in ("meetings", "meeting-detail"):
            try:
                project_meeting_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"meeting_projection_error": "projection_failed"})

        # Phase 04B RFI enrichment: project the RFI (responsibility, cost/schedule
        # impacts, question/proposed-solution text intelligence, signals) and its
        # inline replies (answer text, official flag, response->rfi edges). Guarded.
        if adapter.endpoint_id == "rfis":
            try:
                project_rfi(
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"rfi_projection_error": "projection_failed"})

        # Phase 04B submittal workflow enrichment: approvers, responses,
        # attachments, workflow-duration metrics, procurement/schedule signals.
        # Reads raw; guarded so it never breaks the latest-state upsert.
        if adapter.endpoint_id == "submittals":
            try:
                project_submittal(
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"submittal_projection_error": "projection_failed"})

        # Phase 04B punch-item enrichment: assignments (assignee/vendor, status,
        # notified/responded dates), location/trade/ball-in-court edges, unresolved
        # response + schedule-risk text intelligence, overdue/waiting signals. Guarded.
        if adapter.endpoint_id == "punch-items":
            try:
                project_punch_item(
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"punch_projection_error": "projection_failed"})

        # Phase 04B observation + safety enrichment: description text intelligence,
        # assignee/vendor/created-by/location/trade edges, safety classification +
        # priority / closed / due-soon signals. Guarded.
        if adapter.endpoint_id == "observations":
            try:
                project_observation(
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"observation_projection_error": "projection_failed"})

        # Phase 04B schedule enrichment: activity critical-path / float / deadline-
        # variance / constraint signals, hierarchy + schedule + assigned-company /
        # resource / category edges. Reads raw; guarded. (Schedule version/data-date
        # history is captured by the generic history path above.)
        if adapter.endpoint_id == "activities":
            try:
                project_activity(
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"schedule_projection_error": "projection_failed"})
            try:
                from hb_assistant.construction.analytics.schedule_procore_activity_adapter import (
                    project_procore_activity,
                )

                project_procore_activity(
                    raw,
                    project_key=project_key,
                    db_path=db_path,
                    parent_schedule_id=parent_id_for_upsert,
                    sync_run_id=sync_run_id,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"schedule_activity_projection_error": "projection_failed"})

        # Phase 05 owner-side financial enrichment: project prime contracts /
        # line items / attachments / change orders / CO line items / payment
        # applications into the V8 financial tables (+ amount facts, edges,
        # owner-side signals). parent_procore_id flows through for child
        # endpoints once Prompt 10 wires the N+1 fetch. Guarded.
        if adapter.endpoint_id in OWNER_ENDPOINTS:
            try:
                project_owner_contract_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                    parent_procore_id=parent_id_for_upsert,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"owner_projection_error": "projection_failed"})

        # Phase 05 vendor-side financial enrichment: commitments + line items +
        # attachments + compliance + the v1 purchase-order compatibility surface
        # (with data-driven commitment/PO de-duplication). Guarded.
        if adapter.endpoint_id in COMMITMENT_ENDPOINTS:
            try:
                project_commitment_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                    parent_procore_id=parent_id_for_upsert,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"commitment_projection_error": "projection_failed"})

        # Phase 05 subcontractor billing enrichment: billing periods +
        # subcontractor invoices + invoice items (contract / detail / change-order)
        # into the V9 billing tables + V8 invoice-items table. Guarded.
        if adapter.endpoint_id in INVOICE_ENDPOINTS:
            try:
                project_invoice_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                    parent_procore_id=parent_id_for_upsert,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"invoice_projection_error": "projection_failed"})

        # Phase 05 change-management enrichment: RFQs + responses/quotes + change
        # events + comments — links informal pricing/change workflow to the formal
        # change records (amount facts, edges, signals). Guarded.
        if adapter.endpoint_id in RFQ_ENDPOINTS:
            try:
                project_rfq_change_event_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                    parent_procore_id=parent_id_for_upsert,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"rfq_projection_error": "projection_failed"})

        # Phase 05 budget enrichment: project budget views / detail rows / change
        # history / change line items / modifications into the V8 budget tables
        # (+ amount facts, edges, budget signals). budget-details (sentinel) is not
        # in BUDGET_ENDPOINTS. Guarded.
        if adapter.endpoint_id in BUDGET_ENDPOINTS:
            try:
                project_budget_family(
                    adapter.endpoint_id,
                    raw,
                    project_key=project_key,
                    sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                    parent_procore_id=parent_id_for_upsert,
                )
            except Exception:  # noqa: BLE001
                redacted_errors.append({"budget_projection_error": "projection_failed"})

        if child_adapter is None or child_normalizer is None:
            continue

        # Inline child extraction: Procore's parent list payload already
        # embeds children (RFI replies, submittal responses). Read them
        # inline rather than issuing a per-parent child GET — that N+1
        # pattern triggers rate-limit storms and the data is already in
        # hand. meeting-detail's children live nested under
        # meeting_categories[].meeting_topic[] (two levels deep), so it
        # uses a dedicated walker rather than the single-field map.
        if adapter.endpoint_id == "meeting-detail":
            raw_children = extract_topics_from_categories(raw)
        else:
            child_field = _INLINE_CHILD_FIELD_BY_PARENT_ID.get(adapter.endpoint_id, "")
            if not child_field:
                continue
            raw_children = raw.get(child_field) if isinstance(raw, dict) else None
        if not isinstance(raw_children, list):
            continue
        inline_children: List[Dict[str, Any]] = [c for c in raw_children if isinstance(c, dict)]

        for child_raw in inline_children:
            child_retrieved_count += 1
            # Raw-first for the inline child: persist the full child payload before
            # the lossy child normalize/upsert below.
            child_id = child_raw.get("id")
            if will_write_db and child_id not in (None, ""):
                try:
                    child_full = upsert_full_raw_payload_and_structured(
                        db_path=db_path,
                        endpoint_id=child_adapter.endpoint_id,
                        project_key=project_key,
                        procore_project_id=str(procore_project_id),
                        raw_item=child_raw,
                        parent_procore_id=str(record_id),
                        record_id=str(child_id),
                        fetched_at_utc=fetched_at,
                        source_quality=SOURCE_QUALITY_LIVE_FULL,
                        capture_run_id=sync_run_id,
                    )
                    raw_payload_rows_written += child_full["raw_payload_rows_written"]
                    structured_rows_written += child_full["structured_rows_written"]
                    raw_persist_skipped_higher_quality += child_full["skipped_due_to_higher_quality"]
                except Exception:  # noqa: BLE001 -- isolate per-item; verdict downgraded below
                    raw_persist_error_count += 1
                    child_errors_count += 1
                    redacted_errors.append({"raw_persist_error": "child_full_raw_persist_failed"})
            try:
                child_record = child_normalizer(
                    child_raw,
                    parent_procore_id=str(record_id),
                    project_key=project_key,
                    endpoint_id=child_adapter.endpoint_id,
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            except (TypeError, ValueError):
                child_errors_count += 1
                redacted_errors.append({"child_normalize_error": "invalid_child_payload"})
                continue
            child_normalized_count += 1
            normalized_count += 1

            child_id = child_raw.get("id")
            if child_id is None or child_id == "":
                child_errors_count += 1
                redacted_errors.append({"child_normalize_error": "missing_child_id"})
                continue
            try:
                upsert_procore_live_record(
                    project_key=project_key,
                    procore_project_id=str(procore_project_id),
                    endpoint_id=child_adapter.endpoint_id,
                    procore_record_id=str(child_id),
                    parent_procore_id=str(record_id),
                    normalized_fields=child_record["canonical_fields"],
                    review_required=bool(child_record.get("review_required", True)),
                    sensitive_reason=child_record.get("routing_reason"),
                    source_url_redacted=redact_source_url(
                        _resolve_child_path(child_adapter, str(procore_project_id), str(record_id))
                    ),
                    last_sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
                child_upserted_count += 1
                sqlite_upserted_count += 1
            except Exception:  # noqa: BLE001
                child_errors_count += 1
                redacted_errors.append(
                    {
                        "child_upsert_error": "sqlite_upsert_failed",
                        "parent_procore_id": record_id,
                    }
                )

    completed_at = _now_utc()
    attempt_count = transport_calls["count"]
    request_count = max(request_count, attempt_count)
    retry_count = 0
    state = "success" if not redacted_errors else "partial_success"
    status = "success" if not redacted_errors else "partial"
    # Verdict rule: a run that retrieved rows but failed to persist any full raw
    # payload must NOT read as ok. Per-item failures isolate (loop continues), but
    # the endpoint-run verdict is degraded so the operator sees the gap.
    raw_persistence_ok = not (raw_persist_error_count > 0 and retrieved_count > 0)
    if not raw_persistence_ok:
        state = "degraded_raw_persistence"
        status = "partial"

    if will_write_db:
        update_watermark(
            company_id=COMPANY_ID,
            project_key=project_key,
            procore_project_id=str(procore_project_id),
            endpoint_id=adapter.endpoint_id,
            cursor_redacted=None,
            receipt_id=receipt_id,
            now_utc=completed_at,
            db_path=db_path,
        )
        record_sync_run_complete(
            sync_run_id=sync_run_id,
            status=status,
            state=state,
            reason_codes=reason_codes,
            request_count=request_count,
            retrieved_count=retrieved_count,
            normalized_count=normalized_count,
            sqlite_upserted_count=sqlite_upserted_count,
            evidence_path=evidence_path,
            completed_at_utc=completed_at,
            no_live_call_performed=False,
            db_path=db_path,
        )

    sqlite_total = (
        count_procore_live_records(
            project_key=project_key,
            endpoint_id=adapter.endpoint_id,
            db_path=db_path,
        )
        if will_write_db
        else 0
    )

    # Count guarded enrichment/projection failures (each entry names a
    # ``*_projection_error`` family). Captured here, not raised — a projection
    # failure never breaks the latest-state upsert + history recording above.
    projection_error_count = sum(
        1 for err in redacted_errors if any(str(k).endswith("projection_error") for k in err)
    )

    return _build_receipt(
        receipt_id=receipt_id,
        sync_run_id=sync_run_id,
        mode=mode,
        adapter=adapter,
        command_endpoint=endpoint,
        endpoint_id_resolved=endpoint_id_resolved,
        legacy_alias=legacy_alias,
        project_key=project_key,
        procore_project_id=procore_project_id,
        state=state,
        status=status,
        reason_codes=reason_codes,
        request_count=request_count,
        attempt_count=attempt_count,
        retry_count=retry_count,
        last_retry_after=last_retry_after,
        retrieved_count=retrieved_count,
        normalized_count=normalized_count,
        sqlite_upserted_count=sqlite_upserted_count,
        sqlite_total_count_after=sqlite_total,
        no_live_call_performed=False,
        started_at=started_at,
        completed_at=completed_at,
        evidence_path=evidence_path,
        redacted_errors=redacted_errors,
        parent_retrieved_count=parent_retrieved_count,
        parent_normalized_count=parent_normalized_count,
        parent_upserted_count=parent_upserted_count,
        child_endpoint_id=child_endpoint_id,
        child_retrieved_count=child_retrieved_count,
        child_normalized_count=child_normalized_count,
        child_upserted_count=child_upserted_count,
        child_errors_count=child_errors_count,
        projection_error_count=projection_error_count,
        n1_fanout=n1_fanout,
        wait_on_rate_limit=wait_on_rate_limit,
        rate_limit_wait_count=rate_limit_wait_count,
        rate_limit_sleep_seconds_total=rate_limit_sleep_seconds_total,
        max_rate_limit_wait_cycles=max_rate_limit_wait_cycles,
        raw_payload_rows_written=raw_payload_rows_written,
        structured_rows_written=structured_rows_written,
        raw_persist_error_count=raw_persist_error_count,
        raw_persist_skipped_higher_quality=raw_persist_skipped_higher_quality,
        full_raw_persistence_enabled=will_write_db,
    )


__all__ = ["run_live_sync"]
