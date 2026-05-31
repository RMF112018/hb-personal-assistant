"""Phase 07C — document-source scope policy model + loader.

Loads ``resources/config/document_source_policy.seed.yaml`` (with optional repo
override) into a validated :class:`DocumentSourcePolicy`. This makes the
SharePoint vs OneDrive source-scope distinction explicit and enforceable before
07C document cards are materialized:

- SharePoint: watch/index the approved drive or approved project-drive scope and
  all nested folders.
- OneDrive: index only explicitly selected folders and their nested contents;
  root-wide indexing is not allowed and a selected-folder allowlist is required.

Non-compliant sources are blocked from document-card promotion (fail-closed). The
read-only / no-writeback / no-vault-copy / no-raw-path / no-signed-url defaults are
``Literal``-locked so the YAML cannot loosen them without a code change. Mirrors the
file-ingestion policy loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy

SEED_RELATIVE_PATH = Path("resources") / "config" / "document_source_policy.seed.yaml"
REPO_OVERRIDE_RELATIVE_PATH = Path("config") / "document_source_policy.yml"

_BLOCK_ACTION = "block_document_card_promotion"


class DocumentSourcePolicyError(RuntimeError):
    """Raised when the document-source policy cannot be loaded."""


class DefaultsPolicy(BaseModel):
    # Guardrails — Literal-locked: the YAML cannot loosen them.
    read_only: Literal[True] = True
    external_writeback_allowed: Literal[False] = False
    copy_originals_to_vault: Literal[False] = False
    persist_raw_paths_in_outputs: Literal[False] = False
    persist_signed_or_download_urls: Literal[False] = False

    model_config = {"extra": "forbid"}


class SharePointScopePolicy(BaseModel):
    intended_scope: str = "approved_drive_or_approved_project_drive_scope"
    include_nested_folders: bool = True
    require_delta_or_baseline_receipt: bool = True
    non_compliant_action: Literal["block_document_card_promotion"] = _BLOCK_ACTION

    model_config = {"extra": "forbid"}


class OneDriveScopePolicy(BaseModel):
    intended_scope: str = "selected_folders_only"
    include_nested_folders_under_selected_folders: bool = True
    # Literal-locked: root-wide OneDrive indexing is never allowed by policy.
    root_wide_indexing_allowed: Literal[False] = False
    require_selected_folder_allowlist: Literal[True] = True
    non_compliant_action: Literal["block_document_card_promotion"] = _BLOCK_ACTION

    model_config = {"extra": "forbid"}


class DocumentSourcePolicy(BaseModel):
    version: str = "phase07c-document-source-policy-v1"
    defaults: DefaultsPolicy = DefaultsPolicy()
    sharepoint: SharePointScopePolicy = SharePointScopePolicy()
    onedrive: OneDriveScopePolicy = OneDriveScopePolicy()

    model_config = {"extra": "forbid"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise DocumentSourcePolicyError(f"{path} must contain a top-level mapping")
    return data


def load_document_source_policy(override_path: Path | str | None = None) -> DocumentSourcePolicy:
    """Load + validate the document-source policy (seed → repo override → explicit)."""
    repo_root = PathPolicy().resolve_repo_root()
    seed_path = repo_root / SEED_RELATIVE_PATH
    if not seed_path.exists():
        raise DocumentSourcePolicyError(f"Seed not found at {seed_path}")
    data = _load_yaml(seed_path)
    repo_override = repo_root / REPO_OVERRIDE_RELATIVE_PATH
    if repo_override.exists():
        data.update(_load_yaml(repo_override))
    if override_path:
        data.update(_load_yaml(Path(override_path).expanduser()))
    return DocumentSourcePolicy.model_validate(data)
