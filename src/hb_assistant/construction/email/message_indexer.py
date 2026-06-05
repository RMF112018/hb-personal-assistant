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

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.email.attachment_analyzer import (
    analyze_attachment,
    classify_text_sensitivity,
    detect_drive_links,
)
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


def compute_thread_key(
    conversation_id: Optional[str],
    internet_message_id: Optional[str],
    subject: Optional[str],
    domains: set[str],
) -> str:
    """Deterministic thread key: conversation_id, else a hash of the
    internet message id, else the normalized subject + participant domains."""
    if conversation_id:
        return conversation_id
    if internet_message_id:
        return hash_value(internet_message_id) or internet_message_id
    normalized_subject = (subject or "").strip().lower()
    basis = normalized_subject + "|" + ",".join(sorted(d for d in domains if d))
    return hash_value(basis) or basis


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


def normalize_message(
    msg: dict[str, Any],
    owner_hash: Optional[str],
    source_id: str,
    folder_id: str,
    role: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize a raw Graph message into redacted `upsert_email_message` kwargs +
    recipient rows. Shared by the indexer and the project-discovery persist path."""
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
        recipients.append(_recipient_row(message_id, "from", sender_addr, owner_hash))
    for arr, role_name in _RECIPIENT_FIELDS:
        for entry in msg.get(arr) or []:
            addr = _address(entry)
            if not addr:
                continue
            domains.add(_domain(addr) or "")
            recipients.append(_recipient_row(message_id, role_name, addr, owner_hash))

    thread_key = compute_thread_key(conversation_id, internet_message_id, subject, domains)

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


class IndexedFolder(BaseModel):
    """Per-folder index counts (metadata only)."""

    source_id: str
    folder_role: str
    run_id: str
    messages_seen: int
    messages_indexed: int
    recipients_indexed: int
    attachments_indexed: int
    attachments_with_link_hint: int = 0
    sensitive_attachments: int = 0
    source_link_candidates: int = 0
    review_items_created: int = 0
    bodies_encrypted: int = 0
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
    attachments_with_link_hint: int = 0
    sensitive_attachments: int = 0
    source_link_candidates: int = 0
    review_items_created: int = 0
    bodies_encrypted: int = 0
    # Prompt 08A encrypted-body capture telemetry (no plaintext).
    include_encrypted_body: bool = False
    body_capture_enabled: bool = False
    bodies_eligible: int = 0
    max_full_body_fetch_per_run: int = 0
    plaintext_persisted: bool = False
    vault_blob_written: bool = False

    model_config = {"extra": "forbid"}


class EmailMessageIndexer:
    """Bounded, read-only message metadata indexer."""

    def __init__(self, mail_client: ReadOnlyMailClient, store: ConstructionStore) -> None:
        self._mail = mail_client
        self._store = store
        self._body_budget = 0  # per-run encrypted-body fetch budget (Prompt 08A)

    def index(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        dry_run: bool = False,
        max_messages_per_folder: int = _DEFAULT_MAX_MESSAGES_PER_FOLDER,
        include_encrypted_body: bool = False,
    ) -> IndexResult:
        policy = load_email_intelligence_active_policy()
        lookback = self._clamp_lookback(lookback_days or policy.default_lookback_days)
        max_per_folder = max(1, int(max_messages_per_folder))

        # Prompt 08A: encrypted full-body capture is enabled only when the active
        # policy allows it AND the caller passes the explicit flag. Bounded by a
        # per-run budget; never a full-mailbox backfill.
        body_capture_enabled = bool(include_encrypted_body and policy.full_body_storage_allowed)
        self._body_budget = policy.max_full_body_fetch_per_run if body_capture_enabled else 0

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
                    body_capture=body_capture_enabled,
                )
            )

        totals = {
            "messages_seen": sum(f.messages_seen for f in folder_results),
            "messages_indexed": sum(f.messages_indexed for f in folder_results),
            "recipients_indexed": sum(f.recipients_indexed for f in folder_results),
            "attachments_indexed": sum(f.attachments_indexed for f in folder_results),
            "attachments_with_link_hint": sum(f.attachments_with_link_hint for f in folder_results),
            "sensitive_attachments": sum(f.sensitive_attachments for f in folder_results),
            "source_link_candidates": sum(f.source_link_candidates for f in folder_results),
            "review_items_created": sum(f.review_items_created for f in folder_results),
            "bodies_encrypted": sum(f.bodies_encrypted for f in folder_results),
        }

        # Dry-run eligibility: how many bodies WOULD be captured (no fetch, no blob).
        bodies_eligible = (
            min(totals["messages_seen"], policy.max_full_body_fetch_per_run)
            if (dry_run and body_capture_enabled)
            else 0
        )

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
            include_encrypted_body=include_encrypted_body,
            body_capture_enabled=body_capture_enabled,
            bodies_eligible=bodies_eligible,
            max_full_body_fetch_per_run=policy.max_full_body_fetch_per_run,
            plaintext_persisted=False,
            vault_blob_written=bool((not dry_run) and totals["bodies_encrypted"] > 0),
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
        body_capture: bool = False,
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
        link_hints = 0
        sensitive = 0
        candidates = 0
        review_items = 0
        bodies_encrypted = 0
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
                att_counts = self._index_attachments(msg, project_key)
                attachments_indexed += att_counts["attachments"]
                link_hints += att_counts["links"]
                sensitive += att_counts["sensitive"]
                candidates += att_counts["candidates"]
                review_items += att_counts["review_items"]
                body_counts = self._index_body_links(msg, project_key)
                candidates += body_counts["candidates"]
                review_items += body_counts["review_items"]
                if body_capture and self._body_budget > 0 and self._capture_body(msg):
                    bodies_encrypted += 1
                    self._body_budget -= 1
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
                relationship_candidates_created=candidates,
                review_items_created=review_items,
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
            attachments_with_link_hint=link_hints,
            sensitive_attachments=sensitive,
            source_link_candidates=candidates,
            review_items_created=review_items,
            bodies_encrypted=bodies_encrypted,
            status=status,
        )

    def _capture_body(self, msg: dict[str, Any]) -> bool:
        """Fetch a message body (read-only), encrypt it via the text vault, store
        only the ref + hash/length/metadata, and discard the plaintext.

        Returns True if a body was encrypted and a vault ref persisted. The
        plaintext is never returned, logged, or stored in SQLite/Obsidian/evidence.
        """
        message_id = msg.get("id")
        if not message_id:
            return False
        full = self._mail.get_message_body(message_id)
        body = full.get("body") or {}
        content = body.get("content")
        if not content:
            return False
        content_type = body.get("contentType")
        body_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        body_length = len(content)
        category, _level = classify_text_sensitivity(content)
        review_required = category is not None

        from hb_assistant.security.text_vault import encrypt_text

        ref = encrypt_text(content)
        content = None  # discard plaintext immediately after encryption
        if not ref:
            return False
        self._store.upsert_email_body_vault_ref(
            message_id=message_id,
            internet_message_id=full.get("internetMessageId"),
            conversation_id=full.get("conversationId"),
            body_content_type=content_type,
            body_hash=body_hash,
            body_length=body_length,
            encrypted_full_body_ref=ref,
            extraction_policy="encrypted_text_vault",
            review_required=review_required,
            sensitivity_classification=category,
        )
        return True

    def _index_attachments(self, msg: dict[str, Any], project_key: Optional[str]) -> dict[str, int]:
        counts = {"attachments": 0, "links": 0, "sensitive": 0, "candidates": 0, "review_items": 0}
        if not msg.get("hasAttachments"):
            return counts
        message_id = msg.get("id")
        if not message_id:
            return counts
        for att in self._mail.list_attachment_metadata(message_id):
            att_id = att.get("id")
            analysis = analyze_attachment(
                att.get("name"), att.get("contentType"), bool(att.get("isInline"))
            )
            self._store.upsert_email_message_attachment(
                attachment_key=f"{message_id}:{att_id}",
                message_id=message_id,
                attachment_id=att_id,
                name_redacted=analysis.name_redacted,
                name_hash=analysis.name_hash,
                content_type=att.get("contentType"),
                size_bytes=att.get("size"),
                is_inline=bool(att.get("isInline")),
                sharepoint_or_onedrive_link_detected=analysis.link_detected,
                sensitivity_hint=analysis.sensitivity_hint,
                review_required=analysis.review_required,
                metadata_only=True,
                content_downloaded=False,
            )
            counts["attachments"] += 1
            if analysis.link_detected:
                counts["links"] += 1
            if analysis.source_link_candidate and analysis.name_hash:
                self._store.upsert_email_relationship_candidate(
                    candidate_id=f"{message_id}:{analysis.name_hash}:attachment_filename",
                    message_id=message_id,
                    candidate_type=f"{analysis.candidate_target_system}_drive_item",
                    match_signal="attachment_filename",
                    confidence=0.5,
                    project_key=project_key,
                    target_source_system=analysis.candidate_target_system,
                    target_table="construction_drive_items",
                    target_key=analysis.name_hash,
                    review_required=False,
                    evidence_redacted="attachment filename suggests a stored document",
                )
                counts["candidates"] += 1
            if analysis.review_required and analysis.sensitivity_hint:
                inserted = self._store.enqueue_email_review_item(
                    review_id=f"{message_id}:attachment:{analysis.name_hash}",
                    message_id=message_id,
                    category=analysis.sensitivity_hint,
                    sensitivity=analysis.sensitivity_level or "medium",
                    reason=f"sensitive attachment hint: {analysis.sensitivity_hint}",
                    suggested_action="manual_review",
                    confidence=0.7,
                    project_key=project_key,
                )
                counts["sensitive"] += 1
                if inserted:
                    counts["review_items"] += 1
        return counts

    def _index_body_links(self, msg: dict[str, Any], project_key: Optional[str]) -> dict[str, int]:
        counts = {"candidates": 0, "review_items": 0}
        message_id = msg.get("id")
        if not message_id:
            return counts
        evidence = detect_drive_links(msg.get("bodyPreview"))
        if not evidence:
            return counts
        target_system = "onedrive" if evidence.startswith("onedrive") else "sharepoint"
        self._store.upsert_email_relationship_candidate(
            candidate_id=f"{message_id}:body_link:{hash_value(evidence)}",
            message_id=message_id,
            candidate_type=f"{target_system}_drive_item",
            match_signal="sharepoint_link_in_body_preview",
            confidence=0.6,
            project_key=project_key,
            target_source_system=target_system,
            target_table="construction_drive_items",
            target_key=hash_value(evidence),
            review_required=True,
            evidence_redacted=f"drive link in body preview ({evidence.split(':', 1)[0]})",
        )
        counts["candidates"] += 1
        inserted = self._store.enqueue_email_review_item(
            review_id=f"{message_id}:body_link:{hash_value(evidence)}",
            message_id=message_id,
            category="privileged_or_confidential_markers",
            sensitivity="medium",
            reason="drive link detected in body preview (body-derived match)",
            suggested_action="manual_review",
            confidence=0.6,
            project_key=project_key,
        )
        if inserted:
            counts["review_items"] += 1
        return counts

    def _normalize(
        self,
        msg: dict[str, Any],
        owner_hash: Optional[str],
        source_id: str,
        folder_id: str,
        role: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return normalize_message(msg, owner_hash, source_id, folder_id, role)
