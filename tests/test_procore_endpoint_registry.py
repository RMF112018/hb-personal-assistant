"""Phase 04A endpoint adapter registry shape + alias resolution tests."""

from __future__ import annotations

from hb_assistant.procore import endpoints as ep_registry

_CANONICAL_IDS = {
    "projects",
    "rfis",
    "rfi-responses",
    "submittals",
    "submittal-responses",
    "submittal-packages",
    "observations",
    "meetings",
    "meeting-topics",
    "meeting-detail",
    "daily-log-weather",
    "daily-log-manpower",
    "daily-log-notes",
    "daily-log-deliveries",
    "daily-log-delays-review-routed",
    "daily-log-inspections",
    "daily-log-dcrs",
    "daily-log-accident-review-routed",
    "daily-log-dumpster",
    "daily-log-safety-violation-review-routed",
    "daily-log-visitor",
    "punch-items",
    "schedules",
    "activities",
    "inspections",
    "inspection-sections",
    "inspection-items",
}


def test_registry_lists_all_canonical_endpoints() -> None:
    ids = {ep.endpoint_id for ep in ep_registry.list_all()}
    assert ids == _CANONICAL_IDS


def _resolve(endpoint_id: str):
    adapter = ep_registry.get(endpoint_id)
    assert adapter is not None, f"expected adapter for {endpoint_id}"
    return adapter


def test_legacy_alias_resolves_to_canonical_adapter() -> None:
    assert _resolve("list-rfis").endpoint_id == "rfis"
    assert _resolve("list-submittals").endpoint_id == "submittals"
    assert _resolve("list-meetings").endpoint_id == "meetings"
    assert _resolve("list-meeting-topics").endpoint_id == "meeting-topics"
    assert _resolve("list-observations").endpoint_id == "observations"


def test_canonical_id_resolves_directly() -> None:
    for canonical in _CANONICAL_IDS:
        assert _resolve(canonical).endpoint_id == canonical


def test_unknown_endpoint_resolves_to_none() -> None:
    assert ep_registry.get("does-not-exist") is None


def test_verified_endpoints_match_phase04a_matrix() -> None:
    verified = {ep.endpoint_id for ep in ep_registry.list_verified()}
    # Post daily-log endpoint resolution (2026-05-29): 27/27 verified. The
    # operator supplied real daily-log sub-log contracts; daily-log-weather
    # moved to the v1.1 /daily_logs/weather_logs path and four new sub-logs
    # (accident / dumpster / safety-violation / visitor) were added.
    # Prior note — inspection-sections/items flat-list re-target (2026-05-29):
    # The operator supplied the canonical list URLs —
    # /rest/v1.0/projects/{project_id}/checklist/list_sections (sections)
    # and /rest/v1.1/projects/{project_id}/checklist/list_items (items).
    # Both are flat project-scoped lists, NOT per-inspection N+1; the
    # prior 2-level dispatch was removed. Each item payload carries
    # list_id and section_id directly so parent_procore_id derives from
    # raw["list_id"] at upsert.
    assert verified == _CANONICAL_IDS


def test_child_endpoints_carry_parent_path_template() -> None:
    rfi_resp = _resolve("rfi-responses")
    assert rfi_resp.parent_path_template is not None
    assert "{project_id}" in rfi_resp.path_template
    assert "{rfi_id}" in rfi_resp.path_template
    assert rfi_resp.parent_record_id_field == "rfi_id"


def test_unverified_endpoints_have_verification_reason() -> None:
    for ep in ep_registry.list_all():
        if not ep.live_verified:
            assert ep.verification_reason
            assert isinstance(ep.verification_reason, str)
