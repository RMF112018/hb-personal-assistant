"""Phase 07C — document-type classification policy + review-rules loaders.

Loads ``resources/config/document_type_classification_policy.seed.yaml`` (the
deterministic-first classification vocabulary + order + review-required types) and
``resources/config/review_required_document_rules.seed.yaml`` (the review-routing
policy). Both follow the seed -> repo override -> explicit pattern of the
document-source policy loader. The no-auto-promotion rule booleans are
``Literal``-locked so the YAML cannot loosen them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from hb_assistant.config.path_policy import PathPolicy

_CLASSIFICATION_SEED = (
    Path("resources") / "config" / "document_type_classification_policy.seed.yaml"
)
_CLASSIFICATION_OVERRIDE = Path("config") / "document_type_classification_policy.yml"
_REVIEW_SEED = Path("resources") / "config" / "review_required_document_rules.seed.yaml"
_REVIEW_OVERRIDE = Path("config") / "review_required_document_rules.yml"


class DocumentClassificationPolicyError(RuntimeError):
    """Raised when a document classification / review policy cannot be loaded."""


class DocumentTypeClassificationPolicy(BaseModel):
    version: str = "phase07c-document-type-classification-policy-v1"
    classification_order: list[str] = Field(default_factory=list)
    document_types: dict[str, list[str]] = Field(default_factory=dict)
    review_required_types: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ReviewRequiredWhen(BaseModel):
    document_type: list[str] = Field(default_factory=list)
    confidence_class: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class DocumentReviewPolicyRules(BaseModel):
    # Literal-locked: the YAML cannot loosen the no-auto-promotion guarantees.
    no_auto_promotion_for_sensitive: Literal[True] = True
    no_auto_promotion_for_model_only: Literal[True] = True
    no_final_legal_contractual_claim_personnel_safety_financial_determination: Literal[True] = True

    model_config = {"extra": "forbid"}


class DocumentReviewRules(BaseModel):
    version: str = "phase07c-review-required-document-rules-v1"
    review_required_when: ReviewRequiredWhen = ReviewRequiredWhen()
    rules: DocumentReviewPolicyRules = DocumentReviewPolicyRules()

    model_config = {"extra": "forbid"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DocumentClassificationPolicyError(f"{path} must contain a top-level mapping")
    return data


def _load(seed_rel: Path, override_rel: Path, override_path: Path | str | None) -> dict[str, Any]:
    repo_root = PathPolicy().resolve_repo_root()
    seed_path = repo_root / seed_rel
    if not seed_path.exists():
        raise DocumentClassificationPolicyError(f"Seed not found at {seed_path}")
    data = _load_yaml(seed_path)
    repo_override = repo_root / override_rel
    if repo_override.exists():
        data.update(_load_yaml(repo_override))
    if override_path:
        data.update(_load_yaml(Path(override_path).expanduser()))
    return data


def load_document_type_classification_policy(
    override_path: Path | str | None = None,
) -> DocumentTypeClassificationPolicy:
    """Load + validate the document-type classification policy."""
    return DocumentTypeClassificationPolicy.model_validate(
        _load(_CLASSIFICATION_SEED, _CLASSIFICATION_OVERRIDE, override_path)
    )


def load_document_review_rules(
    override_path: Path | str | None = None,
) -> DocumentReviewRules:
    """Load + validate the 07C document review-required rules."""
    return DocumentReviewRules.model_validate(_load(_REVIEW_SEED, _REVIEW_OVERRIDE, override_path))
