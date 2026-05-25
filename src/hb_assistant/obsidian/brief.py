"""DailyBriefGenerator: assembles redacted, source-linked Daily Brief content.

Consumes Phase 6/7 data (action_items, classified signals via source_links, redacted previews).
Produces markdown suitable for MarkerBoundedWriter (sections + frontmatter).
All output is redacted; no full bodies or secrets are ever included.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.store.repositories import Store


class DailyBriefGenerator:
    """Generates the redacted Daily Brief content for a given date."""

    def __init__(self, store: Optional[Store] = None, registry: Optional[SourceLinkRegistry] = None):
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)

    def generate_for_date(self, target_date: date) -> tuple[str, dict[str, Any]]:
        """
        Return (inner_markdown_content, frontmatter_updates).
        Content is safe for direct insertion between HB-DAILY-BRIEF markers.
        """
        # Fetch recent action_items (from extraction or prior signals)
        actions = self.store.get_recent_action_items(limit=15)

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

        # For demo: also pull any high-signal classified items linked to recent sources (Phase 6)
        # In real runs the morning orchestrator would pass the relevant source_record_ids.
        signals_section = []
        # Placeholder: in a full run we would query recent emails with body_mention_detected or waiting signals
        # and turn them into "Follow-Ups" or "Project Signals".

        sections = [
            "## Priority Actions",
            "\n".join(priority_actions) if priority_actions else "_No high-confidence actions extracted today._",
            "",
            "## Waiting On",
            "\n".join(waiting_on) if waiting_on else "_Nothing explicitly waiting on others._",
            "",
            "## Meeting Prep & Follow-Ups",
            "_(Populated from calendar events + extraction in later runs.)_",
            "",
            "## File Review Queue",
            "_(Linked driveItem / attachment reviews will appear here after Phase 9.)_",
            "",
            "## Project / Workstream Signals",
            "_(Derived from Phase 6 bobby_mention + Phase 7 signals.)_",
            "",
            "## Sources",
            "All items are source-linked. See the corresponding Daily Note or AI Outputs companion for full provenance.",
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
