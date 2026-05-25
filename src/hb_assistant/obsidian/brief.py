"""DailyBriefGenerator: assembles redacted, source-linked Daily Brief content.

Consumes Phase 6/7 data (action_items, classified signals via source_links, redacted previews).
Produces markdown suitable for MarkerBoundedWriter (sections + frontmatter).
All output is redacted; no full bodies or secrets are ever included.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.retrieval import WorkstreamContext, WorkstreamContextBuilder
from hb_assistant.store.repositories import Store


class DailyBriefGenerator:
    """Generates the redacted Daily Brief content for a given date."""

    def __init__(self, store: Optional[Store] = None, registry: Optional[SourceLinkRegistry] = None):
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)

    def generate_for_date(
        self,
        target_date: date,
        context: Optional[WorkstreamContext] = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Return (inner_markdown_content, frontmatter_updates).
        Content is safe for direct insertion between HB-DAILY-BRIEF markers.
        """
        if context is None:
            context = WorkstreamContextBuilder(store=self.store).build_for_today(limit_per=4)

        # Fetch recent action_items (from extraction or prior signals)
        actions = self.store.get_recent_action_items(limit=15)
        calendar_items = self.store.list_upcoming_calendar_events(limit=8)
        file_queue = self.store.list_file_review_queue(limit=8)
        mention_items = self.store.list_recent_body_mentions(limit=8)

        # Build sections (redacted titles only)
        priority_actions = []
        waiting_on = []
        for a in actions:
            title = a.get("title") or "[redacted action]"
            conf = a.get("confidence") or 0.5
            line = f"- [ ] {title} (conf={conf:.2f})"
            if a.get("action_type") in ("waiting", "waiting_on"):
                waiting_on.append(line)
            else:
                priority_actions.append(line)

        # Add waiting-style signals from retrieval context.
        for hit in (context.retrieved or [])[:8]:
            excerpt = str(hit.get("excerpt", ""))
            if "waiting" in excerpt.lower():
                sid = hit.get("source_record_id")
                waiting_on.append(f"- [ ] [signal] {excerpt[:90]}{'...' if len(excerpt) > 90 else ''} (src={sid})")

        meeting_prep = []
        for ev in calendar_items:
            sid = ev.get("source_record_id")
            start = ev.get("start_datetime") or "unknown_start"
            meeting_prep.append(f"- Meeting source {sid} at {start}")

        file_review = []
        for f in file_queue:
            sid = f.get("source_record_id")
            name = f.get("name") or "[redacted file]"
            ds = f.get("download_status") or "unknown"
            ps = f.get("parse_status") or "unknown"
            file_review.append(f"- {name} (src={sid}, download={ds}, parse={ps})")

        signals_section = []
        for m in mention_items:
            sid = m.get("source_record_id")
            title = m.get("title_redacted") or "[redacted mention]"
            signals_section.append(f"- body_mention_detected: {title} (src={sid})")
        for hit in (context.retrieved or [])[:8]:
            excerpt = str(hit.get("excerpt", ""))
            sid = hit.get("source_record_id")
            signals_section.append(f"- retrieval hit (src={sid}): {excerpt[:100]}{'...' if len(excerpt) > 100 else ''}")

        source_map: dict[int, set[str]] = {}
        for hit in (context.retrieved or []):
            sid = hit.get("source_record_id")
            if not sid:
                continue
            source_map.setdefault(int(sid), set())
            for ln in hit.get("links", []) or []:
                lt = ln.get("link_type")
                if lt:
                    source_map[int(sid)].add(str(lt))
        for sid in [m.get("source_record_id") for m in mention_items] + [f.get("source_record_id") for f in file_queue] + [e.get("source_record_id") for e in calendar_items]:
            if sid:
                source_map.setdefault(int(sid), set())
        source_lines = []
        for sid in sorted(source_map.keys())[:20]:
            link_types = sorted(source_map[sid])
            source_lines.append(f"- src={sid} links={', '.join(link_types) if link_types else 'none'}")

        sections = [
            "## Priority Actions",
            "\n".join(priority_actions) if priority_actions else "_No high-confidence actions extracted today._",
            "",
            "## Waiting On",
            "\n".join(waiting_on) if waiting_on else "_Nothing explicitly waiting on others._",
            "",
            "## Meeting Prep & Follow-Ups",
            "\n".join(meeting_prep) if meeting_prep else "No meeting prep items found for the configured window.",
            "",
            "## File Review Queue",
            "\n".join(file_review) if file_review else "No current file review candidates found.",
            "",
            "## Project / Workstream Signals",
            "\n".join(signals_section) if signals_section else "_No current retrieval/body-mention signals._",
            "",
            "## Sources",
            "\n".join(source_lines) if source_lines else "_No source links available in current context._",
        ]

        inner = "\n".join(sections)

        fm_updates = {
            "type": "brief",
            "domain": "work",
            "status": "active",
            "updated": target_date.isoformat(),
            "last_reviewed": target_date.isoformat(),
            "source": {"kind": "graph-derived + extraction"},
        }

        return inner, fm_updates
