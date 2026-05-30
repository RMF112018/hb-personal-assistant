"""Phase 06 — bounded message metadata indexing (read-only, metadata-only).

Discovers messages in the included folders (Inbox / Sent Items / Archive) within a
bounded lookback window, normalizes each to a **redacted, metadata-only** record,
and persists `email_messages` + `email_message_recipients` + `email_message_attachments`,
with `email_crawl_runs` + `email_processing_receipts` as the run audit trail.

Read-only: only `get_me` / `list_messages` / `list_attachment_metadata` (guarded
GETs with a body-free `$select`) are issued — never the full body, never attachment
content. The only writes are local SQLite. `dry_run` previews without writing message
rows. Re-running is idempotent (messages/recipients/attachments are upserted by stable
keys); crawl-run + receipt rows accumulate as an audit log.

Project matching (email_project_matches / project_number_detected / confidence) is a
later prompt; here `--project` is a validated crawl-run label only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.email.folder_discovery import EmailFolderDiscovery
from hb_assistant.construction.policy import (
    EmailIntelligenceActivePolicy,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient
from hb_assistant.normalize.redaction import (
    hash_value,
    redact_subject,
    truncate_preview,
)

_SYNC_MODE = "bounded_lookback"
_DEFAULT_MAX_MESSAGES_PER_FOLDER = 200
_PAGE_SIZE = 50
_RECIPIENT_FIELDS = (("toRecipients", "to"), ("ccRecipients", "cc"), ("bccRecipients", "bcc"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _address(entry: dict[str, Any]) -> Optional[str]:
    return (entry.get("emailAddress") or {}).get("address")


def _domain(addr: Optional[str]) -> Optional[str]:
    if not addr or "@" not in addr:
        return None
    return addr.split("@", 1)[1].lower()


class IndexedFolder(BaseModel):
    """Per-folder index counts (metadata only)."""

    source_id: str
    folder_role: str
    run_id: str
    messages_seen: int
    messages_indexed: int
    recipients_indexed: int
    attachments_indexed: int
    status: str

    model_config = {"extra": "forbid"}


class IndexResult(BaseModel):
    """Outcome of an index run (counts + run ids; no subjects/addresses)."""

    op_id: str
    project_key: Optional[str] = None
    project_resolved: bool = False
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    folders: list[IndexedFolder]
    folders_crawled: int
    messages_seen: int
    messages_indexed: int
    recipients_indexed: int
    attachments_indexed: int

    model_config = {"extra": "forbid"}


class EmailMessageIndexer:
    """Bounded, read-only message metadata indexer."""

    def __init__(self, mail_client: ReadOnlyMailClient, store: ConstructionStore) -> None:
        self._mail = mail_client
        self._store = store

    def index(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        dry_run: bool = False,
        max_messages_per_folder: int = _DEFAULT_MAX_MESSAGES_PER_FOLDER,
    ) -> IndexResult:
        policy = load_email_intelligence_active_policy()
        lookback = self._clamp_lookback(lookback_days or policy.default_lookback_days)
        max_per_folder = max(1, int(max_messages_per_folder))

        project_resolved = False
        if project_key:
            project_resolved = self._store.get_project_identity(project_key) is not None

        included = self._included_folders(policy, dry_run)

        me = self._mail.get_me()
        owner_hash = hash_value(me.get("userPrincipalName") or me.get("mail"))

        received_after = _iso((_utc_now() - timedelta(days=lookback)).replace(microsecond=0))
        op_id = str(uuid.uuid4())

        folder_results: list[IndexedFolder] = []
        for folder in included:
            folder_results.append(
                self._index_folder(
                    folder=folder,
                    op_id=op_id,
                    owner_hash=owner_hash,
                    received_after=received_after,
                    lookback=lookback,
                    max_per_folder=max_per_folder,
                    project_key=project_key,
                    dry_run=dry_run,
                )
            )

        totals = {
            "messages_seen": sum(f.messages_seen for f in folder_results),
            "messages_indexed": sum(f.messages_indexed for f in folder_results),
            "recipients_indexed": sum(f.recipients_indexed for f in folder_results),
            "attachments_indexed": sum(f.attachments_indexed for f in folder_results),
        }

        if not dry_run:
            self._store.insert_email_processing_receipt(
                receipt_id=f"{op_id}:index",
                operation="index_metadata",
                status="ok",
                run_id=op_id,
                project_key=project_key,
                detail={"lookback_days": lookback, "received_after": received_after, **totals},
            )

        return IndexResult(
            op_id=op_id,
            project_key=project_key,
            project_resolved=project_resolved,
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=not dry_run,
            folders=folder_results,
            folders_crawled=len(folder_results),
            **totals,
        )

    # --- internals ----------------------------------------------------------

    @staticmethod
    def _clamp_lookback(days: int) -> int:
        return max(1, min(int(days), 366))

    def _included_folders(
        self, policy: EmailIntelligenceActivePolicy, dry_run: bool
    ) -> list[dict[str, Any]]:
        included = self._store.list_email_source_locations(include_in_sync=True)
        if not included and not dry_run:
            EmailFolderDiscovery(self._mail, self._store).discover(policy=policy, dry_run=False)
            included = self._store.list_email_source_locations(include_in_sync=True)
        return [f for f in included if f.get("folder_id")]

    def _index_folder(
        self,
        *,
        folder: dict[str, Any],
        op_id: str,
        owner_hash: Optional[str],
        received_after: str,
        lookback: int,
        max_per_folder: int,
        project_key: Optional[str],
        dry_run: bool,
    ) -> IndexedFolder:
        source_id = folder["source_id"]
        folder_id = folder["folder_id"]
        role = folder.get("folder_role", "included")
        run_id = f"{op_id}:{role}"

        if not dry_run:
            self._store.insert_email_crawl_run(
                run_id=run_id,
                source_id=source_id,
                mode="index",
                lookback_days=lookback,
                project_key=project_key,
                dry_run=False,
            )

        messages_seen = 0
        messages_indexed = 0
        recipients_indexed = 0
        attachments_indexed = 0
        status = "completed"
        error_redacted: Optional[str] = None

        try:
            messages = self._mail.list_messages(
                folder_id=folder_id,
                top=_PAGE_SIZE,
                received_after=received_after,
                max_items=max_per_folder,
            )
            for msg in messages:
                messages_seen += 1
                if dry_run:
                    continue
                fields, recipients = self._normalize(msg, owner_hash, source_id, folder_id, role)
                self._store.upsert_email_message(**fields)
                for r in recipients:
                    self._store.add_email_message_recipient(**r)
                recipients_indexed += len(recipients)
                attachments_indexed += self._index_attachments(msg)
                messages_indexed += 1
        except Exception as e:  # bounded, sanitized
            status = "failed"
            error_redacted = f"{type(e).__name__}: {str(e)[:120]}"

        if not dry_run:
            self._store.complete_email_crawl_run(
                run_id=run_id,
                status=status,
                messages_seen=messages_seen,
                messages_in_scope=messages_seen,
                messages_indexed=messages_indexed,
                error_redacted=error_redacted,
            )

        return IndexedFolder(
            source_id=source_id,
            folder_role=role,
            run_id=run_id,
            messages_seen=messages_seen,
            messages_indexed=messages_indexed,
            recipients_indexed=recipients_indexed,
            attachments_indexed=attachments_indexed,
            status=status,
        )

    def _index_attachments(self, msg: dict[str, Any]) -> int:
        if not msg.get("hasAttachments"):
            return 0
        message_id = msg.get("id")
        if not message_id:
            return 0
        count = 0
        for att in self._mail.list_attachment_metadata(message_id):
            att_id = att.get("id")
            self._store.upsert_email_message_attachment(
                attachment_key=f"{message_id}:{att_id}",
                message_id=message_id,
                attachment_id=att_id,
                name_hash=hash_value(att.get("name")),
                content_type=att.get("contentType"),
                size_bytes=att.get("size"),
                is_inline=bool(att.get("isInline")),
                metadata_only=True,
                content_downloaded=False,
            )
            count += 1
        return count

    def _normalize(
        self,
        msg: dict[str, Any],
        owner_hash: Optional[str],
        source_id: str,
        folder_id: str,
        role: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        message_id = msg.get("id")
        subject = msg.get("subject")
        conversation_id = msg.get("conversationId")
        internet_message_id = msg.get("internetMessageId")
        body_preview = msg.get("bodyPreview")

        sender_addr = _address(msg.get("from") or msg.get("sender") or {})
        to_list = msg.get("toRecipients") or []
        cc_list = msg.get("ccRecipients") or []
        bcc_list = msg.get("bccRecipients") or []

        recipients: list[dict[str, Any]] = []
        domains: set[str] = set()
        if sender_addr:
            domains.add(_domain(sender_addr) or "")
            recipients.append(
                self._recipient_row(message_id, "from", sender_addr, owner_hash)
            )
        for arr, role_name in _RECIPIENT_FIELDS:
            for entry in msg.get(arr) or []:
                addr = _address(entry)
                if not addr:
                    continue
                domains.add(_domain(addr) or "")
                recipients.append(
                    self._recipient_row(message_id, role_name, addr, owner_hash)
                )

        thread_key = self._thread_key(conversation_id, internet_message_id, subject, domains)

        fields = {
            "message_id": message_id,
            "thread_key": thread_key,
            "source_id": source_id,
            "internet_message_id": internet_message_id,
            "conversation_id": conversation_id,
            "folder_id": folder_id,
            "folder_display_name": role,
            "subject_redacted": redact_subject(subject),
            "subject_hash": hash_value(subject),
            "sender_address_hash": hash_value(sender_addr),
            "sender_domain": _domain(sender_addr),
            "to_recipient_count": len(to_list),
            "cc_recipient_count": len(cc_list),
            "bcc_recipient_count": len(bcc_list),
            "received_datetime": msg.get("receivedDateTime"),
            "sent_datetime": msg.get("sentDateTime"),
            "last_modified_datetime": msg.get("lastModifiedDateTime"),
            "has_attachments": bool(msg.get("hasAttachments")),
            "importance": msg.get("importance"),
            "categories_metadata": msg.get("categories") or None,
            "sensitivity_metadata": msg.get("sensitivity"),
            "web_link": msg.get("webLink"),
            "body_preview_hash": hash_value(body_preview),
            "body_preview_excerpt_redacted": truncate_preview(body_preview, 120),
            "extraction_policy": "metadata_only",
        }
        return fields, recipients

    @staticmethod
    def _recipient_row(
        message_id: Optional[str], role: str, addr: str, owner_hash: Optional[str]
    ) -> dict[str, Any]:
        addr_hash = hash_value(addr)
        return {
            "message_id": message_id,
            "recipient_role": role,
            "address_hash": addr_hash,
            "domain": _domain(addr),
            "is_bobby": bool(owner_hash and addr_hash == owner_hash),
        }

    @staticmethod
    def _thread_key(
        conversation_id: Optional[str],
        internet_message_id: Optional[str],
        subject: Optional[str],
        domains: set[str],
    ) -> str:
        if conversation_id:
            return conversation_id
        if internet_message_id:
            return hash_value(internet_message_id) or internet_message_id
        normalized_subject = (subject or "").strip().lower()
        basis = normalized_subject + "|" + ",".join(sorted(d for d in domains if d))
        return hash_value(basis) or basis
