"""
Tests for the GET-only Procore HTTP client foundation (Prompt_04).

All tests use an injected mock transport. Zero real HTTP calls, zero secrets ever.

Includes the static (AST + text) GET-only scanner that proves the procore/ source tree
contains no non-GET methods.

Designs synthesized from the three subagent explorations (019e6b5b-*) + approved plan.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

from hb_assistant.procore.errors import (
    ProcoreAPIError,
    ProcoreAuthRequired,
    ProcoreRateLimitError,
)
from hb_assistant.procore.http_client import ProcoreHTTPClient

SYNTHETIC_ACCESS_TOKEN = "synthetic-test-access-token"


def _stub_token_provider() -> str:
    return SYNTHETIC_ACCESS_TOKEN


def _empty_token_provider() -> str | None:
    return None


# --- Minimal mock transport support -------------------------------------------------

class FakeResponse:
    def __init__(self, status_code: int, json_body: Any = None, headers: Dict[str, str] | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body
        self.headers = headers or {}
        self.text = text

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


Transport = Callable[[str, str, Dict[str, str], Dict[str, Any] | None], FakeResponse]


def make_recording_transport(responses: List[FakeResponse]) -> tuple[Transport, List[Dict[str, Any]]]:
    calls: List[Dict[str, Any]] = []
    idx = {"i": 0}

    def t(method: str, url: str, headers: Dict[str, str], params: Dict[str, Any] | None = None) -> FakeResponse:
        calls.append({"method": method, "url": url, "headers": headers, "params": params})
        if idx["i"] < len(responses):
            resp = responses[idx["i"]]
            idx["i"] += 1
            return resp
        return FakeResponse(200, {})

    return t, calls


# --- Static GET-only scanner (from subagent design, lives in allowed test file) -----

FORBIDDEN_METHODS = {"post", "put", "patch", "delete", "head", "options"}
FORBIDDEN_STRINGS = {"POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _scan_file_for_non_get(py_path: Path) -> List[str]:
    violations: List[str] = []
    try:
        src = py_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(getattr(node, "func", None), ast.Attribute):
                attr = node.func.attr.lower()  # type: ignore[attr-defined]
                if attr in FORBIDDEN_METHODS:
                    violations.append(f"{py_path}:{getattr(node, 'lineno', '?')}: .{attr}() call")
            if isinstance(node, (ast.Constant, ast.Str)):
                v = getattr(node, "value", getattr(node, "s", None))
                if isinstance(v, str) and v.upper() in FORBIDDEN_STRINGS:
                    violations.append(f"{py_path}:{getattr(node, 'lineno', '?')}: HTTP method string {v!r}")
    except Exception as e:
        violations.append(f"{py_path}: parse-failed {e}")
    return violations


def scan_procore_tree_for_non_get() -> List[str]:
    procore_dir = Path(__file__).resolve().parents[2] / "src" / "hb_assistant" / "procore"
    vios: List[str] = []
    for f in procore_dir.rglob("*.py"):
        if any(p in f.parts for p in ("__pycache__", "test", "tests", ".git")):
            continue
        vios.extend(_scan_file_for_non_get(f))
    return vios


# --- Tests ----------------------------------------------------------------------------

def test_static_get_only_enforcement_procore_source_tree():
    """The static scanner must prove the entire procore/ tree (including the new http_client) is GET-only."""
    violations = scan_procore_tree_for_non_get()
    assert not violations, "Non-GET HTTP methods detected in procore/ source:\n" + "\n".join(violations[:30])


def test_single_get_happy_path():
    transport, calls = make_recording_transport([
        FakeResponse(200, {"id": 123, "name": "Test"}, headers={"X-Request-Id": "corr-1"})
    ])
    client = ProcoreHTTPClient(environment="sandbox", transport=transport, access_token_provider=_stub_token_provider)
    resp = client.get("/rest/v1.0/projects/123")

    assert len(calls) == 1
    call = calls[0]
    assert call["method"] == "GET"
    assert "Procore-Company-Id" in call["headers"]
    assert call["headers"]["Authorization"].startswith("Bearer ")
    # The real secret from Prompt_02 loader is used at runtime; in this test it is the test value
    assert resp.status_code == 200
    assert resp.json()["id"] == 123


def test_get_only_runtime_guard():
    transport, _ = make_recording_transport([])
    client = ProcoreHTTPClient(environment="sandbox", transport=transport, access_token_provider=_stub_token_provider)

    with pytest.raises(ProcoreAPIError) as exc:
        client._request("POST", "/rest/v1.0/anything")  # type: ignore[attr-defined]

    assert "Only GET is permitted" in str(exc.value)


def test_error_normalization_and_redaction():
    transport, _ = make_recording_transport([
        FakeResponse(403, {"message": "forbidden"}, headers={"Authorization": "Bearer SECRET"})
    ])
    client = ProcoreHTTPClient(environment="sandbox", transport=transport, access_token_provider=_stub_token_provider)

    with pytest.raises(ProcoreAPIError) as exc:
        client.get("/rest/v1.0/secret-stuff")

    err = exc.value
    assert err.status == 403
    # Redaction must have stripped the Authorization header from any response surface
    # (the response object itself is redacted before error construction in real path)
    assert "SECRET" not in str(err)
    assert "Bearer" not in str(err).lower()


def test_429_rate_limit_error_with_retry_after():
    transport, _ = make_recording_transport([
        FakeResponse(429, {}, headers={"Retry-After": "2", "X-RateLimit-Remaining": "0"})
    ])
    client = ProcoreHTTPClient(environment="sandbox", transport=transport, access_token_provider=_stub_token_provider)

    with pytest.raises(ProcoreRateLimitError) as exc:
        client.get("/rest/v1.0/heavy")

    assert exc.value.status == 429
    assert exc.value.retry_after == 2


# --- Phase 04 Prompt 01 hardening tests --------------------------------------

def test_client_fails_closed_when_no_access_token():
    """No access token from the provider must raise ProcoreAuthRequired
    before any transport invocation. The client must never reuse
    PROCORE_CLIENT_SECRET as a bearer credential.
    """
    def _exploding_transport(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise AssertionError("transport must not be reached without an access token")

    client = ProcoreHTTPClient(
        environment="sandbox",
        transport=_exploding_transport,
        access_token_provider=_empty_token_provider,
    )
    with pytest.raises(ProcoreAuthRequired):
        client.get("/rest/v1.1/projects")


def test_authorization_header_uses_access_token_not_client_secret():
    """The Authorization header must carry the access token from the provider,
    not anything sourced from the client secret loader.
    """
    transport, calls = make_recording_transport([FakeResponse(200, {"items": []})])
    client = ProcoreHTTPClient(
        environment="sandbox",
        transport=transport,
        access_token_provider=_stub_token_provider,
    )
    client.get("/rest/v1.1/projects")
    assert calls[0]["headers"]["Authorization"] == f"Bearer {SYNTHETIC_ACCESS_TOKEN}"


def test_paginate_method_aligned_with_sync_call_site():
    """sync.py invokes ``client.paginate(...)``. The HTTP client must expose
    that exact name; the legacy ``get_paginated`` name must not survive.
    """
    assert hasattr(ProcoreHTTPClient, "paginate")
    assert not hasattr(ProcoreHTTPClient, "get_paginated")
