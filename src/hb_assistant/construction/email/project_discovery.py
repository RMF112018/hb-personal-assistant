"""Phase 06 — project-aware email discovery (read-only, in-memory matching).

Reads a bounded window of messages from the included folders (live, GET-only),
matches each in-memory against the pilot-project descriptors (subject/bodyPreview
are never persisted raw), and produces a discovery report. In dry-run (the
default) nothing is written. When committed, accepted matches persist:
`email_project_matches` (one row per signal) + the message's project fields on
`email_messages` (the message is upserted first so the FK row exists). Thread
continuation propagates an accepted project to other messages sharing a thread.

Mailbox stays read-only; the only writes are local SQLite. Re-running is
idempotent (matches upsert on UNIQUE(message_id, project_key, match_signal)).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.email.folder_discovery import EmailFolderDiscovery
from hb_assistant.construction.email.message_indexer import (
    compute_thread_key,
    normalize_message,
)
from hb_assistant.construction.email.project_matcher import (
    ACCEPT_THRESHOLD,
    MatchSignal,
    ProjectDescriptor,
    ProjectMatcher,
    load_pilot_project_descriptors,
    thread_continuation_signal,
)
from hb_assistant.construction.policy import (
    EmailIntelligenceActivePolicy,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.mail_readonly_client import ReadOnlyMailClient
from hb_assistant.normalize.redaction import hash_value

_PAGE_SIZE = 50
_DEFAULT_MAX_MESSAGES_PER_FOLDER = 200
_RECIPIENT_ARRAYS = ("toRecipients", "ccRecipients", "bccRecipients")


def _domain(addr: Optional[str]) -> Optional[str]:
    if not addr or "@" not in addr:
        return None
    return addr.split("@", 1)[1].lower()


def _msg_domains(msg: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    sender = ((msg.get("from") or msg.get("sender") or {}).get("emailAddress") or {}).get("address")
    if sender and _domain(sender):
        domains.append(_domain(sender) or "")
    for arr in _RECIPIENT_ARRAYS:
        for entry in msg.get(arr) or []:
            addr = (entry.get("emailAddress") or {}).get("address")
            d = _domain(addr)
            if d:
                domains.append(d)
    return domains


class ProjectMatchSummary(BaseModel):
    """Per-project aggregate (metadata only)."""

    project_key: str
    project_number: Optional[str] = None
    matched_messages: int
    review_required: int
    by_signal: dict[str, int]
    best_confidence: float

    model_config = {"extra": "forbid"}


class DiscoveryReport(BaseModel):
    """Discovery outcome — counts + signal histograms, no subjects/addresses."""

    op_id: str
    requested_project: Optional[str] = None
    pilot_projects: list[str]
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    folders: list[dict[str, Any]]
    messages_scanned: int
    matched_messages: int
    projects: list[ProjectMatchSummary]
    signal_counts: dict[str, int]
    query_strategy: dict[str, Any]
    guardrails: dict[str, bool]

    model_config = {"extra": "forbid"}


class ProjectEmailDiscovery:
    """Project-aware discovery over a bounded, read-only message window."""

    def __init__(self, mail_client: ReadOnlyMailClient, store: ConstructionStore) -> None:
        self._mail = mail_client
        self._store = store
        self._matcher = ProjectMatcher()

    def discover(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        dry_run: bool = True,
        max_messages_per_folder: int = _DEFAULT_MAX_MESSAGES_PER_FOLDER,
    ) -> DiscoveryReport:
        policy = load_email_intelligence_active_policy()
        lookback = max(1, min(int(lookback_days or policy.default_lookback_days), 366))
        max_per_folder = max(1, int(max_messages_per_folder))
        descriptors = load_pilot_project_descriptors(project_key)

        included = self._included_folders(policy, dry_run)
        owner_hash = hash_value(
            (self._mail.get_me().get("userPrincipalName") or self._mail.get_me().get("mail"))
        )
        received_after = (
            (datetime.now(timezone.utc) - timedelta(days=lookback)).replace(microsecond=0).isoformat()
        )
        op_id = str(uuid.uuid4())

        # message_id -> (raw msg, source_id, folder_id, role, thread_key, {project_key: [signals]})
        scanned: list[dict[str, Any]] = []
        folder_counts: list[dict[str, Any]] = []
        for folder in included:
            msgs = self._mail.list_messages(
                folder_id=folder["folder_id"],
                top=_PAGE_SIZE,
                received_after=received_after,
                max_items=max_per_folder,
            )
            folder_counts.append(
                {"source_id": folder["source_id"], "folder_role": folder.get("folder_role"), "messages_seen": len(msgs)}
            )
            for msg in msgs:
                scanned.append({"msg": msg, "folder": folder})

        # Primary matching pass.
        matches: dict[str, dict[str, list[MatchSignal]]] = {}  # message_id -> project_key -> signals
        thread_index: dict[str, set[str]] = {}  # thread_key -> set(project_key) accepted
        records: dict[str, dict[str, Any]] = {}  # message_id -> record
        for entry in scanned:
            msg = entry["msg"]
            message_id = msg.get("id")
            if not message_id:
                continue
            domains = _msg_domains(msg)
            thread_key = compute_thread_key(
                msg.get("conversationId"), msg.get("internetMessageId"), msg.get("subject"), set(domains)
            )
            records[message_id] = {"msg": msg, "folder": entry["folder"], "thread_key": thread_key}
            for descriptor in descriptors:
                signals = self._matcher.match(
                    subject=msg.get("subject"),
                    body_preview=msg.get("bodyPreview"),
                    sender_domain=domains[0] if domains else None,
                    participant_domains=domains,
                    web_link=msg.get("webLink"),
                    descriptor=descriptor,
                )
                if not signals:
                    continue
                matches.setdefault(message_id, {})[descriptor.project_key] = signals
                if max(s.confidence for s in signals) >= ACCEPT_THRESHOLD:
                    thread_index.setdefault(thread_key, set()).add(descriptor.project_key)

        # Thread-continuation pass: messages in an accepted thread inherit the project.
        for message_id, record in records.items():
            accepted = thread_index.get(record["thread_key"], set())
            for pk in accepted:
                existing = matches.setdefault(message_id, {})
                if pk not in existing:
                    existing[pk] = [thread_continuation_signal()]

        # Persist + aggregate.
        per_project: dict[str, dict[str, Any]] = {
            d.project_key: {"descriptor": d, "matched": 0, "review": 0, "by_signal": {}, "best": 0.0}
            for d in descriptors
        }
        signal_counts: dict[str, int] = {}
        matched_messages = 0
        for message_id, by_project in matches.items():
            matched_messages += 1
            record = records[message_id]
            for pk, signals in by_project.items():
                best = max(s.confidence for s in signals)
                review = any(s.review_required for s in signals) or best < ACCEPT_THRESHOLD
                agg = per_project[pk]
                agg["matched"] += 1
                agg["review"] += 1 if review else 0
                agg["best"] = max(agg["best"], best)
                for s in signals:
                    agg["by_signal"][s.name] = agg["by_signal"].get(s.name, 0) + 1
                    signal_counts[s.name] = signal_counts.get(s.name, 0) + 1
                if not dry_run:
                    self._persist_match(message_id, pk, per_project[pk]["descriptor"], signals, best, review, owner_hash, record)

        if not dry_run:
            self._store.insert_email_processing_receipt(
                receipt_id=f"{op_id}:discover",
                operation="project_discovery",
                status="ok",
                run_id=op_id,
                project_key=project_key,
                detail={"messages_scanned": len(scanned), "matched_messages": matched_messages, "signal_counts": signal_counts},
            )

        projects = [
            ProjectMatchSummary(
                project_key=pk,
                project_number=agg["descriptor"].project_number,
                matched_messages=agg["matched"],
                review_required=agg["review"],
                by_signal=agg["by_signal"],
                best_confidence=round(agg["best"], 2),
            )
            for pk, agg in per_project.items()
        ]

        return DiscoveryReport(
            op_id=op_id,
            requested_project=project_key,
            pilot_projects=[d.project_key for d in descriptors],
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=not dry_run,
            folders=folder_counts,
            messages_scanned=len(scanned),
            matched_messages=matched_messages,
            projects=projects,
            signal_counts=signal_counts,
            query_strategy={
                "folders": [f["source_id"] for f in folder_counts],
                "lookback_days": lookback,
                "received_after": received_after,
                "max_messages_per_folder": max_per_folder,
                "filter": f"receivedDateTime ge {received_after}",
            },
            guardrails={
                "mailbox_read_only": True,
                "full_body_persisted": False,
                "attachment_content_retrieved": False,
                "subject_matched_in_memory_only": True,
            },
        )

    # --- internals ----------------------------------------------------------

    def _included_folders(
        self, policy: EmailIntelligenceActivePolicy, dry_run: bool
    ) -> list[dict[str, Any]]:
        included = self._store.list_email_source_locations(include_in_sync=True)
        if not included and not dry_run:
            EmailFolderDiscovery(self._mail, self._store).discover(policy=policy, dry_run=False)
            included = self._store.list_email_source_locations(include_in_sync=True)
        return [f for f in included if f.get("folder_id")]

    def _persist_match(
        self,
        message_id: str,
        project_key: str,
        descriptor: ProjectDescriptor,
        signals: list[MatchSignal],
        best: float,
        review: bool,
        owner_hash: Optional[str],
        record: dict[str, Any],
    ) -> None:
        # Ensure the email_messages FK row exists, carrying the project verdict.
        fields, recipients = normalize_message(
            record["msg"],
            owner_hash,
            record["folder"]["source_id"],
            record["folder"]["folder_id"],
            record["folder"].get("folder_role", "included"),
        )
        fields["project_number_detected"] = descriptor.project_number
        fields["project_match_confidence"] = round(best, 2)
        fields["body_mention_detected"] = any(
            s.name in ("hb_project_number_in_body_preview", "project_name_in_body_preview") for s in signals
        )
        fields["review_required"] = review
        self._store.upsert_email_message(**fields)
        for r in recipients:
            self._store.add_email_message_recipient(**r)
        for s in signals:
            self._store.upsert_email_project_match(
                match_id=f"{message_id}:{project_key}:{s.name}",
                message_id=message_id,
                match_signal=s.name,
                confidence=s.confidence,
                project_key=project_key,
                project_number=descriptor.project_number,
                project_name_normalized=descriptor.project_name_normalized,
                match_value_hash=s.match_value_hash,
                review_required=s.review_required,
                evidence_redacted=s.evidence_redacted,
            )
