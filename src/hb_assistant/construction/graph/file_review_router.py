"""Phase 06 — sensitive-file review routing for SharePoint / OneDrive driveItems.

Routes construction-sensitive files (contracts, financials, claims, notices,
legal, HR/personnel, insurance/bonding, safety/incident, medical, disputes,
cost/schedule impact) and low-confidence project matches into the existing
``construction_review_queue`` (V3) so a controller triages them before any
extraction.

This is the **V5 driveItem** counterpart to :class:`ReviewQueueRouter`, which
reads the V2 ``construction_drive_item_inventory``. It reuses the same
deterministic :class:`ReviewPolicyEvaluator` (name/parent_path only — no content
body) and the idempotent ``ConstructionStore.enqueue_review_item`` (``INSERT OR
IGNORE`` on ``(source_key, item_id, rule_id)``), so re-running never duplicates
rows. Dry-run is the default; nothing is written unless ``dry_run=False``.

Read-only against Microsoft 365: this module touches SQLite + the rule set only;
it never calls Graph and never alters extraction eligibility. The hard
no-extraction guarantee for review-routed files is enforced by the V18
``construction_file_ingestion_decisions`` CHECK (``review_required = 0 OR
extraction_allowed = 0``); here we *verify* it by cross-checking every routed
item's V18 decision and reporting ``extraction_blocked_for_all_routed``.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.policy.evaluator import ReviewPolicyEvaluator
from hb_assistant.construction.policy.models import RuleMatch
from hb_assistant.construction.store import ConstructionStore

# A driveItem whose project match is this weak is routed for controller review
# even when no sensitivity rule fires.
_LOW_CONFIDENCE_STATUSES = frozenset({"low_confidence", "unmatched"})
_LOW_CONFIDENCE_RULE_ID = "low-confidence-project-match"


class FileReviewResult(BaseModel):
    """Per-source routing outcome (offline; report-only in dry-run)."""

    source_id: str
    mode: str  # dry_run | apply
    items_seen: int = 0
    matches_found: int = 0
    enqueued: int = 0
    skipped_already_open: int = 0
    low_confidence_routed: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    extraction_blocked_for_all_routed: bool = True
    matches: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class FileReviewRouter:
    """Route sensitive + low-confidence V5 driveItems into the review queue."""

    def __init__(self, store: ConstructionStore, evaluator: ReviewPolicyEvaluator) -> None:
        self._store = store
        self._evaluator = evaluator

    def route(
        self,
        *,
        source_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> list[FileReviewResult]:
        """Evaluate driveItems for one source (or every registry source).

        Returns one :class:`FileReviewResult` per source. With ``dry_run`` (the
        default) nothing is written — counts reflect what *would* be enqueued.
        """
        if source_id is not None:
            source_ids = [source_id]
        else:
            source_ids = [s["source_id"] for s in self._store.list_source_locations(limit=100000)]
        return [self._route_one(sid, dry_run=dry_run) for sid in source_ids]

    def _route_one(self, source_id: str, *, dry_run: bool) -> FileReviewResult:
        result = FileReviewResult(source_id=source_id, mode="dry_run" if dry_run else "apply")

        src = self._store.get_source_location(source_id)
        source_project_key = src.get("project_key") if src else None

        # V17 project-match info keyed by drive item (project_key + match_status).
        match_info = {
            m["drive_item_id"]: m
            for m in self._store.list_drive_item_project_matches(source_id=source_id, limit=100000)
        }

        routed_item_ids: set[str] = set()
        for item in self._store.list_drive_items(source_id=source_id, limit=100000):
            if not item.get("is_file") or item.get("deleted"):
                continue
            result.items_seen += 1
            drive_item_id = item["drive_item_id"]
            mi = match_info.get(drive_item_id, {})
            project_key = mi.get("project_key") or source_project_key

            item_dict = {
                "item_id": drive_item_id,
                "name": item.get("name"),
                "parent_path": item.get("parent_reference_path") or item.get("path"),
            }
            matches = self._evaluator.evaluate(
                source_key=source_id, project_key=project_key, item=item_dict
            )

            # Route low-confidence / unmatched project matches as a hint, even
            # when no sensitivity rule fired.
            if mi.get("match_status") in _LOW_CONFIDENCE_STATUSES:
                matches.append(self._low_confidence_match(item_dict, source_id, project_key))

            for match in matches:
                routed_item_ids.add(drive_item_id)
                result.matches_found += 1
                result.by_category[match.classification_label] = (
                    result.by_category.get(match.classification_label, 0) + 1
                )
                if match.rule_id == _LOW_CONFIDENCE_RULE_ID:
                    result.low_confidence_routed += 1
                if not dry_run:
                    inserted = self._store.enqueue_review_item(match)
                    if inserted:
                        result.enqueued += 1
                    else:
                        result.skipped_already_open += 1
                result.matches.append(
                    {
                        "item_id": match.item_id,
                        "rule_id": match.rule_id,
                        "classification_label": match.classification_label,
                        "sensitivity": match.sensitivity,
                        "name": match.name,
                        "parent_path": match.parent_path,
                    }
                )

        result.extraction_blocked_for_all_routed = self._verify_no_extraction(
            source_id, routed_item_ids
        )
        return result

    def _low_confidence_match(
        self, item_dict: dict[str, Any], source_id: str, project_key: Optional[str]
    ) -> RuleMatch:
        return RuleMatch(
            rule_id=_LOW_CONFIDENCE_RULE_ID,
            item_id=item_dict["item_id"],
            source_key=source_id,
            project_key=project_key,
            name=item_dict.get("name"),
            parent_path=item_dict.get("parent_path"),
            sensitivity="medium",
            classification_label="low_confidence_project_match",
            reason="project match is low-confidence or unmatched",
            suggested_action="controller_review",
            confidence=0.5,
        )

    def _verify_no_extraction(self, source_id: str, routed_item_ids: set[str]) -> bool:
        """True iff no routed item's V18 decision allows extraction.

        A missing decision means nothing has authorised extraction, which is
        also safe.
        """
        if not routed_item_ids:
            return True
        extraction_by_item = {
            d["drive_item_id"]: d["extraction_allowed"]
            for d in self._store.list_file_ingestion_decisions(source_id=source_id, limit=100000)
        }
        return all(not extraction_by_item.get(iid, False) for iid in routed_item_ids)
