"""Email-intelligence deferred-foundation policy (Phase 02 Prompt 10).

Records the tenant-level Microsoft Graph mail-permission grants and locks
the no-mailbox-writeback / no-body-persistence / sensitive-review guardrails
that Phase 02 enforces at three layers (Pydantic Literal here, Python
adapter guards on :class:`ConstructionStore`, SQLite V5 CHECK constraints).

Loader precedence mirrors :mod:`hb_assistant.construction.policy.loader`:

1. Built-in seed at ``resources/config/email_intelligence_deferred_policy.yaml``.
2. Optional repo override at ``config/email_intelligence_deferred_policy.yml``.
3. Explicit ``override_path`` argument.

No environment-variable override this prompt — the policy is intentionally
not operator-overridable from a shell. If a later phase needs that escape
hatch, introduce ``HB_EMAIL_INTELLIGENCE_DEFERRED_POLICY`` then.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy

SEED_RELATIVE_PATH = (
    Path("resources") / "config" / "email_intelligence_deferred_policy.yaml"
)
REPO_OVERRIDE_RELATIVE_PATH = (
    Path("config") / "email_intelligence_deferred_policy.yml"
)


class EmailIntelligenceDeferredPolicyError(RuntimeError):
    """Raised when the deferred policy file cannot be loaded."""


class EmailIntelligenceDeferredPolicy(BaseModel):
    """Phase 02 email-intelligence deferred policy.

    The three locked fields use ``Literal[False]`` / ``Literal[True]`` so the
    YAML file cannot be edited to loosen mailbox protection without a Pydantic
    model change. The ``*_granted`` booleans record tenant-level consent and
    are operator truth — they have no runtime side-effect because the
    application's MSAL scope request still asks only for ``Mail.Read``.
    """

    mail_read_all_granted: bool
    mail_readwrite_all_granted: bool
    mailbox_writeback_allowed: Literal[False]
    persist_full_body: Literal[False]
    review_required_for_sensitive: Literal[True]
    future_phase: Optional[str] = None

    model_config = {"extra": "forbid"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise EmailIntelligenceDeferredPolicyError(
            f"Email deferred policy file {path} must contain a mapping at top level"
        )
    return data


def _resolve_seed_path() -> Path:
    return PathPolicy().resolve_repo_root() / SEED_RELATIVE_PATH


def _resolve_repo_override_path() -> Path:
    return PathPolicy().resolve_repo_root() / REPO_OVERRIDE_RELATIVE_PATH


def load_email_intelligence_deferred_policy(
    override_path: Path | str | None = None,
) -> EmailIntelligenceDeferredPolicy:
    """Load and validate the email-intelligence deferred-foundation policy.

    Raises :class:`EmailIntelligenceDeferredPolicyError` if the seed is
    missing or any input file is malformed; raises
    :class:`pydantic.ValidationError` if the merged data fails schema
    validation (which includes the three locked-flag constraints).
    """
    seed_path = _resolve_seed_path()
    if not seed_path.exists():
        raise EmailIntelligenceDeferredPolicyError(
            f"Seed email deferred policy not found at {seed_path}. "
            "Phase 02 mailbox lockout requires the seeded policy file."
        )

    data: dict[str, Any] = _load_yaml(seed_path)

    repo_override = _resolve_repo_override_path()
    if repo_override.exists():
        data = _load_yaml(repo_override)

    if override_path is not None:
        data = _load_yaml(Path(override_path).expanduser())

    return EmailIntelligenceDeferredPolicy.model_validate(data)
