"""Phase 06A — file ingestion eligibility evaluation (pre-download/extraction gate).

Assigns each indexed file an ingestion disposition so sensitive, large, or
low-confidence files never auto-extract. Pure SQLite + policy + source registry —
**no Graph calls, no token, no writeback, no content read**. Reuses the existing
review-rule engine (`ReviewPolicyEvaluator`) for sensitive-category detection, the
per-source `FolderPolicies`, the V17 per-file project match, and the file ingestion
policy. Persists to ``construction_file_ingestion_decisions`` on apply.

``extraction_allowed`` / ``download_allowed`` are True only for the ``eligible``
disposition; everything else is False (and the DB CHECK forbids a review-required
row from allowing extraction).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.policy.evaluator import ReviewPolicyEvaluator
from hb_assistant.construction.policy.file_ingestion import (
    FileIngestionPolicy,
    load_file_ingestion_policy,
)
from hb_assistant.construction.policy.loader import load_review_rules
from hb_assistant.construction.store import ConstructionStore


class IngestionDecisionResult(BaseModel):
    source_id: str
    drive_item_id: str
    name: Optional[str] = None
    drive_id: Optional[str] = None
    project_key: Optional[str] = None
    project_number_detected: Optional[str] = None
    document_type_detected: Optional[str] = None
    ingestion_disposition: str
    review_required: bool = False
    review_reason: Optional[str] = None
    download_allowed: bool = False
    extraction_allowed: bool = False
    reason_codes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class EligibilityReport(BaseModel):
    command: str = "graph files ingestion-policy"
    mode: str
    source: Optional[str] = None
    summary: dict[str, int] = Field(default_factory=dict)
    items: list[IngestionDecisionResult] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def _folder_hit(parent_path: str, folders: list[str]) -> Optional[str]:
    low = parent_path.casefold()
    for f in folders:
        if f.casefold() in low:
            return f
    return None


class IngestionEligibilityEvaluator:
    """Per-file ingestion-disposition evaluator (offline; reuses review rules)."""

    def __init__(
        self,
        store: ConstructionStore,
        *,
        policy: Optional[FileIngestionPolicy] = None,
        review_evaluator: Optional[ReviewPolicyEvaluator] = None,
    ) -> None:
        self._store = store
        self._policy = policy or load_file_ingestion_policy()
        self._review = review_evaluator or ReviewPolicyEvaluator(load_review_rules())

    def _decide(self, item: dict, match: dict, source: Any) -> IngestionDecisionResult:
        pol = self._policy
        ext = (item.get("file_extension") or "").lower()
        name = item.get("name") or ""
        parent = item.get("parent_reference_path") or item.get("path") or ""
        size = item.get("size_bytes") or 0
        project_key = (match or {}).get("project_key")
        match_status = (match or {}).get("match_status")
        folder_pol = getattr(source, "folder_policies", None) if source else None

        def out(
            disposition: str,
            *,
            review: bool,
            reason: Optional[str],
            codes: list[str],
            eligible: bool = False,
        ) -> IngestionDecisionResult:
            return IngestionDecisionResult(
                source_id=item["source_id"],
                drive_item_id=item["drive_item_id"],
                name=item.get("name"),
                drive_id=item.get("drive_id"),
                project_key=project_key,
                project_number_detected=item.get("project_number_detected"),
                document_type_detected=item.get("document_type_detected"),
                ingestion_disposition=disposition,
                review_required=review,
                review_reason=reason,
                download_allowed=eligible,
                extraction_allowed=eligible,
                reason_codes=codes,
            )

        # 1. Blocked unsupported extension.
        if ext and ext in pol.extension_dispositions.blocked:
            return out(
                "blocked_unsupported_type",
                review=False,
                reason=None,
                codes=[f"blocked_extension:{ext}"],
            )

        # 2. Sensitive review-rule match (name + folder path).
        matches = self._review.evaluate(
            source_key=item["source_id"],
            project_key=project_key,
            item={"item_id": item["drive_item_id"], "name": name, "parent_path": parent},
        )
        if matches:
            cats = sorted({m.classification_label for m in matches})
            return out(
                "review_required",
                review=True,
                reason=f"sensitive:{','.join(cats)}",
                codes=[f"review_rule:{m.rule_id}" for m in matches],
            )

        # 3. Folder policy: review-required folder.
        if folder_pol:
            hit = _folder_hit(parent, folder_pol.review_required)
            if hit:
                return out(
                    "review_required",
                    review=True,
                    reason="folder_review_required",
                    codes=[f"folder_policy_review_required:{hit}"],
                )

        # 4. Blocked: too large to extract (metadata-effective; never extracted).
        if size and size > pol.large_file.block_extract_bytes:
            return out(
                "blocked_too_large", review=False, reason=None, codes=[f"size_over_block:{size}"]
            )

        # 5. Low-confidence / unmatched project match → review.
        if match_status in ("low_confidence", "unmatched"):
            return out(
                "low_confidence",
                review=True,
                reason="low_confidence_project_match",
                codes=[f"match_status:{match_status}"],
            )

        # 6. Large-file warning band → manual approval before extraction.
        if size and size > pol.large_file.extract_warning_bytes:
            return out(
                "manual_approval_required",
                review=True,
                reason="large_file_manual_approval",
                codes=[f"size_warning:{size}"],
            )

        # 7. Folder policy: metadata-only folder.
        if folder_pol:
            hit = _folder_hit(parent, folder_pol.metadata_only)
            if hit:
                return out(
                    "metadata_only",
                    review=False,
                    reason=None,
                    codes=[f"folder_policy_metadata_only:{hit}"],
                )

        # 8. Metadata-only extension (native/archive/video/images).
        if ext and ext in pol.extension_dispositions.metadata_only:
            return out(
                "metadata_only", review=False, reason=None, codes=[f"metadata_only_extension:{ext}"]
            )

        # 9. Eligible: allowed extension + matched project + deep-index folder.
        deep = bool(folder_pol and _folder_hit(parent, folder_pol.deep_index_allowed))
        if ext in pol.extension_dispositions.eligible and match_status == "matched" and deep:
            return out(
                "eligible",
                review=False,
                reason=None,
                codes=["allowed_extension", "matched_project", "deep_index_folder"],
                eligible=True,
            )

        # Default: metadata only.
        return out("metadata_only", review=False, reason=None, codes=["default_metadata_only"])

    def evaluate(
        self, *, source_id: Optional[str] = None, dry_run: bool = True
    ) -> EligibilityReport:
        registry = load_source_registry()
        source_by_key = {s.source_key: s for s in registry.sources}
        source_keys = [source_id] if source_id else list(source_by_key)

        results: list[IngestionDecisionResult] = []
        for sk in source_keys:
            source = source_by_key.get(sk)
            matches = {
                m["drive_item_id"]: m
                for m in self._store.list_drive_item_project_matches(source_id=sk, limit=100000)
            }
            for item in self._store.list_drive_items(source_id=sk, limit=100000):
                if item.get("deleted") or not item.get("is_file"):
                    continue
                r = self._decide(item, matches.get(item["drive_item_id"], {}), source)
                results.append(r)
                if not dry_run:
                    self._store.insert_file_ingestion_decision(
                        decision_id=str(uuid.uuid4()),
                        source_id=r.source_id,
                        drive_item_id=r.drive_item_id,
                        drive_id=r.drive_id,
                        project_key=r.project_key,
                        project_number_detected=r.project_number_detected,
                        document_type_detected=r.document_type_detected,
                        ingestion_disposition=r.ingestion_disposition,
                        review_required=r.review_required,
                        review_reason=r.review_reason,
                        extraction_allowed=r.extraction_allowed,
                        download_allowed=r.download_allowed,
                        reason_codes_json=json.dumps(r.reason_codes),
                    )

        summary: dict[str, int] = {"total_evaluated": len(results)}
        for r in results:
            summary[r.ingestion_disposition] = summary.get(r.ingestion_disposition, 0) + 1
        summary["review_routed"] = sum(1 for r in results if r.review_required)
        summary["extraction_eligible"] = sum(1 for r in results if r.extraction_allowed)
        return EligibilityReport(
            mode="dry_run" if dry_run else "apply",
            source=source_id,
            summary=summary,
            items=results,
        )
