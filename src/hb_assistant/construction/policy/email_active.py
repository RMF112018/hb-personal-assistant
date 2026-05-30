"""Phase 06 *active* email-intelligence policy (operational, read-only).

Phase 02 deferred email intelligence via
:mod:`hb_assistant.construction.policy.email_deferred`. Phase 06 activates it
for operational, project-aware, **read-only** email workflows. This module adds
the active policy *alongside* the deferred one — the deferred policy + its V5
``construction_email_intelligence_deferred_state`` row remain untouched as
preserved historical evidence.

The hard guardrails reuse the deferred pattern: ``Literal``-locked fields make
the YAML/seed unable to loosen mailbox protection without a Pydantic model
change. Defense in depth continues at the store adapter (ValueError guards) and
the SQLite ``CHECK`` constraints on the V10 ``email_intelligence_active_policy``
table.

Loader precedence mirrors
:mod:`hb_assistant.construction.policy.email_deferred`:

1. Built-in seed at ``resources/config/email_intelligence_active_policy.yaml``.
2. Optional repo override at ``config/email_intelligence_active_policy.yml``.
3. Explicit ``override_path`` argument.

No environment-variable override — this is a security-locked policy, not an
operator-shell knob (matching the deferred policy).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Literal

import yaml
from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy

SEED_RELATIVE_PATH = (
    Path("resources") / "config" / "email_intelligence_active_policy.yaml"
)
REPO_OVERRIDE_RELATIVE_PATH = (
    Path("config") / "email_intelligence_active_policy.yml"
)


class EmailIntelligenceActivePolicyError(RuntimeError):
    """Raised when the active email-intelligence policy cannot be loaded."""


class EmailIntelligenceActivePolicy(BaseModel):
    """Phase 06 operational email-intelligence policy.

    The locked fields use ``Literal`` so the YAML file cannot be edited to
    loosen mailbox protection (read-only, no writeback/mutation, no full-archive
    crawl, no source/body copy to Obsidian, no default attachment-content
    download, metadata-only, review-required-for-sensitive, pilot-only backfill,
    invalid-JSON-routes-to-review) without a Pydantic model change.
    """

    mailbox_mode: Literal["read_only"]
    writeback_allowed: Literal[False]
    mailbox_mutation_allowed: Literal[False]
    full_archive_crawl: Literal[False]
    source_copy_to_vault: Literal[False]
    full_email_body_in_obsidian: Literal[False]
    attachment_content_download_by_default: Literal[False]
    metadata_only_by_default: Literal[True]
    review_required_for_sensitive: Literal[True]
    initial_backfill_mode: Literal["pilot_projects_only"]
    ollama_invalid_json_routes_to_review: Literal[True]

    default_lookback_days: int = 30
    include_folders: List[str]
    exclude_folders: List[str]
    ollama_enabled_for_email_intelligence: bool = True
    low_confidence_threshold: float = 0.75

    # Prompt 08A — controlled encrypted full-body storage. Full body capture is
    # permitted ONLY when encrypted at rest via text_vault; plaintext persistence
    # in SQLite / Obsidian / evidence / logs stays hard-locked False. The mailbox
    # remains strictly read-only (writeback/mutation locked above). These Literal
    # locks mean the YAML cannot loosen them without a Pydantic model change.
    full_body_storage_allowed: bool = False
    full_body_storage_mode: Literal["encrypted_text_vault"] = "encrypted_text_vault"
    plaintext_body_persistence_allowed: Literal[False] = False
    obsidian_full_body_allowed: Literal[False] = False
    evidence_full_body_allowed: Literal[False] = False
    log_full_body_allowed: Literal[False] = False
    attachment_content_storage_allowed: Literal[False] = False
    encrypted_body_requires_review_for_sensitive: Literal[True] = True
    max_full_body_fetch_per_run: int = 100

    model_config = {"extra": "forbid"}

    @field_validator("default_lookback_days")
    @classmethod
    def _bounded_lookback(cls, value: int) -> int:
        # Bounded lookback only — never a full-mailbox backfill window.
        if not 1 <= value <= 366:
            raise ValueError("default_lookback_days must be between 1 and 366 (bounded lookback)")
        return value

    @field_validator("max_full_body_fetch_per_run")
    @classmethod
    def _bounded_body_fetch(cls, value: int) -> int:
        # Bounded per-run body capture — never a full-mailbox backfill.
        if not 1 <= value <= 1000:
            raise ValueError("max_full_body_fetch_per_run must be between 1 and 1000")
        return value

    @field_validator("low_confidence_threshold")
    @classmethod
    def _threshold_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("low_confidence_threshold must be between 0.0 and 1.0")
        return value


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise EmailIntelligenceActivePolicyError(
            f"Active email policy file {path} must contain a mapping at top level"
        )
    return data


def _resolve_seed_path() -> Path:
    return PathPolicy().resolve_repo_root() / SEED_RELATIVE_PATH


def _resolve_repo_override_path() -> Path:
    return PathPolicy().resolve_repo_root() / REPO_OVERRIDE_RELATIVE_PATH


def load_email_intelligence_active_policy(
    override_path: Path | str | None = None,
) -> EmailIntelligenceActivePolicy:
    """Load and validate the Phase 06 active email-intelligence policy.

    Raises :class:`EmailIntelligenceActivePolicyError` if the seed is missing or
    any input file is malformed; raises :class:`pydantic.ValidationError` if the
    merged data fails schema validation (including the locked-flag constraints).
    """
    seed_path = _resolve_seed_path()
    if not seed_path.exists():
        raise EmailIntelligenceActivePolicyError(
            f"Seed active email policy not found at {seed_path}. "
            "Phase 06 operational email workflows require the seeded policy file."
        )

    data: dict[str, Any] = _load_yaml(seed_path)

    repo_override = _resolve_repo_override_path()
    if repo_override.exists():
        data = _load_yaml(repo_override)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser())

    return EmailIntelligenceActivePolicy.model_validate(data)
