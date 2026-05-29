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

import uuid
from datetime import datetime, timezone
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
    assert_live_mapping_strict,
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
from hb_assistant.procore.normalizers.owner_contract import (
    normalize_payment_application,
    normalize_prime_change_order,
    normalize_prime_change_order_line_item,
    normalize_prime_contract,
    normalize_prime_contract_attachment,
    normalize_prime_contract_line_item,
)
from hb_assistant.procore.redaction import redact_source_url
from hb_assistant.procore.token_provider import default_procore_token_provider
from hb_assistant.store.procore_history import record_procore_history_for_record
from hb_assistant.store.procore_inspection_projection import project_inspection
from hb_assistant.store.procore_meeting_projection import project_meeting_family
from hb_assistant.store.procore_observation_projection import project_observation
from hb_assistant.store.procore_owner_projection import (
    OWNER_ENDPOINTS,
    project_owner_contract_family,
)
from hb_assistant.store.procore_punch_projection import project_punch_item
from hb_assistant.store.procore_repositories import (
    count_procore_live_records,
    record_sync_run_complete,
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)
from hb_assistant.store.procore_rfi_projection import project_rfi
from hb_assistant.store.procore_schedule_projection import project_activity
from hb_assistant.store.procore_submittal_projection import project_submittal

COMPANY_ID = "5280"
EVIDENCE_DIR_REL = "docs/evidence/construction-intelligence-phase-04a"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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
}


def resolve_normalizer(endpoint_id: str) -> Optional[Callable[..., Dict[str, Any]]]:
    """Return the normalizer callable for an endpoint id (parent map, then child
    map). Read-only lookup used by the local coverage tooling — no I/O."""
    return _NORMALIZER_BY_ID.get(endpoint_id) or _CHILD_NORMALIZER_BY_ID.get(endpoint_id)


def _record_id_of(adapter: EndpointAdapter, raw: Dict[str, Any]) -> Optional[str]:
    value = raw.get(adapter.record_id_field)
    if value is None or value == "":
        return None
    return str(value)


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
) -> Dict[str, Any]:
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
        "request_count": request_count,
        "attempt_count": attempt_count,
        "retry_count": retry_count,
        "last_retry_after": last_retry_after,
        "retrieved_count": retrieved_count,
        "normalized_count": normalized_count,
        "sqlite_upserted_count": sqlite_upserted_count,
        "sqlite_total_count_after": sqlite_total_count_after,
        "raw_body_persisted": False,
        "secrets_redacted": True,
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
    }


def run_live_sync(
    *,
    project_key: str,
    endpoint: str,
    apply: bool,
    sqlite_only: bool,
    confirm_live_get: bool,
    max_pages: int = 3,
    max_items: int = 100,
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

    started_at = _now_utc()
    receipt_id = str(uuid.uuid4())
    sync_run_id = receipt_id
    correlation_id = str(uuid.uuid4())
    reason_codes: List[str] = []
    redacted_errors: List[Dict[str, Any]] = []
    request_count = 0
    attempt_count = 0
    retry_count = 0
    last_retry_after: Optional[int] = None
    retrieved_count = 0
    normalized_count = 0
    sqlite_upserted_count = 0

    # Ensure V6 schema is present before any count/upsert path runs.
    from hb_assistant.store.migrator import SQLiteMigrator
    SQLiteMigrator(db_path=str(db_path) if db_path is not None else None).apply()

    # 1. Resolve adapter (canonical id or legacy alias)
    adapter = get_adapter(endpoint)
    endpoint_id_resolved = adapter.endpoint_id if adapter else None
    legacy_alias = adapter.legacy_endpoint_alias if adapter else None
    if adapter is None:
        reason_codes.append("endpoint_alias_unknown")
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

    # 4. Gate: mapped pilot project + non-empty procore_project_id
    procore_project_id: Optional[str] = None
    try:
        registry = load_procore_projects()
        assert_live_mapping_strict(registry, [project_key])
        procore_project_id = _resolve_procore_project_id(project_key)
        if not procore_project_id:
            reason_codes.append("procore_project_id_unresolved")
    except ProcoreAPIError:
        reason_codes.append("mapping_not_live_eligible")
    except Exception:  # noqa: BLE001
        reason_codes.append("mapping_registry_unavailable")

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
        and adapter.parent_path_template
    ):
        path = adapter.parent_path_template.replace(
            "{project_id}", str(procore_project_id)
        ).replace("{company_id}", COMPANY_ID)
    else:
        path = _resolve_path(adapter, str(procore_project_id))

    # Build query params: project_id (when not already a path segment) plus an
    # optional date window (daily-log endpoints default to a narrow/empty window
    # and need a date filter to return historical rows).
    get_params: Dict[str, str] = {}
    if "{project_id}" not in path:
        get_params["project_id"] = str(procore_project_id)
    if start_date:
        get_params["start_date"] = str(start_date)
    if end_date:
        get_params["end_date"] = str(end_date)

    try:
        items_iter = client.paginate(
            path=path,
            params=get_params or None,
            per_page=min(max_items, 100),
            max_pages=max_pages,
            max_items=max_items,
        )
        items: List[Dict[str, Any]] = []
        for item in items_iter:
            request_count = max(request_count, 1)
            items.append(item)
            retrieved_count += 1
            if retrieved_count >= max_items:
                break
    except ProcoreAuthRequired:
        reason_codes.append("token_provider_unavailable")
        attempt_count = transport_calls["count"]
        request_count = max(request_count, attempt_count)
        retry_count = max(0, attempt_count - 1)
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
        )
    except ProcoreAPIError as exc:
        attempt_count = transport_calls["count"]
        request_count = max(request_count, attempt_count)
        retry_count = max(0, attempt_count - 1)
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
        for schedule_summary in items:
            if not isinstance(schedule_summary, dict):
                continue
            schedule_id = schedule_summary.get("schedule_id")
            if schedule_id is None or schedule_id == "":
                continue
            activities_path = (
                f"/rest/v2.0/companies/{COMPANY_ID}/projects/{procore_project_id}"
                f"/schedules/{schedule_id}/activities"
            )
            try:
                activity_iter = list(
                    client.paginate(
                        activities_path, per_page=100, max_pages=3, max_items=200
                    )
                )
            except ProcoreAPIError as exc:
                redacted_errors.append(
                    {
                        "detail_transport_error": exc.code,
                        "status": exc.status,
                        "schedule_id": schedule_id,
                    }
                )
                continue
            except Exception:  # noqa: BLE001
                redacted_errors.append(
                    {"detail_transport_error": "unexpected", "schedule_id": schedule_id}
                )
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
    # any single detail call is recorded in redacted_errors and the loop
    # continues to the next meeting.
    if adapter.endpoint_id == "meeting-detail" and items:
        detail_items: List[Dict[str, Any]] = []
        for meeting_summary in items:
            if not isinstance(meeting_summary, dict):
                continue
            meeting_id = meeting_summary.get("id")
            if meeting_id is None or meeting_id == "":
                continue
            detail_path = (
                f"/rest/v1.1/projects/{procore_project_id}/meetings/{meeting_id}"
            )
            try:
                detail_iter = list(
                    client.paginate(detail_path, per_page=1, max_pages=1, max_items=1)
                )
            except ProcoreAPIError as exc:
                redacted_errors.append(
                    {
                        "detail_transport_error": exc.code,
                        "status": exc.status,
                        "meeting_id": meeting_id,
                    }
                )
                continue
            except Exception:  # noqa: BLE001
                redacted_errors.append(
                    {"detail_transport_error": "unexpected", "meeting_id": meeting_id}
                )
                continue
            if detail_iter:
                detail_items.append(detail_iter[0])
        items = detail_items
        retrieved_count = len(items)

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

        record_id = _record_id_of(adapter, raw)
        if record_id is None:
            redacted_errors.append({"normalize_error": "missing_record_id"})
            continue
        source_url = record["canonical_fields"].get("source_url") if isinstance(record.get("canonical_fields"), dict) else None
        # activities link back to their parent schedule_id via parent_procore_id.
        # inspection-items links back to its parent list_id (each item
        # payload carries list_id directly on the v1.1 list endpoint).
        # inspection-sections are project-wide template surfaces with no
        # list_id field on the v1.0 list endpoint — parent_procore_id stays
        # None for sections. All other top-level endpoints leave
        # parent_procore_id as None.
        parent_id_for_upsert: Optional[str] = None
        if adapter.endpoint_id == "activities":
            sched_id = raw.get("schedule_id") if isinstance(raw, dict) else None
            if sched_id is not None and sched_id != "":
                parent_id_for_upsert = str(sched_id)
        elif adapter.endpoint_id == "inspection-items":
            list_id = raw.get("list_id") if isinstance(raw, dict) else None
            if list_id is not None and list_id != "":
                parent_id_for_upsert = str(list_id)
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
        inline_children: List[Dict[str, Any]] = [
            c for c in raw_children if isinstance(c, dict)
        ]

        for child_raw in inline_children:
            child_retrieved_count += 1
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
                redacted_errors.append(
                    {"child_normalize_error": "invalid_child_payload"}
                )
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
                    source_url_redacted=redact_source_url(child_adapter.path_template),
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
    retry_count = max(0, attempt_count - 1)
    state = "success" if not redacted_errors else "partial_success"
    status = "success" if not redacted_errors else "partial"

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

    sqlite_total = count_procore_live_records(
        project_key=project_key,
        endpoint_id=adapter.endpoint_id,
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
    )


__all__ = ["run_live_sync"]
