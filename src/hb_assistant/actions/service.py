"""ActionService: orchestration for extract (dry-run safe preview + optional persist) and list.

Uses only discovered patterns: Store (get_recent_action_items, create_source_link, transaction),
SourceLinkRegistry (for ledger record/finish_run), extractor.
No full bodies, no mutation on dry_run, local deterministic only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from hb_assistant.actions.extractor import extract_candidates
from hb_assistant.actions.models import ActionItem
from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.store import get_connection, transaction
from hb_assistant.store.repositories import Store
from hb_assistant.store.errors import StoreReadinessError


class ActionService:
    """Minimal service for actions CLI foundation."""

    def __init__(self, store: Optional[Store] = None, registry: Optional[SourceLinkRegistry] = None) -> None:
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(store=self.store)
        self._db_path = getattr(self.store, "_db_path", None)

    def extract(self, dry_run: bool = True) -> list[ActionItem]:
        """Return candidate ActionItems (always preview).

        If not dry_run: persist new ones + source_links using discovered low-level + ledger.
        Dry-run is provably safe (no DB writes in that path).
        """
        run_id = self.registry.record_run(
            run_type="actions:extract",
            target_date=datetime.now(timezone.utc).date().isoformat(),
            trigger="cli",
            dry_run=dry_run,
        )
        try:
            # Deterministic candidates (signals empty for foundation; extractor falls back to store recent)
            cands = extract_candidates(signals=[], store=self.store)

            if not dry_run:
                for c in cands:
                    conn = get_connection(self._db_path)
                    with transaction(conn):
                        cur = conn.execute(
                            """
                            INSERT INTO action_items (stable_key, action_type, title, due_date, confidence, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(stable_key) DO NOTHING
                            RETURNING id
                            """,
                            (c.stable_key, c.action_type, c.title, c.due_date, c.confidence, c.status),
                        )
                        row = cur.fetchone()
                        if row:
                            ai_id = int(row[0])
                            # Provenance link using discovered create_source_link (action_item_id support)
                            src_id = None
                            if c.sources:
                                src_id = c.sources[0].get("source_id")
                            self.store.create_source_link(
                                from_source_record_id=src_id,
                                to_source_record_id=src_id,
                                action_item_id=ai_id,
                                link_type="parsed_from",
                                confidence=c.confidence,
                            )

            self.registry.finish_run(run_id)
            return cands
        except StoreReadinessError:
            self.registry.finish_run(run_id, status="failed")
            raise
        except Exception:
            self.registry.finish_run(run_id, status="failed")
            raise

    def list_recent(self, limit: int = 20) -> list[ActionItem]:
        """Recent open actions (redacted excerpts only, via discovered store helper)."""
        rows = self.store.get_recent_action_items(limit=limit)
        items: list[ActionItem] = []
        for r in rows:
            items.append(
                ActionItem(
                    stable_key=r.get("stable_key", ""),
                    title=r.get("title", ""),
                    action_type=r.get("action_type", "task"),
                    due_date=r.get("due_date"),
                    confidence=r.get("confidence", 0.5),
                    status=r.get("status", "open"),
                    sources=[{"id": r.get("id"), "link_type": "stored"}],
                )
            )
        return items
