"""Phase 04B daily-log live normalizers — one per Procore daily-log sub-log.

These replace the thin inline ``_normalize_daily_log_*`` helpers that lived in
``live_sync.py`` (whose field contracts were unverified guesses). Each function
here matches the **real** Procore response shape supplied by the operator
(2026-05-29) and projects a PII-safe enrichment block:

- real scalar fields preserved verbatim,
- free-text fields (``comment``/``comments``/``notes``/``details``/
  ``safety_notice``/``contents`` + sensitive ``subject``) reduced to
  ``*_summary`` hash blocks,
- people (``created_by``/``user``/``contact``/``inspector_name``/
  ``involved_name``) reduced to hashed person entities,
- ``vendor``/``trade``/``cost_code``/``location``/``daily_log_segment`` and
  ``attachments`` (URLs stripped to path-only) and typed ``custom_fields``
  projected as entities, plus derived relationship ``edges`` and
  ``action_signals``.

The orchestrator (``live_sync.run_live_sync``) consumes ``canonical_fields``,
``review_required`` and ``routing_reason`` and never persists raw bodies.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from .entities import EntityBuilder
from .hashing import hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

# inspection_type / inspecting_entity fragments that flag a safety-class daily
# inspection log (case-insensitive substring) -> review + safety_route + signal.
_SAFETY_FRAGMENTS = (
    "safety",
    "incident",
    "injury",
    "near miss",
    "near-miss",
    "osha",
    "ppe",
    "fall",
)


def _is_safety(*values: Any) -> bool:
    for value in values:
        if isinstance(value, str) and any(frag in value.lower() for frag in _SAFETY_FRAGMENTS):
            return True
    return False


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _manpower_anomaly(raw: Dict[str, Any]) -> bool:
    """Flag an inconsistent manpower row: workers reported with zero hours, or
    hours reported with zero workers."""
    workers = _num(raw.get("num_workers"))
    hours = _num(raw.get("man_hours"))
    if hours is None:
        hours = _num(raw.get("num_hours"))
    return bool((workers and not hours) or (hours and not workers))


def _base(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    category: str,
    scalar_keys: Tuple[str, ...],
    freetext_keys: Tuple[str, ...],
    builder: EntityBuilder,
    review_required: bool,
    routing_reason: str,
    safety_route: bool = False,
) -> Dict[str, Any]:
    """Assemble one canonical daily-log record from a real sub-log payload."""
    if not isinstance(raw, dict):
        raise TypeError(f"normalize {endpoint_id} requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError(f"normalize {endpoint_id} requires raw['id']")

    canonical: Dict[str, Any] = {}
    for key in scalar_keys:
        if key in raw and raw[key] is not None:
            canonical[key] = raw[key]
    for key in freetext_keys:
        summary = hash_summary(raw.get(key))
        if summary is not None:
            canonical[f"{key}_summary"] = summary
    if isinstance(raw.get("permissions"), dict):
        canonical["permissions"] = raw["permissions"]

    projection = builder.build()
    canonical["entities"] = projection["entities"]
    canonical["edges"] = projection["edges"]
    canonical["action_signals"] = projection["action_signals"]

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": category,
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if safety_route:
        record["safety_route"] = True
    return record


# ---------------------------------------------------------------------------
# Selected / low-medium sensitivity sections
# ---------------------------------------------------------------------------


def normalize_daily_log_weather(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .add_signal("weather_delay" if raw.get("is_weather_delay") else None)
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_weather",
        scalar_keys=(
            "id", "date", "datetime", "time", "position", "average", "sky", "ground",
            "wind", "temperature", "precipitation", "is_weather_delay", "calamity",
            "daily_log_segment_id", "created_at", "updated_at", "deleted_at",
        ),
        freetext_keys=("comments",),
        builder=builder,
        review_required=False,
        routing_reason="weather_low_sensitivity",
    )


def normalize_daily_log_manpower(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_person(raw.get("user"), "user")
        .add_person(raw.get("contact"), "contact")
        .add_company(raw.get("vendor"), "vendor")
        .add_company(raw.get("cost_code"), "cost_code")
        .add_company(raw.get("trade"), "trade")
        .set_location(raw.get("location"))
        .set_attachments(raw.get("attachments"))
        .set_custom_fields(raw.get("custom_fields"))
        .add_signal("daily_manpower_anomaly" if _manpower_anomaly(raw) else None)
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_manpower",
        scalar_keys=(
            "id", "date", "datetime", "man_hours", "num_workers", "num_hours",
            "status", "position", "created_at", "updated_at",
        ),
        freetext_keys=("notes",),
        builder=builder,
        review_required=False,
        routing_reason="manpower_contact_pii_hashed_medium",
    )


def normalize_daily_log_notes(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .set_custom_fields(raw.get("custom_fields"))
        .add_signal("issue_day" if raw.get("is_issue_day") else None)
        .add_signal("daily_note_review_required")
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_notes",
        scalar_keys=(
            "id", "date", "datetime", "daily_log_header_id", "is_issue_day", "status",
            "position", "created_by_collaborator", "daily_log_segment_id",
            "created_at", "updated_at",
        ),
        freetext_keys=("comment",),
        builder=builder,
        review_required=True,
        routing_reason="notes_section_review_required_high_sensitivity",
    )


def normalize_daily_log_deliveries(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_deliveries",
        scalar_keys=(
            "id", "date", "datetime", "delivery_from", "status", "time_hour",
            "time_minute", "tracking_number", "position", "daily_log_segment_id",
            "created_at", "updated_at",
        ),
        freetext_keys=("comments", "contents"),
        builder=builder,
        review_required=False,
        routing_reason="deliveries_structured_medium",
    )


def normalize_daily_log_delay(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .add_signal("delay")
        .add_signal("daily_delay_reported")
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_delays",
        scalar_keys=(
            "id", "date", "datetime", "delay_type", "duration", "end_time",
            "end_time_hour", "end_time_minute", "start_time_hour", "start_time_minute",
            "status", "position", "daily_log_segment_id", "created_at", "updated_at",
        ),
        freetext_keys=("comments",),
        builder=builder,
        review_required=True,
        routing_reason="delays_section_safety_routed_critical",
        safety_route=True,
    )


def normalize_daily_log_inspection(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    safety = _is_safety(raw.get("inspection_type"), raw.get("inspecting_entity"))
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_person_name(raw.get("inspector_name"), "inspector")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .add_signal("safety" if safety else None)
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_inspections",
        scalar_keys=(
            "id", "date", "datetime", "area", "inspecting_entity", "inspection_type",
            "start_hour", "start_minute", "end_hour", "end_minute", "position",
            "daily_log_segment_id", "created_at", "updated_at",
        ),
        freetext_keys=("comments",),
        builder=builder,
        review_required=safety,
        routing_reason="inspections_safety_routed_high" if safety else "inspections_structured_medium",
        safety_route=safety,
    )


def normalize_daily_log_dcr(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .add_company(raw.get("trade"), "trade")
        .set_location(raw.get("location"))
        .set_attachments(raw.get("attachments"))
        .set_custom_fields(raw.get("custom_fields"))
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_dcrs",
        scalar_keys=(
            "id", "date", "datetime", "status", "position",
            "apprentice_hours", "first_year_hours", "foreman_hours", "journeyman_hours",
            "local_city_hours", "local_county_hours", "minority_hours", "other_hours",
            "veteran_hours", "women_hours", "number_of_apprentice_workers",
            "number_of_foreman_workers", "number_of_journeyman_workers",
            "number_of_other_workers", "created_at", "updated_at",
        ),
        freetext_keys=("notes",),
        builder=builder,
        review_required=False,
        routing_reason="dcrs_structured_medium",
    )


# ---------------------------------------------------------------------------
# New sections (Phase 04B): accident / dumpster / safety_violation / visitor
# ---------------------------------------------------------------------------


def normalize_daily_log_accident(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_person_name(raw.get("involved_name"), "involved")
        .add_company_name(raw.get("involved_company"), "involved_company")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .add_signal("safety")
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_accident",
        scalar_keys=(
            "id", "date", "datetime", "position", "time_hour", "time_minute",
            "daily_log_segment_id", "created_at", "updated_at",
        ),
        freetext_keys=("comments",),
        builder=builder,
        review_required=True,
        routing_reason="accident_section_safety_routed_critical",
        safety_route=True,
    )


def normalize_daily_log_dumpster(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_dumpster",
        scalar_keys=(
            "id", "date", "datetime", "position", "quantity_delivered",
            "quantity_removed", "daily_log_segment_id", "created_at", "updated_at",
        ),
        freetext_keys=("comments",),
        builder=builder,
        review_required=False,
        routing_reason="dumpster_structured_low",
    )


def normalize_daily_log_safety_violation(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company_name(raw.get("issued_to"), "issued_to")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_segment(raw.get("daily_log_segment"))
        .set_attachments(raw.get("attachments"))
        .add_signal("safety")
        .add_signal("compliance_due_set" if raw.get("compliance_due") else None)
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_safety_violation",
        scalar_keys=(
            "id", "date", "datetime", "position", "compliance_due", "subject",
            "time_hour", "time_minute", "daily_log_segment_id", "created_at", "updated_at",
        ),
        freetext_keys=("comments", "safety_notice"),
        builder=builder,
        review_required=True,
        routing_reason="safety_violation_section_safety_routed_critical",
        safety_route=True,
    )


def normalize_daily_log_visitor(raw, *, project_key, endpoint_id, correlation_id, fetched_at):
    # subject carries the visitor's name (PII) -> hashed via freetext_keys.
    builder = (
        EntityBuilder()
        .add_person(raw.get("created_by"), "created_by")
        .add_company(raw.get("vendor"), "vendor")
        .set_location(raw.get("location"))
        .set_custom_fields(raw.get("custom_fields"))
    )
    return _base(
        raw, project_key=project_key, endpoint_id=endpoint_id,
        correlation_id=correlation_id, fetched_at=fetched_at,
        category="daily_log_visitor",
        scalar_keys=(
            "id", "date", "datetime", "position", "begin_hour", "begin_minute",
            "end_hour", "end_minute", "status", "created_at", "updated_at",
        ),
        freetext_keys=("details", "subject"),
        builder=builder,
        review_required=True,
        routing_reason="visitor_subject_pii_hashed_review_high",
    )


NORMALIZER_BY_ENDPOINT: Dict[str, Callable[..., Dict[str, Any]]] = {
    "daily-log-weather": normalize_daily_log_weather,
    "daily-log-manpower": normalize_daily_log_manpower,
    "daily-log-notes": normalize_daily_log_notes,
    "daily-log-deliveries": normalize_daily_log_deliveries,
    "daily-log-delays-review-routed": normalize_daily_log_delay,
    "daily-log-inspections": normalize_daily_log_inspection,
    "daily-log-dcrs": normalize_daily_log_dcr,
    "daily-log-accident-review-routed": normalize_daily_log_accident,
    "daily-log-dumpster": normalize_daily_log_dumpster,
    "daily-log-safety-violation-review-routed": normalize_daily_log_safety_violation,
    "daily-log-visitor": normalize_daily_log_visitor,
}

__all__ = ["NORMALIZER_BY_ENDPOINT"] + [fn.__name__ for fn in NORMALIZER_BY_ENDPOINT.values()]
