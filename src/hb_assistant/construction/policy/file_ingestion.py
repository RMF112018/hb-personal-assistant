"""Phase 06A — file ingestion eligibility policy model + loader.

Loads ``resources/config/file_ingestion_policy.seed.yaml`` (with optional repo
override) into a validated :class:`FileIngestionPolicy`. The runtime guardrail
booleans are ``Literal``-locked so the YAML cannot loosen the download/extract
defaults without a code change. Mirrors the email-active policy loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from hb_assistant.config.path_policy import PathPolicy

SEED_RELATIVE_PATH = Path("resources") / "config" / "file_ingestion_policy.seed.yaml"
REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "file_ingestion_policy.yml"


class FileIngestionPolicyError(RuntimeError):
    """Raised when the file ingestion policy cannot be loaded."""


class LargeFilePolicy(BaseModel):
    extract_warning_bytes: int = 26214400
    block_extract_bytes: int = 104857600

    model_config = {"extra": "forbid"}


class ExtensionDispositions(BaseModel):
    eligible: list[str] = Field(default_factory=list)
    metadata_only: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class FileIngestionPolicy(BaseModel):
    version: int = 1
    default_disposition: Literal["metadata_only"] = "metadata_only"
    # Guardrails — Literal-locked: the YAML cannot loosen them.
    require_explicit_download_flag: Literal[True] = True
    require_explicit_extract_flag: Literal[True] = True
    block_review_required_extraction: Literal[True] = True

    eligible_document_types: list[str] = Field(default_factory=list)
    metadata_only_document_types: list[str] = Field(default_factory=list)
    review_required_document_types: list[str] = Field(default_factory=list)
    extension_dispositions: ExtensionDispositions = Field(default_factory=ExtensionDispositions)
    large_file: LargeFilePolicy = Field(default_factory=LargeFilePolicy)

    model_config = {"extra": "forbid"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise FileIngestionPolicyError(f"{path} must contain a top-level mapping")
    return data


def load_file_ingestion_policy(override_path: Path | str | None = None) -> FileIngestionPolicy:
    """Load + validate the file ingestion policy (seed → repo override → explicit)."""
    repo_root = PathPolicy().resolve_repo_root()
    seed_path = repo_root / SEED_RELATIVE_PATH
    if not seed_path.exists():
        raise FileIngestionPolicyError(f"Seed not found at {seed_path}")
    data = _load_yaml(seed_path)
    repo_override = repo_root / REPO_OVERRIDE_RELATIVE_PATH
    if repo_override.exists():
        data.update(_load_yaml(repo_override))
    if override_path:
        data.update(_load_yaml(Path(override_path).expanduser()))
    return FileIngestionPolicy.model_validate(data)
