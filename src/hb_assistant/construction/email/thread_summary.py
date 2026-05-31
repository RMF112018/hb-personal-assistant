"""Phase 07B Prompt 07 — Email thread summary materialization (local-only, redacted).

Aggregates already-indexed, project-matched email (grouped by ``thread_key``) into a
**metadata-only**, redacted thread summary and routes sensitive / high-impact threads to
the existing human-review queue. Read-only with respect to Microsoft 365 — this is
Graph-free; it reads local SQLite rows (`email_messages`, `email_project_matches`, and,
under the controlled body-context policy, the local encrypted-body vault) and writes only
local SQLite rows behind an explicit apply (``dry_run=False``).

Guardrails (enforced here and by schema CHECKs):
- The persisted ``summary_redacted`` is metadata only — message/participant counts, the
  time window, and detected review-category ids. No subject text, no preview text, no
  email address, no body, no prompt, and no model response is ever persisted.
- Body context (when both the ``use_encrypted_body_context`` flag and the policy allow it)
  is decrypted IN MEMORY only to improve review-category recall, then immediately
  ``del``-eted. The decrypted plaintext is never logged, returned, or persisted.
- Sensitive / high-impact threads route to ``email_review_queue`` (human review remains
  mandatory). A per-run audit receipt records counts only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.calendar.policy import (
    EmailThreadSummaryPolicy,
    load_email_thread_summary_policy,
)
from hb_assistant.construction.email.review_categories import (
    classify_review_categories,
    get_review_category,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.security.text_vault import decrypt_text

# The persisted summary_policy label for these metadata-only summaries.
SUMMARY_POLICY_LABEL = "metadata_only"
_MAX_SAMPLES = 10


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ThreadSummarySample(BaseModel):
    """Evidence-safe preview of one thread summary (redacted; never raw content)."""

    thread_ref: str
    message_count: int
    participant_count: int
    review_required: bool
    review_categories: list[str]
    summary_char_count: int
    encrypted_body_context_used: bool

    model_config = {"extra": "forbid"}


class ThreadSummaryReport(BaseModel):
    """Outcome of a materialization run (counts + redacted samples; no raw content)."""

    project_key: Optional[str] = None
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    policy_version: str
    summary_mode: str
    use_encrypted_body_context: bool
    threads_considered: int
    threads_summarized: int
    review_required_count: int
    encrypted_body_context_used_count: int
    plaintext_persisted: bool = False
    run_id: Optional[str] = None
    samples: list[ThreadSummarySample]
    disclaimer: str = (
        "thread summaries are metadata only; no subject, preview, body, prompt, or model "
        "response is persisted; sensitive/high-impact threads route to human review"
    )

    model_config = {"extra": "forbid"}


class EmailThreadSummaryMaterializer:
    """Materialize redacted, metadata-only email thread summaries (local-only)."""

    def __init__(
        self,
        store: ConstructionStore,
        *,
        policy: Optional[EmailThreadSummaryPolicy] = None,
    ) -> None:
        self._store = store
        self._policy = policy or load_email_thread_summary_policy()

    def materialize(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        use_encrypted_body_context: bool = False,
        dry_run: bool = True,
        max_threads: int = 200,
    ) -> ThreadSummaryReport:
        defaults = self._policy.defaults
        lookback = max(1, min(int(lookback_days or 30), 366))
        received_after = (
            (_utc_now() - timedelta(days=lookback)).replace(microsecond=0).isoformat()
        )
        # Body context is gated by BOTH the caller flag AND the policy opt-in.
        body_context_allowed = bool(
            use_encrypted_body_context and defaults.allow_encrypted_body_context
        )

        thread_keys = self._discover_thread_keys(project_key, max_threads)

        run_id = f"{uuid.uuid4()}:thread-summary"
        considered = 0
        summarized = 0
        review_count = 0
        body_used_count = 0
        samples: list[ThreadSummarySample] = []
        persisted = False

        if not dry_run:
            self._store.insert_email_thread_summary_materialization_run(
                run_id=run_id, mode="apply", project_key=project_key, status="running"
            )

        try:
            for thread_key in thread_keys:
                msgs = self._store.list_email_messages(thread_key=thread_key, limit=1000)
                if not msgs:
                    continue
                received = sorted(
                    m.get("received_datetime") for m in msgs if m.get("received_datetime")
                )
                # Window filter: include the thread if its newest message is in range.
                if received and received[-1] < received_after:
                    continue
                considered += 1

                first_dt = received[0] if received else None
                last_dt = received[-1] if received else None
                conversation_id = next(
                    (m.get("conversation_id") for m in msgs if m.get("conversation_id")), None
                )
                participant_hashes = sorted(
                    {m["sender_address_hash"] for m in msgs if m.get("sender_address_hash")}
                )

                # Review-category detection over bounded redacted subjects/previews
                # (in-memory only; the text below is never persisted).
                redacted_text = " | ".join(
                    part
                    for m in msgs
                    for part in (
                        m.get("subject_redacted") or "",
                        m.get("body_preview_excerpt_redacted") or "",
                    )
                    if part
                )
                categories = set(classify_review_categories(redacted_text))

                # Controlled body context: decrypt IN MEMORY only, then discard.
                body_used = False
                if body_context_allowed:
                    for m in msgs:
                        vault = self._store.get_email_body_vault_ref(m["message_id"])
                        if vault is None:
                            continue
                        plaintext = decrypt_text(vault.get("encrypted_full_body_ref"))
                        if plaintext:
                            body_used = True
                            for cat in classify_review_categories(plaintext):
                                categories.add(cat)
                            del plaintext
                    if body_used:
                        body_used_count += 1

                review_required = bool(categories) and (
                    defaults.route_sensitive_to_review or defaults.route_high_impact_to_review
                )
                if review_required:
                    review_count += 1

                summary_redacted = self._build_summary(
                    message_count=len(msgs),
                    first_dt=first_dt,
                    last_dt=last_dt,
                    participant_count=len(participant_hashes),
                    categories=sorted(categories),
                    cap=defaults.max_summary_chars,
                )

                if not dry_run:
                    self._store.upsert_email_thread_summary(
                        thread_key=thread_key,
                        project_key=project_key,
                        conversation_id=conversation_id,
                        message_count=len(msgs),
                        first_message_datetime=first_dt,
                        last_message_datetime=last_dt,
                        participants_hash=participant_hashes,
                        summary_redacted=summary_redacted,
                        summary_policy=SUMMARY_POLICY_LABEL,
                        review_required=review_required,
                        model_used=None,
                        model_output_validated=False,
                    )
                    summarized += 1
                    if review_required:
                        self._enqueue_thread_review(
                            thread_key=thread_key,
                            msgs=msgs,
                            categories=sorted(categories),
                            project_key=project_key,
                        )

                if len(samples) < _MAX_SAMPLES:
                    samples.append(
                        ThreadSummarySample(
                            thread_ref=hash_value(thread_key) or thread_key,
                            message_count=len(msgs),
                            participant_count=len(participant_hashes),
                            review_required=review_required,
                            review_categories=sorted(categories),
                            summary_char_count=len(summary_redacted),
                            encrypted_body_context_used=body_used,
                        )
                    )

            if not dry_run:
                self._store.complete_email_thread_summary_materialization_run(
                    run_id=run_id,
                    status="completed",
                    threads_considered=considered,
                    threads_summarized=summarized,
                    review_required_count=review_count,
                )
                persisted = True
        except Exception as exc:  # pragma: no cover - defensive run finalization
            if not dry_run:
                self._store.complete_email_thread_summary_materialization_run(
                    run_id=run_id,
                    status="error",
                    threads_considered=considered,
                    threads_summarized=summarized,
                    review_required_count=review_count,
                    error_redacted=type(exc).__name__,
                )
            raise

        return ThreadSummaryReport(
            project_key=project_key,
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=persisted,
            policy_version=self._policy.version,
            summary_mode=defaults.summary_mode,
            use_encrypted_body_context=body_context_allowed,
            threads_considered=considered,
            threads_summarized=summarized,
            review_required_count=review_count,
            encrypted_body_context_used_count=body_used_count,
            run_id=run_id if not dry_run else None,
            samples=samples,
        )

    def _discover_thread_keys(
        self, project_key: Optional[str], max_threads: int
    ) -> list[str]:
        """Distinct thread_keys for the project's matched messages (bounded, ordered)."""
        thread_keys: list[str] = []
        seen: set[str] = set()
        for match in self._store.list_email_project_matches(
            project_key=project_key, limit=2000
        ):
            msg = self._store.get_email_message(match["message_id"])
            if msg is None:
                continue
            thread_key = msg.get("thread_key")
            if thread_key and thread_key not in seen:
                seen.add(thread_key)
                thread_keys.append(thread_key)
                if len(thread_keys) >= max_threads:
                    break
        return thread_keys

    def _enqueue_thread_review(
        self,
        *,
        thread_key: str,
        msgs: list[dict[str, Any]],
        categories: list[str],
        project_key: Optional[str],
    ) -> None:
        latest = max(msgs, key=lambda m: m.get("received_datetime") or "")
        category = categories[0]
        meta = get_review_category(category)
        sensitivity = meta.sensitivity_level if meta else "medium"
        action = meta.recommended_review_action if meta else "manual_review"
        reason = "thread_sensitive_categories:" + ",".join(categories)
        review_id = hash_value(f"{thread_key}|{category}|{reason}") or f"{thread_key}:{category}"
        self._store.enqueue_email_review_item(
            review_id=review_id,
            message_id=latest["message_id"],
            category=category,
            sensitivity=sensitivity,
            reason=reason,
            suggested_action=action,
            confidence=1.0,
            project_key=project_key,
        )

    @staticmethod
    def _build_summary(
        *,
        message_count: int,
        first_dt: Optional[str],
        last_dt: Optional[str],
        participant_count: int,
        categories: list[str],
        cap: int,
    ) -> str:
        """Metadata-only summary string — counts, window, and review-category ids only."""
        out = (
            f"thread: {message_count} message(s), {participant_count} participant(s); "
            f"window {first_dt or '?'} -> {last_dt or '?'}"
        )
        if categories:
            out += f"; review_categories: {', '.join(categories)}"
        if len(out) > cap:
            out = out[: max(1, cap - 1)] + "…"
        return out
