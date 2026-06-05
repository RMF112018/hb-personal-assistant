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
from hb_assistant.store.errors import StoreReadinessError
from hb_assistant.store.repositories import Store


class ActionService:
    """Minimal service for actions CLI foundation."""

    def __init__(
        self, store: Optional[Store] = None, registry: Optional[SourceLinkRegistry] = None
    ) -> None:
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(store=self.store)
        self._db_path = getattr(self.store, "_db_path", None)

    def extract(self, dry_run: bool = True) -> list[ActionItem]:
        """Return candidate ActionItems (always preview).

        Per Phase 15 Prompt 02 policy:
        - Dry-run never mutates action_items, source_links, or any business objects.
        - record_run / finish_run (ledger) and evidence writes are intentionally performed
          even in dry-run for auditability; these are the only side effects.
        - If not dry_run: persist new ones + source_links using discovered low-level + ledger.
        Dry-run is provably safe for business state (no DB writes to action_items or source_links).
        """
        run_id = self.registry.record_run(
            run_type="actions:extract",
            target_date=datetime.now(timezone.utc).date().isoformat(),
            trigger="cli",
            dry_run=dry_run,
        )
        try:
            # P04: pass signals=None to trigger rich bounded signal load/aggregate inside extractor (when store provided).
            # P03 upsert_action_item + link_action + dry_run guard + ledger + registry.finish_run all preserved exactly.
            cands = extract_candidates(signals=None, store=self.store)

            if not dry_run:
                for c in cands:
                    ai_id = self.store.upsert_action_item(
                        stable_key=c.stable_key,
                        action_type=c.action_type,
                        title=c.title,
                        due_date=c.due_date,
                        confidence=c.confidence,
                        status=c.status,
                    )
                    # Provenance via registry (mandatory source link for every persisted action)
                    src_id = None
                    if c.sources:
                        src_id = c.sources[0].get("source_id")
                    self.registry.link_action(
                        action_item_id=ai_id,
                        from_source_record_id=src_id,
                        to_source_record_id=src_id,
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
