"""Phase 10A raw-content-capable email query endpoints.

These provide the backend "local API" surface for email (threads, messages)
with support for include_raw / raw_mode parameters, resolved against the
raw_content policy (EndpointsConfig + default_endpoint_behavior).

When effective raw is not allowed (policy metadata_only, param exclude,
source not enabled, or allow_include_raw_param=false), callers receive
the standard redacted metadata shapes (from email_thread_summaries /
email_messages) with no raw bodies or participant plaintext leaked.

When effective, a "raw_content" sub-dict (or inlined fields for message)
is attached containing the persisted plaintext from email_message_raw_content
/ email_thread_raw_context.

All operations are read-only. No Graph calls here (raw was captured at
index time).
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from hb_assistant.construction.second_brain.local_ai import load_raw_content_policy
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

RawMode = Literal["include", "metadata_only"]


def _load_policy_endpoints():
    try:
        rc = load_raw_content_policy()
        rcs = rc.raw_content
        ep = getattr(rcs, "endpoints", None)
        if ep is None:
            # Defaults per policy model
            class _Ep:
                allow_include_raw_param = True
                default_raw_mode: RawMode = "include"

            ep = _Ep()
        return rcs, ep
    except Exception:
        # Fail closed
        class _Rcs:
            enabled = False
            mode = "disabled"
            default_endpoint_behavior: RawMode = "metadata_only"
            starting_sources = type("ss", (), {"email": False, "calendar": False})()

        class _Ep:
            allow_include_raw_param = True
            default_raw_mode: RawMode = "include"

        return _Rcs(), _Ep()


def _source_email_allowed(rcs: Any) -> bool:
    if not getattr(rcs, "enabled", False):
        return False
    mode = getattr(rcs, "mode", None)
    if mode not in ("email_calendar", "all_supported", "all_supported_plus_downstream"):
        return False
    ss = getattr(rcs, "starting_sources", None)
    return bool(ss and getattr(ss, "email", False))


def _resolve_include_raw(
    *,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
) -> bool:
    """Compute effective raw inclusion for this call.

    Rules (defense in depth, fail-closed):
    - Policy must be email_calendar (or broader) with email starting source.
    - If endpoints.allow_include_raw_param is False, ignore caller hints and
      use policy default_endpoint_behavior.
    - Explicit raw_mode wins, then explicit include_raw, then policy default.
    """
    rcs, ep = _load_policy_endpoints()
    if not _source_email_allowed(rcs):
        return False
    allow_param = bool(getattr(ep, "allow_include_raw_param", True))
    policy_default_is_raw = (
        getattr(rcs, "default_endpoint_behavior", "include_raw") == "include_raw"
    )

    if raw_mode is not None:
        if not allow_param:
            return policy_default_is_raw
        return raw_mode == "include"

    if include_raw is not None:
        if not allow_param:
            return policy_default_is_raw
        return bool(include_raw)

    return policy_default_is_raw


def list_email_threads(
    *,
    project_key: Optional[str] = None,
    limit: int = 1000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """List email thread summaries (redacted metadata base).

    When effective raw inclusion is resolved true, each thread that has a
    matching email_thread_raw_context will carry a "raw_content" key with
    the thread_subject, counts, and the list of per-message plaintext
    (subject, body_text/html, participants) captured at ingest time.

    When raw is not included, the shape is exactly the store's thread
    summary (metadata/redacted only) plus a marker _raw_content_included=False.
    """
    s = store or ConstructionStore()
    effective = _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode)
    threads = s.list_email_thread_summaries(project_key=project_key, limit=limit)
    if not effective:
        for t in threads:
            t["_raw_content_included"] = False
        return threads

    # Build lookup by thread_ref (which is conversationId or fallback msg id from indexer)
    raw_threads = s.list_email_thread_raw_context(project_key=project_key, limit=limit)
    raw_by_ref: dict[str, dict[str, Any]] = {}
    for rt in raw_threads:
        ref = rt.get("thread_ref")
        if ref:
            raw_by_ref[ref] = rt
        # also index by conversation_id_hash if present for robustness
        ch = rt.get("conversation_id_hash")
        if ch:
            raw_by_ref[ch] = rt

    for t in threads:
        t["_raw_content_included"] = False
        tk = t.get("thread_key") or t.get("conversation_id")
        raw = None
        if tk and tk in raw_by_ref:
            raw = raw_by_ref[tk]
        else:
            # fallback: try conversation hash if the summary carries one
            ch = t.get("conversation_id_hash")
            if ch and ch in raw_by_ref:
                raw = raw_by_ref[ch]
        if raw:
            t["raw_content"] = {
                "thread_subject": raw.get("thread_subject"),
                "message_count": raw.get("message_count"),
                "participant_count": raw.get("participant_count"),
                "messages": raw.get("messages") or [],
                "source_refs": raw.get("source_refs") or [],
            }
            t["_raw_content_included"] = True
    return threads


def list_email_messages(
    *,
    project_number_detected: Optional[str] = None,
    review_required: Optional[bool] = None,
    thread_key: Optional[str] = None,
    limit: int = 1000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """List email messages (redacted metadata base from email_messages).

    When effective raw, each message that has a persisted raw row will
    include a "raw_content" sub-dict with subject, body_text, body_html,
    from_*, recipients, sent/received, attachment meta (plaintext).
    """
    s = store or ConstructionStore()
    effective = _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode)
    msgs = s.list_email_messages(
        project_number_detected=project_number_detected,
        review_required=review_required,
        thread_key=thread_key,
        limit=limit,
    )
    if not effective:
        for m in msgs:
            m["_raw_content_included"] = False
        return msgs

    for m in msgs:
        m["_raw_content_included"] = False
        mid = m.get("message_id")
        if not mid:
            continue
        try:
            mhash = hash_value(mid)
        except Exception:
            continue
        raw = s.get_email_message_raw_content(message_id_hash=mhash)
        if raw:
            m["raw_content"] = {
                "subject": raw.get("subject"),
                "body_preview": raw.get("body_preview"),
                "body_text": raw.get("body_text"),
                "body_html": raw.get("body_html"),
                "from_name": raw.get("from_name"),
                "from_address": raw.get("from_address"),
                "to_recipients": raw.get("to_recipients") or [],
                "cc_recipients": raw.get("cc_recipients") or [],
                "bcc_recipients": raw.get("bcc_recipients") or [],
                "sent_at_utc": raw.get("sent_at_utc"),
                "received_at_utc": raw.get("received_at_utc"),
                "has_attachments": bool(raw.get("has_attachments")),
                "attachment_metadata": raw.get("attachment_metadata") or [],
            }
            m["_raw_content_included"] = True
    return msgs


def get_email_message(
    *,
    message_id: str,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> Optional[dict[str, Any]]:
    """Get a single email message (metadata base).

    Supports the same raw inclusion controls. When raw included and a raw
    row exists for the (hashed) message_id, attaches "raw_content".
    """
    if not message_id:
        return None
    s = store or ConstructionStore()
    effective = _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode)
    meta = s.get_email_message(message_id=message_id)
    if not meta:
        return None
    meta = dict(meta)  # copy
    meta["_raw_content_included"] = False
    if not effective:
        return meta
    try:
        mhash = hash_value(message_id)
        raw = s.get_email_message_raw_content(message_id_hash=mhash)
        if raw:
            meta["raw_content"] = {
                "subject": raw.get("subject"),
                "body_preview": raw.get("body_preview"),
                "body_text": raw.get("body_text"),
                "body_html": raw.get("body_html"),
                "from_name": raw.get("from_name"),
                "from_address": raw.get("from_address"),
                "to_recipients": raw.get("to_recipients") or [],
                "cc_recipients": raw.get("cc_recipients") or [],
                "bcc_recipients": raw.get("bcc_recipients") or [],
                "sent_at_utc": raw.get("sent_at_utc"),
                "received_at_utc": raw.get("received_at_utc"),
                "has_attachments": bool(raw.get("has_attachments")),
                "attachment_metadata": raw.get("attachment_metadata") or [],
            }
            meta["_raw_content_included"] = True
    except Exception:
        pass
    return meta


def list_email_thread_raw_context(
    *,
    project_key: Optional[str] = None,
    limit: int = 1000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """Direct access to persisted raw thread contexts (when effective).

    Respects policy + params; returns [] when raw not included for this call.
    Useful for targeted raw packet consumers.
    """
    if not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return []
    s = store or ConstructionStore()
    return s.list_email_thread_raw_context(project_key=project_key, limit=limit)


def get_email_thread_raw_context(
    *,
    thread_ref: str,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> Optional[dict[str, Any]]:
    """Direct access to a single raw thread context (when effective)."""
    if not thread_ref or not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return None
    s = store or ConstructionStore()
    return s.get_email_thread_raw_context(thread_ref=thread_ref)


def list_email_message_raw_content(
    *,
    project_key: Optional[str] = None,
    limit: int = 1000,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> list[dict[str, Any]]:
    """Direct access to persisted raw message rows (when effective)."""
    if not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return []
    s = store or ConstructionStore()
    return s.list_email_message_raw_content(project_key=project_key, limit=limit)


def get_email_message_raw_content(
    *,
    message_id_hash: str,
    include_raw: Optional[bool] = None,
    raw_mode: Optional[RawMode] = None,
    store: Optional[ConstructionStore] = None,
) -> Optional[dict[str, Any]]:
    """Direct access to a single raw message row by its stored hash (when effective)."""
    if not message_id_hash or not _resolve_include_raw(include_raw=include_raw, raw_mode=raw_mode):
        return None
    s = store or ConstructionStore()
    return s.get_email_message_raw_content(message_id_hash=message_id_hash)
