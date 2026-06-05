"""Deterministic router: model recommendation -> accepted | review.

Always produces a :class:`ClassificationDecision`. The model never influences
its own verdict — routing reads only the validated payload plus the
deterministic controller policy (``construction/policy/``).

Decision order (first match wins):
1. proposed_label in PROTECTED_CATEGORIES  -> review
2. confidence < threshold                  -> review
3. controller policy already fires         -> review (model cannot override)
4. otherwise                               -> accepted
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.construction.policy import ReviewPolicyEvaluator

from .models import (
    ClassificationDecision,
    ModelClassification,
    ModelRoutingConfig,
    ModelTask,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str, limit: int) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"  # ellipsis


class ClassificationRouter:
    def __init__(
        self,
        config: ModelRoutingConfig,
        policy_evaluator: Optional[ReviewPolicyEvaluator] = None,
    ) -> None:
        self._config = config
        self._policy_evaluator = policy_evaluator

    @property
    def config(self) -> ModelRoutingConfig:
        return self._config

    def decide(
        self,
        *,
        classification: ModelClassification,
        source_key: str,
        item_id: str,
        project_key: str | None,
        model_name: str,
        model_task: ModelTask,
        raw_output: str,
        inventory_item: dict[str, Any] | None = None,
    ) -> ClassificationDecision:
        status: str = "accepted"
        reasons: list[str] = []

        if classification.proposed_label in self._config.protected_categories:
            status = "review"
            reasons.append(f"protected_category:{classification.proposed_label}")

        if classification.confidence < self._config.low_confidence_threshold:
            status = "review"
            reasons.append(f"low_confidence:{classification.confidence:.3f}")

        if self._policy_evaluator is not None and inventory_item is not None:
            policy_matches = self._policy_evaluator.evaluate(
                source_key=source_key,
                project_key=project_key,
                item=inventory_item,
            )
            if policy_matches:
                status = "review"
                rule_ids = ",".join(sorted({m.rule_id for m in policy_matches}))
                reasons.append(f"controller_policy_flagged:{rule_ids}")

        if not reasons:
            reasons.append("model_accepted")

        return ClassificationDecision(
            source_key=source_key,
            item_id=item_id,
            project_key=project_key,
            model_name=model_name,
            model_task=model_task,
            proposed_label=classification.proposed_label,
            confidence=classification.confidence,
            rationale_truncated=_truncate(
                classification.rationale,
                self._config.max_output_chars,
            ),
            raw_output_truncated=_truncate(raw_output, self._config.max_output_chars),
            status=status,  # type: ignore[arg-type]
            routing_reason=";".join(reasons),
            routed_at=_utc_now(),
        )
