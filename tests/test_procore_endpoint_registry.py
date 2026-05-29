"""Phase 04A endpoint adapter registry shape + alias resolution tests."""

from __future__ import annotations

from hb_assistant.procore import endpoints as ep_registry
from hb_assistant.procore.live_sync import resolve_normalizer

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

# Phase 05 financial / contract-control endpoint shells. All are registered
# live_verified=False (fail-closed, no transport) until per-endpoint smoke
# evidence promotes them; see endpoints.py and
# docs/evidence/construction-intelligence-phase-05-financials/.
_PHASE05_FINANCIAL_IDS = frozenset(
    {
        "prime-contracts",
        "prime-contract-line-items",
        "prime-contract-attachments",
        "prime-change-orders",
        "prime-change-order-line-items",
        "payment-applications",
        "commitment-contracts",
        "commitment-line-items",
        "commitment-attachments",
        "commitment-compliance",
        "commitment-change-orders",
        "commitment-change-order-line-items",
        "purchase-order-contracts",
        "purchase-order-line-items",
        "purchase-order-detail-line-items",
        "billing-periods",
        "subcontractor-invoices",
        "subcontractor-invoice-contract-items",
        "subcontractor-invoice-contract-detail-items",
        "subcontractor-invoice-change-order-items",
        "rfqs",
        "rfq-responses",
        "rfq-quotes",
        "change-events",
        "change-event-comments",
        "budget-views",
        "budget-detail-columns",
        "budget-details",
        "budget-detail-rows",
        "budget-change-history",
        "budget-change-line-items",
        "budget-modifications",
    }
)


def test_registry_lists_all_canonical_endpoints() -> None:
    ids = {ep.endpoint_id for ep in ep_registry.list_all()}
    assert ids == _CANONICAL_IDS | _PHASE05_FINANCIAL_IDS


def test_phase05_financial_endpoint_count_is_intentional() -> None:
    # 27 verified operational rows + 32 fail-closed financial shells = 59.
    assert len(_PHASE05_FINANCIAL_IDS) == 32
    assert len(ep_registry.list_all()) == len(_CANONICAL_IDS) + 32 == 59


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


def test_phase05_financial_ids_all_resolve() -> None:
    for fin_id in _PHASE05_FINANCIAL_IDS:
        assert ep_registry.is_known(fin_id)
        assert _resolve(fin_id).endpoint_id == fin_id


# Owner-family endpoints whose normalizers + projections are implemented (Prompt
# 04). They are registered in the dispatch map but stay live_verified=False, so
# they still fail closed before the normalizer lookup until smoke promotion.
_OWNER_IMPLEMENTED = frozenset(
    {
        "prime-contracts",
        "prime-contract-line-items",
        "prime-contract-attachments",
        "prime-change-orders",
        "prime-change-order-line-items",
        "payment-applications",
    }
)

# Vendor-side endpoints implemented in Prompt 05 (commitments + PO compatibility).
_COMMITMENT_IMPLEMENTED = frozenset(
    {
        "commitment-contracts",
        "commitment-line-items",
        "commitment-attachments",
        "commitment-compliance",
        "purchase-order-contracts",
        "purchase-order-line-items",
        "purchase-order-detail-line-items",
    }
)

_IMPLEMENTED = _OWNER_IMPLEMENTED | _COMMITMENT_IMPLEMENTED


def test_phase05_financial_endpoints_are_fail_closed() -> None:
    # The durable fail-closed guarantee is live_verified=False (the orchestrator
    # returns not_live_verified BEFORE any normalizer lookup). Not-yet-implemented
    # endpoints additionally have no normalizer registered.
    for fin_id in _PHASE05_FINANCIAL_IDS:
        adapter = _resolve(fin_id)
        assert adapter.live_verified is False, fin_id
        assert adapter.sensitivity == "high", fin_id
        if fin_id not in _IMPLEMENTED:
            assert resolve_normalizer(fin_id) is None, fin_id


def test_phase05_owner_endpoints_have_normalizers() -> None:
    # Prompt 04 registered the owner-family normalizers (ready to project once
    # promoted); they remain unverified above.
    for fin_id in _OWNER_IMPLEMENTED:
        assert resolve_normalizer(fin_id) is not None, fin_id


def test_phase05_commitment_endpoints_have_normalizers() -> None:
    # Prompt 05 registered the vendor-side normalizers; still unverified above.
    for fin_id in _COMMITMENT_IMPLEMENTED:
        assert resolve_normalizer(fin_id) is not None, fin_id


def test_phase05_financial_endpoints_excluded_from_verified() -> None:
    verified = {ep.endpoint_id for ep in ep_registry.list_verified()}
    assert verified.isdisjoint(_PHASE05_FINANCIAL_IDS)


def test_budget_details_is_non_routable_sentinel() -> None:
    # Source reference has no resolved path (Prompt 00 §3.2); the sentinel must
    # never look like a real REST route so it cannot accidentally transport.
    adapter = _resolve("budget-details")
    assert not adapter.path_template.startswith("/rest/")
    assert adapter.required_path_params == ()
    assert adapter.live_verified is False


def test_phase05_financial_parent_child_consistency() -> None:
    by_path = {
        ep.path_template: ep
        for ep in ep_registry.list_all()
        if ep.endpoint_id in _PHASE05_FINANCIAL_IDS
    }
    for fin_id in _PHASE05_FINANCIAL_IDS:
        adapter = _resolve(fin_id)
        if adapter.parent_path_template is None:
            # Top-level financial endpoint: no parent linkage expected.
            assert adapter.parent_record_id_field is None, fin_id
            continue
        # Child endpoint: parent path must point at a registered financial parent.
        assert adapter.parent_path_template in by_path, fin_id
        # Where a parent id field is declared, it must appear in the child path
        # (the non-routable budget-details sentinel is exempt from this check).
        if adapter.parent_record_id_field and fin_id != "budget-details":
            assert "{" + adapter.parent_record_id_field + "}" in adapter.path_template, fin_id
