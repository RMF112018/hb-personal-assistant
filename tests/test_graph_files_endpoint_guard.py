"""Phase 06 (Files) — runtime endpoint-guard behavior.

Mirrors tests/test_graph_mail_endpoint_guard.py: proves the loaded contract is
GET-only, every allowlisted read GET is permitted, and every mutating verb / path
/ keyword is refused before any HTTP request.
"""

from __future__ import annotations

import pytest

from hb_assistant.graph.files_endpoint_guard import (
    FileMutationBlockedError,
    assert_files_request_allowed,
    load_files_endpoint_contract,
    run_files_no_writeback_self_test,
    sample_path,
)


def test_contract_loads_get_only():
    contract = load_files_endpoint_contract(refresh=True)
    assert contract.allowed_methods == frozenset({"GET"})
    assert contract.forbidden_methods == frozenset({"POST", "PUT", "PATCH", "DELETE"})
    assert contract.allowed_paths
    assert contract.forbidden_paths


def test_allowlisted_get_paths_are_permitted():
    contract = load_files_endpoint_contract()
    for tmpl in contract.allowed_paths:
        # Returns None when allowed; raises otherwise.
        assert assert_files_request_allowed("GET", sample_path(tmpl), contract=contract) is None


def test_forbidden_methods_blocked_on_any_path():
    contract = load_files_endpoint_contract()
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(FileMutationBlockedError):
            assert_files_request_allowed(verb, "/drives/D1/items/I1", contract=contract)


def test_forbidden_mutation_paths_blocked():
    contract = load_files_endpoint_contract()
    for tmpl in contract.forbidden_paths:
        with pytest.raises(FileMutationBlockedError):
            assert_files_request_allowed("POST", sample_path(tmpl), contract=contract)


def test_upload_and_share_and_permission_ops_blocked():
    contract = load_files_endpoint_contract()
    # Even if a verb were GET, these mutation operations must never be allowed.
    for method, path in (
        ("PUT", "/drives/D1/items/I1/content"),
        ("POST", "/drives/D1/items/I1/createUploadSession"),
        ("POST", "/drives/D1/items/I1/createLink"),
        ("POST", "/drives/D1/items/I1/invite"),
        ("POST", "/drives/D1/items/I1/copy"),
        ("POST", "/drives/D1/items/I1/checkout"),
        ("DELETE", "/drives/D1/items/I1"),
    ):
        with pytest.raises(FileMutationBlockedError):
            assert_files_request_allowed(method, path, contract=contract)


def test_get_on_content_path_permitted_but_put_blocked():
    contract = load_files_endpoint_contract()
    # Controlled download is a GET on /content; the *verb* decides.
    assert (
        assert_files_request_allowed("GET", "/me/drive/items/I1/content", contract=contract) is None
    )
    with pytest.raises(FileMutationBlockedError):
        assert_files_request_allowed("PUT", "/me/drive/items/I1/content", contract=contract)


def test_self_test_passes_with_no_anomalies():
    result = run_files_no_writeback_self_test()
    assert result["passed"] is True
    assert result["anomalies"] == []
    assert result["read_paths_allowed"] > 0
    assert result["mutation_attempts_blocked"] > 0


def test_blocked_error_is_sanitized():
    contract = load_files_endpoint_contract()
    with pytest.raises(FileMutationBlockedError) as ei:
        assert_files_request_allowed("DELETE", "/drives/D1/items/I1", contract=contract)
    msg = str(ei.value)
    assert "DELETE" in msg
    # No token-shaped material in the sanitized error.
    for leak in ("Bearer", "access_token", "eyJ"):
        assert leak not in msg
