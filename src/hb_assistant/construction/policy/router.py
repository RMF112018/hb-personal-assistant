"""Review-queue router: orchestrates evaluator + store.

Pulls inventory rows from :class:`ConstructionStore`, runs the deterministic
:class:`ReviewPolicyEvaluator`, and in apply mode persists each match to the
``construction_review_queue`` SQLite table. Idempotent on the
``(source_key, item_id, rule_id)`` UNIQUE constraint.

No external systems are touched — this is a SQLite-only operation.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import SourceRegistry
from hb_assistant.construction.store import ConstructionStore

from .evaluator import ReviewPolicyEvaluator
from .models import RuleMatch


class RouterResult(BaseModel):
    source_key: str
    project_key: Optional[str] = None
    items_seen: int = 0
    matches_found: int = 0
    enqueued: int = 0
    skipped_already_open: int = 0
    matches: list[RuleMatch] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ReviewQueueRouter:
    """Apply a :class:`ReviewPolicyEvaluator` across inventory for one or all sources."""

    def __init__(
        self,
        store: ConstructionStore,
        evaluator: ReviewPolicyEvaluator,
    ) -> None:
        self._store = store
        self._evaluator = evaluator

    def evaluate_source(
        self,
        *,
        source_key: str,
        project_key: str | None,
        apply: bool,
    ) -> RouterResult:
        items = self._store.list_inventory_for_source(source_key)
        result = RouterResult(source_key=source_key, project_key=project_key)
        result.items_seen = len(items)

        for item in items:
            for match in self._evaluator.evaluate(
                source_key=source_key, project_key=project_key, item=item,
            ):
                result.matches_found += 1
                result.matches.append(match)
                if apply:
                    inserted = self._store.enqueue_review_item(match)
                    if inserted:
                        result.enqueued += 1
                    else:
                        result.skipped_already_open += 1
        return result

    def evaluate_registry(
        self,
        *,
        registry: SourceRegistry,
        only_source_key: str | None = None,
        apply: bool,
    ) -> list[RouterResult]:
        targets = [
            s for s in registry.sources
            if only_source_key is None or s.source_key == only_source_key
        ]
        return [
            self.evaluate_source(
                source_key=s.source_key, project_key=s.project_key, apply=apply,
            )
            for s in targets
        ]
