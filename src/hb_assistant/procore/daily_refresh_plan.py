"""Daily source-refresh canonical endpoint plan + status taxonomy.

The scheduled ``daily-source-refresh`` historically fanned every legacy
``list-*`` seed-contract endpoint through ``procore/sync.py`` against stale
routes, producing HTTP 400/404 failures (see
``docs/evidence/procore-endpoint-workflow-remediation/``). This module is the
canonical replacement: it maps the daily-refresh endpoint set onto canonical
:class:`~hb_assistant.procore.endpoints.EndpointAdapter` ids, classifies scope
(company-level vs per-project), computes a bounded daily-log date window, and
translates :func:`~hb_assistant.procore.live_sync.run_live_sync` receipts into
an operator-facing status taxonomy.

It contains only pure planning/classification logic — no I/O, no HTTP, no DB.
The orchestrator (`source_refresh/orchestrator.py`) executes the plan by
calling ``run_live_sync`` per planned item and aggregates the receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from hb_assistant.procore import endpoints

# Bounded lookback for date-windowed daily-log endpoints. A daily refresh reads
# a small, deterministic trailing window (never unbounded) so Procore's
# "Start/End Date required" contract is always satisfied and the read stays cheap.
DAILY_LOG_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class PlannedEndpoint:
    """One canonical endpoint scheduled for the daily refresh.

    ``legacy_alias`` is the historical ``list-*`` id, preserved for operator
    receipts and continuity with prior evidence. ``company_level`` endpoints are
    run once per company (not per pilot project). ``date_windowed`` endpoints
    receive bounded ``start_date``/``end_date`` query params.
    """

    canonical_id: str
    legacy_alias: str
    company_level: bool = False
    date_windowed: bool = False


def _daily_log_endpoint_ids() -> tuple[str, ...]:
    """Live-verified daily-log subtype adapter ids, in registry order.

    Replaces the single stale ``list-daily-logs`` seed endpoint (which Procore
    rejects without a date window) with the canonical per-subtype adapters.
    """
    return tuple(ep.endpoint_id for ep in endpoints.list_verified() if ep.family == "daily_logs")


def build_daily_refresh_plan() -> tuple[PlannedEndpoint, ...]:
    """The canonical daily-refresh endpoint plan.

    Mirrors the business coverage of the legacy daily-refresh set
    (projects, rfis, submittals, commitments, change-events, invoices,
    prime-contracts, punch-items, daily-logs) mapped onto canonical adapters.
    ``list-drawings`` is intentionally absent — it has no canonical adapter and
    is classified as ``skipped_tool_not_enabled`` by :data:`UNSUPPORTED_ENDPOINTS`.
    """
    plan: list[PlannedEndpoint] = [
        PlannedEndpoint("projects", "list-projects", company_level=True),
        PlannedEndpoint("rfis", "list-rfis"),
        PlannedEndpoint("submittals", "list-submittals"),
        PlannedEndpoint("commitment-contracts", "list-commitments"),
        PlannedEndpoint("change-events", "list-change-events"),
        PlannedEndpoint("subcontractor-invoices", "list-invoices"),
        PlannedEndpoint("prime-contracts", "list-prime-contracts"),
        PlannedEndpoint("punch-items", "list-punch-items"),
    ]
    plan.extend(
        PlannedEndpoint(eid, "list-daily-logs", date_windowed=True)
        for eid in _daily_log_endpoint_ids()
    )
    return tuple(plan)


# Legacy endpoints with no canonical adapter -> classified, never run, never a
# generic error. ``list-drawings`` returns HTTP 404 (tool not enabled for these
# pilot projects) and has no adapter in the registry.
UNSUPPORTED_ENDPOINTS: Mapping[str, str] = {
    "list-drawings": "skipped_tool_not_enabled",
}


def daily_log_window(
    brief_date: date, lookback_days: int = DAILY_LOG_LOOKBACK_DAYS
) -> tuple[str, str]:
    """Bounded ``(start_date, end_date)`` ISO strings for daily-log reads."""
    end = brief_date
    start = brief_date - timedelta(days=lookback_days)
    return start.isoformat(), end.isoformat()


# --- Status taxonomy --------------------------------------------------------------

# Operator-facing endpoint status taxonomy (superset used across the receipt).
SUCCESS = "success"
SKIPPED_COMPANY_ALREADY_HANDLED = "skipped_company_level_already_handled"
SKIPPED_TOOL_NOT_ENABLED = "skipped_tool_not_enabled"
SKIPPED_PERMISSION_LIMITED = "skipped_permission_limited"
SKIPPED_NOT_LIVE_ELIGIBLE = "skipped_not_live_eligible"
BLOCKED_AUTH_NOT_READY = "blocked_auth_not_ready"
BLOCKED_MAPPING_NOT_READY = "blocked_mapping_not_ready"
CONTRACT_BUG_MISSING_REQUIRED_PARAM = "contract_bug_missing_required_param"
TRANSPORT_RATE_LIMITED = "transport_rate_limited"
TRANSPORT_ERROR_RETRYABLE = "transport_error_retryable"
TRANSPORT_ERROR_NON_RETRYABLE = "transport_error_non_retryable"
NORMALIZER_MISSING = "normalizer_missing"
PROJECTION_ERROR = "projection_error"
UNKNOWN_DEGRADED = "unknown_degraded"

_AUTH_GATE_REASONS = frozenset(
    {
        "live_env_not_set",
        "confirm_live_get_required",
        "apply_required",
        "sqlite_only_required",
        "token_provider_unavailable",
    }
)
_MAPPING_GATE_REASONS = frozenset(
    {
        "mapping_not_live_eligible",
        "mapping_registry_unavailable",
        "procore_project_id_unresolved",
    }
)

# Codes that constitute genuine run degradation (manual run must exit nonzero).
# Intentional skips (skipped_*) are NOT degradation.
_DEGRADED_CODES = frozenset(
    {
        CONTRACT_BUG_MISSING_REQUIRED_PARAM,
        TRANSPORT_RATE_LIMITED,
        TRANSPORT_ERROR_RETRYABLE,
        TRANSPORT_ERROR_NON_RETRYABLE,
        NORMALIZER_MISSING,
        PROJECTION_ERROR,
        BLOCKED_AUTH_NOT_READY,
        BLOCKED_MAPPING_NOT_READY,
        UNKNOWN_DEGRADED,
    }
)


def is_degraded_status(code: str) -> bool:
    """True if a taxonomy code should degrade the overall run."""
    return code in _DEGRADED_CODES


def is_skipped_status(code: str) -> bool:
    return code.startswith("skipped_")


def _has_projection_error(receipt: Mapping[str, Any]) -> bool:
    """True if any redacted error key marks a domain-projection failure."""
    for err in receipt.get("redacted_errors", []) or []:
        if isinstance(err, Mapping) and any(str(k).endswith("_projection_error") for k in err):
            return True
    return False


def _http_status_from_receipt(receipt: Mapping[str, Any]) -> int | None:
    """Best-effort HTTP status from a transport-error receipt (no raw body)."""
    for err in receipt.get("redacted_errors", []) or []:
        if isinstance(err, Mapping) and isinstance(err.get("status"), int):
            return int(err["status"])
    for rc in receipt.get("reason_codes", []) or []:
        if isinstance(rc, str) and rc.startswith("transport_error:"):
            tail = rc.split(":", 1)[1]
            if tail.startswith("429"):
                return 429
            if tail.isdigit():
                return int(tail)
    return None


def classify_receipt(receipt: Mapping[str, Any]) -> str:
    """Map a ``run_live_sync`` receipt to the operator status taxonomy."""
    state = str(receipt.get("state") or "")
    reason_codes: Sequence[str] = [str(r) for r in (receipt.get("reason_codes") or [])]

    if state == "success":
        return SUCCESS
    if state == "partial_success":
        if _has_projection_error(receipt):
            return PROJECTION_ERROR
        return SUCCESS
    if state == "not_live_verified":
        return SKIPPED_NOT_LIVE_ELIGIBLE
    if state == "fail_closed_unsupported":
        if "normalizer_missing" in reason_codes:
            return NORMALIZER_MISSING
        return SKIPPED_TOOL_NOT_ENABLED
    if state == "gate_blocked":
        if any(r in _AUTH_GATE_REASONS for r in reason_codes):
            return BLOCKED_AUTH_NOT_READY
        if any(r in _MAPPING_GATE_REASONS for r in reason_codes):
            return BLOCKED_MAPPING_NOT_READY
        return UNKNOWN_DEGRADED
    if state == "transport_error":
        status = _http_status_from_receipt(receipt)
        if status == 400:
            return CONTRACT_BUG_MISSING_REQUIRED_PARAM
        if status == 403:
            return SKIPPED_PERMISSION_LIMITED
        if status == 404:
            return SKIPPED_TOOL_NOT_ENABLED
        if status == 429:
            return TRANSPORT_RATE_LIMITED
        if status is not None and 500 <= status < 600:
            return TRANSPORT_ERROR_RETRYABLE
        return TRANSPORT_ERROR_NON_RETRYABLE
    return UNKNOWN_DEGRADED


__all__ = [
    "DAILY_LOG_LOOKBACK_DAYS",
    "PlannedEndpoint",
    "UNSUPPORTED_ENDPOINTS",
    "build_daily_refresh_plan",
    "classify_receipt",
    "daily_log_window",
    "is_degraded_status",
    "is_skipped_status",
]
