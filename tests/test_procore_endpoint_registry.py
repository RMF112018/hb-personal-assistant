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
    "punch-items",
    "schedules",
    "activities",
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
    # Post schedules + activities addition: 20/20 verified. Both are
    # v2.0 company-scoped endpoints; activities iterates per-schedule N+1.
    # The shared http_client.paginate now unwraps both `items` and `data`
    # envelopes.
    assert verified == {
        "projects",
        "rfis",
        "rfi-responses",
        "submittals",
        "submittal-responses",
        "submittal-packages",
        "meetings",
        "meeting-topics",
        "meeting-detail",
        "daily-log-weather",
        "observations",
        "daily-log-manpower",
        "daily-log-notes",
        "daily-log-deliveries",
        "daily-log-delays-review-routed",
        "daily-log-inspections",
        "daily-log-dcrs",
        "punch-items",
        "schedules",
        "activities",
    }


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
