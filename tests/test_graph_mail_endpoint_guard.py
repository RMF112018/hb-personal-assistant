"""Phase 06 Prompt 04 — Graph mail endpoint guard (runtime read-only enforcement).

Proves the guard allows every allowlisted GET read pattern and refuses every
mailbox-mutation verb/path/keyword before any HTTP request, using the Prompt 01
contract resources.
"""

from __future__ import annotations

import pytest

from hb_assistant.graph.mail_endpoint_guard import (
    MailboxMutationBlockedError,
    assert_mail_request_allowed,
    load_mail_endpoint_contract,
)


def test_contract_loads_get_only_and_metadata_only() -> None:
    c = load_mail_endpoint_contract(refresh=True)
    assert c.allowed_methods == frozenset({"GET"})
    assert {"POST", "PATCH", "DELETE", "PUT"} <= c.forbidden_methods
    # metadata-only: full body and attachment content are structurally excluded.
    assert "body" not in c.message_metadata_select
    assert "bodyPreview" in c.message_metadata_select
    assert "contentBytes" not in c.attachment_metadata_select


@pytest.mark.parametrize(
    "path",
    [
        "/me",
        "/me/mailFolders",
        "/me/mailFolders/AAMkADk/messages",
        "/me/messages",
        "/me/messages/AAMkADk",
        "/me/messages/AAMkADk/attachments",
        "/me/mailFolders/AAMkADk/messages/delta",
        # folder addressed by well-known name must NOT trip a keyword false-positive
        "/me/mailFolders/drafts/messages",
        "/me/mailFolders/deleteditems/messages",
        # absolute graph URL with query string normalizes correctly
        "https://graph.microsoft.com/v1.0/me/mailFolders?$top=1",
    ],
)
def test_allowlisted_get_is_permitted(path: str) -> None:
    assert assert_mail_request_allowed("GET", path) is None


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
def test_forbidden_methods_are_blocked_on_any_path(method: str) -> None:
    with pytest.raises(MailboxMutationBlockedError):
        assert_mail_request_allowed(method, "/me/messages/AAMkADk")


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/me/sendMail"),
        ("POST", "/me/messages/AAMkADk/move"),
        ("POST", "/me/messages/AAMkADk/copy"),
        ("POST", "/me/messages/AAMkADk/forward"),
        ("POST", "/me/messages/AAMkADk/reply"),
        ("POST", "/me/messages/AAMkADk/replyAll"),
        ("POST", "/me/messages/AAMkADk/send"),
        # even a GET against a mutation action endpoint is refused
        ("GET", "/me/messages/AAMkADk/reply"),
        # raw attachment content download path is refused
        ("GET", "/me/messages/AAMkADk/attachments/A1/$value"),
    ],
)
def test_mutation_paths_are_blocked(method: str, path: str) -> None:
    with pytest.raises(MailboxMutationBlockedError):
        assert_mail_request_allowed(method, path)


def test_non_get_method_on_allowlisted_path_is_blocked() -> None:
    # GET /me/mailFolders is allowed, but no other verb is.
    with pytest.raises(MailboxMutationBlockedError):
        assert_mail_request_allowed("PUT", "/me/mailFolders")


def test_unknown_read_path_is_blocked() -> None:
    # A GET that is simply not on the allowlist is refused.
    with pytest.raises(MailboxMutationBlockedError):
        assert_mail_request_allowed("GET", "/me/contacts")


def test_blocked_error_is_sanitized() -> None:
    try:
        assert_mail_request_allowed("POST", "/me/sendMail")
    except MailboxMutationBlockedError as e:
        assert e.method == "POST"
        assert e.path == "/me/sendMail"
        assert e.reason
    else:  # pragma: no cover
        pytest.fail("expected MailboxMutationBlockedError")
