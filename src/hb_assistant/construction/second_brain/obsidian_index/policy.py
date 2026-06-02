"""Phase 08A approved Obsidian index policy (Synthesized Prompt 05).

Loads the index policy seed (approved roots, excludes, marker requirement) and
provides managed-marker detection + exclusion checks. Read-only.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy

_SEED_RELATIVE = Path("resources") / "config" / "phase_08a_obsidian_index_policy.seed.yaml"
SEED_ENV_VAR = "HB_SECOND_BRAIN_OBSIDIAN_INDEX_POLICY"

# Managed/generated notes carry an HB marker block, e.g. <!-- HB-DAILY-BRIEF:START -->.
MANAGED_MARKER_RE = re.compile(r"<!--\s*(HB-[A-Z0-9-]+):START\s*-->")


class ObsidianIndexPolicyError(RuntimeError):
    """Raised when the index policy seed cannot be loaded."""


class ObsidianIndexPolicy(BaseModel):
    version: str
    include_generated_outputs_only_by_default: bool = True
    approved_roots: list[str] = []
    exclude: list[str] = []
    marker_boundaries_required: bool = True
    review_tier_metadata_required: bool = True

    model_config = {"extra": "forbid"}


def load_obsidian_index_policy() -> ObsidianIndexPolicy:
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise ObsidianIndexPolicyError(f"index policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ObsidianIndexPolicyError(f"{candidate} must contain a mapping at top level")
    return ObsidianIndexPolicy.model_validate(data)


def is_excluded(rel_path: str, policy: ObsidianIndexPolicy) -> bool:
    """True if any path segment matches an exclude keyword (case-insensitive)."""
    lowered = rel_path.lower()
    for token in policy.exclude:
        key = token.lower().split()[0]  # e.g. "raw source documents" -> "raw"
        if key and key in lowered:
            return True
    return "attachments" in lowered
