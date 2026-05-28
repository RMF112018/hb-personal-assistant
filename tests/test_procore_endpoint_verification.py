"""Phase 04 Prompt 03 — structured endpoint verification metadata.

Validates the five new fields on ``ProcoreEndpoint``
(``verification_status``, ``official_reference_url``, ``verified_at_utc``,
``verified_by``, ``live_dry_run_receipt_id``, plus ``verification_reason``),
the model-level invariants, and the derived ``is_live_eligible`` property.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hb_assistant.procore.loader import load_endpoint_contract
from hb_assistant.procore.models import ProcoreEndpoint


def _valid_validated_payload(**overrides: object) -> dict:
    base = {
        "endpoint_id": "ep-test",
        "http_method": "GET",
        "path_template": "/rest/v1.0/anything",
        "category": "rfis",
        "status": "validated",
        "sensitivity": "low",
        "included_in_phase_01": True,
        "verification_status": "official_docs_verified",
        "official_reference_url": "https://developers.procore.com/test",
        "verified_at_utc": "2026-05-27T00:00:00Z",
        "verified_by": "test-fixture",
    }
    base.update(overrides)
    return base


def _valid_excluded_payload() -> dict:
    return {
        "endpoint_id": "ep-excluded",
        "http_method": "GET",
        "path_template": "/rest/v1.0/excluded",
        "category": "correspondence",
        "status": "excluded",
        "sensitivity": "critical",
        "included_in_phase_01": False,
        "verification_status": "excluded_by_guardrail",
        "verification_reason": "Hard guardrail.",
    }


def _valid_deferred_payload() -> dict:
    return {
        "endpoint_id": "ep-deferred",
        "http_method": "GET",
        "path_template": "/rest/v1.0/schedule",
        "category": "schedule",
        "status": "deferred",
        "sensitivity": "medium",
        "included_in_phase_01": False,
        "verification_status": "deferred_by_guardrail",
        "verification_reason": "Hard guardrail.",
    }


# --- Loader against the migrated seed ----------------------------------------


def test_seed_loads_with_structured_verification_fields() -> None:
    contract = load_endpoint_contract()
    # 13 prior endpoints + Phase 04 Prompt 06's candidate `list-observations`.
    assert len(contract.endpoints) == 14

    by_v: dict[str, int] = {}
    for ep in contract.endpoints:
        by_v[ep.verification_status] = by_v.get(ep.verification_status, 0) + 1
    assert by_v == {
        "official_docs_verified": 10,
        "excluded_by_guardrail": 1,
        "deferred_by_guardrail": 2,
        "candidate": 1,
    }


def test_seed_live_eligible_count_matches_official_docs_verified() -> None:
    contract = load_endpoint_contract()
    eligible_ids = sorted(e.endpoint_id for e in contract.endpoints if e.is_live_eligible)
    assert len(eligible_ids) == 10
    # No excluded / deferred / unverified endpoint leaks into the eligible set.
    for ep in contract.endpoints:
        if ep.endpoint_id in eligible_ids:
            assert ep.status in ("validated", "sensitive_validated")
            assert ep.verification_status == "official_docs_verified"
            assert ep.included_in_phase_01 is True


def test_seed_every_included_endpoint_has_url_or_reason() -> None:
    contract = load_endpoint_contract()
    for ep in contract.endpoints:
        if ep.included_in_phase_01 and ep.status not in ("excluded", "deferred"):
            assert ep.official_reference_url or ep.verification_reason


def test_contract_get_endpoint_helper_returns_match_or_none() -> None:
    contract = load_endpoint_contract()
    assert contract.get_endpoint("list-projects") is not None
    assert contract.get_endpoint("nonexistent-id") is None


# --- Model-level invariants --------------------------------------------------


def test_included_phase_01_endpoint_without_url_or_reason_is_rejected() -> None:
    payload = _valid_validated_payload(
        official_reference_url=None,
        verification_reason=None,
    )
    with pytest.raises(ValidationError, match="official_reference_url or verification_reason"):
        ProcoreEndpoint(**payload)


def test_excluded_endpoint_with_wrong_verification_status_is_rejected() -> None:
    payload = _valid_excluded_payload()
    payload["verification_status"] = "official_docs_verified"
    with pytest.raises(ValidationError, match="excluded_by_guardrail"):
        ProcoreEndpoint(**payload)


def test_deferred_endpoint_with_wrong_verification_status_is_rejected() -> None:
    payload = _valid_deferred_payload()
    payload["verification_status"] = "candidate"
    with pytest.raises(ValidationError, match="deferred_by_guardrail"):
        ProcoreEndpoint(**payload)


def test_validated_endpoint_with_guardrail_verification_status_is_rejected() -> None:
    payload = _valid_validated_payload(verification_status="excluded_by_guardrail")
    with pytest.raises(ValidationError):
        ProcoreEndpoint(**payload)


def test_non_https_official_reference_url_is_rejected() -> None:
    payload = _valid_validated_payload(official_reference_url="http://example.com/x")
    with pytest.raises(ValidationError, match="https://"):
        ProcoreEndpoint(**payload)


def test_malformed_verified_at_utc_is_rejected() -> None:
    payload = _valid_validated_payload(verified_at_utc="not-a-date")
    with pytest.raises(ValidationError, match="verified_at_utc"):
        ProcoreEndpoint(**payload)


def test_is_live_eligible_is_false_for_excluded() -> None:
    ep = ProcoreEndpoint(**_valid_excluded_payload())
    assert ep.is_live_eligible is False


def test_is_live_eligible_is_false_for_deferred() -> None:
    ep = ProcoreEndpoint(**_valid_deferred_payload())
    assert ep.is_live_eligible is False


def test_is_live_eligible_is_false_for_candidate_verification_status() -> None:
    payload = _valid_validated_payload(
        verification_status="candidate",
        official_reference_url=None,
        verified_at_utc=None,
        verified_by=None,
        verification_reason="pending verification",
    )
    ep = ProcoreEndpoint(**payload)
    assert ep.is_live_eligible is False


def test_is_live_eligible_is_false_when_not_included_in_phase_01() -> None:
    payload = _valid_validated_payload(included_in_phase_01=False)
    ep = ProcoreEndpoint(**payload)
    assert ep.is_live_eligible is False


def test_is_live_eligible_is_true_for_verified_included_endpoint() -> None:
    ep = ProcoreEndpoint(**_valid_validated_payload())
    assert ep.is_live_eligible is True
