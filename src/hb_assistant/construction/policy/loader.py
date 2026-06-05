"""Construction review-queue rules loader.

Loads the seeded YAML rule file and validates against
:mod:`hb_assistant.construction.policy.models`.

Search order (later wins; replacement semantics, matching
``construction/config/loader.py``):

1. Built-in seed at ``resources/config/review_required_rules.seed.yaml``
   (resolved relative to repo root via :meth:`PathPolicy.resolve_repo_root`).
2. Optional repo override at ``config/review_required_rules.yml``.
3. Explicit ``override_path`` argument.
4. Environment variable ``HB_CONSTRUCTION_REVIEW_RULES``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from .models import ReviewRules

SEED_RELATIVE_PATH = Path("resources") / "config" / "review_required_rules.seed.yaml"
REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "review_required_rules.yml"
ENV_VAR = "HB_CONSTRUCTION_REVIEW_RULES"


class ReviewRulesError(RuntimeError):
    """Raised when the review-rules file cannot be loaded."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ReviewRulesError(f"Review rules file {path} must contain a mapping at top level")
    return data


def _resolve_seed_path() -> Path:
    return PathPolicy().resolve_repo_root() / SEED_RELATIVE_PATH


def _resolve_repo_override_path() -> Path:
    return PathPolicy().resolve_repo_root() / REPO_OVERRIDE_RELATIVE_PATH


def load_review_rules(override_path: Path | str | None = None) -> ReviewRules:
    """Load and validate the construction-agent review-queue rules.

    Raises :class:`ReviewRulesError` if the seed is missing or any input file is
    malformed; raises :class:`pydantic.ValidationError` if the merged data
    fails schema validation.
    """

    seed_path = _resolve_seed_path()
    if not seed_path.exists():
        raise ReviewRulesError(
            f"Seed review rules not found at {seed_path}. "
            "Construction-agent review queue cannot start without the seeded rules."
        )

    data: dict[str, Any] = _load_yaml(seed_path)

    repo_override = _resolve_repo_override_path()
    if repo_override.exists():
        data = _load_yaml(repo_override)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser())
    else:
        env_value = os.environ.get(ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser())

    return ReviewRules.model_validate(data)
