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
)
from hb_assistant.procore.live_gate import (
    assert_live_mapping_strict,
    live_env_active,
)
from hb_assistant.procore.loader import load_procore_projects
from hb_assistant.procore.normalizers import (
    normalize_meeting,
    normalize_observation,
    normalize_rfi,
    normalize_rfi_reply,
    normalize_submittal,
)
from hb_assistant.procore.redaction import redact_source_url
from hb_assistant.procore.token_provider import default_procore_token_provider
from hb_assistant.store.procore_repositories import (
    count_procore_live_records,
    record_sync_run_complete,
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)

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


def _normalize_daily_log_weather(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Flat weather-log normalizer (per-section Procore endpoint shape)."""
    if not isinstance(raw, dict):
        raise TypeError("normalize_daily_log_weather requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_daily_log_weather requires raw['id']")
    canonical: Dict[str, Any] = {}
    for key in (
        "id",
        "date",
        "high_temperature",
        "low_temperature",
        "average_temperature",
        "precipitation",
        "humidity",
        "wind_speed",
        "conditions",
        "updated_at",
    ):
        if key in raw and raw[key] is not None:
            canonical[key] = raw[key]
    return {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "daily_log_weather",
        "review_required": False,
        "routing_reason": "weather_low_sensitivity",
        "canonical_fields": canonical,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
    }


# Canonical-id -> normalizer fn for the 5 live-verified endpoints. Unverified
# endpoints intentionally have no entry: they fail closed before normalization.
_NORMALIZER_BY_ID: Dict[str, Callable[..., Dict[str, Any]]] = {
    "projects": _normalize_project,
    "rfis": normalize_rfi,
    "submittals": normalize_submittal,
    "meetings": normalize_meeting,
    "daily-log-weather": _normalize_daily_log_weather,
    # Convenience: observations is not docs-verified in the matrix, but its
    # normalizer is already exercised in dry-run tests. Future promotion can
    # flip endpoints.live_verified=True without code changes here.
    "observations": normalize_observation,
}


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
    """Substitute the project_id parameter; raise if a child endpoint lacks
    its parent record id (we never invoke child endpoints in this prompt)."""
    if "{project_id}" in adapter.path_template:
        return adapter.path_template.replace("{project_id}", procore_project_id)
    return adapter.path_template


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

    client = ProcoreHTTPClient(
        environment="production",
        transport=transport,
        access_token_provider=default_procore_token_provider(),
        live_enabled=transport is None,
    )

    path = _resolve_path(adapter, str(procore_project_id))

    try:
        items_iter = client.paginate(
            path=path,
            params={"project_id": str(procore_project_id)} if "{project_id}" not in adapter.path_template else None,
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
        reason_codes.append(f"transport_error:{exc.code}")
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

    # Normalize + upsert. For `rfis`, after each parent upsert, perform an
    # N+1 child GET to /rfis/{rfi_id}/replies and persist replies as
    # endpoint_id="rfi-responses" with parent_procore_id set.
    fetched_at = _now_utc()
    parent_retrieved_count = len(items)
    parent_normalized_count = 0
    parent_upserted_count = 0
    child_endpoint_id: Optional[str] = None
    child_retrieved_count = 0
    child_normalized_count = 0
    child_upserted_count = 0
    child_errors_count = 0
    fetch_rfi_replies = adapter.endpoint_id == "rfis" and will_write_db
    if fetch_rfi_replies:
        child_endpoint_id = "rfi-responses"

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
        try:
            upsert_procore_live_record(
                project_key=project_key,
                procore_project_id=str(procore_project_id),
                endpoint_id=adapter.endpoint_id,
                procore_record_id=record_id,
                parent_procore_id=None,
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

        if not fetch_rfi_replies:
            continue

        # N+1: fetch this RFI's replies, normalize each, upsert as a child row.
        reply_path = f"/rest/v1.0/projects/{procore_project_id}/rfis/{record_id}/replies"
        try:
            reply_items = list(
                client.paginate(reply_path, per_page=50, max_pages=1, max_items=50)
            )
        except ProcoreAPIError as child_exc:
            child_errors_count += 1
            redacted_errors.append(
                {
                    "child_transport_error": child_exc.code,
                    "status": child_exc.status,
                    "parent_procore_id": record_id,
                }
            )
            continue
        except Exception:  # noqa: BLE001
            child_errors_count += 1
            redacted_errors.append(
                {"child_transport_error": "unexpected", "parent_procore_id": record_id}
            )
            continue

        for reply_raw in reply_items:
            child_retrieved_count += 1
            try:
                reply_record = normalize_rfi_reply(
                    reply_raw,
                    parent_rfi_stable_key=str(record_id),
                    project_key=project_key,
                    endpoint_id="rfi-responses",
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            except (TypeError, ValueError):
                child_errors_count += 1
                redacted_errors.append({"child_normalize_error": "invalid_reply_payload"})
                continue
            child_normalized_count += 1
            normalized_count += 1

            reply_id = reply_raw.get("id") if isinstance(reply_raw, dict) else None
            if reply_id is None or reply_id == "":
                child_errors_count += 1
                redacted_errors.append({"child_normalize_error": "missing_reply_id"})
                continue
            try:
                upsert_procore_live_record(
                    project_key=project_key,
                    procore_project_id=str(procore_project_id),
                    endpoint_id="rfi-responses",
                    procore_record_id=str(reply_id),
                    parent_procore_id=str(record_id),
                    normalized_fields=reply_record["canonical_fields"],
                    review_required=True,
                    sensitive_reason=reply_record.get("routing_reason"),
                    source_url_redacted=redact_source_url(reply_path),
                    last_sync_run_id=sync_run_id,
                    now_utc=fetched_at,
                    db_path=db_path,
                )
                child_upserted_count += 1
                sqlite_upserted_count += 1
            except Exception:  # noqa: BLE001
                child_errors_count += 1
                redacted_errors.append(
                    {"child_upsert_error": "sqlite_upsert_failed", "parent_procore_id": record_id}
                )

    completed_at = _now_utc()
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
            request_count=max(request_count, 1),
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
        request_count=max(request_count, 1),
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
