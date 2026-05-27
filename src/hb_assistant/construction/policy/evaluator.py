"""Deterministic policy evaluator for the construction-agent review queue.

Pure functions; no I/O. Accepts a row dict from
``construction_drive_item_inventory`` and returns every matching
:class:`RuleMatch`. Matching is case-insensitive substring + simple regex; no
ML, no inference, no LLM calls.

A single inventory item can match multiple rules (e.g. a file in a "Contracts/"
folder also named "Change Order 04.pdf" — both rules fire and produce separate
queue rows so a controller sees full provenance).
"""

from __future__ import annotations

import re
from typing import Any

from .models import ReviewRule, ReviewRules, RuleMatch


class ReviewPolicyEvaluator:
    """Apply a :class:`ReviewRules` set against inventory items."""

    def __init__(self, rules: ReviewRules) -> None:
        self._rules = rules
        # Pre-compile patterns by kind; document_name + folder_path use regex,
        # risk_term uses a comma-separated substring list.
        self._compiled: dict[str, re.Pattern[str]] = {}
        for rule in rules.rules:
            if rule.kind in ("folder_path", "document_name"):
                self._compiled[rule.rule_id] = re.compile(rule.pattern, re.IGNORECASE)

    @property
    def rules(self) -> ReviewRules:
        return self._rules

    def evaluate(
        self,
        *,
        source_key: str,
        project_key: str | None,
        item: dict[str, Any],
    ) -> list[RuleMatch]:
        """Evaluate every rule against one inventory item; return all matches.

        ``item`` is a row dict as returned by
        :meth:`ConstructionStore.list_inventory_for_source`. Only ``item_id``,
        ``name``, and ``parent_path`` are inspected — never any content body.
        """

        item_id = item.get("item_id")
        if not item_id:
            return []
        name = item.get("name") or ""
        parent_path = item.get("parent_path") or ""

        matches: list[RuleMatch] = []
        for rule in self._rules.rules:
            if self._rule_matches(rule, name=name, parent_path=parent_path):
                matches.append(
                    RuleMatch(
                        rule_id=rule.rule_id,
                        item_id=item_id,
                        source_key=source_key,
                        project_key=project_key,
                        name=item.get("name"),
                        parent_path=item.get("parent_path"),
                        sensitivity=rule.sensitivity,
                        classification_label=rule.classification_label,
                        reason=rule.reason,
                        suggested_action=rule.suggested_action,
                        confidence=rule.confidence,
                    )
                )
        return matches

    def _rule_matches(self, rule: ReviewRule, *, name: str, parent_path: str) -> bool:
        if rule.kind == "folder_path":
            return bool(self._compiled[rule.rule_id].search(parent_path))
        if rule.kind == "document_name":
            return bool(self._compiled[rule.rule_id].search(name))
        if rule.kind == "risk_term":
            lowered = name.lower()
            terms = [t.strip().lower() for t in rule.pattern.split(",") if t.strip()]
            return any(term in lowered for term in terms)
        return False
