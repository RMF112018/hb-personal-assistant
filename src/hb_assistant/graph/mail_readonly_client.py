"""Phase 06 — read-only Microsoft Graph mail client.

A thin GET-only wrapper over :class:`GraphHttpClient`. Every request is routed
through :func:`assert_mail_request_allowed` *before* any HTTP call, so a mailbox
mutation can never leave this process. Message and attachment listings use the
metadata-first ``$select`` sets from the Prompt 01 contract, which structurally
exclude the full message ``body`` and attachment ``contentBytes``.

This client exposes **only** read methods (identity, folders, message metadata,
attachment metadata). It intentionally has no mailbox-mutation method (no send,
draft, move, copy, delete, mark-read, categorize, or flag) and no attachment-
content download — read-only is enforced by both the absence of those methods and
the per-request guard.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.graph.http_client import GraphHttpClient
from hb_assistant.graph.mail_endpoint_guard import (
    MailEndpointContract,
    assert_mail_request_allowed,
    load_mail_endpoint_contract,
)

# Graph $top valid range is 1..1000; keep default conservative for bounded reads.
_DEFAULT_PAGE_SIZE = 25
_MAX_TOP = 1000


class ReadOnlyMailClient:
    """GET-only mail reader: folders, message metadata, attachment metadata."""

    def __init__(
        self,
        http_client: GraphHttpClient,
        *,
        contract: Optional[MailEndpointContract] = None,
    ) -> None:
        self._client = http_client
        self._contract = contract or load_mail_endpoint_contract()

    # --- guarded request primitives ----------------------------------------

    def _guarded_get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        assert_mail_request_allowed("GET", path, contract=self._contract)
        return self._client.get(path, params=params)

    def _guarded_pages(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        assert_mail_request_allowed("GET", path, contract=self._contract)
        return list(self._client.get_all_pages(path, params=params, max_items=max_items))

    # --- $select helpers ----------------------------------------------------

    def _message_select(self) -> str:
        return ",".join(self._contract.message_metadata_select)

    def _attachment_select(self) -> str:
        return ",".join(self._contract.attachment_metadata_select)

    def _body_select(self) -> str:
        return ",".join(self._contract.body_fetch_select)

    @staticmethod
    def _clamp_top(top: int) -> int:
        return max(1, min(int(top), _MAX_TOP))

    # --- read operations ----------------------------------------------------

    def get_me(self) -> dict[str, Any]:
        """Identity / mailbox-owner probe (``GET /me``)."""
        return self._guarded_get("/me", {"$select": "id,displayName,userPrincipalName,mail"})

    def list_mail_folders(self, *, top: int = _DEFAULT_PAGE_SIZE, max_items: Optional[int] = None) -> list[dict[str, Any]]:
        """List mail folders (``GET /me/mailFolders``), metadata only."""
        params = {
            "$top": self._clamp_top(top),
            "$select": "id,displayName,parentFolderId,childFolderCount,totalItemCount,unreadItemCount",
        }
        return self._guarded_pages("/me/mailFolders", params, max_items=max_items)

    def get_mail_folder(self, folder_id: str) -> dict[str, Any]:
        """Single folder metadata (``GET /me/mailFolders/{id}``)."""
        params = {"$select": "id,displayName,parentFolderId,childFolderCount,totalItemCount,unreadItemCount"}
        return self._guarded_get(f"/me/mailFolders/{folder_id}", params)

    def list_messages(
        self,
        *,
        folder_id: Optional[str] = None,
        top: int = _DEFAULT_PAGE_SIZE,
        received_after: Optional[str] = None,
        max_items: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """List message **metadata** (no body) for a folder, or mailbox-wide.

        Bounded by ``$top`` and an optional ``received_after`` ISO timestamp
        (``$filter`` on ``receivedDateTime``) — never a full-mailbox backfill.
        """
        params: dict[str, Any] = {
            "$top": self._clamp_top(top),
            "$select": self._message_select(),
            "$orderby": "receivedDateTime desc",
        }
        if received_after:
            params["$filter"] = f"receivedDateTime ge {received_after}"
        if folder_id:
            path = f"/me/mailFolders/{folder_id}/messages"
        else:
            path = "/me/messages"
        return self._guarded_pages(path, params, max_items=max_items)

    def get_message_metadata(self, message_id: str) -> dict[str, Any]:
        """Single message **metadata** (``GET /me/messages/{id}``); no body."""
        return self._guarded_get(f"/me/messages/{message_id}", {"$select": self._message_select()})

    def list_attachment_metadata(self, message_id: str) -> list[dict[str, Any]]:
        """Attachment **metadata** only (``$select`` excludes ``contentBytes``)."""
        params = {"$select": self._attachment_select()}
        return self._guarded_pages(f"/me/messages/{message_id}/attachments", params)

    def get_message_body(self, message_id: str) -> dict[str, Any]:
        """Single message **with body** (``GET /me/messages/{id}``), read-only.

        Used only by the Prompt 08A controlled encrypted-body capture path: the
        returned ``body`` (``{contentType, content}``) is encrypted immediately
        via the text vault and the plaintext discarded — it is never persisted to
        SQLite/Obsidian/evidence/logs. The path is allowlisted; only the
        ``$select`` differs from the body-free metadata path.
        """
        return self._guarded_get(f"/me/messages/{message_id}", {"$select": self._body_select()})
