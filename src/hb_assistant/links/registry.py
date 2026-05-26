"""SourceLinkRegistry: the provenance gate for all persisted objects.

Per 07: "generated outputs cannot persist without source links".
All high-level persist_* methods here create at least a self-link (or explicit links)
using types from resources/source-link-types.json before writing child rows.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.normalize.attachment import Attachment
from hb_assistant.normalize.calendar_event import CalendarEvent
from hb_assistant.normalize.drive_item import DriveItem
from hb_assistant.normalize.email import Email
from hb_assistant.store.repositories import Store

# Hardcoded from resources/source-link-types.json (no runtime dep on docs/)
ALLOWED_LINK_TYPES: set[str] = {
    "mentions",
    "attaches",
    "references",
    "derived_from",
    "follow_up_to",
    "waiting_on",
    "prepares_for",
    "same_conversation",
    "same_project",
    "same_file",
    "written_to_note",
    "parsed_from",
    "semantic_match",
}


class SourceLinkRegistry:
    """High-level API for persisting normalize models with mandatory source linking."""

    def __init__(self, store: Optional[Store] = None):
        self.store = store or Store()

    def _require_valid_link_type(self, link_type: str) -> None:
        if link_type not in ALLOWED_LINK_TYPES:
            raise ValueError(f"Invalid link_type '{link_type}'. Allowed: {sorted(ALLOWED_LINK_TYPES)}")

    def _ensure_link(
        self,
        from_id: int,
        to_id: int | None = None,
        link_type: str = "derived_from",
        confidence: float | None = 1.0,
    ) -> int:
        """Create a link (self-link if to_id None)."""
        self._require_valid_link_type(link_type)
        target = to_id if to_id is not None else from_id
        return self.store.create_source_link(
            from_source_record_id=from_id,
            to_source_record_id=target,
            link_type=link_type,
            confidence=confidence,
        )

    # --- Persist methods (enforce links + populate source_* on models) ---

    def persist_email(self, email: Email, source_key: str | None = None, initial_link_type: str = "derived_from") -> int:
        sid = self.store.persist_email(email, source_key=source_key)
        self._ensure_link(sid, link_type=initial_link_type)
        # Record any pre-existing links the model carried (from Phase 4 or classification)
        for link in getattr(email, "source_links", []) or []:
            lt = link.get("type") or link.get("link_type")
            if lt and lt in ALLOWED_LINK_TYPES:
                self.store.create_source_link(
                    from_source_record_id=sid,
                    to_source_record_id=link.get("target_source_record_id") or sid,
                    link_type=lt,
                    confidence=link.get("confidence"),
                )
        email.source_links = self.store.get_links_for_source(sid)
        return sid

    def persist_calendar_event(self, event: CalendarEvent, source_key: str | None = None, initial_link_type: str = "derived_from") -> int:
        sid = self.store.persist_calendar_event(event, source_key=source_key)
        self._ensure_link(sid, link_type=initial_link_type)
        for link in getattr(event, "source_links", []) or []:
            lt = link.get("type") or link.get("link_type")
            if lt and lt in ALLOWED_LINK_TYPES:
                self.store.create_source_link(
                    from_source_record_id=sid,
                    to_source_record_id=link.get("target_source_record_id") or sid,
                    link_type=lt,
                    confidence=link.get("confidence"),
                )
        event.source_links = self.store.get_links_for_source(sid)
        return sid

    def persist_attachment(self, att: Attachment, parent_source_record_id: int, source_key: str | None = None) -> int:
        sid = self.store.persist_attachment(att, parent_source_record_id=parent_source_record_id, source_key=source_key)
        # Always link attachment to its parent
        self._ensure_link(sid, to_id=parent_source_record_id, link_type="attaches")
        att.source_links = self.store.get_links_for_source(sid)
        return sid

    def persist_drive_item(self, item: DriveItem, source_key: str | None = None, initial_link_type: str = "derived_from") -> int:
        sid = self.store.persist_drive_item(item, source_key=source_key)
        self._ensure_link(sid, link_type=initial_link_type)
        item.source_links = self.store.get_links_for_source(sid)
        return sid

    # Low-level link creation for later phases (classification, extraction, obsidian writes)
    def link_sources(self, from_id: int, to_id: int, link_type: str, confidence: float | None = None) -> int:
        self._require_valid_link_type(link_type)
        return self.store.create_source_link(
            from_source_record_id=from_id,
            to_source_record_id=to_id,
            link_type=link_type,
            confidence=confidence,
        )

    def link_action(
        self,
        action_item_id: int,
        from_source_record_id: Optional[int] = None,
        to_source_record_id: Optional[int] = None,
        link_type: str = "parsed_from",
        confidence: Optional[float] = None,
    ) -> int:
        """Action-aware source link helper (supports action_item_id in create_source_link).

        Idempotent via guard using existing get_links_for_source (ensures links exactly once).
        Keeps high-level provenance gate.
        """
        self._require_valid_link_type(link_type)
        # Guard for exactly-once: reuse get_links_for_source (no new store helpers)
        src_id = from_source_record_id or to_source_record_id
        if src_id is not None:
            for l in self.store.get_links_for_source(src_id):
                if l.get("action_item_id") == action_item_id and l.get("link_type") == link_type:
                    return int(l.get("id", 0))
        return self.store.create_source_link(
            from_source_record_id=from_source_record_id,
            to_source_record_id=to_source_record_id,
            action_item_id=action_item_id,
            link_type=link_type,
            confidence=confidence,
        )

    def get_links(self, source_record_id: int) -> list[dict[str, Any]]:
        return self.store.get_links_for_source(source_record_id)

    # Convenience for run ledger (used by CLI)
    def record_run(self, **kwargs: Any) -> int:
        return self.store.record_assistant_run(**kwargs)

    def finish_run(self, run_id: int, status: str = "completed") -> None:
        self.store.finish_assistant_run(run_id, status)
