"""Synthetic transport-shape fixtures for offline Procore tests (Phase 03, Prompt 12).

These fixtures are pure Python dicts that mirror the shapes the GET-only Procore
HTTP client emits and consumes: paginated responses, error envelopes, rate-limit
header maps, sensitive-routing rows, and malformed bodies used to probe redaction.

Every credential-shaped value in this module is synthetic — the JWT prefix uses
the well-known ``eyJ`` header followed by deterministic garbage, and the bearer
token / client_secret values contain the literal substring "synthetic" so the
repo sensitive-scan allowlist can name this file once and never produce a false
positive.

No live HTTP, no Pydantic validation, no real credentials.
"""

from __future__ import annotations

from typing import Any, Dict

_SYNTHETIC_JWT = (
    "eyJhbGciOiJIUzI1NiJ9"
    ".eyJzdWIiOiJzeW50aGV0aWMtZml4dHVyZS1ub3QtcmVhbCJ9"
    ".synthetic-signature-not-a-real-token-value"
)
_SYNTHETIC_BEARER = f"Bearer {_SYNTHETIC_JWT}"
_SYNTHETIC_CLIENT_SECRET = "synthetic-fixture-not-a-real-credential"

PROCORE_PAGE_FIXTURES: Dict[str, Dict[str, Any]] = {
    "single_page": {
        "status": 200,
        "headers": {
            "Content-Type": "application/json",
            "X-Total": "2",
            "X-RateLimit-Limit": "300",
            "X-RateLimit-Remaining": "298",
        },
        "body": [
            {"id": 1, "name": "Synthetic Project A"},
            {"id": 2, "name": "Synthetic Project B"},
        ],
        "expected_next_link": None,
        "expected_next_cursor": None,
    },
    "multi_page_first": {
        "status": 200,
        "headers": {
            "Content-Type": "application/json",
            "Link": '<https://api.procore.com/rest/v1.0/projects?page=2>; rel="next"',
            "X-Total": "120",
            "X-RateLimit-Limit": "300",
            "X-RateLimit-Remaining": "287",
        },
        "body": [{"id": i, "name": f"Synthetic Project {i}"} for i in range(1, 51)],
        "expected_next_link": "https://api.procore.com/rest/v1.0/projects?page=2",
        "expected_next_cursor": None,
    },
    "multi_page_next": {
        "status": 200,
        "headers": {
            "Content-Type": "application/json",
            "X-RateLimit-Limit": "300",
            "X-RateLimit-Remaining": "286",
        },
        "body": [{"id": i, "name": f"Synthetic Project {i}"} for i in range(51, 101)],
        "expected_next_link": None,
        "expected_next_cursor": None,
    },
    "empty_page": {
        "status": 200,
        "headers": {"Content-Type": "application/json", "X-Total": "0"},
        "body": [],
        "expected_next_link": None,
        "expected_next_cursor": None,
    },
}

PROCORE_ERROR_FIXTURES: Dict[str, Dict[str, Any]] = {
    "bad_request_400": {
        "status": 400,
        "headers": {"Content-Type": "application/json"},
        "body": {"errors": ["invalid_parameter"], "message": "Bad Request"},
        "expected_exception": "ProcoreAPIError",
    },
    "unauthorized_401": {
        "status": 401,
        "headers": {"Content-Type": "application/json", "WWW-Authenticate": "Bearer realm=procore"},
        "body": {"errors": ["unauthorized"], "message": "Invalid or expired token"},
        "expected_exception": "ProcoreAPIError",
    },
    "forbidden_403": {
        "status": 403,
        "headers": {"Content-Type": "application/json"},
        "body": {"errors": ["forbidden"], "message": "Insufficient permissions"},
        "expected_exception": "ProcoreAPIError",
    },
    "not_found_404": {
        "status": 404,
        "headers": {"Content-Type": "application/json"},
        "body": {"errors": ["not_found"], "message": "Resource not found"},
        "expected_exception": "ProcoreAPIError",
    },
    "rate_limited_429": {
        "status": 429,
        "headers": {"Retry-After": "5", "X-RateLimit-Remaining": "0", "X-RateLimit-Limit": "300"},
        "body": {"errors": ["rate_limited"], "message": "Too Many Requests"},
        "expected_exception": "ProcoreRateLimitError",
        "expected_retry_after_seconds": 5,
    },
    "server_error_500": {
        "status": 500,
        "headers": {"Content-Type": "application/json"},
        "body": {"errors": ["internal_server_error"], "message": "Internal Server Error"},
        "expected_exception": "ProcoreAPIError",
    },
    "gateway_timeout_504": {
        "status": 504,
        "headers": {"Content-Type": "application/json"},
        "body": {"errors": ["gateway_timeout"], "message": "Gateway Timeout"},
        "expected_exception": "ProcoreAPIError",
    },
}

PROCORE_RATE_LIMIT_HEADERS: Dict[str, Dict[str, str]] = {
    "healthy": {
        "X-RateLimit-Limit": "300",
        "X-RateLimit-Remaining": "295",
        "X-RateLimit-Reset": "1735689600",
    },
    "warning_low_remaining": {
        "X-RateLimit-Limit": "300",
        "X-RateLimit-Remaining": "12",
        "X-RateLimit-Reset": "1735689600",
    },
    "exhausted_with_retry_after": {
        "X-RateLimit-Limit": "300",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": "1735689600",
        "Retry-After": "8",
    },
}

PROCORE_SENSITIVE_ROUTING_FIXTURES: Dict[str, Dict[str, Any]] = {
    "high_financial_commitment": {
        "category": "commitments",
        "title": "Commitment 2025-014 budget revision",
        "expected_route": "review_required",
        "expected_sensitivity": "high",
    },
    "critical_pco_change_order": {
        "category": "commitment_change_orders",
        "title": "PCO-014 pricing revision",
        "expected_route": "review_required",
        "expected_sensitivity": "critical",
    },
    "critical_incident_keywords": {
        "category": "daily_log",
        "title": "Site incident on 2026-05-20 — injury report filed",
        "expected_route": "review_required",
        "expected_sensitivity": "critical",
    },
    "normal_low_sensitivity": {
        "category": "projects",
        "title": "Project summary update",
        "expected_route": "normal",
        "expected_sensitivity": "low",
    },
}

PROCORE_MALFORMED_BODY_FIXTURES: Dict[str, Dict[str, Any]] = {
    "body_with_bearer_token": {
        "items": [{"note": _SYNTHETIC_BEARER, "id": 1}],
        "comment": "synthetic bearer string embedded in body content",
    },
    "body_with_jwt": {
        "items": [{"jwt": _SYNTHETIC_JWT, "id": 2}],
        "comment": "synthetic JWT-like string embedded in body content",
    },
    "body_with_client_secret_field": {
        "client_secret": _SYNTHETIC_CLIENT_SECRET,
        "id": 3,
    },
    "body_with_oversize_string": {
        "blob": "A" * 4096,
        "id": 4,
    },
    "body_with_nested_token_field": {
        "data": {"meta": {"auth": {"token": _SYNTHETIC_JWT}}},
        "id": 5,
    },
}

SYNTHETIC_TOKEN_LITERALS: tuple[str, ...] = (
    _SYNTHETIC_JWT,
    _SYNTHETIC_BEARER,
    _SYNTHETIC_CLIENT_SECRET,
)
