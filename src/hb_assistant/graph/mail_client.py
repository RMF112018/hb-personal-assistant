"""MailClient: inbound (5d) / sent (7d) metadata + bounded body retrieval.

Per 06_Graph_Integration_Specification + Addendum Prompt 05:
- Exact $select for minimal fields
- Redacted subject/sender/recipients/bodyPreview
- Body retrieval staged/bounded (never log full body)
- New: get_message_body_for_inspection (in-memory only, for BodyInspector fallback)
- Source links populated for later registry
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.normalize.email import Email

from .http_client import GraphHttpClient


class MailClient:
    def __init__(self, http_client: GraphHttpClient, cfg=None):
        self.client = http_client
        self.cfg = cfg or load_config()
        self.pp = PathPolicy(self.cfg)

    def _inbound_window(self) -> str:
        days = self.cfg.mail.inbound_lookback_days
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return f"receivedDateTime ge {since}"

    def _sent_window(self) -> str:
        days = self.cfg.mail.sent_lookback_days
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return f"sentDateTime ge {since}"

    def list_inbound(self, top: int = 25) -> List[Email]:
        filter_q = self._inbound_window()
        select = "id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,hasAttachments,webLink"
        url = f"/me/mailFolders/inbox/messages?$filter={filter_q}&$select={select}&$top={top}"
        max_items = min(top, self.cfg.mail.max_items_per_run)
        emails = []
        for msg in self.client.get_all_pages(
            url,
            max_pages=self.cfg.graph.max_pages_per_call,
            max_items=max_items,
        ):
            e = Email.from_graph_message(msg, folder="inbox")
            emails.append(e)
        return emails

    def list_sent(self, top: int = 25) -> List[Email]:
        filter_q = self._sent_window()
        select = "id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,sentDateTime,bodyPreview,hasAttachments,webLink"
        url = f"/me/mailFolders/sentItems/messages?$filter={filter_q}&$select={select}&$top={top}"
        max_items = min(top, self.cfg.mail.max_items_per_run)
        emails = []
        for msg in self.client.get_all_pages(
            url,
            max_pages=self.cfg.graph.max_pages_per_call,
            max_items=max_items,
        ):
            e = Email.from_graph_message(msg, folder="sent")
            emails.append(e)
        return emails

    def get_message(self, message_id: str, include_body: bool = False) -> Optional[Email]:
        select = "id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,bodyPreview,hasAttachments,webLink"
        if include_body and self.cfg.mail.persist_full_body:  # guarded, default false
            select += ",body"
        url = f"/me/messages/{message_id}?$select={select}"
        try:
            msg = self.client.get(url)
            return Email.from_graph_message(msg)
        except Exception:
            return None

    def get_message_body_for_inspection(self, message_id: str, max_chars: int = 8000) -> str:
        """Fetch bounded body content **in memory only** for classification/inspector use.

        - Never writes raw body to DB, logs, evidence, or cache.
        - Truncates after safe extraction.
        - Intended for BodyInspector + EmailClassifier fallback path (Addendum Prompt 05).
        - Caller is responsible for redaction before any persistence or logging of results.
        - Returns empty string on any failure (never raises into classification).
        """
        url = f"/me/messages/{message_id}?$select=id,body"
        try:
            msg = self.client.get(url)
            body = msg.get("body") or {}
            content = body.get("content") or ""
            # Truncate early; inspector will further clean/strip
            if len(content) > max_chars:
                content = content[:max_chars] + "..."
            return content
        except Exception:
            return ""
