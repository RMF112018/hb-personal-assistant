"""FileRelevanceScorer: heuristic selective scoring for ingestion (Phase 6 signals + filename/size/type).

v1.0.0: simple weighted heuristics. No ML. Full triage deferred.
All outputs redacted (scores, reason codes, signal flags only; no PII, no content).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from hb_assistant.normalize.drive_item import DriveItem


class RelevanceScore(BaseModel):
    """Redacted, source-traceable relevance assessment for a DriveItem/attachment."""

    score: float = Field(ge=0.0, le=1.0, description="0-1 composite worth score")
    reasons: List[str] = Field(default_factory=list, description="human + machine reason codes")
    signals: Dict[str, Any] = Field(default_factory=dict, description="classification hits, size, name matches (no content)")
    worth_ingesting: bool = Field(default=False)
    # source_record_id etc handled by caller / registry


class FileRelevanceScorer:
    """Heuristic scorer leveraging Phase 6 classification signals + work-product filename patterns + size/type.

    Threshold ~0.20 for "worth" in selective pipeline.
    """

    WORK_KEYWORDS = {
        "report", "contract", "invoice", "proposal", "budget", "agenda", "minutes",
        "q1", "q2", "q3", "q4", "fy", "plan", "review", "summary", "legal", "finance",
        "board", "strategy", "roadmap", "brief", "memo", "presentation", "deck",
    }

    def score(
        self,
        item: DriveItem,
        *,
        classifications: Optional[List[str]] = None,
        parent_classifications: Optional[List[str]] = None,
        has_attachments: bool = False,
        parent_has_attachments: bool = False,
    ) -> RelevanceScore:
        """Compute score. classifications can come from linked email/calendar via Phase 6."""
        score = 0.08  # base for supported file in matrix
        reasons: List[str] = ["supported_type"]
        signals: Dict[str, Any] = {
            "size_mb": round((item.size or 0) / (1024 * 1024), 2) if item.size else 0.0,
            "is_file": bool(item.is_file),
        }

        classifs = set((classifications or []) + (parent_classifications or []))
        if "bobby_mention" in classifs:
            score += 0.38
            reasons.append("bobby_mention")
            signals["bobby_mention"] = True
        if any(k in classifs for k in ("possible_action_or_waiting", "action", "waiting_on")):
            score += 0.28
            reasons.append("action_or_waiting_signal")
            signals["action_signal"] = True

        if has_attachments or parent_has_attachments:
            score += 0.12
            reasons.append("attachment_context")
            signals["attachment_context"] = True

        name_l = (item.name or "").lower()
        for kw in self.WORK_KEYWORDS:
            if kw in name_l:
                score += 0.18
                reasons.append(f"name_kw:{kw}")
                signals.setdefault("name_hits", []).append(kw)
                break  # one sufficient for v1

        size_mb: float = signals["size_mb"]
        if 0.05 < size_mb < 80:
            score += 0.06
            reasons.append("size_work_doc")
        elif size_mb >= 300:
            score -= 0.15
            reasons.append("very_large_penalty")

        # tiny files (e.g. 0-byte placeholders) penalized
        if size_mb < 0.01:
            score -= 0.05
            reasons.append("tiny_file_penalty")

        score = max(0.0, min(1.0, round(score, 3)))
        worth = score >= 0.22  # selective threshold (tunable; 20-gate for large still applies)

        return RelevanceScore(
            score=score,
            reasons=reasons,
            signals=signals,
            worth_ingesting=worth,
        )
