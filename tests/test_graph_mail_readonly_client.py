"""Phase 06 Prompt 04 — read-only Graph mail client.

Proves the client only ever issues guarded GETs with the metadata-only $select
sets, exposes no mutation method, and that a mutation path is refused before any
HTTP call reaches the underlying client.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest

from hb_assistant.graph.mail_endpoint_guard import MailboxMutationBlockedError
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient


class FakeHttp:
    """Records calls; stands in for GraphHttpClient (GET surface only)."""

    def __init__(self) -> None:
        self.get_calls: list[tuple[str, Optional[dict[str, Any]]]] = []
        self.pages_calls: list[tuple[str, Optional[dict[str, Any]], Optional[int]]] = []

    def get(self, path: str, *, params: Optional[dict[str, Any]] = None, scopes: Optional[list[str]] = None) -> dict[str, Any]:
        self.get_calls.append((path, params))
        return {"id": "X", "userPrincipalName": "u@example.com"}

    def get_all_pages(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        scopes: Optional[list[str]] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ):
        self.pages_calls.append((path, params, max_items))
        yield {"id": "item1"}


def _client() -> tuple[ReadOnlyMailClient, FakeHttp]:
    http = FakeHttp()
    return ReadOnlyMailClient(http), http  # type: ignore[arg-type]


def test_get_me_issues_guarded_get() -> None:
    client, http = _client()
    me = client.get_me()
    assert me["id"] == "X"
    assert http.get_calls[0][0] == "/me"


def test_list_mail_folders_uses_top_and_paths() -> None:
    client, http = _client()
    client.list_mail_folders(top=1, max_items=1)
    path, params, max_items = http.pages_calls[0]
    assert path == "/me/mailFolders"
    assert params["$top"] == 1
    assert max_items == 1


def test_list_messages_folder_scoped_metadata_only() -> None:
    client, http = _client()
    client.list_messages(folder_id="AAMkFolder", top=10, received_after="2026-05-01T00:00:00Z")
    path, params, _ = http.pages_calls[0]
    assert path == "/me/mailFolders/AAMkFolder/messages"
    fields = params["$select"].split(",")
    assert "body" not in fields  # full body never selected (bodyPreview is fine)
    assert "bodyPreview" in fields
    assert params["$filter"] == "receivedDateTime ge 2026-05-01T00:00:00Z"
    assert "desc" in params["$orderby"]


def test_list_messages_mailbox_wide_when_no_folder() -> None:
    client, http = _client()
    client.list_messages(top=5)
    assert http.pages_calls[0][0] == "/me/messages"


def test_get_message_metadata_excludes_body() -> None:
    client, http = _client()
    client.get_message_metadata("AAMkMsg")
    path, params = http.get_calls[0]
    assert path == "/me/messages/AAMkMsg"
    assert "body" not in params["$select"].split(",")


def test_list_attachment_metadata_excludes_content_bytes() -> None:
    client, http = _client()
    client.list_attachment_metadata("AAMkMsg")
    path, params, _ = http.pages_calls[0]
    assert path == "/me/messages/AAMkMsg/attachments"
    assert "contentBytes" not in params["$select"]


def test_top_is_clamped_to_valid_range() -> None:
    client, http = _client()
    client.list_mail_folders(top=99999)
    assert http.pages_calls[0][1]["$top"] == 1000
    client.list_messages(top=0)
    assert http.pages_calls[1][1]["$top"] == 1


def test_client_exposes_no_mutation_method() -> None:
    forbidden_fragments = (
        "send", "draft", "forward", "reply", "move", "copy", "delete",
        "mark", "categorize", "flag", "create", "update", "download",
    )
    public = [name for name in dir(ReadOnlyMailClient) if not name.startswith("_")]
    leaks = [
        name for name in public
        if any(frag in name.lower() for frag in forbidden_fragments)
    ]
    assert not leaks, f"read-only client exposes mutation-like methods: {leaks}"


def test_guarded_request_refuses_mutation_before_http() -> None:
    client, http = _client()
    # Reach the guarded primitive directly with a forbidden path: it must raise
    # before the underlying http client is ever touched.
    with pytest.raises(MailboxMutationBlockedError):
        client._guarded_get("/me/sendMail")
    assert http.get_calls == []
    assert http.pages_calls == []
