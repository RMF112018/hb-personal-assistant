"""Boundary tests for Procore redaction primitives + error envelopes (Prompt 12).

Each test exercises one redaction boundary using only synthetic fixtures from
``hb_assistant.procore.fixtures``. No real HTTP, no real credentials.
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.procore.errors import ProcoreAPIError, ProcoreRateLimitError
from hb_assistant.procore.fixtures import (
    PROCORE_ERROR_FIXTURES,
    PROCORE_MALFORMED_BODY_FIXTURES,
    SYNTHETIC_TOKEN_LITERALS,
)
from hb_assistant.procore.redaction import (
    redact_body,
    redact_headers,
    redact_request,
    redact_response,
)


def _assert_no_synthetic_leak(text: str) -> None:
    for literal in SYNTHETIC_TOKEN_LITERALS:
        assert literal not in text, f"synthetic literal leaked: {literal[:24]!r}..."
    assert "eyJ" not in text
    assert "Bearer " not in text


def test_redact_headers_masks_authorization() -> None:
    headers = {
        "Authorization": "Bearer should-never-appear-1234567890",
        "Cookie": "session=should-never-appear",
        "X-Api-Key": "k-should-never-appear-1234567890",
        "Content-Type": "application/json",
    }
    out = redact_headers(headers)

    assert out["Authorization"] == "[REDACTED]"
    assert out["Cookie"] == "[REDACTED]"
    assert out["X-Api-Key"] == "[REDACTED]"
    assert out["Content-Type"] == "application/json"
    _assert_no_synthetic_leak(json.dumps(out))


def test_redact_headers_masks_token_in_value() -> None:
    headers = {"X-Trace": "Bearer should-never-appear-1234567890"}
    out = redact_headers(headers)
    assert out["X-Trace"] == "[REDACTED]"


def test_redact_request_strips_query_string() -> None:
    out = redact_request(
        "GET",
        "https://api.procore.com/rest/v1.0/projects?access_token=should-never-appear-1234567890",
        {"Authorization": "Bearer should-never-appear-1234567890"},
        params={"per_page": 100},
    )
    assert out["method"] == "GET"
    assert "?" not in (out["url_path_redacted"] or "")
    assert "access_token" not in (out["url_path_redacted"] or "")
    assert out["headers"]["Authorization"] == "[REDACTED]"
    assert out["params_summary"]["type"] == "dict"


def test_redact_response_extracts_rate_limit_separately() -> None:
    headers = {
        "Authorization": "Bearer should-never-appear-1234567890",
        "X-RateLimit-Limit": "300",
        "X-RateLimit-Remaining": "0",
        "Retry-After": "5",
    }
    out = redact_response(
        429, headers, {"errors": ["rate_limited"], "message": "Too Many Requests"}
    )

    assert out["status"] == 429
    assert out["rate_limit"]["Retry-After"] == "5"
    assert out["rate_limit"]["X-RateLimit-Remaining"] == "0"
    assert out["headers"]["Authorization"] == "[REDACTED]"
    summary = out["body_summary"]
    assert summary["type"] == "dict"
    assert summary["error_fields"]["message"] == "Too Many Requests"


def test_redact_body_dict_returns_structural_summary() -> None:
    body = {"id": 1, "name": "Synthetic", "nested": {"a": 1}}
    out = redact_body(body)
    assert out["type"] == "dict"
    assert set(out["top_level_keys"]).issubset({"id", "name", "nested"})
    assert out["key_count"] == 3
    assert "Synthetic" not in json.dumps(out)


def test_redact_body_for_error_allowlist() -> None:
    fixture = PROCORE_MALFORMED_BODY_FIXTURES["body_with_client_secret_field"]
    out = redact_body(fixture, for_error=True)

    assert out["type"] == "dict"
    error_fields = out.get("error_fields") or {}
    assert set(error_fields.keys()).issubset(
        {"error", "errors", "message", "code", "status", "title"}
    )
    _assert_no_synthetic_leak(json.dumps(out))


def test_redact_body_string_hashes_oversize() -> None:
    body = "X" * 1024
    out = redact_body(body)
    assert out["type"] == "string"
    assert out["length"] == 1024
    assert "hash_prefix" in out
    assert "value" not in out


def test_procore_api_error_str_is_redacted() -> None:
    fixture = PROCORE_ERROR_FIXTURES["forbidden_403"]
    redacted_response = redact_response(fixture["status"], fixture["headers"], fixture["body"])
    redacted_request = redact_request(
        "GET",
        "/rest/v1.0/projects/9",
        {"Authorization": "Bearer should-never-appear-1234567890"},
    )

    err = ProcoreAPIError(
        status=fixture["status"],
        code="forbidden",
        message=fixture["body"]["message"],
        correlation_id="corr-1",
        request=redacted_request,
        response=redacted_response,
    )

    rendered = str(err)
    _assert_no_synthetic_leak(rendered)
    assert "[REDACTED]" in rendered
    assert "Insufficient permissions" in rendered


def test_rate_limit_error_repr_safe() -> None:
    fixture = PROCORE_ERROR_FIXTURES["rate_limited_429"]
    redacted_response = redact_response(fixture["status"], fixture["headers"], fixture["body"])
    err = ProcoreRateLimitError(
        status=fixture["status"],
        code="rate_limited",
        message=fixture["body"]["message"],
        correlation_id="corr-429",
        response=redacted_response,
        retry_after=fixture["expected_retry_after_seconds"],
    )

    _assert_no_synthetic_leak(str(err))
    assert err.retry_after == 5
    assert repr(err).startswith("<ProcoreAPIError")


@pytest.mark.parametrize("fixture_key", sorted(PROCORE_MALFORMED_BODY_FIXTURES.keys()))
def test_no_fixture_leak_round_trip(fixture_key: str) -> None:
    body = PROCORE_MALFORMED_BODY_FIXTURES[fixture_key]
    headers = {
        "Authorization": "Bearer should-never-appear-1234567890",
        "X-RateLimit-Limit": "300",
    }
    summary = redact_response(500, headers, body)
    serialized = json.dumps(summary)
    _assert_no_synthetic_leak(serialized)
    assert summary["headers"]["Authorization"] == "[REDACTED]"
