"""Phase 07B calendar + email-thread policy seeds (loaders + validation).

Loads and validates the read-only YAML policy seeds under ``resources/config/``:

- ``calendar_source_policy.seed.yaml`` — calendar source registry policy.
- ``email_thread_summary_policy.seed.yaml`` — thread-summary materialization policy.
- ``review_required_calendar_email_rules.seed.yaml`` — review-routing rules.

The Pydantic models enforce the non-negotiable safety invariants at load time:
calendar sources are read-only, event bodies and join URLs are never persisted,
and decrypted bodies / raw prompts / raw responses are never persisted. A seed
that violates these raises ``ValidationError`` rather than loading silently.

All loading is read-only and offline; no external calls, no raw content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy

_CONFIG_RELATIVE = Path("resources") / "config"
_CALENDAR_SOURCE_POLICY_FILE = "calendar_source_policy.seed.yaml"
_EMAIL_THREAD_SUMMARY_POLICY_FILE = "email_thread_summary_policy.seed.yaml"
_REVIEW_RULES_FILE = "review_required_calendar_email_rules.seed.yaml"


class CalendarPolicyError(RuntimeError):
    """Raised when a calendar/email policy seed cannot be loaded or validated."""


def _resolve_config_file(filename: str) -> Path:
    return PathPolicy().resolve_repo_root() / _CONFIG_RELATIVE / filename


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CalendarPolicyError(f"Policy seed not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise CalendarPolicyError(f"Policy seed {path} must contain a mapping at top level")
    return data


# ---------------------------------------------------------------------------
# Calendar source policy
# ---------------------------------------------------------------------------


class CalendarSourceDefaults(BaseModel):
    enabled: bool = True
    read_only: bool = True
    lookback_days: int = 14
    lookahead_days: int = 30
    max_items_per_run: int = 250
    persist_event_body: bool = False
    persist_join_url: bool = False
    private_event_policy: str = "metadata_minimal_review_required"

    @field_validator("read_only")
    @classmethod
    def _must_be_read_only(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("calendar source policy read_only must be true (no writeback path)")
        return v

    @field_validator("persist_event_body", "persist_join_url")
    @classmethod
    def _must_not_persist(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("calendar source policy must not persist event body or join URL")
        return v


class CalendarSourceEntry(BaseModel):
    source_id: str
    mailbox_owner: str
    calendar_role: str = "primary"
    policy_id: str | None = None


class CalendarSourcePolicy(BaseModel):
    version: str
    defaults: CalendarSourceDefaults = CalendarSourceDefaults()
    sources: list[CalendarSourceEntry] = []


def load_calendar_source_policy() -> CalendarSourcePolicy:
    data = _load_yaml_mapping(_resolve_config_file(_CALENDAR_SOURCE_POLICY_FILE))
    return CalendarSourcePolicy.model_validate(data)


# ---------------------------------------------------------------------------
# Email thread summary policy
# ---------------------------------------------------------------------------


class EmailThreadSummaryDefaults(BaseModel):
    summary_mode: str = "metadata_only"
    allow_encrypted_body_context: bool = False
    allow_local_model_advisory: bool = True
    persist_decrypted_body: bool = False
    persist_raw_prompt: bool = False
    persist_raw_response: bool = False
    max_summary_chars: int = 900
    route_sensitive_to_review: bool = True
    route_high_impact_to_review: bool = True

    @field_validator("persist_decrypted_body", "persist_raw_prompt", "persist_raw_response")
    @classmethod
    def _must_not_persist(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError(
                "email thread summary policy must not persist decrypted body, raw prompt, "
                "or raw response"
            )
        return v


class EmailThreadSummaryPolicy(BaseModel):
    version: str
    defaults: EmailThreadSummaryDefaults = EmailThreadSummaryDefaults()


def load_email_thread_summary_policy() -> EmailThreadSummaryPolicy:
    data = _load_yaml_mapping(_resolve_config_file(_EMAIL_THREAD_SUMMARY_POLICY_FILE))
    return EmailThreadSummaryPolicy.model_validate(data)


# ---------------------------------------------------------------------------
# Review-required rules
# ---------------------------------------------------------------------------


class ReviewRule(BaseModel):
    id: str
    action: str
    when: str | None = None
    categories: list[str] | None = None
    confidence_classes: list[str] | None = None


class ReviewProhibited(BaseModel):
    auto_promote_model_only: bool = True
    persist_raw_body: bool = True
    persist_raw_prompt: bool = True
    persist_raw_response: bool = True
    persist_join_url: bool = True


class ReviewRequiredRules(BaseModel):
    version: str
    rules: list[ReviewRule] = []
    prohibited: ReviewProhibited = ReviewProhibited()


def load_review_required_rules() -> ReviewRequiredRules:
    data = _load_yaml_mapping(_resolve_config_file(_REVIEW_RULES_FILE))
    return ReviewRequiredRules.model_validate(data)
