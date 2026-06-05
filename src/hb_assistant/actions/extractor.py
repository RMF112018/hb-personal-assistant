"""Deterministic action candidate extractor (no LLM, no Graph, local only).

Uses discovered classification signals (bobby_mention, possible_action_or_waiting via heuristics)
and/or store signals. stable_key deterministic + source-linked.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from hb_assistant.actions.models import ActionItem
from hb_assistant.classification.aliases import DEFAULT_BOBBY_ALIASES, AliasResolver
from hb_assistant.store.repositories import Store


def _load_bounded_signals(store: Optional[Store]) -> list[dict[str, Any]]:
    """Load/aggregate the 5 bounded redacted signals from existing store helpers.

    Pre-process into the signal dict format extract_candidates understands.
    Reads only; dry-run safe. Redacted/bounded excerpts and titles only.
    """
    if store is None:
        return []
    signals: list[dict[str, Any]] = []
    try:
        # 1. High-conf body mentions (bobby_mention from emails)
        for m in store.list_recent_body_mentions(limit=20):
            signals.append(
                {
                    "classifications": ["bobby_mention"],
                    "message_source_record_id": m.get("source_record_id") or m.get("id"),
                    "title": m.get("title_redacted") or m.get("web_link") or "Mentioned item",
                    "excerpt": None,
                }
            )
    except Exception:
        pass
    try:
        # 2. Parser outputs (excerpts as signals; proxy for retrieval/parser content)
        for p in store.list_recent_parser_outputs(limit=30):
            signals.append(
                {
                    "classifications": ["parser_content"],
                    "message_source_record_id": p.get("file_source_record_id") or p.get("id"),
                    "title": p.get("parser_name") or "Parsed content",
                    "excerpt": p.get("text_excerpt"),
                    "source_record_id": p.get("file_source_record_id"),
                }
            )
    except Exception:
        pass
    try:
        # 3. Upcoming calendar events (meeting_prep signals)
        for c in store.list_upcoming_calendar_events(limit=10):
            signals.append(
                {
                    "classifications": ["calendar_event"],
                    "message_source_record_id": c.get("source_record_id") or c.get("id"),
                    "title": "Meeting prep / calendar item",
                    "excerpt": c.get("web_link"),
                }
            )
    except Exception:
        pass
    try:
        # 4. File review / pending queue (file_review signals)
        for f in store.list_file_review_queue(limit=10) or []:
            signals.append(
                {
                    "classifications": ["file_review"],
                    "message_source_record_id": f.get("source_record_id") or f.get("id"),
                    "title": f.get("name") or "File review",
                    "excerpt": None,
                }
            )
    except Exception:
        pass
    try:
        for p in store.list_pending_ingest_candidates(limit=10):
            signals.append(
                {
                    "classifications": ["pending_file"],
                    "message_source_record_id": p.get("source_record_id") or p.get("id"),
                    "title": p.get("name") or "Pending file",
                    "excerpt": None,
                }
            )
    except Exception:
        pass
    return signals


def _map_signal_to_action_type(
    excerpt: str, classifications: list[str] | str, has_bobby_mention: bool
) -> tuple[str, float]:
    """Extend phrase-to-action_type mapping (reuse detector heuristics + aliases exactly + 06 spec).

    Full set: respond/review/approve/follow_up/waiting_on/meeting_prep/file_review/monitor.
    Conf: 0.9 explicit bobby+phrase, 0.75 heuristic, lower for weak -> monitor.
    Deterministic, redacted input only.
    """
    text = (excerpt or "").lower()
    class_str = (
        " ".join(classifications).lower()
        if isinstance(classifications, (list, tuple))
        else str(classifications).lower()
    )

    # Bobby boost (reuse AliasResolver exactly as in detector)
    if has_bobby_mention or AliasResolver(DEFAULT_BOBBY_ALIASES).matches(text):
        if any(p in text for p in ["please review", "review by", "needs review"]):
            return "review", 0.9
        if any(p in text for p in ["approve", "approval", "sign off"]):
            return "approve", 0.9
        if any(p in text for p in ["waiting on", "waiting for", "follow up"]):
            return "waiting_on", 0.9
        if any(p in text for p in ["prep for", "meeting prep", "prepare for"]):
            return "meeting_prep", 0.9
        if any(p in text for p in ["file review", "review file"]):
            return "file_review", 0.9
        return "respond", 0.9

    # Heuristic mapping (extend detector phrases)
    detector_phrases = [
        ("review", ["please review", "review by", "needs review", "take a look"]),
        ("approve", ["approve", "approval", "sign off", "ok to"]),
        ("waiting_on", ["waiting on", "waiting for", "follow up", "let me know"]),
        ("meeting_prep", ["prep for", "meeting prep", "prepare for", "agenda"]),
        ("file_review", ["file review", "review file", "look at the file"]),
        ("monitor", ["monitor", "keep an eye", "watch for"]),
    ]
    for a_type, phrases in detector_phrases:
        if any(p in text for p in phrases) or a_type in class_str:
            return a_type, 0.75

    # Weak / monitor fallback
    if "monitor" in class_str or len(text) < 20:
        return "monitor", 0.45
    return "task", 0.65


def extract_candidates(
    signals: list[dict[str, Any]] | None = None,
    store: Optional[Store] = None,
    limit: int = 50,
) -> list[ActionItem]:
    """Generate deduped ActionItem candidates.

    - signals: list of classification-like dicts (or None to load rich bounded signals from store).
    - When signals is falsy and store is provided: load from body mentions, parser outputs,
      calendar events, file review/pending, retrieval hits (pre-processed to existing format).
    - Falls back to recent store action_items for seeding/dedup.
    - action_type: full set per 06 spec (review/approve/waiting_on/meeting_prep/file_review/monitor/etc.).
    - No full content ever; all excerpts/titles redacted and bounded from sources.
    """
    cands: list[ActionItem] = []
    seen: set[str] = set()
    sigs = signals or []

    # P04: load rich bounded signals if none provided (the core integration)
    if not sigs and store is not None:
        sigs = _load_bounded_signals(store)

    for sig in sigs:
        src_id = (
            sig.get("message_source_record_id")
            or sig.get("source_id")
            or sig.get("source_record_id")
            or 0
        )
        raw_title = (
            sig.get("title")
            or sig.get("excerpt")
            or sig.get("match_excerpt_redacted")
            or "Follow up on item"
        )
        title = str(raw_title)[:200].strip()
        classifications = sig.get("classifications", [])
        excerpt = sig.get("excerpt") or sig.get("match_excerpt_redacted") or ""
        has_bobby = (
            "bobby_mention" in str(classifications).lower() or "bobby_mention" in str(sig).lower()
        )

        a_type, conf = _map_signal_to_action_type(excerpt, classifications, has_bobby)

        h = hashlib.sha256(title[:100].encode("utf-8")).hexdigest()[:12]
        sk = f"action:{a_type}:{src_id}:{h}"
        if sk in seen:
            continue
        seen.add(sk)

        # Source link type per signal type (reuse P02/P03 patterns)
        link_type = "mentions" if "bobby_mention" in str(classifications).lower() else "parsed_from"
        if "calendar" in str(classifications).lower():
            link_type = "prepares_for"
        sources = [{"source_id": src_id, "link_type": link_type}]

        cands.append(
            ActionItem(
                stable_key=sk,
                title=title,
                action_type=a_type,
                confidence=conf,
                sources=sources,
            )
        )
        if len(cands) >= limit:
            break

    # Fallback / dedup seed from existing store items (discovered get_recent_action_items)
    if store is not None and len(cands) < limit:
        try:
            recent = store.get_recent_action_items(limit=limit)
            for r in recent:
                sk = r.get("stable_key")
                if sk and sk not in seen:
                    seen.add(sk)
                    cands.append(
                        ActionItem(
                            stable_key=sk,
                            title=r.get("title", "Existing item"),
                            action_type=r.get("action_type", "task"),
                            due_date=r.get("due_date"),
                            confidence=r.get("confidence", 0.5),
                            status=r.get("status", "open"),
                            sources=[{"source_id": r.get("id"), "link_type": "existing"}],
                        )
                    )
        except Exception:
            pass  # never fail extraction on store read issues for dry-run safety

    return cands[:limit]
