"""Procore daily log section selection scope (Phase 04 Prompt 08).

Declares which daily log sub-collections receive which normalization
treatment: ``selected_sections`` persist as canonical rows;
``review_only_sections`` persist with ``review_required=True`` and hash-only
body summaries; ``routed_to_review_sections`` persist with
``review_required=True`` AND ``safety_route=True`` AND hash-only body
summaries (accident / injury / delay / safety section text never enters
normal rows by construction).

Mirrors the loader pattern in :mod:`hb_assistant.procore.loader`:

1. Built-in seed under ``resources/config/`` (resolved via PathPolicy).
2. Optional repo override at ``config/<basename>.yml``.
3. Explicit ``override_path`` argument.
4. Environment variable ``HB_PROCORE_DAILY_LOG_SELECTION``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from hb_assistant.config.path_policy import PathPolicy

DAILY_LOG_SELECTION_SEED_RELATIVE = (
    Path("resources") / "config" / "procore_daily_log_selection.seed.yaml"
)
DAILY_LOG_SELECTION_REPO_OVERRIDE_RELATIVE = (
    Path("config") / "procore_daily_log_selection.yml"
)
DAILY_LOG_SELECTION_ENV_VAR = "HB_PROCORE_DAILY_LOG_SELECTION"


class DailyLogSelectionError(RuntimeError):
    """Raised when the daily log selection scope cannot be loaded."""


class DailyLogSection(BaseModel):
    """One entry in any of the three section buckets.

    ``canonical_field_keys`` is required for selected sections (drives the
    canonical-fields whitelist on persisted rows) and optional for the other
    two buckets (which carry minimal fields by construction).
    """

    id: str
    payload_key: str
    category: str
    canonical_field_keys: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @field_validator("id", "payload_key", "category")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("section id / payload_key / category must be non-empty")
        return v


class ProcoreDailyLogSelection(BaseModel):
    version: int = 1
    selected_sections: list[DailyLogSection] = Field(default_factory=list)
    review_only_sections: list[DailyLogSection] = Field(default_factory=list)
    routed_to_review_sections: list[DailyLogSection] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_consistency(self) -> "ProcoreDailyLogSelection":
        if (
            not self.selected_sections
            and not self.review_only_sections
            and not self.routed_to_review_sections
        ):
            raise ValueError("daily log selection scope must declare at least one section")
        seen_ids: set[str] = set()
        seen_payload_keys: set[str] = set()
        seen_categories: set[str] = set()
        for bucket in (
            self.selected_sections,
            self.review_only_sections,
            self.routed_to_review_sections,
        ):
            for section in bucket:
                if section.id in seen_ids:
                    raise ValueError(f"duplicate section id across buckets: {section.id!r}")
                if section.payload_key in seen_payload_keys:
                    raise ValueError(
                        f"duplicate payload_key across buckets: {section.payload_key!r}"
                    )
                if section.category in seen_categories:
                    raise ValueError(
                        f"duplicate category across buckets: {section.category!r}"
                    )
                seen_ids.add(section.id)
                seen_payload_keys.add(section.payload_key)
                seen_categories.add(section.category)
        return self

    def payload_keys(self) -> dict[str, str]:
        """Return ``{payload_key: bucket_name}`` for fast lookup."""
        out: dict[str, str] = {}
        for section in self.selected_sections:
            out[section.payload_key] = "selected"
        for section in self.review_only_sections:
            out[section.payload_key] = "review_only"
        for section in self.routed_to_review_sections:
            out[section.payload_key] = "routed_to_review"
        return out


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DailyLogSelectionError(f"{path} must contain a mapping at top level")
    return data


def _resolve(relative: Path) -> Path:
    return PathPolicy().resolve_repo_root() / relative


def load_daily_log_selection(
    override_path: Path | str | None = None,
) -> ProcoreDailyLogSelection:
    seed = _resolve(DAILY_LOG_SELECTION_SEED_RELATIVE)
    if not seed.exists():
        raise DailyLogSelectionError(
            f"Seed Procore daily log selection scope not found at {seed}. "
            "Daily log dry-run cannot start without the seeded selection."
        )
    data = _load_yaml(seed)
    repo_override = _resolve(DAILY_LOG_SELECTION_REPO_OVERRIDE_RELATIVE)
    if repo_override.exists():
        data = _load_yaml(repo_override)
    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser())
    else:
        env_value = os.environ.get(DAILY_LOG_SELECTION_ENV_VAR)
        if env_value:
            data = _load_yaml(Path(env_value).expanduser())
    return ProcoreDailyLogSelection.model_validate(data)


__all__ = [
    "DAILY_LOG_SELECTION_ENV_VAR",
    "DAILY_LOG_SELECTION_SEED_RELATIVE",
    "DailyLogSection",
    "DailyLogSelectionError",
    "ProcoreDailyLogSelection",
    "load_daily_log_selection",
]
