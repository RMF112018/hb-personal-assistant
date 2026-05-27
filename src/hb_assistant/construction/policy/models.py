"""Pydantic models for the construction-agent review-queue policy.

Three model classes:

- :class:`ReviewRule` — a single deterministic routing rule loaded from YAML.
- :class:`ReviewRules` — the top-level rule set with cross-rule invariants.
- :class:`RuleMatch` — the deterministic output of evaluating one rule against
  one inventory item; carries everything needed to persist a queue row.

Guardrails enforced at type level:

- ``kind`` is a closed ``Literal`` — unknown rule kinds are rejected.
- ``sensitivity`` is a closed ``Literal`` — unknown levels are rejected.
- ``extra="forbid"`` on every model.
- ``rule_id`` uniqueness validated on :class:`ReviewRules`.
- At least one rule must be present per protected category (contract,
  financial, legal, incident, injury, personnel) so the seed can never silently
  drop coverage.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RuleKind = Literal["folder_path", "document_name", "risk_term"]
Sensitivity = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "resolved", "deferred"]

PROTECTED_CATEGORIES: tuple[str, ...] = (
    "contract",
    "financial",
    "legal",
    "incident",
    "injury",
    "personnel",
)

_RULE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ReviewRule(BaseModel):
    """A single deterministic routing rule."""

    rule_id: str
    kind: RuleKind
    pattern: str
    sensitivity: Sensitivity
    classification_label: str
    reason: str
    suggested_action: str
    confidence: float = 1.0

    model_config = {"extra": "forbid"}

    @field_validator("rule_id")
    @classmethod
    def _rule_id_kebab(cls, v: str) -> str:
        if not _RULE_ID_RE.match(v):
            raise ValueError(
                f"rule_id must be lowercase kebab-case (a-z0-9 with single hyphens); got {v!r}"
            )
        return v

    @field_validator("pattern")
    @classmethod
    def _pattern_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("pattern must be a non-empty string")
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0]; got {v}")
        return v


class ReviewRules(BaseModel):
    """Top-level rule set loaded from YAML."""

    version: int = 1
    low_confidence_threshold: float = 0.7
    rules: list[ReviewRule] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("low_confidence_threshold")
    @classmethod
    def _threshold_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"low_confidence_threshold must be in [0.0, 1.0]; got {v}")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "ReviewRules":
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            dupes = sorted({k for k in ids if ids.count(k) > 1})
            raise ValueError(f"duplicate rule_id entries: {dupes}")

        labels = {r.classification_label for r in self.rules}
        missing = [c for c in PROTECTED_CATEGORIES if c not in labels]
        if missing:
            raise ValueError(
                "review rule set must cover every protected category at least once; "
                f"missing classification_label values: {missing}"
            )
        return self


class RuleMatch(BaseModel):
    """Deterministic output of evaluating one rule against one inventory item."""

    rule_id: str
    item_id: str
    source_key: str
    project_key: str | None = None
    name: str | None = None
    parent_path: str | None = None
    sensitivity: Sensitivity
    classification_label: str
    reason: str
    suggested_action: str
    confidence: float = 1.0

    model_config = {"extra": "forbid"}
